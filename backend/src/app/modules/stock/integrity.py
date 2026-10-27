"""Проверка инвариантов склада (см. DB_SCHEMA.md): остатки не должны расходиться с журналом."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.stock.models import Batch, StockMovement


def find_violations(session: Session) -> list[str]:
    """Возвращает список нарушений; пустой список — всё сходится."""
    violations: list[str] = []

    # 1. Остаток партии = сумма движений по партии
    moved_by_batch = (
        select(StockMovement.batch_id, func.sum(StockMovement.quantity_delta).label("moved"))
        .where(StockMovement.batch_id.is_not(None))
        .group_by(StockMovement.batch_id)
        .subquery()
    )
    rows = session.execute(
        select(Batch.id, Batch.qty_remaining, func.coalesce(moved_by_batch.c.moved, 0)).outerjoin(
            moved_by_batch, moved_by_batch.c.batch_id == Batch.id
        )
    )
    for batch_id, remaining, moved in rows:
        if remaining != moved:
            violations.append(f"партия {batch_id}: остаток {remaining}, по журналу {moved}")

    # 2. Сумма остатков партий товара = сумма движений товара (количество на складе)
    remaining_by_product = (
        select(Batch.product_id, func.sum(Batch.qty_remaining).label("remaining"))
        .group_by(Batch.product_id)
        .subquery()
    )
    moved_by_product = (
        select(
            StockMovement.product_id,
            func.sum(StockMovement.quantity_delta).label("moved"),
            func.sum(StockMovement.reserved_delta).label("reserved"),
        )
        .group_by(StockMovement.product_id)
        .subquery()
    )
    rows = session.execute(
        select(
            moved_by_product.c.product_id,
            func.coalesce(remaining_by_product.c.remaining, 0),
            moved_by_product.c.moved,
            moved_by_product.c.reserved,
        ).outerjoin(
            remaining_by_product, remaining_by_product.c.product_id == moved_by_product.c.product_id
        )
    )
    for product_id, remaining, moved, reserved in rows:
        if remaining != moved:
            violations.append(
                f"товар {product_id}: сумма остатков партий {remaining}, сумма движений {moved}"
            )
        # 3. Резерв не бывает отрицательным
        if reserved < 0:
            violations.append(f"товар {product_id}: отрицательный резерв {reserved}")
    return violations
