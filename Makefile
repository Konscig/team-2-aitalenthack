.DEFAULT_GOAL := test

PROJECT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
GIT_COMMON_DIR := $(shell git -C "$(PROJECT_DIR)" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
MAIN_CHECKOUT ?= $(if $(GIT_COMMON_DIR),$(abspath $(GIT_COMMON_DIR)/..),$(PROJECT_DIR))
PYTHON ?= $(MAIN_CHECKOUT)/.venv/bin/python

.PHONY: .check-python-env python lint tests test

.check-python-env:
	@if [ ! -x "$(PYTHON)" ]; then \
		echo "Project Python environment not found: $(PYTHON)"; \
		echo 'Create it with: uv sync --project "$(MAIN_CHECKOUT)"'; \
		echo 'Or override it with: make test PYTHON=/absolute/path/to/python'; \
		exit 1; \
	fi

python: .check-python-env
	@echo "$(PYTHON)"

lint: .check-python-env
	cd "$(PROJECT_DIR)" && "$(PYTHON)" -m ruff check .

tests: .check-python-env
	cd "$(PROJECT_DIR)" && "$(PYTHON)" -m pytest tests

test: tests
