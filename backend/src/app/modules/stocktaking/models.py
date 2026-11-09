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


class InventorySession(IdMixin, CreatedAtMixin, Base):
    """Сессия инвентаризации: DRAFT → IN_PROGRESS → CLOSED (или CANCELLED до закрытия)."""

    __tablename__ = "inventory_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'IN_PROGRESS', 'CLOSED', 'CANCELLED')", name="status"),
        Index("ix_inventory_sessions_status", "status"),
    )

    status: Mapped[str] = mapped_column(Text, server_default="DRAFT")
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lines: Mapped[list["InventoryLine"]] = relationship(
        back_populates="session", order_by="InventoryLine.product_id"
    )


class InventoryLine(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "inventory_lines"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "product_id", name="uq_inventory_lines_session_id_product_id"
        ),
        CheckConstraint("counted_qty IS NULL OR counted_qty >= 0", name="counted_qty"),
        CheckConstraint("expected_qty IS NULL OR expected_qty >= 0", name="expected_qty"),
        Index("ix_inventory_lines_product_id", "product_id"),
    )

    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("inventory_sessions.id"))
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"))
    # «Ожидали» фиксируется при старте сессии, «насчитали» вводится потом
    expected_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    counted_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))

    session: Mapped[InventorySession] = relationship(back_populates="lines")
