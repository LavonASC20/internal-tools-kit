PYTHON ?= python3
TEST_DATABASE_URL ?= postgresql+psycopg://itk:itk@localhost:5432/itk_test

.PHONY: up down seed test lint install

up:
	docker compose up

down:
	docker compose down

# Drops and recreates the schema in the compose database, then loads synthetic data.
seed:
	docker compose run --rm backend python /app/db/seed.py

install:
	$(PYTHON) -m pip install -r backend/requirements-dev.txt

# Needs a reachable Postgres (e.g. `docker compose up -d postgres`). Uses a separate itk_test database.
test:
	cd backend && TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check backend db
	$(PYTHON) -m ruff format --check backend db
	cd backend && $(PYTHON) -m mypy . ../db
