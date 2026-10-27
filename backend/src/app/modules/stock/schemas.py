from decimal import Decimal

from pydantic import BaseModel

from app.core.types import QuantityOut


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
