# Архитектура

## Общая картина
```
Браузер (React SPA) ──HTTP/JSON──▶ FastAPI (backend) ──SQL──▶ PostgreSQL
                                        │
                                        └── фоновые задачи: истечение резервов, проверка нехватки
```
Монолит: один backend-сервис, одна БД. Микросервисы тут не нужны.

## Структура backend (целевая)
```
backend/
  pyproject.toml            # зависимости (uv), настройки ruff/pytest
  alembic.ini
  migrations/               # миграции Alembic
  src/app/
    main.py                 # create_app(): подключает роутеры, обработчики ошибок
    core/
      config.py             # Settings (pydantic-settings, читает .env)
      security.py           # хеширование паролей, выпуск/проверка JWT
      errors.py             # доменные исключения + их маппинг в HTTP
    db/
      base.py               # DeclarativeBase, соглашение об именах индексов/ограничений
      session.py            # engine, SessionLocal, зависимость get_session
    modules/                # по одному пакету на область
      auth/                 # users, login, роли
      catalog/              # categories, products
      suppliers/
      stock/                # batches, movements, остатки, приход/списание
      reservations/
      stocktaking/          # инвентаризация
      alerts/               # нехватка, истекающие партии
    seed.py                 # тестовые данные
  tests/
```

### Слои внутри модуля
Каждый модуль содержит одинаковый набор файлов:
```
modules/<name>/
  models.py     # SQLAlchemy-модели
  schemas.py    # Pydantic: запросы/ответы (НЕ отдавать модели наружу напрямую)
  service.py    # бизнес-логика; единственное место, где решаются правила из DOMAIN.md
  router.py     # HTTP: разбор запроса → вызов сервиса → ответ
```
Правила зависимостей (их нарушение — повод не принимать PR):
1. `router` знает про `service` и `schemas`, **но не** содержит бизнес-логики и не ходит в БД напрямую.
2. `service` принимает `Session` параметром, не знает про HTTP и FastAPI; ошибки — доменные исключения из `core/errors.py`.
3. Модули не лезут в таблицы друг друга: нужны данные другого модуля — вызывают его `service`.
4. **Любое изменение остатков — только через `modules/stock/service.py`** (приход, списание, резерв/освобождение, корректировка).
   Резервы и инвентаризация вызывают `stock`, а не пишут в `stock_movements` сами.

### Транзакции
Один запрос = один сценарий = **одна транзакция**. Сессия открывается в зависимости `get_session`, `commit` — при успешном
завершении запроса, `rollback` — при любом исключении. Внутри сервиса `commit` не вызываем.
Конкурентность: операции над остатками товара начинаются с `SELECT … FOR UPDATE` строки `products` (см. DOMAIN). При нескольких
товарах блокируем **в порядке возрастания `product_id`** — иначе возможны взаимоблокировки.

### Ошибки
Сервис кидает доменное исключение, `core/errors.py` превращает его в HTTP-ответ единого формата:
```json
{ "code": "INSUFFICIENT_STOCK", "detail": "Запрошено 10, доступно 7", "meta": { "product_id": 5, "available": "7" } }
```
| Исключение | HTTP | `code` |
|---|---|---|
| `NotFound` | 404 | `NOT_FOUND` |
| `Conflict` (уникальность, архивирован) | 409 | `CONFLICT` |
| `InsufficientStock` | 409 | `INSUFFICIENT_STOCK` |
| `StocktakingInProgress` | 409 | `STOCKTAKING_IN_PROGRESS` |
| `Forbidden` | 403 | `FORBIDDEN` |
| `Unauthorized` | 401 | `UNAUTHORIZED` |
| ошибки валидации Pydantic | 422 | `VALIDATION_ERROR` |

### Аутентификация и права
JWT access-токен в заголовке `Authorization: Bearer …`, срок жизни 60 минут. Права проверяются зависимостью
`require_role("storekeeper")` на уровне роутера/эндпоинта (иерархия: `viewer < storekeeper < admin`, см. матрицу в DOMAIN.md).

### Фоновые задачи
- Истечение резервов: `ACTIVE` с `expires_at < now()` → `EXPIRED` + `RELEASE`. Реализация в MVP — простой планировщик внутри процесса
  (APScheduler) либо отдельная команда `python -m app.jobs.expire_reservations`, которую вызывает cron. Выбор зафиксируйте здесь.

## Frontend (целевая структура)
```
frontend/src/
  api/          # клиент к backend (типизированные функции, базовый URL из env)
  features/     # по области: products/, stock/, reservations/, ... (страницы + хуки TanStack Query)
  components/   # переиспользуемые компоненты
  routes.tsx    # маршруты; защищённые маршруты проверяют роль
```
Состояние сервера — TanStack Query; формы — Ant Design Form. Токен хранится в памяти + `sessionStorage`; при `401` — редирект на логин.
Типы ответов API желательно генерировать из OpenAPI (`/openapi.json`), а не переписывать руками.

## Как добавить новый модуль (чеклист)
1. Создать `modules/<name>/` с `models.py`, `schemas.py`, `service.py`, `router.py`.
2. Подключить модели в `db/base.py` (чтобы их видел Alembic), роутер — в `main.py` с префиксом `/api/v1/<name>`.
3. Создать миграцию: `uv run alembic revision --autogenerate -m "add <name>"`, просмотреть, дописать CHECK/индексы, проверить `upgrade` и `downgrade`.
4. Написать тесты сервиса (основные сценарии + ошибки) и 1–2 теста API.
5. Обновить [API.md](API.md), при изменении правил — [DOMAIN.md](DOMAIN.md), при изменении таблиц — [DB_SCHEMA.md](DB_SCHEMA.md).
6. Обновить таблицу статуса в README.
