.PHONY: help install migrate test lint run create_test_user set_groups up down run_granian

MANAGE := uv run manage.py

install:
	uv sync && uv run pre-commit install

makemigrations:
	$(MANAGE) makemigrations

migrate:
	$(MANAGE) migrate

create_test_user:
	$(MANAGE) create_test_user

set_groups:
	$(MANAGE) set_groups

run:
	$(MANAGE) runserver

run_granian:
	uv run granian config.wsgi:application --interface wsgi --host 127.0.0.1 --port 8000 --workers 1 --blocking-threads 1 --access-log

run_celery:
	uv run celery -A config worker -l INFO

setup: install makemigrations migrate set_groups create_test_user 
	@echo "開發環境設定完成!!!"

setup_prod: install makemigrations migrate set_groups
	@echo "The production enviorment has been set up!!!"

format:
	uv run ruff format .
	uv run ruff check --select I --fix .
	@echo "Code formatted!"

lint:
	uv run ruff format --check .
	uv run ruff check .
	@echo "Linting passed!"

lint-fix:
	uv run ruff check --fix .
	@echo " Auto-fixed issues!"

up:
	docker compose -f ./compose.yaml -p nexus-test up -d --build

down:
	docker compose -p nexus-test down -t 10

test:
	$(MANAGE) test 

ci-test: lint format 

