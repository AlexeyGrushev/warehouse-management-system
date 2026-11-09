from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.reservations.models import Reservation, ReservationItem
from app.modules.stock.models import StockMovement
from tests.factories import make_product
from tests.helpers import make_user


def make_reservation(session: Session, status: str = "ACTIVE", user=None) -> Reservation:
    user = user or make_user(session)
    reservation = Reservation(
        reference="ЗАКАЗ-1",
        status=status,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        created_by=user.id,
    )
    session.add(reservation)
    session.flush()
    return reservation


def test_reservation_defaults_to_active(session: Session) -> None:
    user = make_user(session)
    reservation = Reservation(
        reference="ЗАКАЗ-2", expires_at=datetime.now(UTC) + timedelta(days=1), created_by=user.id
    )
    session.add(reservation)
    session.flush()
    session.refresh(reservation)
    assert reservation.status == "ACTIVE"


def test_unknown_status_is_rejected(session: Session) -> None:
    with pytest.raises(IntegrityError):
        make_reservation(session, status="PENDING")


@pytest.mark.parametrize("quantity", ["0", "-1"])
def test_item_quantity_must_be_positive(session: Session, quantity: str) -> None:
    reservation = make_reservation(session)
    product = make_product(session)
    session.add(
        ReservationItem(
            reservation_id=reservation.id, product_id=product.id, quantity=Decimal(quantity)
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_product_appears_once_per_reservation(session: Session) -> None:
    reservation = make_reservation(session)
    product = make_product(session)
    for _ in range(2):
        session.add(
            ReservationItem(
                reservation_id=reservation.id, product_id=product.id, quantity=Decimal("1")
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()


def test_same_product_in_different_reservations(session: Session) -> None:
    user = make_user(session)
    first = make_reservation(session, user=user)
    second = make_reservation(session, user=user)
    product = make_product(session)
    session.add_all(
        [
            ReservationItem(reservation_id=r.id, product_id=product.id, quantity=Decimal("1"))
            for r in (first, second)
        ]
    )
    session.flush()


def test_reserve_movement_can_reference_reservation(session: Session) -> None:
    reservation = make_reservation(session)
    product = make_product(session)
    session.add(
        StockMovement(
            type="RESERVE",
            product_id=product.id,
            reservation_id=reservation.id,
            reserved_delta=Decimal("2"),
            user_id=reservation.created_by,
        )
    )
    session.flush()


def test_movement_cannot_reference_missing_reservation(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    session.add(
        StockMovement(
            type="RESERVE",
            product_id=product.id,
            reservation_id=999999,
            reserved_delta=Decimal("2"),
            user_id=user.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_items_are_loaded_through_relationship(session: Session) -> None:
    reservation = make_reservation(session)
    products = [make_product(session), make_product(session)]
    for product in reversed(products):
        session.add(
            ReservationItem(
                reservation_id=reservation.id, product_id=product.id, quantity=Decimal("1")
            )
        )
    session.flush()
    session.refresh(reservation)
    assert [item.product_id for item in reservation.items] == sorted(p.id for p in products)
