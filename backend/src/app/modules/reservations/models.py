from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, IdMixin

RESERVATION_STATUSES = ("ACTIVE", "FULFILLED", "CANCELLED", "EXPIRED")


class Reservation(IdMixin, CreatedAtMixin, Base):
    """Резерв товара под заказ. Статусы: ACTIVE → FULFILLED | CANCELLED | EXPIRED."""

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'FULFILLED', 'CANCELLED', 'EXPIRED')", name="status"),
        Index("ix_reservations_status_expires_at", "status", "expires_at"),
    )

    reference: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="ACTIVE")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))

    items: Mapped[list["ReservationItem"]] = relationship(
        back_populates="reservation", order_by="ReservationItem.product_id"
    )


class ReservationItem(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "reservation_items"
    __table_args__ = (
        UniqueConstraint(
            "reservation_id", "product_id", name="uq_reservation_items_reservation_id_product_id"
        ),
        CheckConstraint("quantity > 0", name="quantity"),
    )

    reservation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reservations.id"))
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))

    reservation: Mapped[Reservation] = relationship(back_populates="items")
