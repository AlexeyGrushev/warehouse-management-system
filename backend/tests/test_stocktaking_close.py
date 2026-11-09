from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reservations import service as reservations
from app.modules.reservations.schemas import ReservationCreate, ReservationItemCreate
from app.modules.stock import service as stock
from app.modules.stock.integrity import find_violations
from app.modules.stock.models import Batch, StockMovement
from tests.factories import add_batch, make_product
from tests.helpers import auth_header, make_user

URL = "/api/v1/stocktakings"


def started(client: TestClient, user, **body) -> dict:
    created = client.post(URL, json=body, headers=auth_header(user)).json()
    return client.post(f"{URL}/{created['id']}/start", headers=auth_header(user)).json()


def count(client: TestClient, user, session_id: int, product_id: int, qty: str):
    return client.put(
        f"{URL}/{session_id}/lines/{product_id}",
        json={"counted_qty": qty},
        headers=auth_header(user),
    )


def close(client: TestClient, user, session_id: int):
    return client.post(f"{URL}/{session_id}/close", headers=auth_header(user))


def adjustments(session: Session, session_id: int) -> list[StockMovement]:
    return list(
        session.scalars(
            select(StockMovement)
            .where(StockMovement.inventory_session_id == session_id)
            .order_by(StockMovement.id)
        )
    )


def test_counting_shows_difference(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    inventory = started(client, user)
    body = count(client, user, inventory["id"], product.id, "7").json()
    line = body["lines"][0]
    assert (line["expected_qty"], line["counted_qty"], line["diff"]) == (
        "10.000",
        "7.000",
        "-3.000",
    )
    assert (body["lines_total"], body["lines_counted"]) == (1, 1)
    # исправить введённое можно, пока сессия идёт
    again = count(client, user, inventory["id"], product.id, "10").json()
    assert again["lines"][0]["diff"] == "0.000"


def test_counting_validation_and_errors(client: TestClient, session: Session) -> None:
    user = make_user(session)
    pieces = make_product(session)
    weighed = make_product(session, unit="kg")
    inventory = started(client, user)
    sid = inventory["id"]
    assert count(client, user, sid, pieces.id, "-1").status_code == 422
    assert count(client, user, sid, pieces.id, "1.5").status_code == 422  # штучный товар
    assert count(client, user, sid, weighed.id, "1.5").status_code == 200
    assert count(client, user, sid, pieces.id, "0").status_code == 200  # ноль — допустимо
    assert count(client, user, sid, 999999, "1").status_code == 404
    assert count(client, user, 999999, pieces.id, "1").status_code == 404
    assert (
        client.put(f"{URL}/{sid}/lines/{pieces.id}", json={}, headers=auth_header(user)).status_code
        == 422
    )


def test_counting_only_while_in_progress(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    draft = client.post(URL, json={}, headers=auth_header(user)).json()
    assert count(client, user, draft["id"], product.id, "1").status_code == 409
    client.post(f"{URL}/{draft['id']}/start", headers=auth_header(user))
    client.post(f"{URL}/{draft['id']}/cancel", headers=auth_header(user))
    assert count(client, user, draft["id"], product.id, "1").status_code == 409


def test_close_requires_all_lines_counted(client: TestClient, session: Session) -> None:
    user = make_user(session)
    first, second = make_product(session), make_product(session)
    inventory = started(client, user)
    count(client, user, inventory["id"], first.id, "0")
    response = close(client, user, inventory["id"])
    assert response.status_code == 422
    assert response.json()["meta"] == {"missing": "1", "first_product_id": str(second.id)}
    assert adjustments(session, inventory["id"]) == []
    count(client, user, inventory["id"], second.id, "0")
    assert close(client, user, inventory["id"]).status_code == 200


def test_shortage_is_written_off_by_fefo_including_expired(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    product = make_product(session)
    today = date.today()
    expired = add_batch(session, product, user.id, "3", expires_at=today - timedelta(days=2))
    soon = add_batch(session, product, user.id, "4", expires_at=today + timedelta(days=5))
    later = add_batch(session, product, user.id, "5", expires_at=today + timedelta(days=30))
    inventory = started(client, user)
    count(client, user, inventory["id"], product.id, "5")  # ожидали 12, насчитали 5, недостача 7

    response = close(client, user, inventory["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CLOSED"
    assert body["closed_at"] is not None
    for batch in (expired, soon, later):
        session.refresh(batch)
    assert (expired.qty_remaining, soon.qty_remaining, later.qty_remaining) == (0, 0, 5)
    moves = adjustments(session, inventory["id"])
    assert [(m.type, m.batch_id, int(m.quantity_delta)) for m in moves] == [
        ("ADJUSTMENT", expired.id, -3),
        ("ADJUSTMENT", soon.id, -4),
    ]
    assert stock.get_totals(session, product.id).on_hand == 5
    assert find_violations(session) == []


def test_surplus_creates_correcting_batch_with_last_cost(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10", received_at=date(2026, 10, 1), unit_cost="5.00")
    add_batch(session, product, user.id, "1", received_at=date(2026, 10, 20), unit_cost="7.50")
    inventory = started(client, user)
    count(client, user, inventory["id"], product.id, "15")  # ожидали 11, насчитали 15

    assert close(client, user, inventory["id"]).status_code == 200
    batch = session.scalar(
        select(Batch).where(Batch.product_id == product.id, Batch.batch_no.like("INV-%"))
    )
    assert batch.batch_no == f"INV-{inventory['id']}"
    assert batch.supplier_id is None
    assert (batch.qty_received, batch.qty_remaining, batch.unit_cost) == (4, 4, 7.5)
    assert batch.expires_at is None
    move = adjustments(session, inventory["id"])[0]
    assert (move.type, move.batch_id, int(move.quantity_delta)) == ("ADJUSTMENT", batch.id, 4)
    assert stock.get_totals(session, product.id).on_hand == 15
    assert find_violations(session) == []


def test_surplus_for_product_without_history_has_zero_cost(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    product = make_product(session)
    inventory = started(client, user)
    count(client, user, inventory["id"], product.id, "3")
    assert close(client, user, inventory["id"]).status_code == 200
    batch = session.scalar(select(Batch).where(Batch.product_id == product.id))
    assert (batch.qty_remaining, batch.unit_cost) == (3, 0)


def test_no_difference_means_no_movements(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "6")
    inventory = started(client, user)
    count(client, user, inventory["id"], product.id, "6")
    assert close(client, user, inventory["id"]).status_code == 200
    assert adjustments(session, inventory["id"]) == []


def test_reserves_are_not_touched(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    reservations.create_reservation(
        session,
        user,
        ReservationCreate(
            reference="Р", items=[ReservationItemCreate(product_id=product.id, quantity=6)]
        ),
    )
    inventory = started(client, user)
    count(client, user, inventory["id"], product.id, "4")  # осталось меньше, чем в резерве
    assert close(client, user, inventory["id"]).status_code == 200
    totals = stock.get_totals(session, product.id)
    assert (totals.on_hand, totals.reserved) == (4, 6)
    assert totals.available == -2  # резерв остаётся, товар попадёт в отчёт о нехватке
    assert find_violations(session) == []


def test_closed_session_cannot_be_reopened_or_changed(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    inventory = started(client, user)
    count(client, user, inventory["id"], product.id, "2")
    assert close(client, user, inventory["id"]).status_code == 200
    for response in (
        close(client, user, inventory["id"]),
        client.post(f"{URL}/{inventory['id']}/start", headers=auth_header(user)),
        client.post(f"{URL}/{inventory['id']}/cancel", headers=auth_header(user)),
        count(client, user, inventory["id"], product.id, "5"),
    ):
        assert response.status_code == 409
    assert stock.get_totals(session, product.id).on_hand == 2


def test_movements_allowed_again_after_close(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    add_batch(session, product, user.id, "10")
    inventory = started(client, user)
    write_off = {"product_id": product.id, "quantity": "1", "reason": "SALE"}
    headers = auth_header(user)
    assert client.post("/api/v1/write-offs", json=write_off, headers=headers).status_code == 409
    count(client, user, inventory["id"], product.id, "10")
    close(client, user, inventory["id"])
    assert client.post("/api/v1/write-offs", json=write_off, headers=headers).status_code == 201


def test_close_unknown_session_and_zero_counts(client: TestClient, session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    inventory = started(client, user)
    assert close(client, user, 999999).status_code == 404
    count(client, user, inventory["id"], product.id, "0")
    assert close(client, user, inventory["id"]).status_code == 200


def test_roles(client: TestClient, session: Session) -> None:
    keeper = make_user(session)
    viewer = make_user(session, role="viewer")
    product = make_product(session)
    inventory = started(client, keeper)
    sid = inventory["id"]
    assert count(client, viewer, sid, product.id, "1").status_code == 403
    assert close(client, viewer, sid).status_code == 403
    assert client.post(f"{URL}/{sid}/close").status_code == 401
