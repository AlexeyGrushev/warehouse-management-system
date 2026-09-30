# Руководство разработчика

> Команды ниже — целевой рабочий процесс. Пока каркас (спринт 1) не сделан, часть из них не сработает; после спринта 1
> пройдите этот файл на чистом клоне и поправьте всё, что не заработало. Это входит в «готово» задачи про каркас.

## Требования
- Docker + Docker Compose
- [uv](https://docs.astral.sh/uv/) (менеджер зависимостей Python; сам подтянет нужный Python 3.13)
- Node.js 20+ (только для фронтенда)

Правила по Python-зависимостям: **только через uv**. Добавить пакет — `uv add <pkg>` (dev — `uv add --dev <pkg>`),
запустить — `uv run …`. Никаких `pip install` и ручных venv: окружение создаётся `uv sync` само.

## Вариант 1. Всё в Docker (проще всего)
```bash
cp .env.example .env
docker compose up --build
```
Поднимет PostgreSQL и backend; миграции применяются при старте. Swagger: http://localhost:8000/docs.
Заполнить тестовыми данными: `docker compose exec backend uv run python -m app.seed`.

## Вариант 2. Backend локально, БД в Docker (для разработки)
```bash
cp .env.example .env
docker compose up -d db
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run fastapi dev src/app/main.py        # автоперезагрузка, http://localhost:8000
```

## Frontend
```bash
cd frontend
npm install
npm run dev                                # http://localhost:5173, проксирует /api на backend
```

## Переменные окружения (`.env.example` — эталон)
| Переменная | Пример | Смысл |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://wms:wms@localhost:5432/wms` | строка подключения |
| `TEST_DATABASE_URL` | `postgresql+psycopg://wms:wms@localhost:5432/wms_test` | отдельная БД для тестов |
| `JWT_SECRET` | *(длинная случайная строка)* | подпись токенов; в `.env.example` — заглушка, **не реальный секрет** |
| `JWT_EXPIRE_MINUTES` | `60` | срок жизни токена |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@example.com` / *(задать)* | первый администратор, создаётся seed-ом |

Реальные значения `.env` **не коммитим** (файл в `.gitignore`).

## Миграции (Alembic)
```bash
cd backend
uv run alembic revision --autogenerate -m "add suppliers"   # создать; ОБЯЗАТЕЛЬНО прочитать результат
uv run alembic upgrade head                                 # применить
uv run alembic downgrade -1                                 # откатить одну
```
Проверка перед PR: `upgrade head` → `downgrade base` → `upgrade head` проходит на чистой БД.
Подводные камни автогенерации — в [DB_SCHEMA.md](DB_SCHEMA.md#миграции).

## Тесты
```bash
cd backend
uv run pytest                      # все
uv run pytest tests/stock -k fefo  # часть
```
- Тесты работают с **настоящим PostgreSQL** (`TEST_DATABASE_URL`), не с SQLite: блокировки и CHECK-ограничения в SQLite ведут себя иначе.
- Каждый тест идёт в транзакции, которая откатывается в конце (фикстура `session`), данные не пачкают друг друга.
- Что обязательно покрывать тестами сервиса: успешный сценарий, каждый `409`/`404`, граничные значения (ровно весь остаток, `0`, отрицательное),
  конкурентность для резервов/списаний (два параллельных запроса на последние единицы — один должен получить `409`).
- Инварианты из [DB_SCHEMA.md](DB_SCHEMA.md#инварианты-на-них-написать-тесты) — отдельный тестовый модуль, вызывается после сценариев.

## Качество кода
```bash
cd backend
uv run ruff check .
uv run ruff format --check .      # автоформат: uv run ruff format .
```
Аннотации типов — обязательны в сервисах и схемах. CI (GitHub Actions) гоняет `ruff` и `pytest` на каждый PR; PR с красным CI не вливаем.
Перед коммитом полезен `pre-commit` (ruff + форматирование): `uv run pre-commit install`.

## Типичные проблемы
| Симптом | Причина / решение |
|---|---|
| `connection refused` к БД | не запущен `db`: `docker compose up -d db`; проверьте порт в `DATABASE_URL` |
| `alembic` не видит новую таблицу | модели не импортированы в `db/base.py` |
| Тесты видят чужие данные | тест пишет мимо фикстуры `session` (например, открыл свою сессию) |
| Автомиграция «потеряла» CHECK/индекс | дописать вручную в файле миграции |
| `409` при параллельных запросах в тесте | ожидаемо: так работает блокировка товара |
