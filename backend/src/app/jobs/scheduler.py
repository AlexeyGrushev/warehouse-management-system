"""Фоновая задача внутри процесса backend: периодически освобождает истёкшие резервы.

Выбор: простой asyncio-цикл в lifespan приложения вместо отдельного планировщика или cron.
Задача выполняется в пуле потоков, ошибка одного прохода не останавливает цикл, а при
нескольких процессах backend повторная обработка исключена (FOR UPDATE SKIP LOCKED).
"""

import asyncio
import logging
from collections.abc import Callable

from starlette.concurrency import run_in_threadpool

from app.jobs.expire_reservations import run_once

logger = logging.getLogger("uvicorn.error")


async def expiry_loop(
    interval: float,
    stop: asyncio.Event,
    run: Callable[[], int] | None = None,
) -> None:
    """Каждые `interval` секунд вызывает run(), пока не выставлен `stop`."""
    run = run or run_once
    logger.info("Освобождение истёкших резервов: проверка каждые %s с", interval)
    while not stop.is_set():
        try:
            released = await run_in_threadpool(run)
            if released:
                logger.info("Освобождено истёкших резервов: %s", released)
        except Exception:
            logger.exception(
                "Не удалось освободить истёкшие резервы, повторим на следующем проходе"
            )
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue
