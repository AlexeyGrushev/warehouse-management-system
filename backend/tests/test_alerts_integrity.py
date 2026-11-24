"""Отчёт нехватки должен сходиться со страницей остатков на любых данных и операциях."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.stock.integrity import find_violations
from app.modules.suppliers.models import Supplier
from app.seed import run as run_seed
from tests.factories import add_batch, make_product
from tests.helpers import auth_header, make_user

API = "/api/v1"


def fetch_all(client: TestClient, user, path: str, **params) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        response = client.get(
            f"{API}{path}",
            params={**params, "page": page, "size": 100},
            headers=auth_header(user),
        )
        assert response.status_code == 200
        body = response.json()
        items.extend(body["items"])
        if len(items) >= body["total"]:
            return items
        page += 1


def assert_report_matches_stock_page(client: TestClient, user) -> dict[int, dict]:
    """Те же товары и те же числа, что на странице остатков с фильтром «ниже минимума»."""
    report = {item["product_id"]: item for item in fetch_all(client, user, "/alerts/low-stock")}
    stock = {row["product_id"]: row for row in fetch_all(client, user, "/stock", low_only="true")}
    assert report.keys() == stock.keys()
    for product_id, row in stock.items():
        for field in ("on_hand", "reserved", "available", "min_stock"):
            assert report[product_id][field] == row[field]
    for severity in ("CRITICAL", "WARNING"):
        filtered = fetch_all(client, user, "/alerts/low-stock", severity=severity)
        assert {item["product_id"] for item in filtered} == {
            product_id for product_id, item in report.items() if item["severity"] == severity
        }
    return report


def post(client: TestClient, user, path: str, **body):
    response = client.post(f"{API}{path}", json=body, headers=auth_header(user))
    assert response.status_code < 300, response.text
    return response.json()


def test_report_matches_stock_page_on_seed_data(client: TestClient, session: Session) -> None:
    run_seed(session)
    user = make_user(session, role="viewer", email="reader@test.example")
    report = assert_report_matches_stock_page(client, user)
    assert report, "в seed должны быть товары ниже минимума для показа"
    assert len(report) < 30
    assert find_violations(session) == []


def test_report_follows_receipts_write_offs_reservations_and_stocktaking(
    client: TestClient, session: Session
) -> None:
    run_seed(session)
    user = make_user(session, email="keeper@test.example")
    supplier = session.scalar(select(Supplier))
    report = assert_report_matches_stock_page(client, user)

    # Приход закрывает нехватку
    low = next(iter(report.values()))
    post(
        client,
        user,
        "/receipts",
        product_id=low["product_id"],
        supplier_id=supplier.id,
        batch_no="INTEGRITY-1",
        quantity=low["recommended_order_qty"],
        unit_cost="10",
        received_at=date.today().isoformat(),
    )
    after_receipt = assert_report_matches_stock_page(client, user)
    assert low["product_id"] not in after_receipt

    # Списание создаёт нехватку у товара, которого раньше хватало
    stock_rows = fetch_all(client, user, "/stock")
    # Берём канцелярию: у неё нет срока годности, и списание не зависит от просрочки партий
    healthy = next(
        row
        for row in stock_rows
        if row["sku"].startswith("STN-") and not row["is_low"] and Decimal(row["available"]) > 0
    )
    post(
        client,
        user,
        "/write-offs",
        product_id=healthy["product_id"],
        quantity=healthy["available"],
        reason="SALE",
    )
    after_write_off = assert_report_matches_stock_page(client, user)
    assert after_write_off[healthy["product_id"]]["severity"] == "CRITICAL"

    # Резерв уменьшает доступное, отмена возвращает
    other = next(
        row
        for row in fetch_all(client, user, "/stock")
        if not row["is_low"] and row["product_id"] != healthy["product_id"]
    )
    reserved_qty = Decimal(other["available"]) - Decimal(other["min_stock"]) + 1
    reservation = post(
        client,
        user,
        "/reservations",
        reference="ЗАКАЗ-INTEGRITY",
        items=[{"product_id": other["product_id"], "quantity": str(reserved_qty)}],
    )
    assert other["product_id"] in assert_report_matches_stock_page(client, user)
    post(client, user, f"/reservations/{reservation['id']}/cancel")
    assert other["product_id"] not in assert_report_matches_stock_page(client, user)

    # Инвентаризация: недостача превращает товар в нехватку
    shorted = next(
        row
        for row in fetch_all(client, user, "/stock")
        if not row["is_low"]
        and row["product_id"] not in (healthy["product_id"], other["product_id"])
    )
    inventory = post(client, user, "/stocktakings")
    post(client, user, f"/stocktakings/{inventory['id']}/start")
    for line in client.get(
        f"{API}/stocktakings/{inventory['id']}", headers=auth_header(user)
    ).json()["lines"]:
        counted = "0" if line["product_id"] == shorted["product_id"] else line["expected_qty"]
        response = client.put(
            f"{API}/stocktakings/{inventory['id']}/lines/{line['product_id']}",
            json={"counted_qty": counted},
            headers=auth_header(user),
        )
        assert response.status_code == 200
    post(client, user, f"/stocktakings/{inventory['id']}/close")
    final = assert_report_matches_stock_page(client, user)
    assert final[shorted["product_id"]]["severity"] == "CRITICAL"
    assert find_violations(session) == []


def test_reserve_above_counted_stock_gives_negative_available(
    client: TestClient, session: Session
) -> None:
    """Инвентаризация нашла меньше, чем в резервах: резервы остаются, товар виден в отчёте."""
    user = make_user(session)
    product = make_product(session, min_stock="5", target_stock="20")
    add_batch(session, product, user.id, "10")
    post(
        client,
        user,
        "/reservations",
        reference="ЗАКАЗ-1",
        items=[{"product_id": product.id, "quantity": "8"}],
    )
    inventory = post(client, user, "/stocktakings")
    post(client, user, f"/stocktakings/{inventory['id']}/start")
    response = client.put(
        f"{API}/stocktakings/{inventory['id']}/lines/{product.id}",
        json={"counted_qty": "2"},
        headers=auth_header(user),
    )
    assert response.status_code == 200
    post(client, user, f"/stocktakings/{inventory['id']}/close")

    item = assert_report_matches_stock_page(client, user)[product.id]
    assert (item["on_hand"], item["reserved"], item["available"]) == ("2.000", "8.000", "-6.000")
    assert item["severity"] == "CRITICAL"
    assert item["deficit"] == "11.000"
    assert item["recommended_order_qty"] == "26.000"
