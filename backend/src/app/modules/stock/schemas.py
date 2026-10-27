from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.types import MoneyOut, QuantityOut

BatchNo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class StockLevel(BaseModel):
    """Остатки товара, посчитанные из журнала движений."""

    product_id: int
    on_hand: QuantityOut
    reserved: QuantityOut
    available: QuantityOut
    min_stock: QuantityOut | None = None


class StockTotals(BaseModel):
    on_hand: Decimal
    reserved: Decimal

    @property
    def available(self) -> Decimal:
        return self.on_hand - self.reserved


class ReceiptCreate(BaseModel):
    product_id: int
    supplier_id: int
    batch_no: BatchNo
    quantity: PositiveQuantity
    unit_cost: Money
    received_at: date
    expires_at: date | None = None

    @model_validator(mode="after")
    def check_dates(self) -> "ReceiptCreate":
        if self.expires_at is not None and self.expires_at < self.received_at:
            raise ValueError("срок годности не может быть раньше даты прихода")
        return self


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    supplier_id: int | None
    batch_no: str
    qty_received: QuantityOut
    qty_remaining: QuantityOut
    unit_cost: MoneyOut
    received_at: date
    expires_at: date | None
