from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.types import QuantityOut
from app.modules.stock.schemas import PositiveQuantity

Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ReservationItemCreate(BaseModel):
    product_id: int
    quantity: PositiveQuantity


class ReservationCreate(BaseModel):
    reference: Reference
    expires_at: datetime | None = None
    items: Annotated[list[ReservationItemCreate], Field(min_length=1, max_length=200)]

    @field_validator("items")
    @classmethod
    def products_are_unique(cls, items: list[ReservationItemCreate]) -> list[ReservationItemCreate]:
        ids = [item.product_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("товар нельзя указывать в резерве дважды")
        return items


class ReservationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    quantity: QuantityOut


class ReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    status: str
    expires_at: datetime
    created_by: int
    created_at: datetime
    items: list[ReservationItemRead]
