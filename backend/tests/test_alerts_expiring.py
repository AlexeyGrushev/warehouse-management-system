from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.alerts.queries import today
from tests.factories import add_batch, make_product, make_supplier
from tests.helpers import auth_header, make_user

URL = "/api/v1/alerts/expiring-batches"


def get(client: TestClient, user, **params):
    return client.get(URL, params=params, headers=auth_header(user))


def batch_numbers(response) -> list[str]:
    return [item["batch_no"] for item in response.json()["items"]]


def in_days(days: int, user_id: int, session: Session, product, quantity: str = "5", **kwargs):
    """Партия, срок годности которой наступает через days дней (отрицательное — уже прошёл)."""
    current = today()
    return add_batch(
        session,
        product,
        user_id,
        quantity,
        received_at=current - timedelta(days=60),
        expires_at=current + timedelta(days=days),
        **kwargs,
    )


def test_default_horizon_is_14_days(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    in_days(14, user.id, session, product, batch_no="LAST-DAY")
    in_days(15, user.id, session, product, batch_no="TOO-FAR")
    assert batch_numbers(get(client, user)) == ["LAST-DAY"]


def test_days_parameter_moves_the_horizon(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    in_days(0, user.id, session, product, batch_no="TODAY")
    in_days(3, user.id, session, product, batch_no="SOON")
    in_days(40, user.id, session, product, batch_no="LATER")
    assert batch_numbers(get(client, user, days=0)) == ["TODAY"]
    assert batch_numbers(get(client, user, days=3)) == ["TODAY", "SOON"]
    assert batch_numbers(get(client, user, days=60)) == ["TODAY", "SOON", "LATER"]
    assert get(client, user, days=-1).status_code == 422
    assert get(client, user, days=366).status_code == 422


def test_expired_batches_are_listed_with_flag(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    in_days(-2, user.id, session, product, batch_no="EXPIRED")
    in_days(0, user.id, session, product, batch_no="TODAY")
    in_days(5, user.id, session, product, batch_no="SOON")
    items = get(client, user).json()["items"]
    assert [(item["batch_no"], item["days_left"], item["is_expired"]) for item in items] == [
        ("EXPIRED", -2, True),
        ("TODAY", 0, False),
        ("SOON", 5, False),
    ]


def test_batches_without_expiry_or_stock_are_skipped(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "5", batch_no="NO-EXPIRY")
    in_days(3, user.id, session, product, batch_no="LISTED")
    drained = in_days(2, user.id, session, product, batch_no="DRAINED")
    drained.qty_remaining = 0
    session.flush()
    assert batch_numbers(get(client, user)) == ["LISTED"]


def test_written_off_batch_leaves_the_list(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    in_days(3, user.id, session, product, "4", batch_no="WILL-GO")
    assert batch_numbers(get(client, user)) == ["WILL-GO"]
    written = client.post(
        "/api/v1/write-offs",
        json={"product_id": product.id, "quantity": "4", "reason": "EXPIRED"},
        headers=auth_header(user),
    )
    assert written.status_code == 201
    assert batch_numbers(get(client, user)) == []


def test_item_has_product_and_supplier_names(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session, unit="kg", sku="CHS-1", name="Сыр")
    supplier = make_supplier(session, "Молочный дом")
    in_days(4, user.id, session, product, "2.5", batch_no="B-1", supplier=supplier)
    item = get(client, user).json()["items"][0]
    assert item["product_id"] == product.id
    assert (item["product_sku"], item["product_name"], item["product_unit"]) == (
        "CHS-1",
        "Сыр",
        "kg",
    )
    assert item["supplier_name"] == "Молочный дом"
    assert item["qty_remaining"] == "2.500"
    assert item["expires_at"] == (today() + timedelta(days=4)).isoformat()


def test_sorted_by_expiry_and_paginated(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    for days in (9, 3, 6, 1, 12):
        in_days(days, user.id, session, product, batch_no=f"D{days}")
    assert batch_numbers(get(client, user)) == ["D1", "D3", "D6", "D9", "D12"]
    page = get(client, user, size=2, page=3).json()
    assert (page["total"], page["page"], batch_numbers(get(client, user, size=2, page=3))) == (
        5,
        3,
        ["D12"],
    )


def test_every_role_can_read_but_anonymous_cannot(client: TestClient, session: Session) -> None:
    for role in ("viewer", "storekeeper", "admin"):
        assert get(client, make_user(session, role=role)).status_code == 200
    assert client.get(URL).status_code == 401
