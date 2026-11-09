"""Импорт всех моделей, чтобы их видел Alembic."""

from app.modules.auth.models import User
from app.modules.catalog.models import Category, Product
from app.modules.reservations.models import Reservation, ReservationItem
from app.modules.stock.models import Batch, StockMovement
from app.modules.suppliers.models import Supplier

__all__ = [
    "Batch",
    "Category",
    "Product",
    "Reservation",
    "ReservationItem",
    "StockMovement",
    "Supplier",
    "User",
]
