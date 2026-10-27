"""Единственное место, где считаются и (дальше) меняются остатки.

На складе = SUM(quantity_delta), в резерве = SUM(reserved_delta), доступно = на складе − в резерве.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.modules.catalog.models import Product
from app.modules.stock.models import StockMovement
from app.modules.stock.schemas import StockLevel, StockTotals

ZERO = Decimal("0")


def lock_product(session: Session, product_id: int) -> Product:
    """Блокирует строку товара до конца транзакции (операции над его остатком идут по очереди)."""
    product = session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise NotFound("Товар не найден", {"product_id": str(product_id)})
    return product


def get_totals(session: Session, product_id: int) -> StockTotals:
    on_hand, reserved = session.execute(
        select(
            func.coalesce(func.sum(StockMovement.quantity_delta), ZERO),
            func.coalesce(func.sum(StockMovement.reserved_delta), ZERO),
        ).where(StockMovement.product_id == product_id)
    ).one()
    return StockTotals(on_hand=on_hand, reserved=reserved)


def get_stock(session: Session, product_id: int) -> StockLevel:
    product = session.get(Product, product_id)
    if product is None:
        raise NotFound("Товар не найден", {"product_id": str(product_id)})
    totals = get_totals(session, product_id)
    return StockLevel(
        product_id=product_id,
        on_hand=totals.on_hand,
        reserved=totals.reserved,
        available=totals.available,
        min_stock=product.min_stock,
    )
