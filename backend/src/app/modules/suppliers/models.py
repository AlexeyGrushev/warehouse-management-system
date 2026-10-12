from sqlalchemy import Boolean, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class Supplier(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(Text, unique=True)
    contact: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
