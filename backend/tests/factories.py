"""Помощники для тестов: быстро создать товар, партию и движения напрямую в БД."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.catalog.models import Category, Product
from app.modules.stock.models import Batch, StockMovement
from app.modules.suppliers.models import Supplier

_counter = {"n": 0}


def _next() -> int:
    _counter["n"] += 1
    return _counter["n"]


def make_category(session: Session, name: str | None = None) -> Category:
    category = Category(name=name or f"Категория {_next()}")
    session.add(category)
    session.flush()
    return category


def make_product(
    session: Session, unit: str = "pcs", min_stock: str = "0", sku: str | None = None
) -> Product:
    category = make_category(session)
    product = Product(
        sku=sku or f"SKU-{_next()}",
        name="Товар",
        category_id=category.id,
        unit=unit,
        min_stock=Decimal(min_stock),
    )
    session.add(product)
    session.flush()
    return product


def make_supplier(session: Session, name: str | None = None) -> Supplier:
    supplier = Supplier(name=name or f"Поставщик {_next()}")
    session.add(supplier)
    session.flush()
    return supplier


def add_batch(
    session: Session,
    product: Product,
    user_id: int,
    quantity: str = "10",
    *,
    batch_no: str | None = None,
    received_at: date = date(2026, 10, 1),
    expires_at: date | None = None,
    supplier: Supplier | None = None,
    unit_cost: str = "10.00",
) -> Batch:
    """Партия вместе с записью RECEIPT, как её создаёт приход."""
    batch = Batch(
        product_id=product.id,
        supplier_id=supplier.id if supplier else None,
        batch_no=batch_no or f"B-{_next()}",
        qty_received=Decimal(quantity),
        qty_remaining=Decimal(quantity),
        unit_cost=Decimal(unit_cost),
        received_at=received_at,
        expires_at=expires_at,
    )
    session.add(batch)
    session.flush()
    session.add(
        StockMovement(
            type="RECEIPT",
            product_id=product.id,
            batch_id=batch.id,
            quantity_delta=Decimal(quantity),
            user_id=user_id,
        )
    )
    session.flush()
    return batch


def add_reserve(session: Session, product: Product, user_id: int, quantity: str) -> None:
    session.add(
        StockMovement(
            type="RESERVE",
            product_id=product.id,
            reserved_delta=Decimal(quantity),
            user_id=user_id,
        )
    )
    session.flush()
