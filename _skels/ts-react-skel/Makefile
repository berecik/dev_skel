# TS React Skeleton - Makefile

.PHONY: gen test deps install-deps help

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Define gen target differently depending on NAME presence
ifdef NAME
gen: ## Generate React TS project (NAME=my-app or PATH)
	@bash $(SKEL_DIR)/gen "$(NAME)" ${PM:+--pm $(PM)} ${TEMPLATE:+--template $(TEMPLATE)}
else
gen: ## Generate React TS project (NAME=my-app or PATH)
	@echo "Usage: make gen NAME=<target-path> [PM=npm|pnpm|yarn|bun] [TEMPLATE=react-swc-ts]"; exit 1
endif

test: ## Run tests in generated project (delegate)
	@bash $(SKEL_DIR)/test

deps: ## Check/install deps required for generator
	@bash $(SKEL_DIR)/deps

install-deps: ## Install required deps
	@bash $(SKEL_DIR)/install-deps

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[0;32m%-15s\033[0m %s\n", $$1, $$2}'
