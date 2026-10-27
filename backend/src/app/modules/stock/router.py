from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.modules.auth.deps import require_role
from app.modules.auth.models import User
from app.modules.stock import service
from app.modules.stock.models import Batch
from app.modules.stock.schemas import (
    BatchRead,
    ReceiptCreate,
    StockLevel,
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
