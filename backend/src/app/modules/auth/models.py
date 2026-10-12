from sqlalchemy import Boolean, CheckConstraint, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class User(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'storekeeper', 'viewer')", name="role"),)

    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
