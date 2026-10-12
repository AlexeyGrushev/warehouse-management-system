from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageQuery
from app.db.session import get_session
from app.modules.auth.deps import require_role
from app.modules.auth.models import User
from app.modules.suppliers import service
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.schemas import SupplierCreate, SupplierRead, SupplierUpdate

router = APIRouter(tags=["suppliers"])

DbSession = Annotated[Session, Depends(get_session)]
Reader = Annotated[User, Depends(require_role("viewer"))]
Writer = Annotated[User, Depends(require_role("storekeeper"))]


@router.get("/suppliers", response_model=Page[SupplierRead])
def list_suppliers(
    session: DbSession,
    _: Reader,
    params: PageQuery,
    q: Annotated[str | None, Query(description="Поиск по названию и контакту")] = None,
    is_active: bool | None = None,
) -> Page[SupplierRead]:
    items, total = service.list_suppliers(session, params, q, is_active)
    return Page(items=items, total=total, page=params.page, size=params.size)


@router.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(data: SupplierCreate, session: DbSession, _: Writer) -> Supplier:
    return service.create_supplier(session, data)


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead)
def read_supplier(supplier_id: int, session: DbSession, _: Reader) -> Supplier:
    return service.get_supplier(session, supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: int, data: SupplierUpdate, session: DbSession, _: Writer
) -> Supplier:
    return service.update_supplier(session, supplier_id, data)


@router.post("/suppliers/{supplier_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_supplier(supplier_id: int, session: DbSession, _: Writer) -> Response:
    service.archive_supplier(session, supplier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
