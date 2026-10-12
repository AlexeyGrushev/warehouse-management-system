from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageQuery
from app.db.session import get_session
from app.modules.auth.deps import require_role
from app.modules.auth.models import User
from app.modules.catalog import service
from app.modules.catalog.models import Category, Product
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryNode,
    CategoryRead,
    CategoryUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)

router = APIRouter(tags=["catalog"])

DbSession = Annotated[Session, Depends(get_session)]
Reader = Annotated[User, Depends(require_role("viewer"))]
Writer = Annotated[User, Depends(require_role("storekeeper"))]


@router.get("/categories", response_model=list[CategoryRead] | list[CategoryNode])
def list_categories(
    session: DbSession,
    _: Reader,
    tree: bool = False,
    is_active: bool | None = None,
) -> list[Category] | list[CategoryNode]:
    categories = service.list_categories(session, is_active)
    return service.build_tree(categories) if tree else categories


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, session: DbSession, _: Writer) -> Category:
    return service.create_category(session, data)


@router.get("/categories/{category_id}", response_model=CategoryRead)
def read_category(category_id: int, session: DbSession, _: Reader) -> Category:
    return service.get_category(session, category_id)


@router.patch("/categories/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int, data: CategoryUpdate, session: DbSession, _: Writer
) -> Category:
    return service.update_category(session, category_id, data)


@router.post("/categories/{category_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_category(category_id: int, session: DbSession, _: Writer) -> Response:
    service.archive_category(session, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/products", response_model=Page[ProductRead])
def list_products(
    session: DbSession,
    _: Reader,
    params: PageQuery,
    q: Annotated[str | None, Query(description="Поиск по названию и артикулу")] = None,
    category_id: int | None = None,
    is_active: bool | None = None,
) -> Page[ProductRead]:
    items, total = service.list_products(session, params, q, category_id, is_active)
    return Page(items=items, total=total, page=params.page, size=params.size)


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, session: DbSession, _: Writer) -> Product:
    return service.create_product(session, data)


@router.get("/products/{product_id}", response_model=ProductRead)
def read_product(product_id: int, session: DbSession, _: Reader) -> Product:
    return service.get_product(session, product_id)


@router.patch("/products/{product_id}", response_model=ProductRead)
def update_product(product_id: int, data: ProductUpdate, session: DbSession, _: Writer) -> Product:
    return service.update_product(session, product_id, data)


@router.post("/products/{product_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_product(product_id: int, session: DbSession, _: Writer) -> Response:
    service.archive_product(session, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
