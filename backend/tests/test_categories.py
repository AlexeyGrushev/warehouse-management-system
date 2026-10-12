from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.helpers import auth_header, make_user

URL = "/api/v1/categories"


def create(client: TestClient, headers: dict, name: str, parent_id: int | None = None):
    return client.post(URL, json={"name": name, "parent_id": parent_id}, headers=headers)


def test_create_and_read_category(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    response = create(client, headers, "  Молочные продукты ")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Молочные продукты"
    assert body["parent_id"] is None
    assert body["is_active"] is True
    assert client.get(f"{URL}/{body['id']}", headers=headers).json() == body


def test_viewer_cannot_create(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session, role="viewer"))
    assert create(client, headers, "Нельзя").status_code == 403


def test_anonymous_cannot_list(client: TestClient) -> None:
    assert client.get(URL).status_code == 401


def test_duplicate_root_name_conflicts(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    assert create(client, headers, "Бакалея").status_code == 201
    response = create(client, headers, "Бакалея")
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_same_name_under_different_parents(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    first = create(client, headers, "Еда").json()["id"]
    second = create(client, headers, "Напитки").json()["id"]
    assert create(client, headers, "Прочее", first).status_code == 201
    assert create(client, headers, "Прочее", second).status_code == 201
    assert create(client, headers, "Прочее", second).status_code == 409


def test_unknown_parent_is_404(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    assert create(client, headers, "Сирота", 999999).status_code == 404


def test_empty_name_is_422(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    response = create(client, headers, "   ")
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_tree_view(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    root = create(client, headers, "Корень").json()["id"]
    create(client, headers, "Ветка", root)
    tree = client.get(URL, params={"tree": True}, headers=headers).json()
    node = next(item for item in tree if item["id"] == root)
    assert [child["name"] for child in node["children"]] == ["Ветка"]


def test_category_cannot_become_its_own_ancestor(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    parent = create(client, headers, "Родитель").json()["id"]
    child = create(client, headers, "Ребёнок", parent).json()["id"]
    response = client.patch(f"{URL}/{parent}", json={"parent_id": child}, headers=headers)
    assert response.status_code == 409
    response = client.patch(f"{URL}/{parent}", json={"parent_id": parent}, headers=headers)
    assert response.status_code == 409


def test_rename_category(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = create(client, headers, "Старое").json()["id"]
    response = client.patch(f"{URL}/{category}", json={"name": "Новое"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Новое"


def test_archive_empty_category(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    category = create(client, headers, "Пустая").json()["id"]
    assert client.post(f"{URL}/{category}/archive", headers=headers).status_code == 204
    assert client.get(f"{URL}/{category}", headers=headers).json()["is_active"] is False
    active = client.get(URL, params={"is_active": True}, headers=headers).json()
    assert category not in [item["id"] for item in active]


def test_archive_category_with_active_product_is_rejected(
    client: TestClient, session: Session
) -> None:
    headers = auth_header(make_user(session))
    category = create(client, headers, "С товарами").json()["id"]
    client.post(
        "/api/v1/products",
        json={"sku": "A-1", "name": "Товар", "category_id": category, "unit": "pcs"},
        headers=headers,
    )
    response = client.post(f"{URL}/{category}/archive", headers=headers)
    assert response.status_code == 409


def test_archive_category_with_active_child_is_rejected(
    client: TestClient, session: Session
) -> None:
    headers = auth_header(make_user(session))
    parent = create(client, headers, "Родитель").json()["id"]
    create(client, headers, "Ребёнок", parent)
    assert client.post(f"{URL}/{parent}/archive", headers=headers).status_code == 409


def test_unknown_category_is_404(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    assert client.get(f"{URL}/999999", headers=headers).status_code == 404
