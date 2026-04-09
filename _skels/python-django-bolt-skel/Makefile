# Python Django-Bolt Skeleton - Makefile

.PHONY: gen test build run stop build-dev run-dev stop-dev

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

GREEN := \033[0;32m
NC := \033[0m

gen: ## Generate Django-Bolt project (NAME=myapp [SERVICE="display name"])
ifndef NAME
	@echo "Usage: make gen NAME=<project-name> [SERVICE=\"Display Name\"]"
	@exit 1
endif
	@echo "$(GREEN)Generating Django-Bolt project: $(NAME)$(NC)"
	@bash $(SKEL_DIR)/gen "$(NAME)" "$(SERVICE)"
	@echo "$(GREEN)Django-Bolt project $(NAME) created!$(NC)"

test: ## Run skeleton end-to-end test
	@bash $(SKEL_DIR)/test_skel

build: ## Build for local development (alias of build-dev)
	@bash $(SKEL_DIR)/build-dev

run: ## Run development server (alias of run-dev)
	@bash $(SKEL_DIR)/run-dev

stop: ## Stop development server
	@bash $(SKEL_DIR)/stop-dev

build-dev: ## Build for local development
	@bash $(SKEL_DIR)/build-dev

run-dev: ## Run local development server
	@bash $(SKEL_DIR)/run-dev

stop-dev: ## Stop local development server
	@bash $(SKEL_DIR)/stop-dev
