from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.catalog.models import Category, Product
from app.modules.reservations import service as reservations
from app.modules.reservations.schemas import ReservationCreate, ReservationItemCreate
from app.modules.stocktaking.models import InventoryLine, InventorySession
from tests.factories import add_batch, make_product, make_supplier
from tests.helpers import auth_header, make_user

URL = "/api/v1/stocktakings"


def create(client: TestClient, user, **body):
    return client.post(URL, json=body, headers=auth_header(user))


def start(client: TestClient, user, session_id: int):
    return client.post(f"{URL}/{session_id}/start", headers=auth_header(user))


def test_session_and_line_constraints(session: Session) -> None:
    user = make_user(session)
    with pytest.raises(IntegrityError):
        session.add(InventorySession(status="WEIRD", created_by=user.id))
        session.flush()
    session.rollback()


def test_line_constraints(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    inventory = InventorySession(status="DRAFT", created_by=user.id)
    session.add(inventory)
    session.flush()
    nested = session.begin_nested()
    session.add(
        InventoryLine(session_id=inventory.id, product_id=product.id, counted_qty=Decimal("-1"))
    )
    with pytest.raises(IntegrityError):
        session.flush()
    nested.rollback()
    session.add(InventoryLine(session_id=inventory.id, product_id=product.id))
    session.flush()
    session.add(InventoryLine(session_id=inventory.id, product_id=product.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_create_covers_all_active_products(client: TestClient, session: Session) -> None:
    user = make_user(session)
    first, second = make_product(session), make_product(session)
    archived = make_product(session)
    archived.is_active = False
    session.flush()
    response = create(client, user)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["created_by"] == user.id
    assert body["started_at"] is None
    assert (body["lines_total"], body["lines_counted"]) == (2, 0)
    assert [line["product_id"] for line in body["lines"]] == [first.id, second.id]
    assert all(line["expected_qty"] is None and line["diff"] is None for line in body["lines"])


def test_create_by_category_includes_subcategories(client: TestClient, session: Session) -> None:
    user = make_user(session)
    root = Category(name="Корень")
    session.add(root)
    session.flush()
    child = Category(name="Дочерняя", parent_id=root.id)
    other = Category(name="Чужая")
    session.add_all([child, other])
    session.flush()
    inside_root = Product(sku="R", name="R", category_id=root.id, unit="pcs")
    inside_child = Product(sku="C", name="C", category_id=child.id, unit="pcs")
    outside = Product(sku="O", name="O", category_id=other.id, unit="pcs")
    session.add_all([inside_root, inside_child, outside])
    session.flush()
    body = create(client, user, category_id=root.id).json()
    assert {line["sku"] for line in body["lines"]} == {"R", "C"}


def test_create_errors(client: TestClient, session: Session) -> None:
    user = make_user(session)
    assert create(client, user).status_code == 422  # товаров нет
    assert create(client, user, category_id=999999).status_code == 404
    empty = Category(name="Пустая")
    session.add(empty)
    session.flush()
    assert create(client, user, category_id=empty.id).status_code == 422


def test_start_fixes_expected_quantity(client: TestClient, session: Session) -> None:
    user = make_user(session)
    stocked, empty = make_product(session), make_product(session)
    add_batch(session, stocked, user.id, "12")
    inventory = create(client, user).json()
    response = start(client, user, inventory["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "IN_PROGRESS"
    assert body["started_at"] is not None
    expected = {line["product_id"]: line["expected_qty"] for line in body["lines"]}
    assert expected == {stocked.id: "12.000", empty.id: "0.000"}


def test_expected_quantity_ignores_reserve(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    reservations.create_reservation(
        session,
        user,
        ReservationCreate(
            reference="Р", items=[ReservationItemCreate(product_id=product.id, quantity=4)]
        ),
    )
    inventory = create(client, user).json()
    body = start(client, user, inventory["id"]).json()
    assert body["lines"][0]["expected_qty"] == "10.000"  # физически на складе, резерв не вычитаем


def test_start_only_from_draft(client: TestClient, session: Session) -> None:
    user = make_user(session)
    make_product(session)
    inventory = create(client, user).json()
    assert start(client, user, inventory["id"]).status_code == 200
    again = start(client, user, inventory["id"])
    assert again.status_code == 409
    assert again.json()["meta"]["status"] == "IN_PROGRESS"
    assert start(client, user, 999999).status_code == 404


def test_product_cannot_be_in_two_open_sessions(client: TestClient, session: Session) -> None:
    user = make_user(session)
    make_product(session)
    first = create(client, user).json()
    second = create(client, user).json()
    assert start(client, user, first["id"]).status_code == 200
    blocked = start(client, user, second["id"])
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "STOCKTAKING_IN_PROGRESS"
    assert blocked.json()["meta"]["inventory_session_id"] == str(first["id"])
    # после отмены первой вторая стартует
    assert client.post(f"{URL}/{first['id']}/cancel", headers=auth_header(user)).status_code == 200
    assert start(client, user, second["id"]).status_code == 200


def test_movements_are_blocked_during_stocktaking(client: TestClient, session: Session) -> None:
    user = make_user(session)
    headers = auth_header(user)
    counted, other = make_product(session), make_product(session)
    supplier = make_supplier(session)
    add_batch(session, counted, user.id, "10")
    add_batch(session, other, user.id, "10")
    # инвентаризация только по одной категории
    inventory = create(client, user, category_id=counted.category_id).json()
    assert [line["product_id"] for line in inventory["lines"]] == [counted.id]
    start(client, user, inventory["id"])

    def blocked(response) -> None:
        assert response.status_code == 409
        assert response.json()["code"] == "STOCKTAKING_IN_PROGRESS"
        assert response.json()["meta"]["product_id"] == str(counted.id)

    blocked(
        client.post(
            "/api/v1/receipts",
            json={
                "product_id": counted.id,
                "supplier_id": supplier.id,
                "batch_no": "NEW",
                "quantity": "1",
                "unit_cost": "1",
                "received_at": "2026-11-01",
            },
            headers=headers,
        )
    )
    blocked(
        client.post(
            "/api/v1/write-offs",
            json={"product_id": counted.id, "quantity": "1", "reason": "SALE"},
            headers=headers,
        )
    )
    blocked(
        client.post(
            "/api/v1/reservations",
            json={"reference": "Н", "items": [{"product_id": counted.id, "quantity": "1"}]},
            headers=headers,
        )
    )
    # товар вне инвентаризации работает как обычно
    assert (
        client.post(
            "/api/v1/write-offs",
            json={"product_id": other.id, "quantity": "1", "reason": "SALE"},
            headers=headers,
        ).status_code
        == 201
    )
    # отмена сессии снимает запрет
    client.post(f"{URL}/{inventory['id']}/cancel", headers=headers)
    assert (
        client.post(
            "/api/v1/write-offs",
            json={"product_id": counted.id, "quantity": "1", "reason": "SALE"},
            headers=headers,
        ).status_code
        == 201
    )


def test_reservation_can_be_cancelled_during_stocktaking(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    reservation = reservations.create_reservation(
        session,
        user,
        ReservationCreate(
            reference="Р",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            items=[ReservationItemCreate(product_id=product.id, quantity=3)],
        ),
    )
    start(client, user, create(client, user).json()["id"])
    # снятие резерва «на складе» ничего не меняет, поэтому разрешено
    response = client.post(
        f"/api/v1/reservations/{reservation.id}/cancel", headers=auth_header(user)
    )
    assert response.status_code == 200


def test_cancel_rules(client: TestClient, session: Session) -> None:
    user = make_user(session)
    make_product(session)
    draft = create(client, user).json()
    cancelled = client.post(f"{URL}/{draft['id']}/cancel", headers=auth_header(user))
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["closed_at"] is not None
    assert client.post(f"{URL}/{draft['id']}/cancel", headers=auth_header(user)).status_code == 409
    assert start(client, user, draft["id"]).status_code == 409


def test_list_get_and_roles(client: TestClient, session: Session) -> None:
    keeper = make_user(session)
    viewer = make_user(session, role="viewer")
    make_product(session)
    first = create(client, keeper).json()
    second = create(client, keeper).json()
    start(client, keeper, second["id"])

    page = client.get(URL, headers=auth_header(viewer)).json()
    assert page["total"] == 2
    assert [item["id"] for item in page["items"]] == [second["id"], first["id"]]
    assert "lines" not in page["items"][0]
    assert (
        client.get(URL, params={"status": "DRAFT"}, headers=auth_header(viewer)).json()["total"]
        == 1
    )
    assert (
        client.get(URL, params={"status": "NOPE"}, headers=auth_header(viewer)).status_code == 422
    )
    detail = client.get(f"{URL}/{first['id']}", headers=auth_header(viewer))
    assert detail.status_code == 200 and detail.json()["lines_total"] == 1
    assert client.get(f"{URL}/999999", headers=auth_header(viewer)).status_code == 404

    assert client.post(URL, json={}, headers=auth_header(viewer)).status_code == 403
    assert client.post(URL, json={}).status_code == 401
    assert client.post(f"{URL}/{first['id']}/start", headers=auth_header(viewer)).status_code == 403
    assert (
        client.post(f"{URL}/{first['id']}/cancel", headers=auth_header(viewer)).status_code == 403
    )
