from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageQuery
from app.db.session import get_session
from app.modules.auth.deps import require_role
from app.modules.auth.models import User
from app.modules.stock import queries, service
from app.modules.stock.models import Batch
from app.modules.stock.schemas import (
    BatchDetail,
    BatchRead,
    MovementRead,
    ReceiptCreate,
    StockLevel,
    StockRow,
    WriteOffCreate,
    WriteOffResult,
)

router = APIRouter(tags=["stock"])

DbSession = Annotated[Session, Depends(get_session)]
Reader = Annotated[User, Depends(require_role("viewer"))]
Writer = Annotated[User, Depends(require_role("storekeeper"))]


@router.get("/products/{product_id}/stock", response_model=StockLevel)
def read_product_stock(product_id: int, session: DbSession, _: Reader) -> StockLevel:
    return service.get_stock(session, product_id)


@router.post("/receipts", response_model=BatchRead, status_code=status.HTTP_201_CREATED)
def create_receipt(data: ReceiptCreate, session: DbSession, user: Writer) -> Batch:
    return service.receive(session, user, data)


@router.post("/write-offs", response_model=WriteOffResult, status_code=status.HTTP_201_CREATED)
def create_write_off(data: WriteOffCreate, session: DbSession, user: Writer) -> WriteOffResult:
    return service.write_off(session, user, data)


@router.get("/batches", response_model=Page[BatchDetail])
def list_batches(
    session: DbSession,
    _: Reader,
    params: PageQuery,
    product_id: int | None = None,
    supplier_id: int | None = None,
    only_in_stock: bool = False,
) -> Page[BatchDetail]:
    items, total = queries.list_batches(session, params, product_id, supplier_id, only_in_stock)
    return Page(items=items, total=total, page=params.page, size=params.size)


MovementType = Literal["RECEIPT", "WRITE_OFF", "RESERVE", "RELEASE", "ADJUSTMENT"]


@router.get("/movements", response_model=Page[MovementRead])
def list_movements(
    session: DbSession,
    _: Reader,
    params: PageQuery,
    product_id: int | None = None,
    type: Annotated[MovementType | None, Query()] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user_id: int | None = None,
) -> Page[MovementRead]:
    items, total = queries.list_movements(
        session, params, product_id, type, date_from, date_to, user_id
    )
    return Page(items=items, total=total, page=params.page, size=params.size)


@router.get("/stock", response_model=Page[StockRow])
def list_stock(
    session: DbSession,
    _: Reader,
    params: PageQuery,
    q: Annotated[str | None, Query(description="Поиск по названию и артикулу")] = None,
    category_id: int | None = None,
    low_only: Annotated[bool, Query(description="Только товары ниже минимального остатка")] = False,
    is_active: bool | None = True,
) -> Page[StockRow]:
    items, total = queries.list_stock(session, params, q, category_id, low_only, is_active)
    return Page(items=items, total=total, page=params.page, size=params.size)
