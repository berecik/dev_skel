SHELL := /bin/bash

# Mirrors the per-skel Makefile contract used by every other skeleton:
#   make -C _skels/wrapper-skel gen NAME=/abs/path/to/wrapper [SERVICE="Title"]
#   make -C _skels/wrapper-skel test
#
# `gen` lays down the project basement only (no services). Add services
# afterwards with `make -C _skels/<service-skel> gen NAME=$NAME`.

NAME ?=
SERVICE ?= Generated Project

.PHONY: help gen test test-skel install-deps build clean

help:
	@echo "wrapper-skel — project basement template"
	@echo ""
	@echo "Targets:"
	@echo "  gen NAME=/abs/path/to/wrapper [SERVICE=\"Title\"]"
	@echo "      Lay down the wrapper directory (.env, _shared/, dispatch"
	@echo "      scripts, project/env/kube helpers, dev_skel.project.yml)."
	@echo "  test"
	@echo "      Smoke-generate into a temp dir and verify file presence."

gen:
	@if [[ -z "$(NAME)" ]]; then echo "Usage: make gen NAME=/abs/path/to/wrapper [SERVICE=\"Title\"]" >&2; exit 1; fi
	@bash $(CURDIR)/gen "$(NAME)" "$(SERVICE)"

test:
	@bash $(CURDIR)/test_skel

test-skel: test

install-deps:
	@echo "wrapper-skel has no runtime dependencies."

build:
	@echo "wrapper-skel itself has no build artifacts (the wrapper basement is the artifact)."

clean:
	@echo "Nothing to clean (no build artifacts)."
