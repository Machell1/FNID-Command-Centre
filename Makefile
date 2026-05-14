.PHONY: help install dev test smoke lint format bundle installer clean

help:
	@echo "FNID Command Centre v2.0 - Make targets"
	@echo "  install     Install Python dependencies into .venv"
	@echo "  dev         Run the Flask dev server (http://127.0.0.1:5000)"
	@echo "  test        Run the pytest suite"
	@echo "  smoke       Run the GET + POST smoke tests"
	@echo "  lint        Run ruff"
	@echo "  bundle      Run PyInstaller into dist/FNID-Command-Centre/"
	@echo "  installer   Build the Windows .exe installer (needs Inno Setup)"
	@echo "  clean       Remove build artefacts and caches"

PY := .venv/Scripts/python.exe

install:
	python -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

dev:
	FNID_USE_REPO_DATA=1 $(PY) main.py

test:
	$(PY) -m pytest tests/ -v --tb=short --ignore=tests/test_ai_assistants.py

smoke:
	$(PY) tests/_smoke_routes_full.py
	$(PY) tests/_smoke_post.py

lint:
	$(PY) -m ruff check fnid_portal/ tests/

bundle:
	$(PY) -m PyInstaller fnid_command_centre.spec --clean --noconfirm

installer:
	powershell -ExecutionPolicy Bypass -File scripts/build_installer.ps1

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov .pytest_cache build dist pyinst.log installer/Output
