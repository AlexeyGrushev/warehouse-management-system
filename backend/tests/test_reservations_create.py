from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.reservations.models import Reservation, ReservationItem
from app.modules.stock import service
from app.modules.stock.integrity import find_violations
from app.modules.stock.models import StockMovement
from tests.factories import add_batch, make_product
from tests.helpers import auth_header, make_user

URL = "/api/v1/reservations"


def body(items: list[tuple[int, str]], **extra) -> dict:
    return {
        "reference": "ЗАКАЗ-100",
        "items": [{"product_id": pid, "quantity": qty} for pid, qty in items],
        **extra,
    }


def counts(session: Session) -> tuple[int, int, int]:
    return (
        session.scalar(select(func.count()).select_from(Reservation)),
        session.scalar(select(func.count()).select_from(ReservationItem)),
        session.scalar(
            select(func.count()).select_from(StockMovement).where(StockMovement.type == "RESERVE")
        ),
    )


def test_reservation_reduces_available_but_not_on_hand(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    first, second = make_product(session), make_product(session)
    add_batch(session, first, user.id, "10")
    add_batch(session, second, user.id, "5")
    response = client.post(
        URL, json=body([(first.id, "4"), (second.id, "5")]), headers=auth_header(user)
    )
    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "ACTIVE"
    assert created["reference"] == "ЗАКАЗ-100"
    assert created["created_by"] == user.id
    assert [(i["product_id"], i["quantity"]) for i in created["items"]] == [
        (first.id, "4.000"),
        (second.id, "5.000"),
    ]
    totals = service.get_totals(session, first.id)
    assert (totals.on_hand, totals.reserved, totals.available) == (10, 4, 6)
    assert service.get_totals(session, second.id).available == 0
    movements = session.scalars(select(StockMovement).where(StockMovement.type == "RESERVE")).all()
    assert len(movements) == 2
    assert all(m.reservation_id == created["id"] and m.quantity_delta == 0 for m in movements)
    assert find_violations(session) == []


def test_default_expiry_is_seven_days(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "5")
    response = client.post(URL, json=body([(product.id, "1")]), headers=auth_header(user))
    expires = datetime.fromisoformat(response.json()["expires_at"])
    delta = expires - datetime.now(UTC)
    assert timedelta(days=6, hours=23) < delta <= timedelta(days=7)


def test_custom_expiry_and_naive_time_is_moscow(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "5")
    when = datetime.now(UTC) + timedelta(days=2)
    aware = client.post(
        URL, json=body([(product.id, "1")], expires_at=when.isoformat()), headers=auth_header(user)
    )
    assert datetime.fromisoformat(aware.json()["expires_at"]) == when
    naive_moscow = (datetime.now(UTC) + timedelta(days=3)).astimezone().replace(tzinfo=None)
    naive = client.post(
        URL,
        json=body([(product.id, "1")], expires_at=naive_moscow.isoformat()),
        headers=auth_header(user),
    )
    assert naive.status_code == 201
    assert datetime.fromisoformat(naive.json()["expires_at"]).utcoffset() is not None


def test_expiry_must_be_in_the_future(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "5")
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    response = client.post(
        URL, json=body([(product.id, "1")], expires_at=past), headers=auth_header(user)
    )
    assert response.status_code == 422
    assert counts(session) == (0, 0, 0)


def test_all_or_nothing_when_one_item_is_short(client: TestClient, session: Session) -> None:
    user = make_user(session)
    enough, short = make_product(session), make_product(session)
    add_batch(session, enough, user.id, "10")
    add_batch(session, short, user.id, "2")
    response = client.post(
        URL, json=body([(enough.id, "3"), (short.id, "3")]), headers=auth_header(user)
    )
    assert response.status_code == 409
    error = response.json()
    assert error["code"] == "INSUFFICIENT_STOCK"
    assert error["meta"] == {
        "product_id": str(short.id),
        "requested": "3.000",
        "available": "2.000",
    }
    assert counts(session) == (0, 0, 0)
    assert service.get_totals(session, enough.id).reserved == 0


def test_cannot_reserve_more_than_already_reserved_leaves(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    headers = auth_header(user)
    assert client.post(URL, json=body([(product.id, "6")]), headers=headers).status_code == 201
    assert client.post(URL, json=body([(product.id, "5")]), headers=headers).status_code == 409
    assert client.post(URL, json=body([(product.id, "4")]), headers=headers).status_code == 201


def test_validation_errors(client: TestClient, session: Session) -> None:
    user = make_user(session)
    headers = auth_header(user)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    bad = [
        {"reference": "  ", "items": [{"product_id": product.id, "quantity": "1"}]},
        {"reference": "A", "items": []},
        {"reference": "A", "items": [{"product_id": product.id, "quantity": "0"}]},
        {"reference": "A", "items": [{"product_id": product.id, "quantity": "-2"}]},
        {"reference": "A", "items": [{"product_id": product.id, "quantity": "1.5"}]},  # штучный
        {
            "reference": "A",
            "items": [
                {"product_id": product.id, "quantity": "1"},
                {"product_id": product.id, "quantity": "2"},
            ],
        },
        {"items": [{"product_id": product.id, "quantity": "1"}]},
    ]
    for payload in bad:
        response = client.post(URL, json=payload, headers=headers)
        assert response.status_code == 422, payload
        assert response.json()["code"] == "VALIDATION_ERROR"
    assert counts(session) == (0, 0, 0)


def test_unknown_and_archived_products(client: TestClient, session: Session) -> None:
    user = make_user(session)
    headers = auth_header(user)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    assert client.post(URL, json=body([(999999, "1")]), headers=headers).status_code == 404
    product.is_active = False
    session.flush()
    assert client.post(URL, json=body([(product.id, "1")]), headers=headers).status_code == 409


def test_fractional_reserve_for_weight_product(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session, unit="kg")
    add_batch(session, product, user.id, "10")
    response = client.post(URL, json=body([(product.id, "2.5")]), headers=auth_header(user))
    assert response.status_code == 201
    assert response.json()["items"][0]["quantity"] == "2.500"


def test_write_off_respects_reserve(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    headers = auth_header(user)
    client.post(URL, json=body([(product.id, "8")]), headers=headers)
    over = client.post(
        "/api/v1/write-offs",
        json={"product_id": product.id, "quantity": "3", "reason": "SALE"},
        headers=headers,
    )
    assert over.status_code == 409
    fits = client.post(
        "/api/v1/write-offs",
        json={"product_id": product.id, "quantity": "2", "reason": "SALE"},
        headers=headers,
    )
    assert fits.status_code == 201


def test_roles(client: TestClient, session: Session) -> None:
    keeper = make_user(session)
    viewer = make_user(session, role="viewer")
    product = make_product(session)
    add_batch(session, product, keeper.id, "10")
    assert client.post(URL, json=body([(product.id, "1")])).status_code == 401
    assert (
        client.post(URL, json=body([(product.id, "1")]), headers=auth_header(viewer)).status_code
        == 403
    )
    created = client.post(URL, json=body([(product.id, "1")]), headers=auth_header(keeper)).json()
    assert client.get(f"{URL}/{created['id']}", headers=auth_header(viewer)).status_code == 200


def test_list_and_get(client: TestClient, session: Session) -> None:
    user = make_user(session)
    headers = auth_header(user)
    product = make_product(session)
    add_batch(session, product, user.id, "20")
    ids = []
    for number in range(3):
        payload = body([(product.id, "1")], reference=f"ЗАКАЗ-{number}")
        ids.append(client.post(URL, json=payload, headers=headers).json()["id"])

    page = client.get(URL, params={"size": 2}, headers=headers).json()
    assert page["total"] == 3
    assert [item["id"] for item in page["items"]] == [ids[2], ids[1]]  # новые сверху
    assert client.get(URL, params={"reference": "заказ-1"}, headers=headers).json()["total"] == 1
    assert client.get(URL, params={"status": "ACTIVE"}, headers=headers).json()["total"] == 3
    assert client.get(URL, params={"status": "CANCELLED"}, headers=headers).json()["total"] == 0
    assert client.get(URL, params={"status": "NOPE"}, headers=headers).status_code == 422
    assert client.get(f"{URL}/999999", headers=headers).status_code == 404
    assert client.get(f"{URL}/{ids[0]}", headers=headers).json()["reference"] == "ЗАКАЗ-0"
