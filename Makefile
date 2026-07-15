.PHONY: up down test-local test-qa lint typecheck fmt run-local

up:
	docker-compose up -d
	@echo "Waiting for postgres..."
	@until docker-compose exec -T postgres pg_isready -U buybox > /dev/null 2>&1; do sleep 1; done
	@echo "Local stack is up (postgres:5432, localstack:4566)."

down:
	docker-compose down

test-local:
	poetry run pytest tests/ -v

run-local:
	poetry run alembic upgrade head
	poetry run uvicorn buybox.api.app:app --reload --port 8000

test-qa:
	@echo "Runs smoke tests against a deployed QA environment (added in Phase 7)."
	poetry run pytest tests/smoke/ -v --env=qa

lint:
	poetry run ruff check .

fmt:
	poetry run ruff format .

typecheck:
	poetry run mypy src/
