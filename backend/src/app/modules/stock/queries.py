"""Чтение: списки партий, журнала движений и остатков (без изменения данных)."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, paginate_rows
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.stock.models import Batch, StockMovement
from app.modules.stock.schemas import BatchDetail, MovementRead, StockRow
from app.modules.suppliers.models import Supplier

MOSCOW = ZoneInfo("Europe/Moscow")


def list_batches(
    session: Session,
    params: PageParams,
    product_id: int | None = None,
    supplier_id: int | None = None,
    only_in_stock: bool = False,
) -> tuple[list[BatchDetail], int]:
    query = (
        select(Batch, Product.sku, Product.name, Supplier.name)
        .join(Product, Product.id == Batch.product_id)
        .outerjoin(Supplier, Supplier.id == Batch.supplier_id)
        .order_by(Batch.received_at.desc(), Batch.id.desc())
    )
    if product_id is not None:
        query = query.where(Batch.product_id == product_id)
    if supplier_id is not None:
        query = query.where(Batch.supplier_id == supplier_id)
    if only_in_stock:
        query = query.where(Batch.qty_remaining > 0)
    rows, total = paginate_rows(session, query, params)
    items = [
        BatchDetail.model_validate(
            {
                **{
                    column: getattr(batch, column)
                    for column in BatchDetail.model_fields
                    if hasattr(batch, column)
                },
                "product_sku": sku,
                "product_name": name,
                "supplier_name": supplier_name,
            }
        )
        for batch, sku, name, supplier_name in rows
    ]
    return items, total


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=MOSCOW)


def list_movements(
    session: Session,
    params: PageParams,
    product_id: int | None = None,
    movement_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user_id: int | None = None,
) -> tuple[list[MovementRead], int]:
    """Журнал: новые записи сверху. Даты включительно, границы суток — по московскому времени."""
    query = (
        select(StockMovement, Product.sku, Product.name, Batch.batch_no, User.email)
        .join(Product, Product.id == StockMovement.product_id)
        .outerjoin(Batch, Batch.id == StockMovement.batch_id)
        .join(User, User.id == StockMovement.user_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    )
    if product_id is not None:
        query = query.where(StockMovement.product_id == product_id)
    if movement_type is not None:
        query = query.where(StockMovement.type == movement_type)
    if date_from is not None:
        query = query.where(StockMovement.created_at >= _day_start(date_from))
    if date_to is not None:
        query = query.where(StockMovement.created_at < _day_start(date_to + timedelta(days=1)))
    if user_id is not None:
        query = query.where(StockMovement.user_id == user_id)
    rows, total = paginate_rows(session, query, params)
    items = [
        MovementRead(
            id=movement.id,
            type=movement.type,
            product_id=movement.product_id,
            product_sku=sku,
            product_name=name,
            batch_id=movement.batch_id,
            batch_no=batch_no,
            quantity_delta=movement.quantity_delta,
            reserved_delta=movement.reserved_delta,
            reason=movement.reason,
            comment=movement.comment,
            user_id=movement.user_id,
            user_email=email,
            created_at=movement.created_at,
        )
        for movement, sku, name, batch_no, email in rows
    ]
    return items, total


def list_stock(
    session: Session,
    params: PageParams,
    q: str | None = None,
    category_id: int | None = None,
    low_only: bool = False,
    is_active: bool | None = True,
) -> tuple[list[StockRow], int]:
    totals = (
        select(
            StockMovement.product_id.label("product_id"),
            func.sum(StockMovement.quantity_delta).label("on_hand"),
            func.sum(StockMovement.reserved_delta).label("reserved"),
        )
        .group_by(StockMovement.product_id)
        .subquery()
    )
    on_hand = func.coalesce(totals.c.on_hand, 0)
    reserved = func.coalesce(totals.c.reserved, 0)
    query = (
        select(Product, on_hand.label("on_hand"), reserved.label("reserved"))
        .outerjoin(totals, totals.c.product_id == Product.id)
        .order_by(Product.name, Product.id)
    )
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(Product.name.ilike(pattern) | Product.sku.ilike(pattern))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)
    if low_only:
        query = query.where(on_hand - reserved < Product.min_stock)
    rows, total = paginate_rows(session, query, params)
    items = [
        StockRow(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            unit=product.unit,
            on_hand=on_hand_value,
            reserved=reserved_value,
            available=Decimal(on_hand_value) - Decimal(reserved_value),
            min_stock=product.min_stock,
            is_low=Decimal(on_hand_value) - Decimal(reserved_value) < product.min_stock,
        )
        for product, on_hand_value, reserved_value in rows
    ]
    return items, total
