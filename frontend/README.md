# Frontend

React + TypeScript + Vite, интерфейс на Ant Design, запросы через TanStack Query.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, запросы на /api проксируются на backend (localhost:8000)
npm run lint
npm run build
```

Адрес backend для прокси можно поменять переменной `VITE_API_PROXY`.

## Структура
```
src/
  api/          # клиент к backend: типы, fetch-обёртка с токеном, функции запросов
  features/     # по областям: auth/ (вход, защищённые маршруты), products/ (список товаров)
  components/   # общие компоненты (каркас страницы)
  routes.tsx    # маршруты
```
Токен хранится в памяти и в `sessionStorage`; при ответе `401` пользователь возвращается на страницу входа.
