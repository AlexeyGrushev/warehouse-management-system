"""Тестовые данные: пользователи, категории, 30 товаров, 5 поставщиков, партии и приходы.

Запуск: `make seed` (или `PYTHONPATH=src python -m app.seed` из каталога backend).
Скрипт можно запускать повторно: уже существующие записи пропускаются.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.modules.auth.models import User
from app.modules.catalog.models import Category, Product
from app.modules.stock import service as stock_service
from app.modules.stock.schemas import ReceiptCreate, WriteOffCreate
from app.modules.suppliers.models import Supplier

SUPPLIERS = [
    ("ООО «Молочный дом»", "sales@milkhouse.example, +7 495 100-10-01"),
    ("АО «Хлебозавод №5»", "orders@bread5.example, +7 495 100-10-02"),
    ("ИП Соколов А. В.", "+7 903 100-10-03"),
    ("ООО «Бытхим»", "info@bythim.example, +7 495 100-10-04"),
    ("ООО «Канцторг»", "zakaz@kanctorg.example, +7 495 100-10-05"),
]

# Дерево категорий: (название, родитель)
CATEGORIES = [
    ("Продукты питания", None),
    ("Молочные продукты", "Продукты питания"),
    ("Хлеб и выпечка", "Продукты питания"),
    ("Бакалея", "Продукты питания"),
    ("Напитки", "Продукты питания"),
    ("Бытовая химия", None),
    ("Канцелярия", None),
]

# (артикул, название, категория, единица, мин. остаток, цель, номер поставщика,
#  срок годности в днях или None)
PRODUCTS = [
    ("MLK-001", "Молоко 2,5% 1 л", "Молочные продукты", "pcs", 40, 120, 0, 10),
    ("MLK-002", "Молоко 3,2% 1 л", "Молочные продукты", "pcs", 30, 90, 0, 10),
    ("MLK-003", "Кефир 1% 0,9 л", "Молочные продукты", "pcs", 20, 60, 0, 14),
    ("MLK-004", "Сметана 20% 300 г", "Молочные продукты", "pcs", 15, 45, 0, 21),
    ("MLK-005", "Творог 5% 200 г", "Молочные продукты", "pcs", 15, 45, 0, 12),
    ("MLK-006", "Сыр твёрдый", "Молочные продукты", "kg", 5, 15, 0, 60),
    ("BRD-001", "Батон нарезной", "Хлеб и выпечка", "pcs", 25, 75, 1, 4),
    ("BRD-002", "Хлеб ржаной", "Хлеб и выпечка", "pcs", 20, 60, 1, 5),
    ("BRD-003", "Булочка с маком", "Хлеб и выпечка", "pcs", 30, 90, 1, 3),
    ("BRD-004", "Багет", "Хлеб и выпечка", "pcs", 10, 30, 1, 2),
    ("GRC-001", "Гречка 800 г", "Бакалея", "pcs", 20, 60, 2, 540),
    ("GRC-002", "Рис круглозёрный 900 г", "Бакалея", "pcs", 20, 60, 2, 540),
    ("GRC-003", "Макароны спагетти 450 г", "Бакалея", "pcs", 25, 75, 2, 720),
    ("GRC-004", "Сахар-песок", "Бакалея", "kg", 30, 100, 2, 720),
    ("GRC-005", "Мука пшеничная", "Бакалея", "kg", 30, 100, 2, 365),
    ("GRC-006", "Масло подсолнечное 1 л", "Бакалея", "pcs", 15, 45, 2, 365),
    ("GRC-007", "Соль поваренная 1 кг", "Бакалея", "pcs", 10, 30, 2, None),
    ("DRK-001", "Вода питьевая 1,5 л", "Напитки", "pcs", 60, 200, 2, 365),
    ("DRK-002", "Сок яблочный 1 л", "Напитки", "pcs", 24, 72, 2, 270),
    ("DRK-003", "Чай чёрный, пачка 100 г", "Напитки", "pcs", 20, 60, 2, 540),
    ("DRK-004", "Кофе молотый 250 г", "Напитки", "pcs", 12, 36, 2, 365),
    ("HSH-001", "Средство для посуды 500 мл", "Бытовая химия", "pcs", 12, 36, 3, None),
    ("HSH-002", "Стиральный порошок 3 кг", "Бытовая химия", "pcs", 8, 24, 3, None),
    ("HSH-003", "Мыло хозяйственное", "Бытовая химия", "pcs", 20, 60, 3, None),
    ("HSH-004", "Салфетки бумажные, упаковка", "Бытовая химия", "box", 10, 30, 3, None),
    ("STN-001", "Тетрадь 48 листов", "Канцелярия", "pcs", 50, 150, 4, None),
    ("STN-002", "Ручка шариковая синяя", "Канцелярия", "pcs", 100, 300, 4, None),
    ("STN-003", "Бумага А4, пачка 500 л", "Канцелярия", "box", 10, 30, 4, None),
    ("STN-004", "Маркер перманентный", "Канцелярия", "pcs", 20, 60, 4, None),
    ("STN-005", "Скотч прозрачный", "Канцелярия", "pcs", 15, 45, 4, None),
]

# Какую долю от мин. остатка принять и сколько списать, чтобы часть товаров оказалась
# выше нормы, часть на грани, а часть ниже минимума (для будущего отчёта о нехватке).
STOCK_FACTORS = (Decimal("2.5"), Decimal("1.6"), Decimal("1.1"), Decimal("0.6"))


def _get_or_create_user(session: Session, email: str, role: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(password), role=role)
        session.add(user)
        session.flush()
    return user


def _seed_users(session: Session) -> User:
    settings = get_settings()
    admin = _get_or_create_user(
        session, settings.admin_email.lower(), "admin", settings.admin_password
    )
    _get_or_create_user(session, "storekeeper@example.com", "storekeeper", settings.admin_password)
    _get_or_create_user(session, "viewer@example.com", "viewer", settings.admin_password)
    return admin


def _seed_categories(session: Session) -> dict[str, Category]:
    result: dict[str, Category] = {}
    for name, parent_name in CATEGORIES:
        parent = result[parent_name] if parent_name else None
        query = select(Category).where(Category.name == name)
        query = query.where(
            Category.parent_id.is_(None) if parent is None else Category.parent_id == parent.id
        )
        category = session.scalar(query)
        if category is None:
            category = Category(name=name, parent_id=parent.id if parent else None)
            session.add(category)
            session.flush()
        result[name] = category
    return result


def _seed_suppliers(session: Session) -> list[Supplier]:
    result = []
    for name, contact in SUPPLIERS:
        supplier = session.scalar(select(Supplier).where(Supplier.name == name))
        if supplier is None:
            supplier = Supplier(name=name, contact=contact)
            session.add(supplier)
            session.flush()
        result.append(supplier)
    return result


def _receive(
    session: Session,
    admin: User,
    product: Product,
    supplier: Supplier,
    number: int,
    quantity: Decimal,
    received_at: date,
    shelf_life_days: int | None,
) -> None:
    stock_service.receive(
        session,
        admin,
        ReceiptCreate(
            product_id=product.id,
            supplier_id=supplier.id,
            batch_no=f"{received_at:%Y%m%d}-{number}",
            quantity=quantity,
            unit_cost=Decimal(10 + (product.id * 7) % 90),
            received_at=received_at,
            expires_at=received_at + timedelta(days=shelf_life_days) if shelf_life_days else None,
        ),
    )


def _seed_products(
    session: Session,
    admin: User,
    categories: dict[str, Category],
    suppliers: list[Supplier],
) -> None:
    """Товары и остатки. Приходы и продажи идут через сервис остатков, как в обычной работе."""
    today = date.today()
    for index, row in enumerate(PRODUCTS):
        sku, name, category_name, unit, min_stock, target, supplier_index, shelf_life = row
        if session.scalar(select(Product.id).where(Product.sku == sku)) is not None:
            continue
        product = Product(
            sku=sku,
            name=name,
            category_id=categories[category_name].id,
            unit=unit,
            min_stock=Decimal(min_stock),
            target_stock=Decimal(target),
        )
        session.add(product)
        session.flush()

        total = (Decimal(min_stock) * STOCK_FACTORS[index % len(STOCK_FACTORS)]).quantize(
            Decimal("1")
        )
        first_part = max((total / 2).quantize(Decimal("1")), Decimal(1))
        second_part = max(total - first_part, Decimal(1))
        supplier = suppliers[supplier_index]

        # Старая партия: часть уже продана (продажа «в тот день», пока партия была свежей)
        old_day = today - timedelta(days=12)
        _receive(session, admin, product, supplier, 1, first_part, old_day, shelf_life)
        sold = min((first_part / 3).quantize(Decimal("1")), first_part)
        if sold > 0:
            stock_service.write_off(
                session,
                admin,
                WriteOffCreate(
                    product_id=product.id, quantity=sold, reason="SALE", comment="Продажа (seed)"
                ),
                today=old_day + timedelta(days=1),
            )
        # Свежая партия принята недавно
        _receive(
            session, admin, product, supplier, 2, second_part, today - timedelta(days=3), shelf_life
        )


def run(session: Session) -> None:
    admin = _seed_users(session)
    categories = _seed_categories(session)
    suppliers = _seed_suppliers(session)
    _seed_products(session, admin, categories, suppliers)


def main() -> None:
    with SessionLocal() as session:
        run(session)
        session.commit()
    print("Тестовые данные загружены.")


if __name__ == "__main__":
    main()
