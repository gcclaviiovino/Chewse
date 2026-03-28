PYTHON ?= python3

.PHONY: dev test lint

dev:
	$(PYTHON) -m uvicorn app.main:app --reload

test:
	$(PYTHON) -m pytest -q

lint:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check app tests; \
	elif command -v flake8 >/dev/null 2>&1; then \
		flake8 app tests; \
	else \
		echo "No linter installed; skipping lint."; \
	fi
