from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int


class PageParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> None:
        self.page = page
        self.size = size


PageQuery = Annotated[PageParams, Depends()]


def paginate(session: Session, query: Select, params: PageParams) -> tuple[list, int]:
    """Возвращает (строки страницы, общее число строк запроса)."""
    total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = session.scalars(query.limit(params.size).offset((params.page - 1) * params.size)).all()
    return list(rows), total or 0
