.PHONY: help install test lint build deploy clean

help:
	@echo "FNID Command Centre v2.0 — Make Commands"
	@echo "  install     Install dependencies"
	@echo "  test        Run test suite"
	@echo "  lint        Run linters"
	@echo "  build       Build Docker images"
	@echo "  deploy      Deploy with docker-compose"
	@echo "  migrate     Run database migrations"
	@echo "  seed        Seed reference data"
	@echo "  clean       Clean build artifacts"

install:
	pip install -r requirements.txt

test:
	pytest -v --tb=short

test-cov:
	pytest --cov=src/fnid_portal --cov-report=html --cov-report=term

lint:
	flake8 src/fnid_portal
	black --check src/fnid_portal

format:
	black src/fnid_portal

build:
	docker-compose build

deploy:
	docker-compose up -d

migrate:
	flask db upgrade

seed:
	flask seed-data

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov .pytest_cache
