from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class Batch(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("product_id", "batch_no", name="uq_batches_product_id_batch_no"),
        CheckConstraint("qty_received > 0", name="qty_received"),
        CheckConstraint(
            "qty_remaining >= 0 AND qty_remaining <= qty_received", name="qty_remaining"
        ),
        CheckConstraint("unit_cost >= 0", name="unit_cost"),
        CheckConstraint("expires_at IS NULL OR expires_at >= received_at", name="expires_at"),
        Index(
            "ix_batches_fefo",
            "product_id",
            text("expires_at NULLS LAST"),
            "received_at",
            "id",
        ),
        Index("ix_batches_expires_at", "expires_at"),
    )

    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"))
    supplier_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("suppliers.id"))
    batch_no: Mapped[str] = mapped_column(Text)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    qty_remaining: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    received_at: Mapped[date] = mapped_column(Date)
    expires_at: Mapped[date | None] = mapped_column(Date)


class StockMovement(IdMixin, CreatedAtMixin, Base):
    """Журнал движений. Только добавление записей, без UPDATE и DELETE."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "type IN ('RECEIPT', 'WRITE_OFF', 'RESERVE', 'RELEASE', 'ADJUSTMENT')", name="type"
        ),
        CheckConstraint(
            "reason IS NULL OR reason IN ('SALE', 'DAMAGE', 'EXPIRED', 'OTHER')", name="reason"
        ),
        CheckConstraint(
            "(type = 'RECEIPT' AND quantity_delta > 0"
            " AND reserved_delta = 0 AND batch_id IS NOT NULL) OR "
            "(type = 'WRITE_OFF' AND quantity_delta < 0"
            " AND reserved_delta = 0 AND batch_id IS NOT NULL) OR "
            "(type = 'RESERVE' AND quantity_delta = 0"
            " AND reserved_delta > 0 AND batch_id IS NULL) OR "
            "(type = 'RELEASE' AND quantity_delta = 0"
            " AND reserved_delta < 0 AND batch_id IS NULL) OR "
            "(type = 'ADJUSTMENT' AND quantity_delta <> 0"
            " AND reserved_delta = 0 AND batch_id IS NOT NULL)",
            name="type_matches_deltas",
        ),
        Index("ix_stock_movements_product_created", "product_id", text("created_at DESC")),
        Index("ix_stock_movements_created_at", "created_at"),
        Index("ix_stock_movements_batch_id", "batch_id"),
    )

    type: Mapped[str] = mapped_column(Text)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"))
    batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("batches.id"))
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3), server_default=text("0"))
    reserved_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3), server_default=text("0"))
    reason: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
