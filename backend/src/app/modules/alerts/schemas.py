from pydantic import BaseModel

from app.core.types import QuantityOut
from app.modules.alerts.rules import Severity


class LowStockItem(BaseModel):
    """Товар ниже минимального остатка с рекомендацией закупки."""

    product_id: int
    sku: str
    name: str
    unit: str
    category_id: int
    category_name: str
    on_hand: QuantityOut
    reserved: QuantityOut
    available: QuantityOut
    min_stock: QuantityOut
    target_stock: QuantityOut
    deficit: QuantityOut
    recommended_order_qty: QuantityOut
    severity: Severity
