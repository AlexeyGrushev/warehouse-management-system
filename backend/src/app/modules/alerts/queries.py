"""Отчёты о нехватке: считаются по запросу из журнала движений."""

from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, paginate_rows
from app.modules.alerts import rules
from app.modules.alerts.schemas import LowStockItem
from app.modules.catalog import service as catalog_service
from app.modules.catalog.models import Category, Product
from app.modules.stock import queries as stock_queries


def list_low_stock(
    session: Session,
    params: PageParams,
    category_id: int | None = None,
    severity: rules.Severity | None = None,
) -> tuple[list[LowStockItem], int]:
    """Активные товары, у которых доступно меньше минимума: самые критичные сверху."""
    totals = stock_queries.stock_totals()
    on_hand = func.coalesce(totals.c.on_hand, 0)
    reserved = func.coalesce(totals.c.reserved, 0)
    available = on_hand - reserved
    # То же правило, что rules.severity_of, только на стороне БД (для фильтра и сортировки)
    is_critical = or_(available <= 0, available < Product.min_stock * rules.CRITICAL_SHARE)

    query = (
        select(Product, Category.name, on_hand.label("on_hand"), reserved.label("reserved"))
        .join(Category, Category.id == Product.category_id)
        .outerjoin(totals, totals.c.product_id == Product.id)
        .where(Product.is_active.is_(True), available < Product.min_stock)
        .order_by(
            case((is_critical, 0), else_=1),
            (available / func.nullif(Product.min_stock, 0)).asc().nulls_first(),
            Product.name,
            Product.id,
        )
    )
    if category_id is not None:
        subtree = catalog_service.category_subtree_ids(session, category_id)
        query = query.where(Product.category_id.in_(subtree))
    if severity == "CRITICAL":
        query = query.where(is_critical)
    elif severity == "WARNING":
        query = query.where(~is_critical)

    rows, total = paginate_rows(session, query, params)
    items = []
    for product, category_name, on_hand_value, reserved_value in rows:
        on_hand_value, reserved_value = Decimal(on_hand_value), Decimal(reserved_value)
        shortage = rules.assess(
            on_hand_value - reserved_value, product.min_stock, product.target_stock, product.unit
        )
        if shortage is None:  # фильтр в запросе и правила расходятся — это ошибка, а не данные
            raise RuntimeError(f"Товар {product.id} попал в отчёт без нехватки")
        items.append(
            LowStockItem(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                unit=product.unit,
                category_id=product.category_id,
                category_name=category_name,
                on_hand=on_hand_value,
                reserved=reserved_value,
                available=shortage.available,
                min_stock=shortage.min_stock,
                target_stock=shortage.target_stock,
                deficit=shortage.deficit,
                recommended_order_qty=shortage.recommended_order_qty,
                severity=shortage.severity,
            )
        )
    return items, total
