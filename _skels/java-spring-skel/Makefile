# Java Spring Skeleton - Makefile

.PHONY: gen test build run stop build-docker run-docker stop-docker

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

gen: ## Generate Spring Boot project (NAME=myapp)
ifndef NAME
	@echo "Usage: make gen NAME=<project-name>"
	@exit 1
endif
	@echo "$(GREEN)Generating Spring Boot project: $(NAME)$(NC)"
	@bash $(SKEL_DIR)/gen "$(NAME)"
	@echo "$(GREEN)Spring Boot project $(NAME) created!$(NC)"

test: ## Run project tests (use in generated project)
	@bash $(SKEL_DIR)/test

build: ## Build for local development
	@bash $(SKEL_DIR)/build-dev

run: ## Run local development server
	@bash $(SKEL_DIR)/run-dev

stop: ## Stop local development server
	@bash $(SKEL_DIR)/stop-dev

build-docker: ## Build Docker image
	@bash $(SKEL_DIR)/build

run-docker: ## Run in Docker container
	@bash $(SKEL_DIR)/run

stop-docker: ## Stop Docker container
	@bash $(SKEL_DIR)/stop
