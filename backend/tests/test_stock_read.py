from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import add_batch, add_reserve, make_product, make_supplier
from tests.helpers import auth_header, make_user


def get(client: TestClient, path: str, user, **params):
    return client.get(f"/api/v1{path}", params=params, headers=auth_header(user))


def test_batches_list_with_names_and_filters(client: TestClient, session: Session) -> None:
    user = make_user(session, role="viewer")
    first, second = make_product(session, sku="A-1"), make_product(session, sku="B-1")
    milk, bread = make_supplier(session, "Молочный дом"), make_supplier(session, "Хлебозавод")
    add_batch(session, first, user.id, "10", supplier=milk, received_at=date(2026, 10, 1))
    add_batch(session, second, user.id, "4", supplier=bread, received_at=date(2026, 10, 5))

    everything = get(client, "/batches", user).json()
    assert everything["total"] == 2
    newest = everything["items"][0]
    assert newest["product_sku"] == "B-1"
    assert newest["supplier_name"] == "Хлебозавод"
    assert newest["qty_remaining"] == "4.000"
    assert newest["unit_cost"] == "10.00"

    by_product = get(client, "/batches", user, product_id=first.id).json()
    assert [item["product_sku"] for item in by_product["items"]] == ["A-1"]
    by_supplier = get(client, "/batches", user, supplier_id=bread.id).json()
    assert by_supplier["total"] == 1


def test_batches_only_in_stock(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "5", batch_no="DRAINED")  # старше — спишется первой (FEFO)
    add_batch(session, product, user.id, "5", batch_no="FULL")
    client.post(
        "/api/v1/write-offs",
        json={"product_id": product.id, "quantity": "5", "reason": "SALE"},
        headers=auth_header(user),
    )
    in_stock = get(client, "/batches", user, only_in_stock=True).json()
    assert [item["batch_no"] for item in in_stock["items"]] == ["FULL"]
    assert get(client, "/batches", user).json()["total"] == 2


def test_batches_pagination(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    for number in range(5):
        add_batch(session, product, user.id, "1", batch_no=f"N-{number}")
    page = get(client, "/batches", user, size=2, page=3).json()
    assert (page["total"], page["page"], len(page["items"])) == (5, 3, 1)
    assert get(client, "/batches", user, size=101).status_code == 422


def test_movements_journal(client: TestClient, session: Session) -> None:
    user = make_user(session, role="storekeeper")
    product = make_product(session, sku="MLK-9")
    add_batch(session, product, user.id, "10", batch_no="B-7")
    client.post(
        "/api/v1/write-offs",
        json={"product_id": product.id, "quantity": "3", "reason": "DAMAGE", "comment": "бой"},
        headers=auth_header(user),
    )
    journal = get(client, "/movements", user).json()
    assert journal["total"] == 2
    latest, first = journal["items"]  # новые сверху
    assert latest["type"] == "WRITE_OFF"
    assert latest["quantity_delta"] == "-3.000"
    assert latest["reason"] == "DAMAGE"
    assert latest["comment"] == "бой"
    assert latest["product_sku"] == "MLK-9"
    assert latest["batch_no"] == "B-7"
    assert latest["user_email"] == user.email
    assert first["type"] == "RECEIPT"
    assert first["reserved_delta"] == "0.000"


def test_movements_filters(client: TestClient, session: Session) -> None:
    keeper = make_user(session)
    other = make_user(session, role="admin")
    first, second = make_product(session), make_product(session)
    add_batch(session, first, keeper.id, "10")
    add_batch(session, second, other.id, "10")
    add_reserve(session, second, other.id, "2")

    assert get(client, "/movements", keeper, product_id=first.id).json()["total"] == 1
    assert get(client, "/movements", keeper, type="RESERVE").json()["total"] == 1
    assert get(client, "/movements", keeper, user_id=other.id).json()["total"] == 2
    assert get(client, "/movements", keeper, type="NOPE").status_code == 422


def test_movements_date_range_is_inclusive(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "1")
    today = date.today()
    # дата в UTC-контейнере и в Москве может отличаться, поэтому берём запас в день
    inside = get(
        client,
        "/movements",
        user,
        date_from=today - timedelta(days=1),
        date_to=today + timedelta(days=1),
    )
    assert inside.json()["total"] == 1
    assert get(client, "/movements", user, date_to=today - timedelta(days=2)).json()["total"] == 0
    assert get(client, "/movements", user, date_from=today + timedelta(days=2)).json()["total"] == 0
    assert get(client, "/movements", user, date_from="не дата").status_code == 422


def test_stock_list(client: TestClient, session: Session) -> None:
    user = make_user(session)
    enough = make_product(session, min_stock="5", sku="OK-1")
    low = make_product(session, min_stock="5", sku="LOW-1")
    empty = make_product(session, min_stock="0", sku="ZERO-1")
    add_batch(session, enough, user.id, "20")
    add_batch(session, low, user.id, "6")
    add_reserve(session, low, user.id, "3")  # доступно 3 < 5

    rows = {row["sku"]: row for row in get(client, "/stock", user).json()["items"]}
    assert rows["OK-1"]["on_hand"] == "20.000"
    assert rows["OK-1"]["is_low"] is False
    assert (rows["LOW-1"]["on_hand"], rows["LOW-1"]["reserved"], rows["LOW-1"]["available"]) == (
        "6.000",
        "3.000",
        "3.000",
    )
    assert rows["LOW-1"]["is_low"] is True
    assert rows["ZERO-1"]["on_hand"] == "0.000"
    assert rows["ZERO-1"]["is_low"] is False
    assert empty.id == rows["ZERO-1"]["product_id"]


def test_stock_filters(client: TestClient, session: Session) -> None:
    user = make_user(session)
    low = make_product(session, min_stock="5", sku="LOW-2")
    fine = make_product(session, min_stock="1", sku="FINE-2")
    add_batch(session, low, user.id, "2")
    add_batch(session, fine, user.id, "9")

    only_low = get(client, "/stock", user, low_only=True).json()
    assert [row["sku"] for row in only_low["items"]] == ["LOW-2"]
    assert get(client, "/stock", user, q="fine").json()["total"] == 1
    assert get(client, "/stock", user, category_id=low.category_id).json()["total"] == 1

    fine.is_active = False
    session.flush()
    assert get(client, "/stock", user).json()["total"] == 1
    assert get(client, "/stock", user, is_active=False).json()["total"] == 1


def test_stock_matches_product_endpoint(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session, min_stock="2")
    add_batch(session, product, user.id, "8")
    add_reserve(session, product, user.id, "3")
    row = get(client, "/stock", user).json()["items"][0]
    single = get(client, f"/products/{product.id}/stock", user).json()
    for key in ("on_hand", "reserved", "available", "min_stock"):
        assert row[key] == single[key]


def test_read_endpoints_require_auth(client: TestClient) -> None:
    for path in ("/batches", "/movements", "/stock"):
        assert client.get(f"/api/v1{path}").status_code == 401
