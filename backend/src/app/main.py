from fastapi import FastAPI

from app.core.errors import register_error_handlers
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.stock.router import router as stock_router
from app.modules.suppliers.router import router as suppliers_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(title="Warehouse Management System", version="0.1.0")
    register_error_handlers(app)

    @app.get("/health", tags=["service"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(catalog_router, prefix=API_PREFIX)
    app.include_router(suppliers_router, prefix=API_PREFIX)
    app.include_router(stock_router, prefix=API_PREFIX)
    return app


app = create_app()
