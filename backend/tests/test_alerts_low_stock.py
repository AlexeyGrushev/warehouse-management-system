from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import add_batch, add_reserve, make_category, make_product
from tests.helpers import auth_header, make_user

URL = "/api/v1/alerts/low-stock"


def get(client: TestClient, user, **params):
    return client.get(URL, params=params, headers=auth_header(user))


def skus(response) -> list[str]:
    return [item["sku"] for item in response.json()["items"]]


def test_empty_when_everything_is_in_norm(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session, min_stock="10")
    add_batch(session, product, user.id, "10")  # ровно на минимуме — ещё норма
    response = get(client, user)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "size": 20}


def test_item_has_numbers_and_recommendation(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session, min_stock="40", target_stock="120", sku="MLK-1", name="Молоко")
    add_batch(session, product, user.id, "30")
    item = get(client, user).json()["items"][0]
    assert item["product_id"] == product.id
    assert (item["sku"], item["name"], item["unit"]) == ("MLK-1", "Молоко", "pcs")
    assert item["on_hand"] == "30.000"
    assert item["available"] == "30.000"
    assert item["min_stock"] == "40.000"
    assert item["target_stock"] == "120.000"
    assert item["deficit"] == "10.000"
    assert item["recommended_order_qty"] == "90.000"
    assert item["severity"] == "WARNING"


def test_missing_target_uses_double_minimum(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session, min_stock="20")
    add_batch(session, product, user.id, "5")
    item = get(client, user).json()["items"][0]
    assert item["target_stock"] == "40.000"
    assert item["recommended_order_qty"] == "35.000"


def test_reservation_lowers_available_and_adds_product(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    product = make_product(session, min_stock="40")
    add_batch(session, product, user.id, "50")
    assert get(client, user).json()["total"] == 0
    add_reserve(session, product, user.id, "20")
    item = get(client, user).json()["items"][0]
    assert (item["on_hand"], item["reserved"], item["available"]) == ("50.000", "20.000", "30.000")


def test_product_without_stock_is_critical(client: TestClient, session: Session) -> None:
    user = make_user(session)
    make_product(session, min_stock="5", target_stock="20")
    item = get(client, user).json()["items"][0]
    assert item["available"] == "0.000"
    assert item["severity"] == "CRITICAL"
    assert item["recommended_order_qty"] == "20.000"


def test_sorted_from_most_critical(client: TestClient, session: Session) -> None:
    user = make_user(session)
    mild = make_product(session, min_stock="40", sku="MILD")  # доступно 30 — WARNING
    almost = make_product(session, min_stock="40", sku="ALMOST")  # доступно 20 — WARNING
    empty = make_product(session, min_stock="40", sku="EMPTY")  # доступно 0 — CRITICAL
    tiny = make_product(session, min_stock="40", sku="TINY")  # доступно 5 — CRITICAL
    add_batch(session, mild, user.id, "30")
    add_batch(session, almost, user.id, "20")
    add_batch(session, tiny, user.id, "5")
    assert empty.id
    response = get(client, user)
    assert skus(response) == ["EMPTY", "TINY", "ALMOST", "MILD"]
    assert [item["severity"] for item in response.json()["items"]] == [
        "CRITICAL",
        "CRITICAL",
        "WARNING",
        "WARNING",
    ]


def test_filter_by_severity(client: TestClient, session: Session) -> None:
    user = make_user(session)
    critical = make_product(session, min_stock="40", sku="CRIT")
    warning = make_product(session, min_stock="40", sku="WARN")
    add_batch(session, critical, user.id, "5")
    add_batch(session, warning, user.id, "30")
    assert skus(get(client, user, severity="CRITICAL")) == ["CRIT"]
    assert skus(get(client, user, severity="WARNING")) == ["WARN"]
    assert get(client, user, severity="HIGH").status_code == 422


def test_filter_by_category_includes_subcategories(client: TestClient, session: Session) -> None:
    user = make_user(session)
    food = make_category(session, "Еда")
    dairy = make_category(session, "Молочные", parent=food)
    chemistry = make_category(session, "Химия")
    make_product(session, min_stock="5", sku="DAIRY", category=dairy)
    make_product(session, min_stock="5", sku="FOOD", category=food)
    make_product(session, min_stock="5", sku="CHEM", category=chemistry)
    assert sorted(skus(get(client, user, category_id=food.id))) == ["DAIRY", "FOOD"]
    assert skus(get(client, user, category_id=chemistry.id)) == ["CHEM"]
    assert get(client, user, category_id=999999).status_code == 404


def test_archived_products_are_not_reported(client: TestClient, session: Session) -> None:
    user = make_user(session)
    make_product(session, min_stock="5", sku="ARCHIVED", is_active=False)
    make_product(session, min_stock="5", sku="ACTIVE")
    assert skus(get(client, user)) == ["ACTIVE"]


def test_pagination(client: TestClient, session: Session) -> None:
    user = make_user(session)
    for number in range(5):
        make_product(session, min_stock="5", sku=f"P-{number}", name=f"Товар {number}")
    page = get(client, user, size=2, page=3).json()
    assert (page["total"], page["page"], len(page["items"])) == (5, 3, 1)
    assert get(client, user, size=101).status_code == 422


def test_every_role_can_read_but_anonymous_cannot(client: TestClient, session: Session) -> None:
    make_product(session, min_stock="5")
    for role in ("viewer", "storekeeper", "admin"):
        user = make_user(session, role=role)
        assert get(client, user).status_code == 200
    assert client.get(URL).status_code == 401
