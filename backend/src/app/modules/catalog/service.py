from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, Unprocessable
from app.core.pagination import PageParams, paginate
from app.modules.catalog.models import Category, Product
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryNode,
    CategoryUpdate,
    ProductCreate,
    ProductUpdate,
    check_stock_levels,
)
from app.modules.stock import service as stock_service

# ---------------------------------------------------------------- категории


def get_category(session: Session, category_id: int) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise NotFound("Категория не найдена", {"category_id": str(category_id)})
    return category


def list_categories(session: Session, is_active: bool | None = None) -> list[Category]:
    query = select(Category).order_by(Category.name, Category.id)
    if is_active is not None:
        query = query.where(Category.is_active == is_active)
    return list(session.scalars(query))


def build_tree(categories: list[Category]) -> list[CategoryNode]:
    nodes = {c.id: CategoryNode.model_validate(c) for c in categories}
    roots: list[CategoryNode] = []
    for node in nodes.values():
        parent = nodes.get(node.parent_id) if node.parent_id is not None else None
        (parent.children if parent else roots).append(node)
    return roots


def _ensure_unique_category_name(
    session: Session, name: str, parent_id: int | None, exclude_id: int | None = None
) -> None:
    query = select(Category.id).where(Category.name == name)
    query = query.where(
        Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id
    )
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    if session.scalar(query) is not None:
        raise Conflict("Категория с таким названием уже есть на этом уровне", {"name": name})


def _ensure_no_cycle(session: Session, category_id: int, new_parent_id: int) -> None:
    current: int | None = new_parent_id
    while current is not None:
        if current == category_id:
            raise Conflict("Категория не может быть своим предком")
        current = session.scalar(select(Category.parent_id).where(Category.id == current))


def create_category(session: Session, data: CategoryCreate) -> Category:
    if data.parent_id is not None:
        get_category(session, data.parent_id)
    _ensure_unique_category_name(session, data.name, data.parent_id)
    category = Category(name=data.name, parent_id=data.parent_id)
    session.add(category)
    session.flush()
    return category


def update_category(session: Session, category_id: int, data: CategoryUpdate) -> Category:
    category = get_category(session, category_id)
    fields = data.model_dump(exclude_unset=True)
    name = fields.get("name", category.name)
    parent_id = fields.get("parent_id", category.parent_id)
    if "parent_id" in fields and parent_id is not None:
        get_category(session, parent_id)
        _ensure_no_cycle(session, category_id, parent_id)
    if name != category.name or parent_id != category.parent_id:
        _ensure_unique_category_name(session, name, parent_id, exclude_id=category_id)
    category.name = name
    category.parent_id = parent_id
    session.flush()
    return category


def archive_category(session: Session, category_id: int) -> None:
    category = get_category(session, category_id)
    has_products = session.scalar(
        select(Product.id)
        .where(Product.category_id == category_id, Product.is_active.is_(True))
        .limit(1)
    )
    if has_products is not None:
        raise Conflict("В категории есть активные товары")
    has_children = session.scalar(
        select(Category.id)
        .where(Category.parent_id == category_id, Category.is_active.is_(True))
        .limit(1)
    )
    if has_children is not None:
        raise Conflict("В категории есть активные подкатегории")
    category.is_active = False
    session.flush()


# ------------------------------------------------------------------- товары


def get_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise NotFound("Товар не найден", {"product_id": str(product_id)})
    return product


def product_query(
    q: str | None, category_id: int | None, is_active: bool | None
) -> Select[tuple[Product]]:
    query = select(Product).order_by(Product.name, Product.id)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)
    return query


def list_products(
    session: Session,
    params: PageParams,
    q: str | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
) -> tuple[list[Product], int]:
    return paginate(session, product_query(q, category_id, is_active), params)


def _ensure_sku_free(session: Session, sku: str, exclude_id: int | None = None) -> None:
    query = select(Product.id).where(Product.sku == sku)
    if exclude_id is not None:
        query = query.where(Product.id != exclude_id)
    if session.scalar(query) is not None:
        raise Conflict("Товар с таким артикулом уже существует", {"sku": sku})


def _ensure_category_usable(session: Session, category_id: int) -> None:
    category = get_category(session, category_id)
    if not category.is_active:
        raise Conflict("Категория архивирована", {"category_id": str(category_id)})


def create_product(session: Session, data: ProductCreate) -> Product:
    _ensure_category_usable(session, data.category_id)
    _ensure_sku_free(session, data.sku)
    product = Product(**data.model_dump())
    session.add(product)
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as exc:
        raise Conflict("Товар с таким артикулом уже существует", {"sku": data.sku}) from exc
    return product


def update_product(session: Session, product_id: int, data: ProductUpdate) -> Product:
    product = get_product(session, product_id)
    fields = data.model_dump(exclude_unset=True)
    if "sku" in fields and fields["sku"] != product.sku:
        _ensure_sku_free(session, fields["sku"], exclude_id=product_id)
    if "category_id" in fields and fields["category_id"] != product.category_id:
        _ensure_category_usable(session, fields["category_id"])
    for required in ("sku", "name", "category_id", "unit", "min_stock"):
        if required in fields and fields[required] is None:
            raise Unprocessable(f"Поле {required} нельзя обнулить", {"field": required})
    unit = fields.get("unit", product.unit)
    min_stock = fields.get("min_stock", product.min_stock)
    target_stock = fields.get("target_stock", product.target_stock)
    try:
        check_stock_levels(unit, min_stock, target_stock)
    except ValueError as exc:
        raise Unprocessable(str(exc)) from exc
    for name, value in fields.items():
        setattr(product, name, value)
    session.flush()
    return product


def archive_product(session: Session, product_id: int) -> None:
    product = get_product(session, product_id)
    if stock_service.product_has_stock(session, product_id):
        raise Conflict("У товара есть остаток на складе или активный резерв")
    product.is_active = False
    session.flush()
