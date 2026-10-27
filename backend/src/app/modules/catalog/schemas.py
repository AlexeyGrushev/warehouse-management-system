from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.core.types import Quantity, QuantityOut

Unit = Literal["pcs", "kg", "l", "m", "box"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Sku = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class CategoryCreate(BaseModel):
    name: Name
    parent_id: int | None = None


class CategoryUpdate(BaseModel):
    name: Name | None = None
    parent_id: int | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    name: str
    is_active: bool


class CategoryNode(CategoryRead):
    children: list["CategoryNode"] = []


def check_stock_levels(unit: str | None, min_stock: Decimal | None, target: Decimal | None) -> None:
    if min_stock is not None and target is not None and target < min_stock:
        raise ValueError("target_stock не может быть меньше min_stock")
    if unit == "pcs":
        for value in (min_stock, target):
            if value is not None and value != value.to_integral_value():
                raise ValueError("для штучных товаров количество должно быть целым")


class ProductCreate(BaseModel):
    sku: Sku
    name: Name
    category_id: int
    unit: Unit
    min_stock: Quantity = Decimal("0")
    target_stock: Quantity | None = None

    @model_validator(mode="after")
    def check_levels(self) -> "ProductCreate":
        check_stock_levels(self.unit, self.min_stock, self.target_stock)
        return self


class ProductUpdate(BaseModel):
    sku: Sku | None = None
    name: Name | None = None
    category_id: int | None = None
    unit: Unit | None = None
    min_stock: Quantity | None = None
    target_stock: Quantity | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category_id: int
    unit: str
    min_stock: QuantityOut
    target_stock: QuantityOut | None
    is_active: bool
