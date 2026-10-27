from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.stock import service
from app.modules.stock.integrity import find_violations
from app.modules.stock.models import StockMovement
from app.modules.stock.schemas import ReceiptCreate, WriteOffCreate
from app.seed import run
from tests.factories import add_batch, make_product, make_supplier
from tests.helpers import auth_header, make_user


def test_empty_database_has_no_violations(session: Session) -> None:
    assert find_violations(session) == []


def test_seed_keeps_stock_consistent(session: Session) -> None:
    run(session)
    assert find_violations(session) == []


def test_scenario_of_receipts_and_write_offs_keeps_stock_consistent(session: Session) -> None:
    user = make_user(session)
    supplier = make_supplier(session)
    product = make_product(session, unit="kg")
    for number, quantity in enumerate(("10", "5", "7.5"), start=1):
        service.receive(
            session,
            user,
            ReceiptCreate(
                product_id=product.id,
                supplier_id=supplier.id,
                batch_no=f"B-{number}",
                quantity=Decimal(quantity),
                unit_cost=Decimal("3"),
                received_at=date.today(),
                expires_at=date.today() + timedelta(days=number),
            ),
        )
    for quantity, reason in (("4", "SALE"), ("6", "DAMAGE"), ("2", "OTHER")):
        service.write_off(
            session,
            user,
            WriteOffCreate(product_id=product.id, quantity=Decimal(quantity), reason=reason),
        )
    assert find_violations(session) == []
    assert service.get_totals(session, product.id).on_hand == Decimal("10.5")


def test_api_operations_keep_stock_consistent(client: TestClient, session: Session) -> None:
    user = make_user(session)
    headers = auth_header(user)
    product, supplier = make_product(session), make_supplier(session)
    client.post(
        "/api/v1/receipts",
        json={
            "product_id": product.id,
            "supplier_id": supplier.id,
            "batch_no": "A",
            "quantity": "20",
            "unit_cost": "1",
            "received_at": date.today().isoformat(),
        },
        headers=headers,
    )
    for _ in range(3):
        client.post(
            "/api/v1/write-offs",
            json={"product_id": product.id, "quantity": "6", "reason": "SALE"},
            headers=headers,
        )  # третий вернёт 409 и ничего не изменит
    assert find_violations(session) == []


def test_checker_detects_batch_that_drifted_from_journal(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    batch = add_batch(session, product, user.id, "10")
    batch.qty_remaining = Decimal("9")  # остаток «поправили руками» мимо журнала
    session.flush()
    violations = find_violations(session)
    assert any(f"партия {batch.id}" in text for text in violations)
    assert any(f"товар {product.id}" in text for text in violations)


def test_checker_detects_movement_without_batch_update(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    batch = add_batch(session, product, user.id, "10")
    session.add(
        StockMovement(
            type="WRITE_OFF",
            product_id=product.id,
            batch_id=batch.id,
            quantity_delta=Decimal("-3"),
            reason="OTHER",
            user_id=user.id,
        )
    )
    session.flush()
    assert find_violations(session)


def test_checker_detects_negative_reserve(session: Session) -> None:
    user = make_user(session)
    product = make_product(session)
    session.add(
        StockMovement(
            type="RELEASE",
            product_id=product.id,
            reserved_delta=Decimal("-1"),
            user_id=user.id,
        )
    )
    session.flush()
    assert any("отрицательный резерв" in text for text in find_violations(session))
