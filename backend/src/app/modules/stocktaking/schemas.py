from datetime import datetime

from pydantic import BaseModel

from app.core.types import QuantityOut


class StocktakingCreate(BaseModel):
    category_id: int | None = None  # None — все активные товары


class LineRead(BaseModel):
    product_id: int
    sku: str
    name: str
    unit: str
    expected_qty: QuantityOut | None
    counted_qty: QuantityOut | None
    diff: QuantityOut | None  # насчитали минус ожидали; пока не введено — None


class StocktakingSummary(BaseModel):
    id: int
    status: str
    created_by: int
    created_at: datetime
    started_at: datetime | None
    closed_at: datetime | None
    lines_total: int
    lines_counted: int


class StocktakingDetail(StocktakingSummary):
    lines: list[LineRead]
