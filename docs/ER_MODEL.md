# ER-модель базы данных

Диаграмма сущностей, которые создаёт первая миграция (спринт 1): пользователи, категории, товары, поставщики, партии и журнал движений.
Резервы и инвентаризация добавятся в спринте 3; полная целевая схема — в [DB_SCHEMA.md](DB_SCHEMA.md).

```mermaid
erDiagram
    USERS ||--o{ STOCK_MOVEMENTS : "создаёт"
    CATEGORIES ||--o{ CATEGORIES : "родитель"
    CATEGORIES ||--o{ PRODUCTS : "содержит"
    PRODUCTS ||--o{ BATCHES : "поставляется партиями"
    SUPPLIERS |o--o{ BATCHES : "поставляет"
    PRODUCTS ||--o{ STOCK_MOVEMENTS : "движется"
    BATCHES |o--o{ STOCK_MOVEMENTS : "затрагивает"

    USERS {
        bigint id PK
        text email UK
        text password_hash
        text role
        bool is_active
    }
    CATEGORIES {
        bigint id PK
        bigint parent_id FK
        text name
        bool is_active
    }
    PRODUCTS {
        bigint id PK
        text sku UK
        text name
        bigint category_id FK
        text unit
        numeric min_stock
        numeric target_stock
        bool is_active
    }
    SUPPLIERS {
        bigint id PK
        text name UK
        text contact
        bool is_active
    }
    BATCHES {
        bigint id PK
        bigint product_id FK
        bigint supplier_id FK
        text batch_no
        numeric qty_received
        numeric qty_remaining
        numeric unit_cost
        date received_at
        date expires_at
    }
    STOCK_MOVEMENTS {
        bigint id PK
        text type
        bigint product_id FK
        bigint batch_id FK
        numeric quantity_delta
        numeric reserved_delta
        text reason
        bigint user_id FK
        timestamptz created_at
    }
```

## Связи
| Связь | Кратность | Комментарий |
|---|---|---|
| категория → категория | 1 : N | дерево; корневая категория без родителя |
| категория → товары | 1 : N | у товара ровно одна категория |
| товар → партии | 1 : N | каждый приход создаёт партию |
| поставщик → партии | 1 : N | у корректирующих партий инвентаризации поставщика нет |
| товар → движения | 1 : N | журнал по товару |
| партия → движения | 1 : N | приход, списания и корректировки по партии |
| пользователь → движения | 1 : N | кто выполнил операцию |

## Ограничения
- `users.email` и `products.sku` уникальны; `suppliers.name` уникально.
- Название категории уникально в пределах родителя.
- `users.role` — одно из `admin`, `storekeeper`, `viewer`.
- `products.unit` — одно из `pcs`, `kg`, `l`, `m`, `box`; `min_stock >= 0`; `target_stock` не меньше `min_stock`.
- Партия: `qty_received > 0`, `0 <= qty_remaining <= qty_received`, `unit_cost >= 0`, срок годности не раньше даты прихода; пара `(product_id, batch_no)` уникальна.
- Журнал движений: тип жёстко связан со знаком количества и наличием партии (приход всегда `+`, списание всегда `−`, резерв не меняет `quantity_delta`). Записи не изменяются и не удаляются.
- Количества — `NUMERIC(14,3)`, деньги — `NUMERIC(14,2)`; `float` не используем.
