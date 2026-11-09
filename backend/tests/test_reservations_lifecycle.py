from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reservations import service as reservations
from app.modules.reservations.models import Reservation
from app.modules.reservations.schemas import ReservationCreate, ReservationItemCreate
from app.modules.stock import service as stock
from app.modules.stock.integrity import find_violations
from app.modules.stock.models import StockMovement
from tests.factories import add_batch, make_product
from tests.helpers import auth_header, make_user

URL = "/api/v1/reservations"


def reserve(session: Session, user, items: list[tuple], now: datetime | None = None, ttl_hours=1):
    now = now or datetime.now(UTC)
    data = ReservationCreate(
        reference="ЗАКАЗ-1",
        expires_at=now + timedelta(hours=ttl_hours),
        items=[ReservationItemCreate(product_id=p.id, quantity=q) for p, q in items],
    )
    return reservations.create_reservation(session, user, data, now=now)


def movements_of(session: Session, reservation_id: int) -> list[StockMovement]:
    return list(
        session.scalars(
            select(StockMovement)
            .where(StockMovement.reservation_id == reservation_id)
            .order_by(StockMovement.id)
        )
    )


def test_cancel_returns_quantity_to_available(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    reservation = reserve(session, user, [(product, "6")])
    assert stock.get_totals(session, product.id).available == 4

    response = client.post(f"{URL}/{reservation.id}/cancel", headers=auth_header(user))
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    totals = stock.get_totals(session, product.id)
    assert (totals.on_hand, totals.reserved, totals.available) == (10, 0, 10)
    types = [m.type for m in movements_of(session, reservation.id)]
    assert types == ["RESERVE", "RELEASE"]
    assert find_violations(session) == []


def test_final_status_has_no_way_out(client: TestClient, session: Session) -> None:
    user = make_user(session)
    headers = auth_header(user)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    reservation = reserve(session, user, [(product, "2")])
    assert client.post(f"{URL}/{reservation.id}/cancel", headers=headers).status_code == 200
    for action in ("cancel", "fulfill"):
        response = client.post(f"{URL}/{reservation.id}/{action}", headers=headers)
        assert response.status_code == 409
        assert response.json()["meta"]["status"] == "CANCELLED"
    # повторное освобождение не вернуло лишнего
    assert stock.get_totals(session, product.id).reserved == 0


def test_fulfill_releases_and_writes_off_by_fefo(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    today = date.today()
    late = add_batch(session, product, user.id, "10", expires_at=today + timedelta(days=20))
    early = add_batch(session, product, user.id, "4", expires_at=today + timedelta(days=5))
    reservation = reserve(session, user, [(product, "6")])

    response = client.post(f"{URL}/{reservation.id}/fulfill", headers=auth_header(user))
    assert response.status_code == 200
    assert response.json()["status"] == "FULFILLED"
    session.refresh(early)
    session.refresh(late)
    assert (early.qty_remaining, late.qty_remaining) == (0, 8)  # 4 из ранней и 2 из поздней
    totals = stock.get_totals(session, product.id)
    assert (totals.on_hand, totals.reserved, totals.available) == (8, 0, 8)

    movements = movements_of(session, reservation.id)
    assert [m.type for m in movements] == ["RESERVE", "RELEASE", "WRITE_OFF", "WRITE_OFF"]
    sales = [m for m in movements if m.type == "WRITE_OFF"]
    assert all(m.reason == "SALE" for m in sales)
    assert sum(-m.quantity_delta for m in sales) == 6
    assert find_violations(session) == []


def test_fulfill_twice_is_rejected(client: TestClient, session: Session) -> None:
    user = make_user(session)
    headers = auth_header(user)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    reservation = reserve(session, user, [(product, "3")])
    assert client.post(f"{URL}/{reservation.id}/fulfill", headers=headers).status_code == 200
    assert client.post(f"{URL}/{reservation.id}/fulfill", headers=headers).status_code == 409
    assert stock.get_totals(session, product.id).on_hand == 7


def test_fulfill_with_several_products(client: TestClient, session: Session) -> None:
    user = make_user(session)
    first, second = make_product(session), make_product(session)
    add_batch(session, first, user.id, "5")
    add_batch(session, second, user.id, "5")
    reservation = reserve(session, user, [(first, "2"), (second, "5")])
    client.post(f"{URL}/{reservation.id}/fulfill", headers=auth_header(user))
    assert stock.get_totals(session, first.id).on_hand == 3
    assert stock.get_totals(session, second.id).on_hand == 0
    assert find_violations(session) == []


def test_failed_fulfillment_changes_nothing(client: TestClient, session: Session) -> None:
    """Партия успела «просрочиться» — продать её уже нельзя, отгрузка откатывается целиком."""
    user = make_user(session)
    ok, doomed = make_product(session), make_product(session)
    add_batch(session, ok, user.id, "5")
    doomed_batch = add_batch(session, doomed, user.id, "5", expires_at=date.today())
    reservation = reserve(session, user, [(ok, "2"), (doomed, "3")])
    doomed_batch.expires_at = date.today() - timedelta(days=1)
    session.flush()

    response = client.post(f"{URL}/{reservation.id}/fulfill", headers=auth_header(user))
    assert response.status_code == 409
    assert response.json()["code"] == "INSUFFICIENT_STOCK"
    session.refresh(reservation)
    assert reservation.status == "ACTIVE"
    assert stock.get_totals(session, ok.id).reserved == 2
    assert stock.get_totals(session, ok.id).on_hand == 5
    assert [m.type for m in movements_of(session, reservation.id)] == ["RESERVE", "RESERVE"]


def test_overdue_reservation_cannot_be_fulfilled(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "5")
    past = datetime.now(UTC) - timedelta(days=2)
    reservation = reserve(session, user, [(product, "2")], now=past, ttl_hours=1)
    response = client.post(f"{URL}/{reservation.id}/fulfill", headers=auth_header(user))
    assert response.status_code == 409
    # отменить просроченный, но ещё не снятый задачей резерв можно
    assert (
        client.post(f"{URL}/{reservation.id}/cancel", headers=auth_header(user)).status_code == 200
    )


def test_expiry_job_releases_only_overdue_active(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "20")
    past = datetime.now(UTC) - timedelta(days=3)
    overdue = reserve(session, user, [(product, "4")], now=past, ttl_hours=1)
    overdue_two = reserve(session, user, [(product, "3")], now=past, ttl_hours=2)
    fresh = reserve(session, user, [(product, "5")])
    cancelled = reserve(session, user, [(product, "1")], now=past, ttl_hours=1)
    reservations.cancel_reservation(session, user, cancelled.id)
    assert stock.get_totals(session, product.id).reserved == 12

    assert reservations.expire_due_reservations(session) == 2
    statuses = {
        r.id: r.status for r in session.scalars(select(Reservation).order_by(Reservation.id))
    }
    assert statuses == {
        overdue.id: "EXPIRED",
        overdue_two.id: "EXPIRED",
        fresh.id: "ACTIVE",
        cancelled.id: "CANCELLED",
    }
    assert stock.get_totals(session, product.id).reserved == 5
    release = movements_of(session, overdue.id)[-1]
    assert (release.type, release.comment) == ("RELEASE", "Истёк срок резерва")
    assert find_violations(session) == []


def test_expiry_job_is_idempotent(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    reserve(session, user, [(product, "4")], now=datetime.now(UTC) - timedelta(days=1))
    assert reservations.expire_due_reservations(session) == 1
    assert reservations.expire_due_reservations(session) == 0
    assert stock.get_totals(session, product.id).reserved == 0


def test_expiry_job_limit(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "20")
    past = datetime.now(UTC) - timedelta(days=1)
    for _ in range(3):
        reserve(session, user, [(product, "1")], now=past)
    assert reservations.expire_due_reservations(session, limit=2) == 2
    assert reservations.expire_due_reservations(session, limit=2) == 1


def test_expired_reservation_frees_stock_for_new_reservation(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "5")
    reserve(session, user, [(product, "5")], now=datetime.now(UTC) - timedelta(days=1))
    blocked = {"reference": "Н", "items": [{"product_id": product.id, "quantity": "1"}]}
    assert client.post(URL, json=blocked, headers=auth_header(user)).status_code == 409
    reservations.expire_due_reservations(session)
    assert client.post(URL, json=blocked, headers=auth_header(user)).status_code == 201


def test_roles_and_unknown_reservation(client: TestClient, session: Session) -> None:
    keeper = make_user(session)
    viewer = make_user(session, role="viewer")
    product = make_product(session)
    add_batch(session, product, keeper.id, "5")
    reservation = reserve(session, keeper, [(product, "1")])
    for action in ("cancel", "fulfill"):
        assert client.post(f"{URL}/{reservation.id}/{action}").status_code == 401
        assert (
            client.post(f"{URL}/{reservation.id}/{action}", headers=auth_header(viewer)).status_code
            == 403
        )
        assert client.post(f"{URL}/999999/{action}", headers=auth_header(keeper)).status_code == 404
