.PHONY: help install run test test-cov lint demo clean

# colors for looks
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

help: ## show this help
	@echo "$(GREEN)whodunit$(NC) - find the culprit in a traceback using git blame"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-12s$(NC) %s\n", $$1, $$2}'

install: ## install dependencies
	pip install -r requirements.txt

run: ## run the CLI (python -m app)
	python -m app --help

test: ## run the tests
	pytest -v

test-cov: ## tests with coverage (needs pytest-cov)
	pytest -v --cov=app --cov-report=term-missing

lint: ## check the code (ruff)
	python -m ruff check app tests scripts || echo "ruff not installed, skip"

demo: ## redraw docs/demo.svg
	python scripts/generate_demo.py

clean: ## clean up junk
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# shortcuts
check: test lint
