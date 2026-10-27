from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import add_batch, add_reserve, make_product, make_supplier
from tests.helpers import auth_header, make_user


def archive(client: TestClient, kind: str, object_id: int, user):
    return client.post(f"/api/v1/{kind}/{object_id}/archive", headers=auth_header(user))


def is_active(client: TestClient, kind: str, object_id: int, user) -> bool:
    return client.get(f"/api/v1/{kind}/{object_id}", headers=auth_header(user)).json()["is_active"]


def test_product_with_stock_cannot_be_archived(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "3")
    response = archive(client, "products", product.id, user)
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"
    assert is_active(client, "products", product.id, user) is True


def test_product_without_movements_can_be_archived(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    assert archive(client, "products", product.id, user).status_code == 204
    assert is_active(client, "products", product.id, user) is False


def test_product_can_be_archived_after_stock_is_written_off(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "3")
    assert archive(client, "products", product.id, user).status_code == 409
    client.post(
        "/api/v1/write-offs",
        json={"product_id": product.id, "quantity": "3", "reason": "SALE"},
        headers=auth_header(user),
    )
    assert archive(client, "products", product.id, user).status_code == 204


def test_product_with_active_reserve_cannot_be_archived(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    product = make_product(session)
    add_reserve(session, product, user.id, "1")
    assert archive(client, "products", product.id, user).status_code == 409


def test_supplier_with_stock_cannot_be_archived(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product, supplier = make_product(session), make_supplier(session)
    add_batch(session, product, user.id, "5", supplier=supplier)
    assert archive(client, "suppliers", supplier.id, user).status_code == 409
    assert is_active(client, "suppliers", supplier.id, user) is True


def test_supplier_can_be_archived_after_stock_is_gone(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product, supplier = make_product(session), make_supplier(session)
    add_batch(session, product, user.id, "5", supplier=supplier)
    client.post(
        "/api/v1/write-offs",
        json={"product_id": product.id, "quantity": "5", "reason": "SALE"},
        headers=auth_header(user),
    )
    assert archive(client, "suppliers", supplier.id, user).status_code == 204


def test_stock_of_other_supplier_does_not_block(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    busy, idle = make_supplier(session), make_supplier(session)
    add_batch(session, product, user.id, "5", supplier=busy)
    assert archive(client, "suppliers", idle.id, user).status_code == 204
    assert archive(client, "suppliers", busy.id, user).status_code == 409


def test_viewer_cannot_archive(client: TestClient, session: Session) -> None:
    viewer = make_user(session, role="viewer")
    product = make_product(session)
    assert archive(client, "products", product.id, viewer).status_code == 403
