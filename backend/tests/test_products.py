from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.helpers import auth_header, make_user

URL = "/api/v1/products"


def make_category(client: TestClient, headers: dict, name: str = "Категория") -> int:
    return client.post("/api/v1/categories", json={"name": name}, headers=headers).json()["id"]


def payload(category_id: int, **overrides) -> dict:
    return {
        "sku": "MILK-1",
        "name": "Молоко 1 л",
        "category_id": category_id,
        "unit": "pcs",
        "min_stock": "5",
        **overrides,
    }


def test_create_product(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    response = client.post(URL, json=payload(category), headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "MILK-1"
    assert body["min_stock"] == "5.000"
    assert body["target_stock"] is None
    assert body["is_active"] is True


def test_duplicate_sku_conflicts(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    assert client.post(URL, json=payload(category), headers=headers).status_code == 201
    response = client.post(URL, json=payload(category, name="Другое"), headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_unknown_category_is_404(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    assert client.post(URL, json=payload(999999), headers=headers).status_code == 404


def test_archived_category_cannot_receive_products(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    client.post(f"/api/v1/categories/{category}/archive", headers=headers)
    assert client.post(URL, json=payload(category), headers=headers).status_code == 409


def test_validation_errors(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    bad_payloads = [
        payload(category, unit="tons"),
        payload(category, min_stock="-1"),
        payload(category, sku="  "),
        payload(category, min_stock="10", target_stock="5"),
        payload(category, min_stock="2.5"),  # штучный товар: только целые
    ]
    for body in bad_payloads:
        response = client.post(URL, json=body, headers=headers)
        assert response.status_code == 422, body
        assert response.json()["code"] == "VALIDATION_ERROR"


def test_fractional_stock_allowed_for_weight_units(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    response = client.post(URL, json=payload(category, unit="kg", min_stock="2.5"), headers=headers)
    assert response.status_code == 201
    assert response.json()["min_stock"] == "2.500"


def test_viewer_can_read_but_not_write(client: TestClient, session: Session) -> None:
    keeper = auth_header(make_user(session))
    viewer = auth_header(make_user(session, role="viewer"))
    category = make_category(client, keeper)
    product = client.post(URL, json=payload(category), headers=keeper).json()
    assert client.get(f"{URL}/{product['id']}", headers=viewer).status_code == 200
    assert client.post(URL, json=payload(category, sku="X"), headers=viewer).status_code == 403
    assert (
        client.patch(f"{URL}/{product['id']}", json={"name": "Y"}, headers=viewer).status_code
        == 403
    )


def test_update_product(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    product = client.post(URL, json=payload(category), headers=headers).json()
    response = client.patch(
        f"{URL}/{product['id']}",
        json={"name": "Молоко 2 л", "target_stock": "20"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Молоко 2 л"
    assert body["target_stock"] == "20.000"
    assert body["sku"] == "MILK-1"


def test_update_cannot_break_stock_levels(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    product = client.post(URL, json=payload(category, target_stock="10"), headers=headers).json()
    response = client.patch(f"{URL}/{product['id']}", json={"min_stock": "50"}, headers=headers)
    assert response.status_code == 422
    response = client.patch(f"{URL}/{product['id']}", json={"unit": None}, headers=headers)
    assert response.status_code == 422


def test_update_sku_to_existing_conflicts(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    client.post(URL, json=payload(category, sku="A"), headers=headers)
    second = client.post(URL, json=payload(category, sku="B"), headers=headers).json()
    response = client.patch(f"{URL}/{second['id']}", json={"sku": "A"}, headers=headers)
    assert response.status_code == 409
    response = client.patch(f"{URL}/{second['id']}", json={"sku": "B"}, headers=headers)
    assert response.status_code == 200


def test_unknown_product_is_404(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    assert client.get(f"{URL}/999999", headers=headers).status_code == 404
    assert client.patch(f"{URL}/999999", json={"name": "X"}, headers=headers).status_code == 404


def test_archive_product(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    product = client.post(URL, json=payload(category), headers=headers).json()
    assert client.post(f"{URL}/{product['id']}/archive", headers=headers).status_code == 204
    assert client.get(f"{URL}/{product['id']}", headers=headers).json()["is_active"] is False
    active = client.get(URL, params={"is_active": True}, headers=headers).json()
    assert product["id"] not in [item["id"] for item in active["items"]]


def test_list_pagination_and_search(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = make_category(client, headers)
    other = make_category(client, headers, "Другая")
    for number in range(1, 6):
        client.post(
            URL,
            json=payload(category, sku=f"MILK-{number}", name=f"Молоко {number}"),
            headers=headers,
        )
    client.post(URL, json=payload(other, sku="BREAD-1", name="Хлеб"), headers=headers)

    first = client.get(URL, params={"size": 2, "page": 1}, headers=headers).json()
    assert first["total"] == 6
    assert (first["page"], first["size"], len(first["items"])) == (1, 2, 2)
    last = client.get(URL, params={"size": 4, "page": 2}, headers=headers).json()
    assert len(last["items"]) == 2

    by_name = client.get(URL, params={"q": "молоко"}, headers=headers).json()
    assert by_name["total"] == 5
    by_sku = client.get(URL, params={"q": "bread"}, headers=headers).json()
    assert [item["sku"] for item in by_sku["items"]] == ["BREAD-1"]
    by_category = client.get(URL, params={"category_id": other}, headers=headers).json()
    assert by_category["total"] == 1


def test_page_size_is_limited(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    assert client.get(URL, params={"size": 101}, headers=headers).status_code == 422
    assert client.get(URL, params={"page": 0}, headers=headers).status_code == 422
