from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Conflict, InsufficientStock, NotFound, Unprocessable
from app.core.pagination import PageParams, paginate
from app.modules.auth.models import User
from app.modules.reservations.models import Reservation, ReservationItem
from app.modules.reservations.schemas import ReservationCreate
from app.modules.stock import service as stock_service
from app.modules.stock.schemas import WriteOffCreate

MOSCOW = ZoneInfo("Europe/Moscow")
DEFAULT_TTL = timedelta(days=7)


def _normalize_expiry(value: datetime | None, now: datetime) -> datetime:
    if value is None:
        return now + DEFAULT_TTL
    if value.tzinfo is None:
        value = value.replace(tzinfo=MOSCOW)  # без часового пояса — считаем московским временем
    if value <= now:
        raise Unprocessable("Срок действия резерва должен быть в будущем", {"field": "expires_at"})
    return value


def get_reservation(session: Session, reservation_id: int) -> Reservation:
    reservation = session.scalar(
        select(Reservation)
        .where(Reservation.id == reservation_id)
        .options(selectinload(Reservation.items))
    )
    if reservation is None:
        raise NotFound("Резерв не найден", {"reservation_id": str(reservation_id)})
    return reservation


def list_reservations(
    session: Session, params: PageParams, status: str | None = None, reference: str | None = None
) -> tuple[list[Reservation], int]:
    query: Select[tuple[Reservation]] = (
        select(Reservation).options(selectinload(Reservation.items)).order_by(Reservation.id.desc())
    )
    if status:
        query = query.where(Reservation.status == status)
    if reference:
        query = query.where(Reservation.reference.ilike(f"%{reference.strip()}%"))
    return paginate(session, query, params)


def create_reservation(
    session: Session, user: User, data: ReservationCreate, now: datetime | None = None
) -> Reservation:
    """Резерв «всё или ничего»: если хотя бы одной позиции не хватает, не создаётся ничего."""
    now = now or datetime.now(UTC)
    expires_at = _normalize_expiry(data.expires_at, now)

    # Товары блокируем по возрастанию id, чтобы параллельные резервы не взаимоблокировались
    products = {
        product.id: product
        for product in stock_service.lock_products(session, [i.product_id for i in data.items])
    }
    for item in data.items:
        product = products[item.product_id]
        if not product.is_active:
            raise Conflict("Товар в архиве", {"product_id": str(product.id)})
        stock_service.require_whole_for_pieces(product, item.quantity)

    shortages = []
    for item in sorted(data.items, key=lambda i: i.product_id):
        available = stock_service.available_quantity(session, item.product_id)
        if item.quantity > available:
            shortages.append((item.product_id, item.quantity, max(available, 0)))
    if shortages:
        first = shortages[0]
        details = "; ".join(
            f"товар {pid}: запрошено {req:.3f}, доступно {avail:.3f}"
            for pid, req, avail in shortages
        )
        raise InsufficientStock(
            f"Не хватает товара для резерва ({details})",
            {
                "product_id": str(first[0]),
                "requested": f"{first[1]:.3f}",
                "available": f"{first[2]:.3f}",
            },
        )

    reservation = Reservation(
        reference=data.reference, status="ACTIVE", expires_at=expires_at, created_by=user.id
    )
    session.add(reservation)
    session.flush()
    for item in sorted(data.items, key=lambda i: i.product_id):
        session.add(
            ReservationItem(
                reservation_id=reservation.id, product_id=item.product_id, quantity=item.quantity
            )
        )
        stock_service.reserve(
            session, user, products[item.product_id], item.quantity, reservation.id
        )
    session.flush()
    session.refresh(reservation)
    return get_reservation(session, reservation.id)


STATUS_LABELS = {"FULFILLED": "исполнен", "CANCELLED": "отменён", "EXPIRED": "истёк"}


def _lock_active(session: Session, reservation_id: int) -> Reservation:
    """Блокирует резерв и проверяет, что он ещё активен (повторные вызовы не освободят дважды)."""
    reservation = session.scalar(
        select(Reservation).where(Reservation.id == reservation_id).with_for_update()
    )
    if reservation is None:
        raise NotFound("Резерв не найден", {"reservation_id": str(reservation_id)})
    if reservation.status != "ACTIVE":
        label = STATUS_LABELS.get(reservation.status, reservation.status)
        raise Conflict(
            f"Резерв уже {label}: из конечного статуса выхода нет",
            {"reservation_id": str(reservation_id), "status": reservation.status},
        )
    return reservation


def _items_sorted(reservation: Reservation) -> list[ReservationItem]:
    return sorted(reservation.items, key=lambda item: item.product_id)


def cancel_reservation(session: Session, user: User, reservation_id: int) -> Reservation:
    reservation = _lock_active(session, reservation_id)
    items = _items_sorted(reservation)
    stock_service.lock_products(session, [item.product_id for item in items])
    for item in items:
        stock_service.release(
            session, user, item.product_id, item.quantity, reservation.id, "Отмена резерва"
        )
    reservation.status = "CANCELLED"
    session.flush()
    return get_reservation(session, reservation.id)


def fulfill_reservation(
    session: Session, user: User, reservation_id: int, now: datetime | None = None
) -> Reservation:
    """Отгрузка: для каждой позиции RELEASE и списание по FEFO (причина SALE) ровно на резерв."""
    now = now or datetime.now(UTC)
    reservation = _lock_active(session, reservation_id)
    if reservation.expires_at <= now:
        raise Conflict(
            "Срок действия резерва истёк, исполнить его нельзя",
            {"reservation_id": str(reservation_id)},
        )
    items = _items_sorted(reservation)
    stock_service.lock_products(session, [item.product_id for item in items])
    # Если какая-то позиция не спишется, откатывается вся отгрузка, а не часть
    with session.begin_nested():
        for item in items:
            stock_service.release(
                session, user, item.product_id, item.quantity, reservation.id, "Отгрузка по резерву"
            )
            stock_service.write_off(
                session,
                user,
                WriteOffCreate(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    reason="SALE",
                    comment=f"Отгрузка по заказу {reservation.reference}",
                ),
                reservation_id=reservation.id,
            )
        reservation.status = "FULFILLED"
        session.flush()
    return get_reservation(session, reservation.id)


def expire_due_reservations(session: Session, now: datetime | None = None, limit: int = 200) -> int:
    """Переводит просроченные ACTIVE-резервы в EXPIRED и освобождает их количество.

    Возвращает число обработанных резервов. Безопасно запускать параллельно:
    уже захваченные другим процессом резервы пропускаются.
    """
    now = now or datetime.now(UTC)
    due = session.scalars(
        select(Reservation)
        .where(Reservation.status == "ACTIVE", Reservation.expires_at <= now)
        .order_by(Reservation.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .options(selectinload(Reservation.items))
    ).all()
    for reservation in due:
        items = _items_sorted(reservation)
        stock_service.lock_products(session, [item.product_id for item in items])
        creator = session.get(User, reservation.created_by)
        for item in items:
            stock_service.release(
                session,
                creator,
                item.product_id,
                item.quantity,
                reservation.id,
                "Истёк срок резерва",
            )
        reservation.status = "EXPIRED"
    session.flush()
    return len(due)
