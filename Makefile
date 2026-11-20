.PHONY: help install test test-fast lint format prose rules gallery demo demo-marimo pre-commit

PY_FILES = $(shell git ls-files '*.py')
MD_FILES = $(shell git ls-files '*.md')

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-12s %s\n", $$1, $$2}'

install: ## Install the package with the dev tools (uv sync) and the git hooks
	uv sync
	uv run prek install

test: ## Run the tests in random order (pytest-randomly) with coverage
	uv run pytest --cov=plotnine_linter --cov-report=term-missing

test-fast: ## Run the tests without the ones that start a Jupyter kernel
	uv run pytest -m "not notebook"

lint: ## Run ruff (lint and format check), pyrefly (strict, baselined) and slop-lint
	uv run ruff check .
	uv run ruff format --check .
	uv run pyrefly check
	uv run slop-lint $(PY_FILES) Makefile
	uv run plotnine-linter rules --markdown | diff -u docs/rules.md -

format: ## Fix what ruff can fix, then format
	uv run ruff check --fix .
	uv run ruff format .

prose: ## Run slop-lint on the Markdown docs too (report only: it reads tables as one sentence)
	-uv run slop-lint $(MD_FILES)

rules: ## Write docs/rules.md from the catalog
	uv run plotnine-linter rules --markdown > docs/rules.md

gallery: ## Draw the before and after gallery (docs/gallery.md and docs/gallery/img/)
	uv run python docs/gallery/make_gallery.py --strict

demo: ## Run the demo notebook again and save its output
	uv run jupyter nbconvert --to notebook --execute --inplace examples/demo.ipynb

demo-marimo: ## Open the two-minute marimo demo in a sandbox (needs only uv)
	uvx marimo edit --sandbox examples/demo_marimo.py

pre-commit: ## Install the git hooks and run them on every file
	uv run prek install
	uv run prek run --all-files
