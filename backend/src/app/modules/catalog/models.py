from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class Category(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_categories_parent_id_name"),
        Index(
            "uq_categories_root_name",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NULL"),
        ),
    )

    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())


class Product(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit IN ('pcs', 'kg', 'l', 'm', 'box')", name="unit"),
        CheckConstraint("min_stock >= 0", name="min_stock"),
        CheckConstraint("target_stock IS NULL OR target_stock >= min_stock", name="target_stock"),
    )

    sku: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text, index=True)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id"))
    unit: Mapped[str] = mapped_column(Text)
    min_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), server_default=text("0"))
    target_stock: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
