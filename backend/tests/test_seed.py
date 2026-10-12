from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.catalog.models import Category, Product
from app.modules.stock.models import Batch, StockMovement
from app.modules.suppliers.models import Supplier
from app.seed import run


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_seed_creates_expected_data(session: Session) -> None:
    run(session)
    assert count(session, Product) == 30
    assert count(session, Supplier) == 5
    assert count(session, Category) == 7
    assert count(session, User) == 3
    assert count(session, Batch) >= 30


def test_seed_is_idempotent(session: Session) -> None:
    run(session)
    totals = [count(session, model) for model in (Product, Supplier, Batch, StockMovement, User)]
    run(session)
    assert totals == [
        count(session, model) for model in (Product, Supplier, Batch, StockMovement, User)
    ]


def test_batch_remaining_equals_sum_of_movements(session: Session) -> None:
    """Инвариант: остаток партии равен сумме движений по этой партии."""
    run(session)
    rows = session.execute(
        select(Batch.id, Batch.qty_remaining, func.sum(StockMovement.quantity_delta))
        .join(StockMovement, StockMovement.batch_id == Batch.id)
        .group_by(Batch.id)
    ).all()
    assert rows
    assert all(remaining == moved for _, remaining, moved in rows)


def test_every_batch_has_a_receipt(session: Session) -> None:
    run(session)
    without_receipt = session.scalar(
        select(func.count())
        .select_from(Batch)
        .where(
            ~select(StockMovement.id)
            .where(StockMovement.batch_id == Batch.id, StockMovement.type == "RECEIPT")
            .exists()
        )
    )
    assert without_receipt == 0
