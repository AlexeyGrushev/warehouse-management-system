from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.modules.auth.deps import require_role
from app.modules.auth.models import User
from app.modules.stock import service
from app.modules.stock.schemas import StockLevel

router = APIRouter(tags=["stock"])

DbSession = Annotated[Session, Depends(get_session)]
Reader = Annotated[User, Depends(require_role("viewer"))]


@router.get("/products/{product_id}/stock", response_model=StockLevel)
def read_product_stock(product_id: int, session: DbSession, _: Reader) -> StockLevel:
    return service.get_stock(session, product_id)
