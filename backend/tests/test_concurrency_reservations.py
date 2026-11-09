"""Гонки: резервы, списания, отмена, исполнение, истечение и инвентаризация."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.models import User
from app.modules.reservations import service as reservations
from app.modules.reservations.models import Reservation
from app.modules.reservations.schemas import ReservationCreate, ReservationItemCreate
from app.modules.stock import service as stock
from app.modules.stock.integrity import find_violations
from app.modules.stock.models import StockMovement
from app.modules.stocktaking.models import InventoryLine
from tests.factories import add_batch, make_product
from tests.helpers import make_user
from tests.parallel import THREADS, api_with_commits, bearer, run_in_parallel

API = "/api/v1"


def setup_products(factory: sessionmaker[Session], quantities: list[str]):
    """Пользователь и товары с одной партией каждый; всё сразу коммитится."""
    with factory() as session:
        user = make_user(session)
        products = []
        for quantity in quantities:
            product = make_product(session)
            add_batch(session, product, user.id, quantity)
            products.append(product.id)
        session.commit()
        return user.id, products


def make_reservation(
    factory: sessionmaker[Session],
    user_id: int,
    product_id: int,
    quantity: int = 1,
    now: datetime | None = None,
) -> int:
    with factory() as session:
        user = session.get(User, user_id)
        now = now or datetime.now(UTC)
        reservation = reservations.create_reservation(
            session,
            user,
            ReservationCreate(
                reference="Р",
                expires_at=now + timedelta(hours=1),
                items=[ReservationItemCreate(product_id=product_id, quantity=quantity)],
            ),
            now=now,
        )
        session.commit()
        return reservation.id


def totals(factory: sessionmaker[Session], product_id: int):
    with factory() as session:
        return stock.get_totals(session, product_id)


def assert_consistent(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        assert find_violations(session) == []


def test_parallel_reservations_never_exceed_stock(committed: sessionmaker[Session]) -> None:
    user_id, (product_id,) = setup_products(committed, ["5"])
    with api_with_commits(committed) as new_client:
        payload = {"reference": "Н", "items": [{"product_id": product_id, "quantity": "1"}]}
        statuses = run_in_parallel(
            [
                lambda: (
                    new_client()
                    .post(f"{API}/reservations", json=payload, headers=bearer(user_id))
                    .status_code
                )
                for _ in range(THREADS)
            ]
        )
    assert sorted(statuses) == [201] * 5 + [409] * (THREADS - 5)
    final = totals(committed, product_id)
    assert (final.on_hand, final.reserved, final.available) == (5, 5, 0)
    assert_consistent(committed)


def test_reserve_and_write_off_compete_for_the_same_units(
    committed: sessionmaker[Session],
) -> None:
    user_id, (product_id,) = setup_products(committed, ["4"])
    with api_with_commits(committed) as new_client:

        def reserve() -> int:
            body = {"reference": "Н", "items": [{"product_id": product_id, "quantity": "1"}]}
            return (
                new_client()
                .post(f"{API}/reservations", json=body, headers=bearer(user_id))
                .status_code
            )

        def sell() -> int:
            body = {"product_id": product_id, "quantity": "1", "reason": "SALE"}
            return (
                new_client()
                .post(f"{API}/write-offs", json=body, headers=bearer(user_id))
                .status_code
            )

        statuses = run_in_parallel([reserve, sell] * 4)
    assert statuses.count(201) == 4
    assert statuses.count(409) == 4
    final = totals(committed, product_id)
    reserved_ok = statuses[0::2].count(201)  # чётные позиции — резервы, нечётные — продажи
    sold_ok = statuses[1::2].count(201)
    assert reserved_ok + sold_ok == 4  # обещано и продано ровно столько, сколько было
    assert final.reserved == reserved_ok
    assert final.on_hand == 4 - sold_ok
    assert final.available == 0
    assert_consistent(committed)


def test_reservations_over_same_products_in_opposite_order_do_not_deadlock(
    committed: sessionmaker[Session],
) -> None:
    user_id, (first, second) = setup_products(committed, ["20", "20"])
    with api_with_commits(committed) as new_client:

        def reserve(order: list[int]):
            def action() -> int:
                body = {
                    "reference": "Н",
                    "items": [{"product_id": pid, "quantity": "1"} for pid in order],
                }
                return (
                    new_client()
                    .post(f"{API}/reservations", json=body, headers=bearer(user_id))
                    .status_code
                )

            return action

        actions = [
            reserve([first, second]) if i % 2 == 0 else reserve([second, first])
            for i in range(THREADS)
        ]
        statuses = run_in_parallel(actions)
    assert statuses == [201] * THREADS
    assert totals(committed, first).reserved == THREADS
    assert totals(committed, second).reserved == THREADS
    assert_consistent(committed)


def test_parallel_cancel_releases_only_once(committed: sessionmaker[Session]) -> None:
    user_id, (product_id,) = setup_products(committed, ["10"])
    reservation_id = make_reservation(committed, user_id, product_id, 3)
    with api_with_commits(committed) as new_client:
        statuses = run_in_parallel(
            [
                lambda: (
                    new_client()
                    .post(f"{API}/reservations/{reservation_id}/cancel", headers=bearer(user_id))
                    .status_code
                )
                for _ in range(THREADS)
            ]
        )
    assert sorted(statuses) == [200] + [409] * (THREADS - 1)
    assert totals(committed, product_id).reserved == 0  # не ушло в минус
    assert_consistent(committed)


def test_parallel_fulfill_ships_only_once(committed: sessionmaker[Session]) -> None:
    user_id, (product_id,) = setup_products(committed, ["10"])
    reservation_id = make_reservation(committed, user_id, product_id, 3)
    with api_with_commits(committed) as new_client:
        statuses = run_in_parallel(
            [
                lambda: (
                    new_client()
                    .post(f"{API}/reservations/{reservation_id}/fulfill", headers=bearer(user_id))
                    .status_code
                )
                for _ in range(THREADS)
            ]
        )
    assert sorted(statuses) == [200] + [409] * (THREADS - 1)
    final = totals(committed, product_id)
    assert (final.on_hand, final.reserved) == (7, 0)
    assert_consistent(committed)


def test_cancel_and_fulfill_race_has_one_winner(committed: sessionmaker[Session]) -> None:
    user_id, (product_id,) = setup_products(committed, ["10"])
    reservation_id = make_reservation(committed, user_id, product_id, 4)
    with api_with_commits(committed) as new_client:

        def call(action: str):
            return lambda: (
                new_client()
                .post(f"{API}/reservations/{reservation_id}/{action}", headers=bearer(user_id))
                .status_code
            )

        statuses = run_in_parallel([call("cancel"), call("fulfill")] * 3)
    assert statuses.count(200) == 1
    with committed() as session:
        status = session.get(Reservation, reservation_id).status
    assert status in ("CANCELLED", "FULFILLED")
    final = totals(committed, product_id)
    assert final.reserved == 0
    assert final.on_hand == (10 if status == "CANCELLED" else 6)
    assert_consistent(committed)


def test_parallel_expiry_jobs_release_each_reservation_once(
    committed: sessionmaker[Session],
) -> None:
    user_id, (product_id,) = setup_products(committed, ["50"])
    past = datetime.now(UTC) - timedelta(days=1)
    for _ in range(6):
        make_reservation(committed, user_id, product_id, 2, now=past)

    def job() -> int:
        with committed() as session:
            count = reservations.expire_due_reservations(session, limit=2)
            session.commit()
            return count

    processed = run_in_parallel([job] * 4)
    # пропуск уже захваченных строк (SKIP LOCKED) не должен приводить к двойному освобождению
    while True:
        extra = job()
        if extra == 0:
            break
        processed.append(extra)
    assert sum(processed) == 6
    assert totals(committed, product_id).reserved == 0
    with committed() as session:
        expired = session.scalar(
            select(func.count()).select_from(Reservation).where(Reservation.status == "EXPIRED")
        )
        releases = session.scalar(
            select(func.count()).select_from(StockMovement).where(StockMovement.type == "RELEASE")
        )
    assert (expired, releases) == (6, 6)
    assert_consistent(committed)


def test_expiry_and_cancel_race_releases_once(committed: sessionmaker[Session]) -> None:
    user_id, (product_id,) = setup_products(committed, ["10"])
    past = datetime.now(UTC) - timedelta(days=1)
    reservation_id = make_reservation(committed, user_id, product_id, 5, now=past)

    def expire() -> int:
        with committed() as session:
            count = reservations.expire_due_reservations(session)
            session.commit()
            return count

    with api_with_commits(committed) as new_client:

        def cancel() -> int:
            return (
                new_client()
                .post(f"{API}/reservations/{reservation_id}/cancel", headers=bearer(user_id))
                .status_code
            )

        run_in_parallel([expire, cancel, expire, cancel])
    assert totals(committed, product_id).reserved == 0
    with committed() as session:
        assert session.get(Reservation, reservation_id).status in ("CANCELLED", "EXPIRED")
    assert_consistent(committed)


def test_stocktaking_start_races_with_write_offs(committed: sessionmaker[Session]) -> None:
    """«Ожидали» должно совпасть с остатком на момент старта, дальше движения запрещены."""
    user_id, (product_id,) = setup_products(committed, ["20"])
    with api_with_commits(committed) as new_client:
        created = new_client().post(f"{API}/stocktakings", json={}, headers=bearer(user_id)).json()
        session_id = created["id"]

        def start() -> int:
            return (
                new_client()
                .post(f"{API}/stocktakings/{session_id}/start", headers=bearer(user_id))
                .status_code
            )

        def sell() -> int:
            body = {"product_id": product_id, "quantity": "1", "reason": "SALE"}
            return (
                new_client()
                .post(f"{API}/write-offs", json=body, headers=bearer(user_id))
                .status_code
            )

        statuses = run_in_parallel([sell, sell, start, sell, sell, sell, sell, sell])
    assert statuses[2] == 200
    with committed() as session:
        expected = session.scalar(
            select(InventoryLine.expected_qty).where(InventoryLine.session_id == session_id)
        )
    final = totals(committed, product_id)
    # ни одно списание не прошло после старта: «ожидали» равно остатку в конце
    assert expected == final.on_hand
    assert statuses.count(201) == 20 - int(final.on_hand)
    assert_consistent(committed)


def test_inventory_close_keeps_stock_consistent_under_parallel_cancel_of_reservations(
    committed: sessionmaker[Session],
) -> None:
    user_id, (product_id,) = setup_products(committed, ["10"])
    reservation_ids = [make_reservation(committed, user_id, product_id, 1) for _ in range(4)]
    with api_with_commits(committed) as new_client:
        session_id = (
            new_client().post(f"{API}/stocktakings", json={}, headers=bearer(user_id)).json()["id"]
        )
        new_client().post(f"{API}/stocktakings/{session_id}/start", headers=bearer(user_id))
        new_client().put(
            f"{API}/stocktakings/{session_id}/lines/{product_id}",
            json={"counted_qty": "7"},
            headers=bearer(user_id),
        )

        def cancel(reservation_id: int):
            return lambda: (
                new_client()
                .post(f"{API}/reservations/{reservation_id}/cancel", headers=bearer(user_id))
                .status_code
            )

        def close() -> int:
            return (
                new_client()
                .post(f"{API}/stocktakings/{session_id}/close", headers=bearer(user_id))
                .status_code
            )

        statuses = run_in_parallel([close] + [cancel(r) for r in reservation_ids])
    assert statuses[0] == 200
    assert statuses[1:] == [200] * 4  # снятие резерва не мешает инвентаризации
    final = totals(committed, product_id)
    assert (final.on_hand, final.reserved) == (7, 0)
    assert_consistent(committed)
