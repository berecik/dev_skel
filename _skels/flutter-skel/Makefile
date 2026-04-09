# Flutter Skeleton - Makefile

.PHONY: gen test deps install-deps help

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Define gen target differently depending on NAME presence
ifdef NAME
gen: ## Generate Flutter project (NAME=my-app)
	@bash $(SKEL_DIR)/gen "$(NAME)" ${SERVICE:+"$(SERVICE)"} ${PLATFORMS:+--platforms $(PLATFORMS)} ${ORG:+--org $(ORG)}
else
gen: ## Generate Flutter project (NAME=my-app)
	@echo "Usage: make gen NAME=<proj_name> [SERVICE=<service_subdir>] [PLATFORMS=web,android,ios,...] [ORG=com.example]"; exit 1
endif

test: ## Run skeleton end-to-end test (generates a fresh project then runs flutter test in it)
	@bash $(SKEL_DIR)/test_skel

deps: ## Check/install deps required for generator
	@bash $(SKEL_DIR)/deps

install-deps: ## Install required deps
	@bash $(SKEL_DIR)/install-deps

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[0;32m%-15s\033[0m %s\n", $$1, $$2}'
