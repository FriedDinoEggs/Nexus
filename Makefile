.PHONY: help install migrate test lint run create_test_user set_groups

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

run_celery:
	uv run celery -A config worker -l INFO

setup: install makemigrations migrate set_groups create_test_user 
	@echo "開發環境設定完成!!!"

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


test:
	$(MANAGE) test 

ci-test: lint format 

