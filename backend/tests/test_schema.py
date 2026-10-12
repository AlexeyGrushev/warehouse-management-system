from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.catalog.models import Category, Product
from app.modules.stock.models import Batch, StockMovement


def make_product(session: Session, sku: str = "SKU-1") -> Product:
    category = Category(name=f"Категория {sku}")
    session.add(category)
    session.flush()
    product = Product(sku=sku, name="Товар", category_id=category.id, unit="pcs")
    session.add(product)
    session.flush()
    return product


def make_batch(session: Session, product: Product, **overrides) -> Batch:
    values = {
        "product_id": product.id,
        "batch_no": "B-1",
        "qty_received": Decimal("10"),
        "qty_remaining": Decimal("10"),
        "unit_cost": Decimal("5.00"),
        "received_at": date(2026, 10, 1),
    }
    batch = Batch(**{**values, **overrides})
    session.add(batch)
    session.flush()
    return batch


def make_user(session: Session) -> User:
    user = User(email="keeper@example.com", password_hash="x", role="storekeeper")
    session.add(user)
    session.flush()
    return user


def test_sku_is_unique(session: Session) -> None:
    product = make_product(session)
    session.add(Product(sku=product.sku, name="Дубль", category_id=product.category_id, unit="pcs"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_root_category_name_is_unique(session: Session) -> None:
    session.add_all([Category(name="Корень"), Category(name="Корень")])
    with pytest.raises(IntegrityError):
        session.flush()


def test_same_name_allowed_under_different_parents(session: Session) -> None:
    first, second = Category(name="Первая"), Category(name="Вторая")
    session.add_all([first, second])
    session.flush()
    session.add_all(
        [
            Category(name="Подкатегория", parent_id=first.id),
            Category(name="Подкатегория", parent_id=second.id),
        ]
    )
    session.flush()


def test_unknown_unit_is_rejected(session: Session) -> None:
    product = make_product(session)
    session.add(Product(sku="SKU-2", name="Товар", category_id=product.category_id, unit="tons"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_batch_remaining_cannot_exceed_received(session: Session) -> None:
    product = make_product(session)
    with pytest.raises(IntegrityError):
        make_batch(session, product, qty_remaining=Decimal("11"))


def test_batch_expiry_cannot_precede_receipt(session: Session) -> None:
    product = make_product(session)
    with pytest.raises(IntegrityError):
        make_batch(session, product, expires_at=date(2026, 9, 1))


def test_batch_number_is_unique_per_product(session: Session) -> None:
    product = make_product(session)
    make_batch(session, product)
    with pytest.raises(IntegrityError):
        make_batch(session, product)


def test_receipt_movement_is_accepted(session: Session) -> None:
    product = make_product(session)
    batch = make_batch(session, product)
    user = make_user(session)
    session.add(
        StockMovement(
            type="RECEIPT",
            product_id=product.id,
            batch_id=batch.id,
            quantity_delta=Decimal("10"),
            user_id=user.id,
        )
    )
    session.flush()


@pytest.mark.parametrize(
    ("movement_type", "quantity_delta", "reserved_delta", "with_batch"),
    [
        ("RECEIPT", "-1", "0", True),
        ("WRITE_OFF", "1", "0", True),
        ("RECEIPT", "1", "0", False),
        ("RESERVE", "0", "1", True),
        ("RELEASE", "0", "1", False),
        ("ADJUSTMENT", "0", "0", True),
    ],
)
def test_movement_type_must_match_signs(
    session: Session,
    movement_type: str,
    quantity_delta: str,
    reserved_delta: str,
    with_batch: bool,
) -> None:
    product = make_product(session)
    batch = make_batch(session, product)
    user = make_user(session)
    session.add(
        StockMovement(
            type=movement_type,
            product_id=product.id,
            batch_id=batch.id if with_batch else None,
            quantity_delta=Decimal(quantity_delta),
            reserved_delta=Decimal(reserved_delta),
            user_id=user.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_unknown_role_is_rejected(session: Session) -> None:
    session.add(User(email="x@example.com", password_hash="x", role="boss"))
    with pytest.raises(IntegrityError):
        session.flush()
