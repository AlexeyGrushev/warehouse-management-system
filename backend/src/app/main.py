import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.jobs.scheduler import expiry_loop
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.reservations.router import router as reservations_router
from app.modules.stock.router import router as stock_router
from app.modules.stocktaking.router import router as stocktaking_router
from app.modules.suppliers.router import router as suppliers_router

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    interval = get_settings().reservation_expiry_interval_seconds
    stop = asyncio.Event()
    task = asyncio.create_task(expiry_loop(interval, stop)) if interval > 0 else None
    try:
        yield
    finally:
        if task is not None:
            stop.set()
            await task


def create_app() -> FastAPI:
    app = FastAPI(title="Warehouse Management System", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)

    @app.get("/health", tags=["service"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(catalog_router, prefix=API_PREFIX)
    app.include_router(suppliers_router, prefix=API_PREFIX)
    app.include_router(stock_router, prefix=API_PREFIX)
    app.include_router(reservations_router, prefix=API_PREFIX)
    app.include_router(stocktaking_router, prefix=API_PREFIX)
    return app


app = create_app()
