"""Правила выявления нехватки: чистые функции без обращения к БД.

Что считаем и где проходят границы, описано в docs/DOMAIN.md, раздел 5.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Literal

Severity = Literal["CRITICAL", "WARNING"]

# Товар критичен, если доступно меньше этой доли от минимального остатка
CRITICAL_SHARE = Decimal("0.25")
# Единицы, которые закупаются только целыми
WHOLE_UNITS = frozenset({"pcs", "box"})
_THOUSANDTH = Decimal("0.001")


@dataclass(frozen=True)
class Shortage:
    available: Decimal
    min_stock: Decimal
    target_stock: Decimal
    deficit: Decimal
    recommended_order_qty: Decimal
    severity: Severity


def effective_target(min_stock: Decimal, target_stock: Decimal | None) -> Decimal:
    """Целевой остаток; если не задан, берём двойной минимальный."""
    return target_stock if target_stock is not None else min_stock * 2


def is_low(available: Decimal, min_stock: Decimal) -> bool:
    return available < min_stock


def severity_of(available: Decimal, min_stock: Decimal) -> Severity:
    if available <= 0 or available < min_stock * CRITICAL_SHARE:
        return "CRITICAL"
    return "WARNING"


def recommended_order_qty(available: Decimal, target: Decimal, unit: str) -> Decimal:
    """Сколько докупить до целевого остатка; штуки и коробки округляются вверх до целого."""
    needed = max(target - available, Decimal(0))
    step = Decimal(1) if unit in WHOLE_UNITS else _THOUSANDTH
    return needed.quantize(step, rounding=ROUND_CEILING)


def assess(
    available: Decimal, min_stock: Decimal, target_stock: Decimal | None, unit: str
) -> Shortage | None:
    """Нехватка по товару или None, если доступного хватает."""
    if not is_low(available, min_stock):
        return None
    target = effective_target(min_stock, target_stock)
    return Shortage(
        available=available,
        min_stock=min_stock,
        target_stock=target,
        deficit=min_stock - available,
        recommended_order_qty=recommended_order_qty(available, target, unit),
        severity=severity_of(available, min_stock),
    )
