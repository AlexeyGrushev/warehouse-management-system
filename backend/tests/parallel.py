"""Помощники для тестов на параллельность (настоящие коммиты, несколько потоков)."""

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app

THREADS = 8


def run_in_parallel(actions: list[Callable[[], object]]) -> list:
    """Запускает все действия одновременно (по барьеру) и возвращает результаты по порядку."""
    barrier = Barrier(len(actions))

    def worker(action: Callable[[], object]):
        barrier.wait()
        return action()

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return list(pool.map(worker, actions))


@contextmanager
def api_with_commits(factory: sessionmaker[Session]) -> Iterator[Callable[[], TestClient]]:
    """HTTP-клиенты, чьи запросы коммитятся в БД так же, как в обычной работе приложения."""

    def override():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_session] = override
    try:
        yield lambda: TestClient(app)
    finally:
        app.dependency_overrides.clear()


def bearer(user_id: int, role: str = "storekeeper") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, role)}"}
