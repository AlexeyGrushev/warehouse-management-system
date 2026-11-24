from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageQuery
from app.db.session import get_session
from app.modules.alerts import queries
from app.modules.alerts.rules import Severity
from app.modules.alerts.schemas import LowStockItem
from app.modules.auth.deps import require_role
from app.modules.auth.models import User

router = APIRouter(prefix="/alerts", tags=["alerts"])

DbSession = Annotated[Session, Depends(get_session, scope="function")]
Reader = Annotated[User, Depends(require_role("viewer"))]


@router.get("/low-stock", response_model=Page[LowStockItem])
def list_low_stock(
    session: DbSession,
    _: Reader,
    params: PageQuery,
    category_id: Annotated[
        int | None, Query(description="Категория вместе с подкатегориями")
    ] = None,
    severity: Annotated[Severity | None, Query(description="Только указанная критичность")] = None,
) -> Page[LowStockItem]:
    """Товары ниже минимального остатка, самые критичные сверху, с рекомендацией закупки."""
    items, total = queries.list_low_stock(session, params, category_id, severity)
    return Page(items=items, total=total, page=params.page, size=params.size)
