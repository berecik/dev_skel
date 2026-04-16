# Skeleton-level Makefile.
#
# Usage from the dev_skel repo root:
#   make -C _skels/go-skel gen NAME=/abs/path/to/wrapper SERVICE="My Service"
#   make -C _skels/go-skel test
#
# `gen` and `test` here mirror the contracts the top-level Makefile
# expects from every skel.

SHELL := /bin/bash

.PHONY: help gen test clean

NAME ?=
SERVICE ?=

help:
	@echo "Targets:"
	@echo "  gen NAME=<path> [SERVICE=\"<display name>\"]   Scaffold a project"
	@echo "  test                                          Run skeleton-level tests"
	@echo "  clean                                         Remove build artifacts"

gen:
	@if [[ -z "$(NAME)" ]]; then \
		echo "ERROR: NAME=<path> is required"; \
		exit 1; \
	fi
	@bash ./gen "$(NAME)" "$(SERVICE)"

test:
	@bash ./test_skel

clean:
	@echo "go-skel itself has no build artifacts (build artifacts live in generated projects)."
