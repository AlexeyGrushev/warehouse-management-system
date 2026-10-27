"""trigram indexes for product search

Revision ID: 7ff635784453
Revises: d900afbf3813
Create Date: 2026-10-27 08:51:50.559814

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7ff635784453"
down_revision: str | Sequence[str] | None = "d900afbf3813"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Поиск по подстроке (ILIKE '%...%') по названию и артикулу без полного перебора таблицы
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX ix_products_name_trgm ON products USING gin (name gin_trgm_ops)")
    op.execute("CREATE INDEX ix_products_sku_trgm ON products USING gin (sku gin_trgm_ops)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX ix_products_sku_trgm")
    op.execute("DROP INDEX ix_products_name_trgm")
    # расширение pg_trgm оставляем: им могут пользоваться другие объекты
