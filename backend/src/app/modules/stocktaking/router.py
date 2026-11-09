from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageQuery
from app.db.session import get_session
from app.modules.auth.deps import require_role
from app.modules.auth.models import User
from app.modules.stocktaking import service
from app.modules.stocktaking.schemas import (
    CountedQuantity,
    StocktakingCreate,
    StocktakingDetail,
    StocktakingSummary,
)

router = APIRouter(tags=["stocktaking"])

DbSession = Annotated[Session, Depends(get_session)]
Reader = Annotated[User, Depends(require_role("viewer"))]
Writer = Annotated[User, Depends(require_role("storekeeper"))]

SessionStatus = Literal["DRAFT", "IN_PROGRESS", "CLOSED", "CANCELLED"]


@router.post("/stocktakings", response_model=StocktakingDetail, status_code=status.HTTP_201_CREATED)
def create_stocktaking(
    data: StocktakingCreate, session: DbSession, user: Writer
) -> StocktakingDetail:
    inventory = service.create_session(session, user, data.category_id)
    return service.detail(session, inventory)


@router.get("/stocktakings", response_model=Page[StocktakingSummary])
def list_stocktakings(
    session: DbSession,
    _: Reader,
    params: PageQuery,
    status: Annotated[SessionStatus | None, Query()] = None,
) -> Page[StocktakingSummary]:
    items, total = service.list_sessions(session, params, status)
    return Page(items=items, total=total, page=params.page, size=params.size)


@router.get("/stocktakings/{session_id}", response_model=StocktakingDetail)
def read_stocktaking(session_id: int, session: DbSession, _: Reader) -> StocktakingDetail:
    return service.detail(session, service.get_session_or_404(session, session_id))


@router.post("/stocktakings/{session_id}/start", response_model=StocktakingDetail)
def start_stocktaking(session_id: int, session: DbSession, _: Writer) -> StocktakingDetail:
    return service.detail(session, service.start_session(session, session_id))


@router.post("/stocktakings/{session_id}/cancel", response_model=StocktakingDetail)
def cancel_stocktaking(session_id: int, session: DbSession, _: Writer) -> StocktakingDetail:
    return service.detail(session, service.cancel_session(session, session_id))


@router.put("/stocktakings/{session_id}/lines/{product_id}", response_model=StocktakingDetail)
def set_counted_quantity(
    session_id: int, product_id: int, data: CountedQuantity, session: DbSession, _: Writer
) -> StocktakingDetail:
    inventory = service.set_counted(session, session_id, product_id, data.counted_qty)
    return service.detail(session, inventory)


@router.post("/stocktakings/{session_id}/close", response_model=StocktakingDetail)
def close_stocktaking(session_id: int, session: DbSession, user: Writer) -> StocktakingDetail:
    return service.detail(session, service.close_session(session, user, session_id))
