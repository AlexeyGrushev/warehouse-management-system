from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.catalog.models import Category, Product


def test_trigram_extension_and_indexes_exist(session: Session) -> None:
    extension = session.scalar(text("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'"))
    assert extension == "pg_trgm"
    names = set(
        session.scalars(text("SELECT indexname FROM pg_indexes WHERE tablename = 'products'")).all()
    )
    assert {"ix_products_name_trgm", "ix_products_sku_trgm"} <= names


def test_substring_search_uses_trigram_index(session: Session) -> None:
    category = Category(name="Для поиска")
    session.add(category)
    session.flush()
    session.add_all(
        Product(
            sku=f"SKU-{number:05d}",
            name=f"Товар номер {number}",
            category_id=category.id,
            unit="pcs",
            min_stock=Decimal(0),
        )
        for number in range(3000)
    )
    session.flush()
    session.execute(text("ANALYZE products"))
    # Отключаем полный перебор, чтобы проверить, что планировщик умеет использовать индекс
    session.execute(text("SET LOCAL enable_seqscan = off"))
    for column in ("name", "sku"):
        plan = "\n".join(
            session.scalars(
                text(f"EXPLAIN SELECT id FROM products WHERE {column} ILIKE '%2999%'")
            ).all()
        )
        assert f"ix_products_{column}_trgm" in plan, plan
