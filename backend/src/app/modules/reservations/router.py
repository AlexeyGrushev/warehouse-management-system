from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageQuery
from app.db.session import get_session
from app.modules.auth.deps import require_role
from app.modules.auth.models import User
from app.modules.reservations import service
from app.modules.reservations.models import Reservation
from app.modules.reservations.schemas import ReservationCreate, ReservationRead

router = APIRouter(tags=["reservations"])

DbSession = Annotated[Session, Depends(get_session)]
Reader = Annotated[User, Depends(require_role("viewer"))]
Writer = Annotated[User, Depends(require_role("storekeeper"))]

ReservationStatus = Literal["ACTIVE", "FULFILLED", "CANCELLED", "EXPIRED"]


@router.post("/reservations", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
def create_reservation(data: ReservationCreate, session: DbSession, user: Writer) -> Reservation:
    return service.create_reservation(session, user, data)


@router.get("/reservations", response_model=Page[ReservationRead])
def list_reservations(
    session: DbSession,
    _: Reader,
    params: PageQuery,
    status: Annotated[ReservationStatus | None, Query()] = None,
    reference: Annotated[str | None, Query(description="Поиск по номеру заказа")] = None,
) -> Page[ReservationRead]:
    items, total = service.list_reservations(session, params, status, reference)
    return Page(items=items, total=total, page=params.page, size=params.size)


@router.get("/reservations/{reservation_id}", response_model=ReservationRead)
def read_reservation(reservation_id: int, session: DbSession, _: Reader) -> Reservation:
    return service.get_reservation(session, reservation_id)


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationRead)
def cancel_reservation(reservation_id: int, session: DbSession, user: Writer) -> Reservation:
    return service.cancel_reservation(session, user, reservation_id)


@router.post("/reservations/{reservation_id}/fulfill", response_model=ReservationRead)
def fulfill_reservation(reservation_id: int, session: DbSession, user: Writer) -> Reservation:
    return service.fulfill_reservation(session, user, reservation_id)
