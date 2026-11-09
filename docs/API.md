# API

Базовый путь: `/api/v1`. Интерактивная документация (Swagger UI): `/docs`, схема: `/openapi.json` — **они первичны**:
этот файл описывает соглашения и план, а точные поля смотрите в Swagger.

## Соглашения
- JSON, UTF-8. Даты — ISO 8601 (`2026-10-15`, время — с часовым поясом).
- Количества и деньги в ответах — **строками** (`"12.500"`), чтобы не терять точность на `float`.
- Аутентификация: `Authorization: Bearer <token>`; токен выдаёт `POST /auth/login`.
- Списки: `?page=1&size=20` (size ≤ 100), ответ: `{ "items": [...], "total": 153, "page": 1, "size": 20 }`.
- Поиск и фильтры — query-параметры (`?q=молоко&category_id=3&is_active=true`).
- Ошибки — единый формат (см. [ARCHITECTURE.md](ARCHITECTURE.md#ошибки)).
- Создание → `201` + созданный объект; удаление/архивация → `204`.
- Недоступные роли → `403`, нет токена → `401`.

## Эндпоинты (план)
Права: R = viewer+, W = storekeeper+, A = admin.

### Auth — спринт 1
| Метод | Путь | Права | Описание |
|---|---|---|---|
| POST | `/auth/login` | — | `{email, password}` → `{access_token, token_type}` |
| GET | `/users/me` | R | текущий пользователь |
| GET/POST/PATCH | `/users`, `/users/{id}` | A | управление пользователями |

### Каталог — спринт 1
| Метод | Путь | Права | Описание |
|---|---|---|---|
| GET | `/categories`, `/categories/{id}` | R | плоский список или дерево (`?tree=true`), фильтр `is_active` |
| POST/PATCH | `/categories`, `/categories/{id}` | W | создать/изменить |
| POST | `/categories/{id}/archive` | W | архивировать (нельзя, если есть активные товары или подкатегории) |
| GET | `/products`, `/products/{id}` | R | фильтры: `q` (название/sku), `category_id`, `is_active`; пагинация |
| POST/PATCH | `/products`, `/products/{id}` | W | sku уникален, `409` при дубле |
| POST | `/products/{id}/archive` | W | архивировать (нельзя, пока есть остаток или активный резерв: `409`) |
| GET | `/products/{id}/stock` | R | `{product_id, on_hand, reserved, available, min_stock}` — считается из журнала движений |

### Поставщики — спринт 1
| Метод | Путь | Права | Описание |
|---|---|---|---|
| GET | `/suppliers` | R | поиск `q`, пагинация |
| POST/PATCH | `/suppliers`, `/suppliers/{id}` | W | |
| POST | `/suppliers/{id}/archive` | W | нельзя, если есть партии с остатком (`409`) |

### Партии и движения — спринт 2
| Метод | Путь | Права | Описание |
|---|---|---|---|
| POST | `/receipts` | W | приход: `{product_id, supplier_id, batch_no, quantity, unit_cost, received_at, expires_at?}` → `201` и созданная партия. Ошибки: `404` (товар или поставщик), `409` (архив, номер партии уже есть у товара), `422` (количество `<= 0`, дробное для штучного товара, срок годности раньше даты прихода) |
| POST | `/write-offs` | W | списание по FEFO: `{product_id, quantity, reason, comment?}`, причина — `SALE`, `DAMAGE`, `EXPIRED`, `OTHER`. `201` и `{product_id, reason, quantity, lines:[{batch_id, batch_no, quantity}]}` — сколько списано из каждой партии. Ошибки: `409 INSUFFICIENT_STOCK` (в `meta`: `requested`, `available`), `404`, `422` |
| GET | `/batches` | R | фильтры: `product_id`, `supplier_id`, `only_in_stock`; пагинация; в ответе названия товара и поставщика |
| GET | `/movements` | R | журнал, новые сверху: `product_id`, `type`, `date_from`, `date_to` (включительно, сутки по московскому времени), `user_id`; пагинация; в ответе артикул, название товара, номер партии, email пользователя |
| GET | `/stock` | R | остатки по товарам: `on_hand`, `reserved`, `available`, `min_stock`, `is_low`; фильтры `q`, `category_id`, `low_only`, `is_active` (по умолчанию `true`); пагинация |

### Резервы — спринт 3
| Метод | Путь | Права | Описание |
|---|---|---|---|
| POST | `/reservations` | W | `{reference, expires_at?, items:[{product_id, quantity}]}` → `201` и резерв с позициями. «Всё или ничего»: если хотя бы одной позиции не хватает — `409 INSUFFICIENT_STOCK` (в `meta` первая нехватка), ничего не создаётся. `422` — пустой список, повтор товара, срок не в будущем, дробное для штучного; `409 STOCKTAKING_IN_PROGRESS` — по товару идёт инвентаризация |
| GET | `/reservations`, `/reservations/{id}` | R | фильтры `status`, `reference` (поиск по подстроке); новые сверху; пагинация |
| POST | `/reservations/{id}/cancel` | W | `RELEASE` по позициям, статус `CANCELLED`; `409`, если резерв уже в конечном статусе |
| POST | `/reservations/{id}/fulfill` | W | отгрузка: `RELEASE` и списание по FEFO (`SALE`) по каждой позиции, статус `FULFILLED`. `409`: уже в конечном статусе, срок истёк, не хватает непросроченного товара (откат целиком) |

Истёкшие резервы освобождает фоновая задача (`EXPIRED` + `RELEASE`); её же можно запустить вручную: `python -m app.jobs.expire_reservations`.

### Инвентаризация — спринт 3
| Метод | Путь | Права | Описание |
|---|---|---|---|
| POST | `/stocktakings` | W | `{category_id?}` → `201`, сессия `DRAFT` со строками; без категории — все активные товары, с категорией — она и её подкатегории; `422`, если товаров нет |
| POST | `/stocktakings/{id}/start` | W | фиксирует `expected_qty` = остаток на складе, статус `IN_PROGRESS`, запрещает движения по товарам; `409`, если не `DRAFT` или товар уже в другой открытой сессии (`STOCKTAKING_IN_PROGRESS`) |
| PUT | `/stocktakings/{id}/lines/{product_id}` | W | `{counted_qty}` (≥ 0), только в `IN_PROGRESS`; `404`, если товара нет в сессии |
| POST | `/stocktakings/{id}/close` | W | проводит корректировки (`ADJUSTMENT`) и ставит `CLOSED`; `422`, если заполнены не все строки |
| POST | `/stocktakings/{id}/cancel` | W | из `DRAFT` или `IN_PROGRESS`, снимает запрет на движения |
| GET | `/stocktakings`, `/stocktakings/{id}` | R | список со счётчиками `lines_total` / `lines_counted` (фильтр `status`); карточка со строками: `expected_qty`, `counted_qty`, `diff` |

### Нехватка — спринт 4
| Метод | Путь | Права | Описание |
|---|---|---|---|
| GET | `/alerts/low-stock` | R | `[{product, available, min_stock, recommended_order_qty, severity}]` |
| GET | `/alerts/expiring-batches?days=14` | R | партии, срок которых истекает |

### Отчёты — спринт 5
`GET /reports/stock.csv`, `GET /reports/movements.csv?date_from&date_to` (Content-Type `text/csv`).

## Служебное
`GET /health` → `{"status":"ok"}` (для healthcheck в Docker), без авторизации.
