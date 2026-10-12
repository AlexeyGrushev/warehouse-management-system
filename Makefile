.PHONY: venv install lint format test migrate seed db-up db-down

PY ?= python3.13
VENV := backend/.venv
BIN := $(VENV)/bin

venv:
	$(PY) -m venv $(VENV)

install: venv
	$(BIN)/pip install -r backend/requirements-dev.txt

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .

format:
	cd backend && .venv/bin/ruff format . && .venv/bin/ruff check --fix .

test:
	cd backend && .venv/bin/pytest

migrate:
	cd backend && .venv/bin/alembic upgrade head

seed:
	cd backend && PYTHONPATH=src .venv/bin/python -m app.seed

db-up:
	docker compose up -d db

db-down:
	docker compose down
