import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.jobs import scheduler
from app.main import create_app
from app.modules.reservations import service as reservations
from app.modules.reservations.models import Reservation
from app.modules.stock import service as stock
from tests.test_concurrency_reservations import make_reservation, setup_products


async def run_loop_for(seconds: float, interval: float, run) -> None:
    stop = asyncio.Event()
    task = asyncio.create_task(scheduler.expiry_loop(interval, stop, run))
    await asyncio.sleep(seconds)
    stop.set()
    await asyncio.wait_for(task, timeout=2)


def test_loop_runs_repeatedly_and_stops() -> None:
    calls: list[float] = []

    def run() -> int:
        calls.append(time.monotonic())
        return 0

    asyncio.run(run_loop_for(0.35, 0.05, run))
    assert 4 <= len(calls) <= 9


def test_loop_survives_errors() -> None:
    calls = {"n": 0}

    def run() -> int:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RuntimeError("БД временно недоступна")
        return 1

    asyncio.run(run_loop_for(0.4, 0.05, run))
    assert calls["n"] >= 4  # после двух ошибок цикл продолжил работать


def test_loop_stops_promptly_even_with_long_interval() -> None:
    started = time.monotonic()
    asyncio.run(run_loop_for(0.1, 3600, lambda: 0))
    assert time.monotonic() - started < 1.5


def test_loop_expires_real_reservations(committed: sessionmaker[Session]) -> None:
    user_id, (product_id,) = setup_products(committed, ["10"])
    past = datetime.now(UTC) - timedelta(days=1)
    overdue = make_reservation(committed, user_id, product_id, 4, now=past)
    fresh = make_reservation(committed, user_id, product_id, 2)

    def run() -> int:
        with committed() as session:
            count = reservations.expire_due_reservations(session)
            session.commit()
            return count

    asyncio.run(run_loop_for(0.3, 0.05, run))
    with committed() as session:
        assert session.get(Reservation, overdue).status == "EXPIRED"
        assert session.get(Reservation, fresh).status == "ACTIVE"
        assert stock.get_totals(session, product_id).reserved == 2


def test_app_does_not_start_scheduler_when_disabled() -> None:
    assert get_settings().reservation_expiry_interval_seconds == 0
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_app_lifespan_starts_and_stops_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_run() -> int:
        calls["n"] += 1
        return 0

    monkeypatch.setenv("RESERVATION_EXPIRY_INTERVAL_SECONDS", "0.05")
    monkeypatch.setattr(scheduler, "run_once", fake_run)
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200
            time.sleep(0.3)
        after_stop = calls["n"]
        assert after_stop >= 3
        time.sleep(0.2)
        assert calls["n"] == after_stop  # после остановки приложения цикл больше не работает
    finally:
        get_settings.cache_clear()
