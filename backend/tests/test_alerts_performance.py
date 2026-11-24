"""Время ответа отчётов на тысяче товаров (цифры из этого теста записаны в docs/API.md)."""

import time
from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.modules.alerts.queries import today
from app.modules.catalog.models import Product
from app.modules.stock.models import Batch, StockMovement
from tests.factories import make_category
from tests.helpers import auth_header, make_user

PRODUCTS = 1000
# Запас по времени с учётом медленных CI-машин; на ноутбуке ответ занимает 5–25 мс
LIMIT_SECONDS = 2.0


def fill_warehouse(session: Session, user_id: int) -> None:
    """1000 товаров: у каждого партия и приход, у каждого третьего ниже минимума, у части резерв."""
    category = make_category(session)
    products = (
        session.execute(
            insert(Product).returning(Product.id),
            [
                {
                    "sku": f"PERF-{number:04d}",
                    "name": f"Товар {number:04d}",
                    "category_id": category.id,
                    "unit": "pcs",
                    "min_stock": Decimal(20),
                    "target_stock": Decimal(60),
                }
                for number in range(PRODUCTS)
            ],
        )
        .scalars()
        .all()
    )
    current = today()
    quantities = [Decimal(8 if number % 3 == 0 else 50) for number in range(PRODUCTS)]
    batches = (
        session.execute(
            insert(Batch).returning(Batch.id),
            [
                {
                    "product_id": product_id,
                    "batch_no": f"PERF-B-{number}",
                    "qty_received": quantity,
                    "qty_remaining": quantity,
                    "unit_cost": Decimal(10),
                    "received_at": current - timedelta(days=30),
                    "expires_at": current + timedelta(days=number % 40)
                    if number % 2 == 0
                    else None,
                }
                for number, (product_id, quantity) in enumerate(
                    zip(products, quantities, strict=True)
                )
            ],
        )
        .scalars()
        .all()
    )
    session.execute(
        insert(StockMovement),
        [
            {
                "type": "RECEIPT",
                "product_id": product_id,
                "batch_id": batch_id,
                "quantity_delta": quantity,
                "user_id": user_id,
            }
            for product_id, batch_id, quantity in zip(products, batches, quantities, strict=True)
        ],
    )
    session.execute(
        insert(StockMovement),
        [
            {
                "type": "RESERVE",
                "product_id": product_id,
                "reserved_delta": Decimal(5),
                "user_id": user_id,
            }
            for number, product_id in enumerate(products)
            if number % 5 == 0
        ],
    )
    session.flush()


def timed_get(client: TestClient, user, path: str, **params) -> tuple[float, dict]:
    started = time.perf_counter()
    response = client.get(f"/api/v1{path}", params=params, headers=auth_header(user))
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    return elapsed, response.json()


def test_reports_on_a_thousand_products(client: TestClient, session: Session) -> None:
    user = make_user(session)
    fill_warehouse(session, user.id)
    session.execute(Product.__table__.select().limit(1))  # прогрев плана и соединения

    low_time, low = timed_get(client, user, "/alerts/low-stock", size=100)
    stock_time, stock = timed_get(client, user, "/stock", low_only="true", size=100)
    expiring_time, expiring = timed_get(client, user, "/alerts/expiring-batches", size=100)
    print(
        f"\nlow-stock {low_time * 1000:.0f} мс, /stock?low_only {stock_time * 1000:.0f} мс, "
        f"expiring-batches {expiring_time * 1000:.0f} мс"
    )

    # Ниже минимума только товары с 8 штуками (каждый третий): 50 штук с резервом 5 — это 45, норма
    expected_low = len(range(0, PRODUCTS, 3))
    assert low["total"] == stock["total"] == expected_low
    assert len(low["items"]) == 100
    assert low["items"][0]["severity"] == "CRITICAL"
    # Срок годности у каждого второго товара, из них в горизонт 14 дней попадает 15 из 40 дней цикла
    assert expiring["total"] == sum(
        1 for number in range(PRODUCTS) if number % 2 == 0 and number % 40 <= 14
    )
    assert max(low_time, stock_time, expiring_time) < LIMIT_SECONDS


def test_last_page_of_the_report(client: TestClient, session: Session) -> None:
    user = make_user(session)
    fill_warehouse(session, user.id)
    elapsed, body = timed_get(client, user, "/alerts/low-stock", page=4, size=100)
    assert body["total"] == len(range(0, PRODUCTS, 3))
    assert len(body["items"]) == body["total"] - 300
    assert elapsed < LIMIT_SECONDS
