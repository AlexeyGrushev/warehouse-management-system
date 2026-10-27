from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.stock.models import Batch, StockMovement
from tests.factories import make_product, make_supplier
from tests.helpers import auth_header, make_user

URL = "/api/v1/receipts"


def payload(product_id: int, supplier_id: int, **overrides) -> dict:
    return {
        "product_id": product_id,
        "supplier_id": supplier_id,
        "batch_no": "B-001",
        "quantity": "10",
        "unit_cost": "12.5",
        "received_at": "2026-10-20",
        "expires_at": "2026-11-20",
        **overrides,
    }


def test_receipt_creates_batch_movement_and_stock(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product, supplier = make_product(session), make_supplier(session)
    response = client.post(URL, json=payload(product.id, supplier.id), headers=auth_header(user))
    assert response.status_code == 201
    body = response.json()
    assert body["batch_no"] == "B-001"
    assert body["qty_received"] == "10.000"
    assert body["qty_remaining"] == "10.000"
    assert body["unit_cost"] == "12.50"
    assert body["expires_at"] == "2026-11-20"

    movement = session.scalars(
        select(StockMovement).where(StockMovement.batch_id == body["id"])
    ).one()
    assert movement.type == "RECEIPT"
    assert movement.quantity_delta == 10
    assert movement.user_id == user.id

    stock = client.get(f"/api/v1/products/{product.id}/stock", headers=auth_header(user)).json()
    assert stock["on_hand"] == "10.000"
    assert stock["available"] == "10.000"


def test_expiry_date_is_optional(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product, supplier = make_product(session), make_supplier(session)
    body = payload(product.id, supplier.id)
    del body["expires_at"]
    response = client.post(URL, json=body, headers=auth_header(user))
    assert response.status_code == 201
    assert response.json()["expires_at"] is None


def test_second_receipt_adds_to_stock(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product, supplier = make_product(session), make_supplier(session)
    headers = auth_header(user)
    client.post(URL, json=payload(product.id, supplier.id), headers=headers)
    client.post(
        URL, json=payload(product.id, supplier.id, batch_no="B-002", quantity="5"), headers=headers
    )
    stock = client.get(f"/api/v1/products/{product.id}/stock", headers=headers).json()
    assert stock["on_hand"] == "15.000"


def test_batch_number_is_unique_per_product(client: TestClient, session: Session) -> None:
    user = make_user(session)
    first, second = make_product(session), make_product(session)
    supplier = make_supplier(session)
    headers = auth_header(user)
    assert client.post(URL, json=payload(first.id, supplier.id), headers=headers).status_code == 201
    duplicate = client.post(URL, json=payload(first.id, supplier.id), headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "CONFLICT"
    # тот же номер у другого товара допустим
    assert (
        client.post(URL, json=payload(second.id, supplier.id), headers=headers).status_code == 201
    )
    # после отказа ничего не записалось
    assert len(session.scalars(select(Batch).where(Batch.product_id == first.id)).all()) == 1


def test_unknown_product_or_supplier(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product, supplier = make_product(session), make_supplier(session)
    headers = auth_header(user)
    assert client.post(URL, json=payload(999999, supplier.id), headers=headers).status_code == 404
    assert client.post(URL, json=payload(product.id, 999999), headers=headers).status_code == 404


def test_archived_product_or_supplier_is_rejected(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product, supplier = make_product(session), make_supplier(session)
    headers = auth_header(user)
    supplier.is_active = False
    session.flush()
    assert (
        client.post(URL, json=payload(product.id, supplier.id), headers=headers).status_code == 409
    )
    supplier.is_active = True
    product.is_active = False
    session.flush()
    assert (
        client.post(URL, json=payload(product.id, supplier.id), headers=headers).status_code == 409
    )


def test_validation_errors(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product, supplier = make_product(session), make_supplier(session)
    headers = auth_header(user)
    bad = [
        {"quantity": "0"},
        {"quantity": "-3"},
        {"quantity": "1.5"},  # штучный товар: только целые
        {"unit_cost": "-1"},
        {"batch_no": "   "},
        {"received_at": "2026-10-20", "expires_at": "2026-10-19"},
        {"received_at": "не дата"},
    ]
    for overrides in bad:
        response = client.post(
            URL, json=payload(product.id, supplier.id, **overrides), headers=headers
        )
        assert response.status_code == 422, overrides
        assert response.json()["code"] == "VALIDATION_ERROR"


def test_fractional_quantity_for_weight_product(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product, supplier = make_product(session, unit="kg"), make_supplier(session)
    response = client.post(
        URL, json=payload(product.id, supplier.id, quantity="2.345"), headers=auth_header(user)
    )
    assert response.status_code == 201
    assert response.json()["qty_received"] == "2.345"


def test_roles(client: TestClient, session: Session) -> None:
    product, supplier = make_product(session), make_supplier(session)
    viewer = auth_header(make_user(session, role="viewer"))
    assert (
        client.post(URL, json=payload(product.id, supplier.id), headers=viewer).status_code == 403
    )
    assert client.post(URL, json=payload(product.id, supplier.id)).status_code == 401
    admin = auth_header(make_user(session, role="admin"))
    assert client.post(URL, json=payload(product.id, supplier.id), headers=admin).status_code == 201
