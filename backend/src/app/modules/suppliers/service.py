from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, Unprocessable
from app.core.pagination import PageParams, paginate
from app.modules.stock.models import Batch
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.schemas import SupplierCreate, SupplierUpdate


def get_supplier(session: Session, supplier_id: int) -> Supplier:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFound("Поставщик не найден", {"supplier_id": str(supplier_id)})
    return supplier


def list_suppliers(
    session: Session, params: PageParams, q: str | None = None, is_active: bool | None = None
) -> tuple[list[Supplier], int]:
    query = select(Supplier).order_by(Supplier.name, Supplier.id)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Supplier.name.ilike(pattern), Supplier.contact.ilike(pattern)))
    if is_active is not None:
        query = query.where(Supplier.is_active == is_active)
    return paginate(session, query, params)


def _ensure_name_free(session: Session, name: str, exclude_id: int | None = None) -> None:
    query = select(Supplier.id).where(Supplier.name == name)
    if exclude_id is not None:
        query = query.where(Supplier.id != exclude_id)
    if session.scalar(query) is not None:
        raise Conflict("Поставщик с таким названием уже существует", {"name": name})


def create_supplier(session: Session, data: SupplierCreate) -> Supplier:
    _ensure_name_free(session, data.name)
    supplier = Supplier(name=data.name, contact=data.contact)
    session.add(supplier)
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as exc:
        raise Conflict("Поставщик с таким названием уже существует", {"name": data.name}) from exc
    return supplier


def update_supplier(session: Session, supplier_id: int, data: SupplierUpdate) -> Supplier:
    supplier = get_supplier(session, supplier_id)
    fields = data.model_dump(exclude_unset=True)
    if "name" in fields:
        if fields["name"] is None:
            raise Unprocessable("Название нельзя обнулить", {"field": "name"})
        if fields["name"] != supplier.name:
            _ensure_name_free(session, fields["name"], exclude_id=supplier_id)
    for name, value in fields.items():
        setattr(supplier, name, value)
    session.flush()
    return supplier


def archive_supplier(session: Session, supplier_id: int) -> None:
    supplier = get_supplier(session, supplier_id)
    has_stock = session.scalar(
        select(Batch.id).where(Batch.supplier_id == supplier_id, Batch.qty_remaining > 0).limit(1)
    )
    if has_stock is not None:
        raise Conflict("У поставщика есть партии с остатком")
    supplier.is_active = False
    session.flush()
