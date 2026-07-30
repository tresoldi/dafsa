# dafsa Makefile
# POSIX-compatible development commands

.PHONY: help quality security format test test-cov test-fast bump-version build build-release clean install install-dev bench site site-serve

# Default target: show help
.DEFAULT_GOAL := help

# Python interpreter
PYTHON := python3
PIP := $(PYTHON) -m pip

# Version bump type (patch, minor, major)
TYPE ?= patch

help: ## Show this help message
	@echo "dafsa Development Commands"
	@echo "=========================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage examples:"
	@echo "  make quality              # Run all quality checks"
	@echo "  make test-cov             # Run tests with coverage"
	@echo "  make bump-version TYPE=minor  # Bump minor version"
	@echo "  make build-release        # Full release build"

quality: ## Run code quality checks (ruff format --check, ruff check, mypy)
	@echo "==> Checking code formatting..."
	ruff format --check .
	@echo "==> Running ruff linter..."
	ruff check .
	@echo "==> Running mypy type checker..."
	mypy
	@echo "OK: all quality checks passed."

security: ## Run the flake8-bandit security rules on their own
	@echo "==> Running security lint..."
	ruff check --select S .
	@echo "OK: security lint passed."

format: ## Auto-format code with ruff
	@echo "==> Formatting code with ruff..."
	ruff format .
	@echo "OK: code formatted."

test: ## Run the test suite (includes doctests and the docs examples)
	@echo "==> Running tests..."
	pytest
	@echo "OK: tests passed."

test-cov: ## Run tests with coverage (HTML report in htmlcov/; the gate is in pyproject.toml)
	@echo "==> Running tests with coverage..."
	pytest
	@echo "OK: coverage report generated in htmlcov/"

test-fast: ## Run tests in parallel, skipping the slow performance guards
	@echo "==> Running tests in parallel..."
	pytest -n auto -m "not slow" --no-cov
	@echo "OK: tests passed."

bump-version: ## Bump version (TYPE=patch|minor|major) in pyproject.toml, commit, and tag
	@CURRENT=$$(grep -m1 -o '^version = "[^"]*"' pyproject.toml | cut -d'"' -f2); \
	echo "==> Current version: $$CURRENT"; \
	major=$$(echo $$CURRENT | cut -d. -f1); \
	minor=$$(echo $$CURRENT | cut -d. -f2); \
	patch=$$(echo $$CURRENT | cut -d. -f3); \
	if [ "$(TYPE)" = "major" ]; then NEW="$$((major + 1)).0.0"; \
	elif [ "$(TYPE)" = "minor" ]; then NEW="$$major.$$((minor + 1)).0"; \
	elif [ "$(TYPE)" = "patch" ]; then NEW="$$major.$$minor.$$((patch + 1))"; \
	else echo "Error: TYPE must be patch, minor, or major"; exit 1; fi; \
	echo "==> Bumping $(TYPE) version to $$NEW..."; \
	sed -i "s/^version = \"$$CURRENT\"/version = \"$$NEW\"/" pyproject.toml; \
	sed -i "s/^version: $$CURRENT/version: $$NEW/" CITATION.cff; \
	echo ""; \
	echo "Update CHANGELOG.md before committing."; \
	echo ""; \
	read -p "Press Enter to commit and tag, or Ctrl+C to cancel..."; \
	git add pyproject.toml CITATION.cff; \
	git commit -m "Bump version to $$NEW"; \
	git tag -a "v$$NEW" -m "Release v$$NEW"; \
	echo "OK: version bumped to $$NEW and tagged."; \
	echo ""; \
	echo "Next steps:"; \
	echo "  1. Update CHANGELOG.md"; \
	echo "  2. git add CHANGELOG.md && git commit --amend --no-edit"; \
	echo "  3. git push && git push --tags"

build: ## Build the package (creates dist/)
	@echo "==> Building package..."
	$(PYTHON) -m build
	@echo "OK: package built in dist/"

build-release: clean quality test build ## Full release build (clean -> quality -> test -> build)
	@echo "==> Checking distribution metadata..."
	twine check dist/*
	@echo "OK: release build complete."
	@ls -lh dist/

clean: ## Remove build artifacts, caches, and coverage reports
	@echo "==> Cleaning build artifacts..."
	rm -rf dist/ build/ src/*.egg-info site/
	rm -rf .coverage htmlcov/
	rm -rf .pytest_cache .ruff_cache .mypy_cache .hypothesis
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "OK: cleaned."

install: ## Install the package in development mode
	@echo "==> Installing package..."
	$(PIP) install -e .
	@echo "OK: package installed."

install-dev: ## Install with development dependencies (everything the Makefile needs)
	@echo "==> Installing package with dev dependencies..."
	$(PIP) install -e ".[dev]"
	@echo "OK: package installed with dev dependencies."
	@echo ""
	@echo "Installed tools for the Makefile:"
	@echo "  - pytest, pytest-cov, hypothesis (testing)"
	@echo "  - ruff, mypy (code quality)"
	@echo "  - build, twine (build/release)"
	@echo "  - mkdocs-material, mkdocstrings (docs site)"

bench: ## Run the benchmark suite (~1 minute; the numbers quoted in ARCHITECTURE.md)
	@echo "==> Running benchmarks..."
	$(PYTHON) benchmarks/run.py
	@echo "OK: benchmarks complete."

site: ## Build the MkDocs documentation site (strict) into site/
	@echo "==> Building documentation site..."
	mkdocs build --strict
	@echo "OK: site built in site/"

site-serve: ## Serve the docs site locally with live reload
	@echo "==> Serving docs at http://127.0.0.1:8000 ..."
	mkdocs serve
