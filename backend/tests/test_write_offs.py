from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.stock.models import Batch, StockMovement
from tests.factories import add_batch, add_reserve, make_product
from tests.helpers import auth_header, make_user

URL = "/api/v1/write-offs"
TODAY = date.today()


def days(offset: int) -> date:
    return TODAY + timedelta(days=offset)


def write_off(client: TestClient, user, product, quantity: str, reason: str = "SALE", **extra):
    body = {"product_id": product.id, "quantity": quantity, "reason": reason, **extra}
    return client.post(URL, json=body, headers=auth_header(user))


def remaining(session: Session, batch: Batch) -> str:
    session.refresh(batch)
    return str(batch.qty_remaining)


def test_fefo_takes_nearest_expiry_first(client: TestClient, session: Session) -> None:
    """Пример из презентации: партии на 5 (срок раньше) и 10; списание 12 → 5 и 7."""
    user = make_user(session)
    product = make_product(session)
    late = add_batch(session, product, user.id, "10", expires_at=days(20))
    early = add_batch(session, product, user.id, "5", expires_at=days(10))
    response = write_off(client, user, product, "12")
    assert response.status_code == 201
    lines = response.json()["lines"]
    assert [(line["batch_id"], line["quantity"]) for line in lines] == [
        (early.id, "5.000"),
        (late.id, "7.000"),
    ]
    assert remaining(session, early) == "0.000"
    assert remaining(session, late) == "3.000"


def test_one_movement_per_affected_batch(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    first = add_batch(session, product, user.id, "4", expires_at=days(5))
    second = add_batch(session, product, user.id, "4", expires_at=days(6))
    third = add_batch(session, product, user.id, "4", expires_at=days(7))
    write_off(client, user, product, "6", reason="DAMAGE", comment="  бой при разгрузке ")
    movements = session.scalars(
        select(StockMovement).where(StockMovement.type == "WRITE_OFF").order_by(StockMovement.id)
    ).all()
    assert [(m.batch_id, int(m.quantity_delta)) for m in movements] == [
        (first.id, -4),
        (second.id, -2),
    ]
    assert all(m.reason == "DAMAGE" and m.comment == "бой при разгрузке" for m in movements)
    assert all(m.user_id == user.id for m in movements)
    assert remaining(session, third) == "4.000"


def test_batches_without_expiry_go_last(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    no_expiry = add_batch(session, product, user.id, "5", received_at=days(-10))
    with_expiry = add_batch(session, product, user.id, "5", expires_at=days(30))
    write_off(client, user, product, "5")
    assert remaining(session, with_expiry) == "0.000"
    assert remaining(session, no_expiry) == "5.000"


def test_same_expiry_uses_older_receipt_then_id(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    newer = add_batch(session, product, user.id, "5", received_at=days(-1), expires_at=days(10))
    older = add_batch(session, product, user.id, "5", received_at=days(-5), expires_at=days(10))
    write_off(client, user, product, "5")
    assert remaining(session, older) == "0.000"
    assert remaining(session, newer) == "5.000"


def test_write_off_exactly_all_stock(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "7")
    assert write_off(client, user, product, "7").status_code == 201
    stock = client.get(f"/api/v1/products/{product.id}/stock", headers=auth_header(user)).json()
    assert stock["on_hand"] == "0.000"


def test_insufficient_stock_changes_nothing(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    batch = add_batch(session, product, user.id, "7")
    response = write_off(client, user, product, "8")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "INSUFFICIENT_STOCK"
    assert body["meta"] == {
        "product_id": str(product.id),
        "requested": "8.000",
        "available": "7.000",
    }
    assert body["detail"] == "Запрошено 8.000, доступно 7.000"
    assert remaining(session, batch) == "7.000"
    assert (
        session.scalars(select(StockMovement).where(StockMovement.type == "WRITE_OFF")).all() == []
    )


def test_reserved_quantity_cannot_be_written_off(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    add_reserve(session, product, user.id, "4")
    assert write_off(client, user, product, "7").status_code == 409
    assert write_off(client, user, product, "6").status_code == 201


def test_sale_skips_expired_batches(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    expired = add_batch(session, product, user.id, "5", received_at=days(-30), expires_at=days(-1))
    fresh = add_batch(session, product, user.id, "5", expires_at=days(10))
    assert write_off(client, user, product, "6").status_code == 409  # просроченные не считаются
    assert write_off(client, user, product, "5").status_code == 201
    assert remaining(session, expired) == "5.000"
    assert remaining(session, fresh) == "0.000"


def test_expired_batch_can_be_written_off_as_expired(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    expired = add_batch(session, product, user.id, "5", received_at=days(-30), expires_at=days(-1))
    assert write_off(client, user, product, "5").status_code == 409
    assert write_off(client, user, product, "5", reason="EXPIRED").status_code == 201
    assert remaining(session, expired) == "0.000"


def test_batch_expiring_today_is_still_sellable(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "3", expires_at=TODAY)
    assert write_off(client, user, product, "3").status_code == 201


def test_validation_errors(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    for body in (
        {"quantity": "0"},
        {"quantity": "-1"},
        {"quantity": "1.5"},  # штучный товар
        {"reason": "GIFT"},
        {"product_id": "abc"},
    ):
        payload = {"product_id": product.id, "quantity": "1", "reason": "SALE", **body}
        response = client.post(URL, json=payload, headers=auth_header(user))
        assert response.status_code == 422, body


def test_fractional_write_off_for_weight_product(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session, unit="kg")
    add_batch(session, product, user.id, "10")
    response = write_off(client, user, product, "2.250")
    assert response.status_code == 201
    assert response.json()["lines"][0]["quantity"] == "2.250"


def test_unknown_product_and_roles(client: TestClient, session: Session) -> None:
    keeper = make_user(session)
    viewer = make_user(session, role="viewer")
    product = make_product(session)
    body = {"product_id": 999999, "quantity": "1", "reason": "SALE"}
    assert client.post(URL, json=body, headers=auth_header(keeper)).status_code == 404
    body["product_id"] = product.id
    assert client.post(URL, json=body, headers=auth_header(viewer)).status_code == 403
    assert client.post(URL, json=body).status_code == 401
