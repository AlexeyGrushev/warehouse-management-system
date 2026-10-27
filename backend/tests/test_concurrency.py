"""Параллельные операции над одним товаром: блокировка строки товара ставит их в очередь."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import NotFound
from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.modules.stock import service
from app.modules.stock.models import Batch, StockMovement
from tests.factories import add_batch, make_product, make_supplier
from tests.helpers import make_user

THREADS = 8


def run_in_parallel(action: Callable[[int], int]) -> list[int]:
    """Запускает action(i) в THREADS потоках одновременно и возвращает их результаты."""
    barrier = Barrier(THREADS)

    def worker(index: int) -> int:
        barrier.wait()
        return action(index)

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        return list(pool.map(worker, range(THREADS)))


def api_action(factory: sessionmaker[Session]):
    def override():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_session] = override
    return lambda: TestClient(app)


def prepare(factory: sessionmaker[Session], quantity: str) -> tuple[int, int, str]:
    with factory() as session:
        user = make_user(session, role="storekeeper")
        product = make_product(session)
        supplier = make_supplier(session)
        add_batch(session, product, user.id, quantity, supplier=supplier)
        session.commit()
        token = create_access_token(user.id, user.role)
        return product.id, supplier.id, token


def test_parallel_write_offs_never_oversell(committed: sessionmaker[Session]) -> None:
    product_id, _, token = prepare(committed, "5")
    new_client = api_action(committed)
    try:

        def action(_: int) -> int:
            response = new_client().post(
                "/api/v1/write-offs",
                json={"product_id": product_id, "quantity": "1", "reason": "SALE"},
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code

        statuses = run_in_parallel(action)
    finally:
        app.dependency_overrides.clear()

    assert sorted(statuses) == [201] * 5 + [409] * (THREADS - 5)
    with committed() as session:
        assert session.scalar(select(Batch.qty_remaining)) == 0
        assert service.get_totals(session, product_id).on_hand == 0
        written_off = session.scalar(
            select(func.count()).select_from(StockMovement).where(StockMovement.type == "WRITE_OFF")
        )
        assert written_off == 5


def test_two_requests_for_last_unit_only_one_wins(committed: sessionmaker[Session]) -> None:
    product_id, _, token = prepare(committed, "1")
    new_client = api_action(committed)
    barrier = Barrier(2)
    try:

        def action(_: int) -> int:
            barrier.wait()
            return (
                new_client()
                .post(
                    "/api/v1/write-offs",
                    json={"product_id": product_id, "quantity": "1", "reason": "SALE"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                .status_code
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(action, range(2)))
    finally:
        app.dependency_overrides.clear()
    assert statuses == [201, 409]


def test_parallel_receipts_with_same_batch_number(committed: sessionmaker[Session]) -> None:
    product_id, supplier_id, token = prepare(committed, "1")
    new_client = api_action(committed)
    try:

        def action(_: int) -> int:
            return (
                new_client()
                .post(
                    "/api/v1/receipts",
                    json={
                        "product_id": product_id,
                        "supplier_id": supplier_id,
                        "batch_no": "SAME",
                        "quantity": "3",
                        "unit_cost": "10",
                        "received_at": date.today().isoformat(),
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                .status_code
            )

        statuses = run_in_parallel(action)
    finally:
        app.dependency_overrides.clear()

    assert sorted(statuses) == [201] + [409] * (THREADS - 1)
    with committed() as session:
        assert (
            service.get_totals(session, product_id).on_hand == 4
        )  # 1 из prepare + одна партия на 3


def test_lock_products_in_opposite_order_does_not_deadlock(
    committed: sessionmaker[Session],
) -> None:
    with committed() as session:
        first, second = make_product(session), make_product(session)
        session.commit()
        ids = [first.id, second.id]

    barrier = Barrier(2)

    def worker(order: list[int]) -> int:
        with committed() as session:
            barrier.wait()
            locked = service.lock_products(session, order)
            session.commit()
            return len(locked)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [ids, list(reversed(ids))]))
    assert results == [2, 2]


def test_lock_products_reports_missing_product(session: Session) -> None:
    product = make_product(session)
    with pytest.raises(NotFound):
        service.lock_products(session, [product.id, 999999])
