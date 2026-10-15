# Спринт 1: итоги

Цель спринта: систему можно поднять одной командой, войти в неё и работать со справочниками.

## Что сделано
| Задача | Что получилось |
|---|---|
| MWMSCOR-5 Требования и объём MVP | [REQUIREMENTS.md](REQUIREMENTS.md): объём MVP, пользовательские истории, критерии приёмки |
| MWMSCOR-6 ER-модель БД | [ER_MODEL.md](ER_MODEL.md): диаграмма Mermaid, связи, ограничения |
| MWMSCOR-7 Модели и миграция | SQLAlchemy-модели, первая миграция Alembic (CHECK-ограничения, индексы под FEFO и журнал) |
| MWMSCOR-8 CRUD категорий и товаров | категории деревом, товары с поиском, фильтрами и пагинацией |
| MWMSCOR-9 Тестовые данные | `app/seed.py`: 30 товаров, 5 поставщиков, 7 категорий, партии и движения, 3 пользователя |
| MWMSCOR-11 Каркас репозитория | `backend/`, `frontend/`, `docs/`, Makefile, pre-commit, шаблон PR |
| MWMSCOR-12 Docker Compose | PostgreSQL 16 и backend, healthcheck, `.env.example` |
| MWMSCOR-13 CI | GitHub Actions: ruff, pytest на реальном PostgreSQL, миграции вверх и вниз, lint и сборка фронтенда |
| MWMSCOR-14 Авторизация | JWT, роли `viewer < storekeeper < admin`, `POST /auth/login`, `GET /users/me` |
| MWMSCOR-15 CRUD поставщиков | поиск, пагинация, архивация (нельзя, если есть партии с остатком) |
| MWMSCOR-16 Каркас фронтенда | Vite + React + TypeScript, вход, общий каркас страницы, список товаров |

## Как запустить
Всё в Docker:
```bash
cp .env.example .env
docker compose up --build
docker compose exec backend python -m app.seed     # тестовые данные
```
Swagger: http://localhost:8000/docs, проверка работы: http://localhost:8000/health.

Тестовые пользователи создаются seed-ом. Пароль — значение `ADMIN_PASSWORD` из `.env` (в `.env.example` это заглушка):

| Email | Роль |
|---|---|
| `admin@example.com` (или `ADMIN_EMAIL`) | администратор |
| `storekeeper@example.com` | кладовщик |
| `viewer@example.com` | наблюдатель |

Фронтенд (отдельно, нужен запущенный backend):
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

## Разработка и проверки
```bash
make install       # venv и зависимости backend
make db-up         # PostgreSQL в Docker
make migrate       # применить миграции
make seed          # тестовые данные
make test          # pytest (нужна БД wms_test, она создаётся при первом запуске контейнера)
make lint          # ruff
```
Подробнее — в [DEVELOPMENT.md](DEVELOPMENT.md).

## API в спринте 1
Базовый путь `/api/v1`. Чтение — для всех ролей, изменения — для кладовщика и администратора.

| Область | Эндпоинты |
|---|---|
| Авторизация | `POST /auth/login`, `GET /users/me` |
| Категории | `GET /categories` (`?tree=true`), `POST`, `GET/PATCH /categories/{id}`, `POST /categories/{id}/archive` |
| Товары | `GET /products` (`q`, `category_id`, `is_active`, `page`, `size`), `POST`, `GET/PATCH /products/{id}`, `POST /products/{id}/archive` |
| Поставщики | `GET /suppliers` (`q`, `is_active`, `page`, `size`), `POST`, `GET/PATCH /suppliers/{id}`, `POST /suppliers/{id}/archive` |
| Служебное | `GET /health` |

Ошибки приходят в едином формате `{code, detail, meta}`: `401`, `403`, `404`, `409`, `422`.

## Что проверено
- 80 автотестов на реальном PostgreSQL: ограничения схемы, авторизация и роли, CRUD, пагинация и поиск, seed.
- Миграция проходит `upgrade → downgrade → upgrade`.
- Запуск с чистого клона одной командой, вход и список товаров во фронтенде.

## Что дальше (спринт 2)
Партии: приход, списание по сроку годности (FEFO), журнал движений, расчёт остатков.
В схеме БД всё нужное уже есть (`batches`, `stock_movements`); в спринте 2 добавится модуль `stock` с API.
