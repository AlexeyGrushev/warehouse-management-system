from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Conflict, NotFound, StocktakingInProgress, Unprocessable
from app.core.pagination import PageParams, paginate
from app.modules.auth.models import User
from app.modules.catalog import service as catalog_service
from app.modules.catalog.models import Product
from app.modules.stock import service as stock_service
from app.modules.stocktaking.models import InventoryLine, InventorySession
from app.modules.stocktaking.schemas import LineRead, StocktakingDetail, StocktakingSummary


def get_session_or_404(session: Session, session_id: int) -> InventorySession:
    inventory = session.scalar(
        select(InventorySession)
        .where(InventorySession.id == session_id)
        .options(selectinload(InventorySession.lines))
    )
    if inventory is None:
        raise NotFound("Инвентаризация не найдена", {"inventory_session_id": str(session_id)})
    return inventory


def _lock_session(session: Session, session_id: int) -> InventorySession:
    inventory = session.scalar(
        select(InventorySession).where(InventorySession.id == session_id).with_for_update()
    )
    if inventory is None:
        raise NotFound("Инвентаризация не найдена", {"inventory_session_id": str(session_id)})
    return inventory


def summary(inventory: InventorySession) -> StocktakingSummary:
    return StocktakingSummary(
        id=inventory.id,
        status=inventory.status,
        created_by=inventory.created_by,
        created_at=inventory.created_at,
        started_at=inventory.started_at,
        closed_at=inventory.closed_at,
        lines_total=len(inventory.lines),
        lines_counted=sum(1 for line in inventory.lines if line.counted_qty is not None),
    )


def detail(session: Session, inventory: InventorySession) -> StocktakingDetail:
    products = {
        product.id: product
        for product in session.scalars(
            select(Product).where(Product.id.in_([line.product_id for line in inventory.lines]))
        )
    }
    lines = []
    for line in sorted(inventory.lines, key=lambda item: item.product_id):
        product = products[line.product_id]
        counted, expected = line.counted_qty, line.expected_qty
        lines.append(
            LineRead(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                unit=product.unit,
                expected_qty=expected,
                counted_qty=counted,
                diff=counted - expected if counted is not None and expected is not None else None,
            )
        )
    return StocktakingDetail(**summary(inventory).model_dump(), lines=lines)


def list_sessions(
    session: Session, params: PageParams, status: str | None = None
) -> tuple[list[StocktakingSummary], int]:
    query = (
        select(InventorySession)
        .options(selectinload(InventorySession.lines))
        .order_by(InventorySession.id.desc())
    )
    if status:
        query = query.where(InventorySession.status == status)
    rows, total = paginate(session, query, params)
    return [summary(row) for row in rows], total


def create_session(
    session: Session, user: User, category_id: int | None = None
) -> InventorySession:
    query = select(Product.id).where(Product.is_active.is_(True)).order_by(Product.id)
    if category_id is not None:
        query = query.where(
            Product.category_id.in_(catalog_service.category_subtree_ids(session, category_id))
        )
    product_ids = list(session.scalars(query))
    if not product_ids:
        raise Unprocessable("Нет активных товаров для инвентаризации")
    inventory = InventorySession(status="DRAFT", created_by=user.id)
    session.add(inventory)
    session.flush()
    session.add_all(InventoryLine(session_id=inventory.id, product_id=pid) for pid in product_ids)
    session.flush()
    return get_session_or_404(session, inventory.id)


def start_session(
    session: Session, session_id: int, now: datetime | None = None
) -> InventorySession:
    """Старт: фиксируем «ожидали» (= на складе сейчас) и запрещаем движения по товарам сессии."""
    now = now or datetime.now(UTC)
    inventory = _lock_session(session, session_id)
    if inventory.status != "DRAFT":
        raise Conflict(
            "Начать можно только черновик инвентаризации",
            {"inventory_session_id": str(session_id), "status": inventory.status},
        )
    lines = list(
        session.scalars(
            select(InventoryLine)
            .where(InventoryLine.session_id == session_id)
            .order_by(InventoryLine.product_id)
        )
    )
    product_ids = [line.product_id for line in lines]
    # Блокировка товаров: пока мы фиксируем остатки, никто не может провести движение
    stock_service.lock_products(session, product_ids)
    busy = session.execute(
        select(InventoryLine.product_id, InventoryLine.session_id)
        .join(InventorySession, InventorySession.id == InventoryLine.session_id)
        .where(
            InventorySession.status == "IN_PROGRESS",
            InventoryLine.product_id.in_(product_ids),
            InventoryLine.session_id != session_id,
        )
        .order_by(InventoryLine.product_id)
        .limit(1)
    ).first()
    if busy is not None:
        raise StocktakingInProgress(
            "Товар уже участвует в другой открытой инвентаризации",
            {"product_id": str(busy[0]), "inventory_session_id": str(busy[1])},
        )
    for line in lines:
        line.expected_qty = stock_service.get_totals(session, line.product_id).on_hand
    inventory.status = "IN_PROGRESS"
    inventory.started_at = now
    session.flush()
    return get_session_or_404(session, session_id)


def cancel_session(
    session: Session, session_id: int, now: datetime | None = None
) -> InventorySession:
    now = now or datetime.now(UTC)
    inventory = _lock_session(session, session_id)
    if inventory.status not in ("DRAFT", "IN_PROGRESS"):
        raise Conflict(
            "Отменить можно только черновик или идущую инвентаризацию",
            {"inventory_session_id": str(session_id), "status": inventory.status},
        )
    inventory.status = "CANCELLED"
    inventory.closed_at = now
    session.flush()
    return get_session_or_404(session, session_id)
