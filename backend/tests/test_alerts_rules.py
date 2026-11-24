from decimal import Decimal

import pytest

from app.modules.alerts.rules import assess, effective_target, severity_of


def d(value: str) -> Decimal:
    return Decimal(value)


def test_no_shortage_when_available_reaches_minimum() -> None:
    assert assess(d("40"), d("40"), None, "pcs") is None
    assert assess(d("41"), d("40"), None, "pcs") is None


def test_shortage_just_below_minimum() -> None:
    result = assess(d("39.999"), d("40"), d("100"), "kg")
    assert result is not None
    assert result.deficit == d("0.001")


@pytest.mark.parametrize(
    ("available", "expected"),
    [
        ("-5", "CRITICAL"),
        ("0", "CRITICAL"),
        ("9.999", "CRITICAL"),  # меньше четверти от 40
        ("10", "WARNING"),  # ровно четверть — ещё не критично
        ("39.999", "WARNING"),
    ],
)
def test_severity_boundaries(available: str, expected: str) -> None:
    assert severity_of(d(available), d("40")) == expected


def test_zero_minimum_is_critical_only_below_zero() -> None:
    assert assess(d("0"), d("0"), None, "pcs") is None
    result = assess(d("-3"), d("0"), None, "pcs")
    assert result is not None
    assert result.severity == "CRITICAL"
    assert result.recommended_order_qty == d("3")


def test_missing_target_defaults_to_double_minimum() -> None:
    assert effective_target(d("20"), None) == d("40")
    result = assess(d("5"), d("20"), None, "pcs")
    assert result is not None
    assert result.target_stock == d("40")
    assert result.recommended_order_qty == d("35")
    assert result.deficit == d("15")


def test_explicit_target_wins_over_default() -> None:
    result = assess(d("5"), d("20"), d("120"), "pcs")
    assert result is not None
    assert result.recommended_order_qty == d("115")


@pytest.mark.parametrize(("unit", "expected"), [("pcs", "8"), ("box", "8"), ("kg", "7.500")])
def test_recommended_quantity_rounding_by_unit(unit: str, expected: str) -> None:
    result = assess(d("3"), d("5"), d("10.5"), unit)
    assert result is not None
    assert result.recommended_order_qty == d(expected)


def test_negative_available_increases_recommendation() -> None:
    result = assess(d("-4"), d("10"), d("30"), "pcs")
    assert result is not None
    assert result.available == d("-4")
    assert result.deficit == d("14")
    assert result.recommended_order_qty == d("34")
