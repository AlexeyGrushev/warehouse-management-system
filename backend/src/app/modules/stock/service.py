"""Единственное место, где считаются и (дальше) меняются остатки.

На складе = SUM(quantity_delta), в резерве = SUM(reserved_delta), доступно = на складе − в резерве.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, Unprocessable
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.stock.models import Batch, StockMovement
from app.modules.stock.schemas import ReceiptCreate, StockLevel, StockTotals
from app.modules.suppliers.models import Supplier

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


def _require_whole_for_pieces(product: Product, quantity: Decimal) -> None:
    if product.unit == "pcs" and quantity != quantity.to_integral_value():
        raise Unprocessable("Для штучных товаров количество должно быть целым")


def receive(session: Session, user: User, data: ReceiptCreate) -> Batch:
    """Приход: создаёт партию и записывает движение RECEIPT в одной транзакции."""
    product = lock_product(session, data.product_id)
    if not product.is_active:
        raise Conflict("Товар в архиве", {"product_id": str(product.id)})
    supplier = session.get(Supplier, data.supplier_id)
    if supplier is None:
        raise NotFound("Поставщик не найден", {"supplier_id": str(data.supplier_id)})
    if not supplier.is_active:
        raise Conflict("Поставщик в архиве", {"supplier_id": str(supplier.id)})
    _require_whole_for_pieces(product, data.quantity)

    duplicate = session.scalar(
        select(Batch.id).where(Batch.product_id == product.id, Batch.batch_no == data.batch_no)
    )
    if duplicate is not None:
        raise Conflict("Партия с таким номером уже есть у товара", {"batch_no": data.batch_no})

    batch = Batch(
        product_id=product.id,
        supplier_id=supplier.id,
        batch_no=data.batch_no,
        qty_received=data.quantity,
        qty_remaining=data.quantity,
        unit_cost=data.unit_cost,
        received_at=data.received_at,
        expires_at=data.expires_at,
    )
    session.add(batch)
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as exc:
        raise Conflict(
            "Партия с таким номером уже есть у товара", {"batch_no": data.batch_no}
        ) from exc
    session.add(
        StockMovement(
            type="RECEIPT",
            product_id=product.id,
            batch_id=batch.id,
            quantity_delta=data.quantity,
            user_id=user.id,
        )
    )
    session.flush()
    return batch
