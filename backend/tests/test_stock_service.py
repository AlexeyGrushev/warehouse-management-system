from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.modules.stock import service
from tests.factories import add_batch, add_reserve, make_product
from tests.helpers import auth_header, make_user


def test_product_without_movements_has_zero_stock(session: Session) -> None:
    product = make_product(session, min_stock="5")
    stock = service.get_stock(session, product.id)
    assert stock.on_hand == Decimal("0")
    assert stock.reserved == Decimal("0")
    assert stock.available == Decimal("0")
    assert stock.min_stock == Decimal("5")


def test_on_hand_is_sum_of_receipts(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    add_batch(session, product, user.id, "5.5")
    assert service.get_totals(session, product.id).on_hand == Decimal("15.5")


def test_available_is_on_hand_minus_reserved(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    add_reserve(session, product, user.id, "4")
    totals = service.get_totals(session, product.id)
    assert (totals.on_hand, totals.reserved, totals.available) == (
        Decimal("10"),
        Decimal("4"),
        Decimal("6"),
    )


def test_stock_is_counted_per_product(session: Session) -> None:
    user = make_user(session)
    first, second = make_product(session), make_product(session)
    add_batch(session, first, user.id, "10")
    add_batch(session, second, user.id, "3")
    assert service.get_totals(session, first.id).on_hand == Decimal("10")
    assert service.get_totals(session, second.id).on_hand == Decimal("3")


def test_unknown_product_raises(session: Session) -> None:
    with pytest.raises(NotFound):
        service.get_stock(session, 999999)
    with pytest.raises(NotFound):
        service.lock_product(session, 999999)


def test_stock_endpoint(client: TestClient, session: Session) -> None:
    user = make_user(session, role="viewer")
    product = make_product(session, min_stock="2")
    add_batch(session, product, user.id, "8")
    add_reserve(session, product, user.id, "3")
    response = client.get(f"/api/v1/products/{product.id}/stock", headers=auth_header(user))
    assert response.status_code == 200
    assert response.json() == {
        "product_id": product.id,
        "on_hand": "8.000",
        "reserved": "3.000",
        "available": "5.000",
        "min_stock": "2.000",
    }


def test_stock_endpoint_errors(client: TestClient, session: Session) -> None:
    user = make_user(session, role="viewer")
    assert client.get("/api/v1/products/1/stock").status_code == 401
    response = client.get("/api/v1/products/999999/stock", headers=auth_header(user))
    assert response.status_code == 404
