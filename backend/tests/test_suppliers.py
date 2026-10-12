from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.catalog.models import Category, Product
from app.modules.stock.models import Batch
from tests.helpers import auth_header, make_user

URL = "/api/v1/suppliers"


def create(client: TestClient, headers: dict, name: str = "ООО Ромашка", **extra):
    return client.post(URL, json={"name": name, **extra}, headers=headers)


def test_create_and_read_supplier(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    response = create(client, headers, "  ООО Ромашка ", contact="+7 495 000-00-00")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "ООО Ромашка"
    assert body["contact"] == "+7 495 000-00-00"
    assert body["is_active"] is True
    assert client.get(f"{URL}/{body['id']}", headers=headers).json() == body


def test_duplicate_name_conflicts(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    assert create(client, headers).status_code == 201
    response = create(client, headers)
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_empty_name_is_422(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    response = create(client, headers, "   ")
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_viewer_can_read_but_not_write(client: TestClient, session: Session) -> None:
    keeper = auth_header(make_user(session))
    viewer = auth_header(make_user(session, role="viewer"))
    supplier = create(client, keeper).json()
    assert client.get(URL, headers=viewer).status_code == 200
    assert client.get(f"{URL}/{supplier['id']}", headers=viewer).status_code == 200
    assert create(client, viewer, "Другой").status_code == 403
    assert (
        client.patch(f"{URL}/{supplier['id']}", json={"name": "X"}, headers=viewer).status_code
        == 403
    )
    assert client.post(f"{URL}/{supplier['id']}/archive", headers=viewer).status_code == 403


def test_anonymous_is_rejected(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={"name": "X"}).status_code == 401


def test_update_supplier(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    supplier = create(client, headers, contact="old@example.com").json()
    response = client.patch(
        f"{URL}/{supplier['id']}",
        json={"name": "ООО Лютик", "contact": "new@example.com"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "ООО Лютик"
    assert response.json()["contact"] == "new@example.com"


def test_update_name_to_existing_conflicts(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    create(client, headers, "Первый")
    second = create(client, headers, "Второй").json()
    assert (
        client.patch(f"{URL}/{second['id']}", json={"name": "Первый"}, headers=headers).status_code
        == 409
    )
    # то же самое имя у самого себя — не конфликт
    assert (
        client.patch(f"{URL}/{second['id']}", json={"name": "Второй"}, headers=headers).status_code
        == 200
    )


def test_name_cannot_be_nulled(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    supplier = create(client, headers).json()
    response = client.patch(f"{URL}/{supplier['id']}", json={"name": None}, headers=headers)
    assert response.status_code == 422


def test_unknown_supplier_is_404(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    assert client.get(f"{URL}/999999", headers=headers).status_code == 404
    assert client.patch(f"{URL}/999999", json={"name": "X"}, headers=headers).status_code == 404
    assert client.post(f"{URL}/999999/archive", headers=headers).status_code == 404


def test_archive_supplier(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    supplier = create(client, headers).json()
    assert client.post(f"{URL}/{supplier['id']}/archive", headers=headers).status_code == 204
    assert client.get(f"{URL}/{supplier['id']}", headers=headers).json()["is_active"] is False
    active = client.get(URL, params={"is_active": True}, headers=headers).json()
    assert supplier["id"] not in [item["id"] for item in active["items"]]


def add_batch(session: Session, supplier_id: int, remaining: str) -> None:
    category = Category(name="Для партии")
    session.add(category)
    session.flush()
    product = Product(sku="P-1", name="Товар", category_id=category.id, unit="pcs")
    session.add(product)
    session.flush()
    session.add(
        Batch(
            product_id=product.id,
            supplier_id=supplier_id,
            batch_no="B-1",
            qty_received=Decimal("10"),
            qty_remaining=Decimal(remaining),
            unit_cost=Decimal("1.00"),
            received_at=date(2026, 10, 1),
        )
    )
    session.flush()


def test_archive_blocked_when_batches_have_stock(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    supplier = create(client, headers).json()
    add_batch(session, supplier["id"], remaining="3")
    response = client.post(f"{URL}/{supplier['id']}/archive", headers=headers)
    assert response.status_code == 409
    assert client.get(f"{URL}/{supplier['id']}", headers=headers).json()["is_active"] is True


def test_archive_allowed_when_batches_are_empty(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    supplier = create(client, headers).json()
    add_batch(session, supplier["id"], remaining="0")
    assert client.post(f"{URL}/{supplier['id']}/archive", headers=headers).status_code == 204


def test_list_search_and_pagination(client: TestClient, session: Session) -> None:
    headers = auth_header(make_user(session))
    for number in range(1, 6):
        create(client, headers, f"Поставщик {number}", contact=f"mail{number}@example.com")
    create(client, headers, "Молочный завод", contact="milk@example.com")

    page = client.get(URL, params={"size": 4, "page": 1}, headers=headers).json()
    assert page["total"] == 6
    assert len(page["items"]) == 4
    assert len(client.get(URL, params={"size": 4, "page": 2}, headers=headers).json()["items"]) == 2

    by_name = client.get(URL, params={"q": "молочный"}, headers=headers).json()
    assert [item["name"] for item in by_name["items"]] == ["Молочный завод"]
    by_contact = client.get(URL, params={"q": "mail3"}, headers=headers).json()
    assert [item["name"] for item in by_contact["items"]] == ["Поставщик 3"]
    assert client.get(URL, params={"size": 101}, headers=headers).status_code == 422
