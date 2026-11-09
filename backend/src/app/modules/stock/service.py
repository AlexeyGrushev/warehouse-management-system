"""Единственное место, где считаются и (дальше) меняются остатки.

На складе = SUM(quantity_delta), в резерве = SUM(reserved_delta), доступно = на складе − в резерве.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    Conflict,
    InsufficientStock,
    NotFound,
    StocktakingInProgress,
    Unprocessable,
)
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.stock.models import Batch, StockMovement
from app.modules.stock.schemas import (
    ReceiptCreate,
    StockLevel,
    StockTotals,
    WriteOffCreate,
    WriteOffLine,
    WriteOffResult,
)
from app.modules.stocktaking.models import InventoryLine, InventorySession
from app.modules.suppliers.models import Supplier

ZERO = Decimal("0")


def lock_product(session: Session, product_id: int) -> Product:
    """Блокирует строку товара до конца транзакции (операции над его остатком идут по очереди)."""
    product = session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise NotFound("Товар не найден", {"product_id": str(product_id)})
    return product


def lock_products(session: Session, product_ids: list[int]) -> list[Product]:
    """Блокирует несколько товаров, строго по возрастанию id (иначе возможны взаимоблокировки)."""
    ids = sorted(set(product_ids))
    products = list(
        session.scalars(
            select(Product).where(Product.id.in_(ids)).order_by(Product.id).with_for_update()
        )
    )
    missing = set(ids) - {product.id for product in products}
    if missing:
        raise NotFound("Товар не найден", {"product_id": str(min(missing))})
    return products


def ensure_not_in_stocktaking(session: Session, product_ids: list[int]) -> None:
    """Пока идёт инвентаризация, приход, списание и новые резервы по её товарам запрещены."""
    row = session.execute(
        select(InventoryLine.product_id, InventoryLine.session_id)
        .join(InventorySession, InventorySession.id == InventoryLine.session_id)
        .where(InventorySession.status == "IN_PROGRESS", InventoryLine.product_id.in_(product_ids))
        .order_by(InventoryLine.product_id)
        .limit(1)
    ).first()
    if row is not None:
        raise StocktakingInProgress(
            "По товару идёт инвентаризация: движения временно запрещены",
            {"product_id": str(row[0]), "inventory_session_id": str(row[1])},
        )


def get_totals(session: Session, product_id: int) -> StockTotals:
    on_hand, reserved = session.execute(
        select(
            func.coalesce(func.sum(StockMovement.quantity_delta), ZERO),
            func.coalesce(func.sum(StockMovement.reserved_delta), ZERO),
        ).where(StockMovement.product_id == product_id)
    ).one()
    return StockTotals(on_hand=on_hand, reserved=reserved)


def product_has_stock(session: Session, product_id: int) -> bool:
    """Есть ли у товара остаток на складе или активный резерв."""
    totals = get_totals(session, product_id)
    return totals.on_hand > 0 or totals.reserved > 0


def supplier_has_stock(session: Session, supplier_id: int) -> bool:
    """Есть ли партии этого поставщика с остатком."""
    return (
        session.scalar(
            select(Batch.id)
            .where(Batch.supplier_id == supplier_id, Batch.qty_remaining > 0)
            .limit(1)
        )
        is not None
    )


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


def require_whole_for_pieces(product: Product, quantity: Decimal) -> None:
    if product.unit == "pcs" and quantity != quantity.to_integral_value():
        raise Unprocessable("Для штучных товаров количество должно быть целым")


def receive(session: Session, user: User, data: ReceiptCreate) -> Batch:
    """Приход: создаёт партию и записывает движение RECEIPT в одной транзакции."""
    product = lock_product(session, data.product_id)
    ensure_not_in_stocktaking(session, [product.id])
    if not product.is_active:
        raise Conflict("Товар в архиве", {"product_id": str(product.id)})
    supplier = session.get(Supplier, data.supplier_id)
    if supplier is None:
        raise NotFound("Поставщик не найден", {"supplier_id": str(data.supplier_id)})
    if not supplier.is_active:
        raise Conflict("Поставщик в архиве", {"supplier_id": str(supplier.id)})
    require_whole_for_pieces(product, data.quantity)

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


def _batches_fefo(
    session: Session, product_id: int, today: date, skip_expired: bool
) -> list[Batch]:
    """Партии с остатком в порядке FEFO: срок годности (NULL в конце), дата прихода, id."""
    query = (
        select(Batch)
        .where(Batch.product_id == product_id, Batch.qty_remaining > 0)
        .order_by(Batch.expires_at.asc().nulls_last(), Batch.received_at, Batch.id)
    )
    if skip_expired:
        query = query.where(Batch.expires_at.is_(None) | (Batch.expires_at >= today))
    return list(session.scalars(query))


def write_off(
    session: Session,
    user: User,
    data: WriteOffCreate,
    today: date | None = None,
    reservation_id: int | None = None,
) -> WriteOffResult:
    """Списание по FEFO: из каждой затронутой партии отдельная запись WRITE_OFF.

    Продажа (SALE) пропускает просроченные партии и проверяет остаток только по непросроченным;
    для остальных причин берутся все партии. Операция выполняется целиком или не выполняется.
    """
    today = today or date.today()
    product = lock_product(session, data.product_id)
    ensure_not_in_stocktaking(session, [product.id])
    require_whole_for_pieces(product, data.quantity)

    skip_expired = data.reason == "SALE"
    batches = _batches_fefo(session, product.id, today, skip_expired)
    reserved = get_totals(session, product.id).reserved
    available = sum((batch.qty_remaining for batch in batches), ZERO) - reserved
    if data.quantity > available:
        shown = max(available, ZERO)
        raise InsufficientStock(
            f"Запрошено {data.quantity:.3f}, доступно {shown:.3f}",
            {
                "product_id": str(product.id),
                "requested": f"{data.quantity:.3f}",
                "available": f"{shown:.3f}",
            },
        )

    need = data.quantity
    lines: list[WriteOffLine] = []
    for batch in batches:
        if need <= 0:
            break
        take = min(batch.qty_remaining, need)
        batch.qty_remaining -= take
        session.add(
            StockMovement(
                type="WRITE_OFF",
                product_id=product.id,
                batch_id=batch.id,
                quantity_delta=-take,
                reason=data.reason,
                reservation_id=reservation_id,
                user_id=user.id,
                comment=data.comment,
            )
        )
        lines.append(WriteOffLine(batch_id=batch.id, batch_no=batch.batch_no, quantity=take))
        need -= take
    session.flush()
    return WriteOffResult(
        product_id=product.id, reason=data.reason, quantity=data.quantity, lines=lines
    )


def available_quantity(session: Session, product_id: int) -> Decimal:
    """Сколько можно обещать: на складе минус в резерве."""
    return get_totals(session, product_id).available


def reserve(
    session: Session, user: User, product: Product, quantity: Decimal, reservation_id: int
) -> StockMovement:
    """Движение RESERVE: уменьшает «доступно», не трогая «на складе» (товар уже заблокирован)."""
    available = available_quantity(session, product.id)
    if quantity > available:
        raise InsufficientStock(
            f"Запрошено {quantity:.3f}, доступно {max(available, ZERO):.3f}",
            {
                "product_id": str(product.id),
                "requested": f"{quantity:.3f}",
                "available": f"{max(available, ZERO):.3f}",
            },
        )
    movement = StockMovement(
        type="RESERVE",
        product_id=product.id,
        reservation_id=reservation_id,
        reserved_delta=quantity,
        user_id=user.id,
    )
    session.add(movement)
    session.flush()
    return movement


def release(
    session: Session,
    user: User,
    product_id: int,
    quantity: Decimal,
    reservation_id: int,
    comment: str | None = None,
) -> StockMovement:
    """Движение RELEASE: возвращает зарезервированное количество в «доступно»."""
    movement = StockMovement(
        type="RELEASE",
        product_id=product_id,
        reservation_id=reservation_id,
        reserved_delta=-quantity,
        user_id=user.id,
        comment=comment,
    )
    session.add(movement)
    session.flush()
    return movement


def adjust_down(
    session: Session,
    user: User,
    product_id: int,
    quantity: Decimal,
    inventory_session_id: int,
    today: date | None = None,
) -> list[StockMovement]:
    """Недостача по инвентаризации: списывает по FEFO из всех партий (и просроченных тоже).

    По одному движению ADJUSTMENT с отрицательным знаком на каждую затронутую партию.
    """
    today = today or date.today()
    batches = _batches_fefo(session, product_id, today, skip_expired=False)
    available = sum((batch.qty_remaining for batch in batches), ZERO)
    if quantity > available:
        raise InsufficientStock(
            "Недостача больше остатка в партиях: остатки не сходятся с журналом",
            {"product_id": str(product_id), "requested": f"{quantity:.3f}"},
        )
    movements: list[StockMovement] = []
    need = quantity
    for batch in batches:
        if need <= 0:
            break
        take = min(batch.qty_remaining, need)
        batch.qty_remaining -= take
        movement = StockMovement(
            type="ADJUSTMENT",
            product_id=product_id,
            batch_id=batch.id,
            quantity_delta=-take,
            inventory_session_id=inventory_session_id,
            user_id=user.id,
            comment="Недостача по инвентаризации",
        )
        session.add(movement)
        movements.append(movement)
        need -= take
    session.flush()
    return movements


def adjust_up(
    session: Session,
    user: User,
    product_id: int,
    quantity: Decimal,
    inventory_session_id: int,
    today: date | None = None,
) -> StockMovement:
    """Излишек по инвентаризации: корректирующая партия INV-<id сессии> и движение ADJUSTMENT.

    Цена — последняя закупочная цена товара (или 0, если партий ещё не было).
    """
    today = today or date.today()
    last_cost = session.scalar(
        select(Batch.unit_cost)
        .where(Batch.product_id == product_id)
        .order_by(Batch.received_at.desc(), Batch.id.desc())
        .limit(1)
    )
    batch = Batch(
        product_id=product_id,
        supplier_id=None,
        batch_no=f"INV-{inventory_session_id}",
        qty_received=quantity,
        qty_remaining=quantity,
        unit_cost=last_cost if last_cost is not None else ZERO,
        received_at=today,
        expires_at=None,
    )
    session.add(batch)
    session.flush()
    movement = StockMovement(
        type="ADJUSTMENT",
        product_id=product_id,
        batch_id=batch.id,
        quantity_delta=quantity,
        inventory_session_id=inventory_session_id,
        user_id=user.id,
        comment="Излишек по инвентаризации",
    )
    session.add(movement)
    session.flush()
    return movement
