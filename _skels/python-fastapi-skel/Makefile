# Python FastAPI Skeleton - Makefile

.PHONY: gen test

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

MERGE := $(SKEL_DIR)/merge.sh

gen: ## Generate FastAPI project (NAME=myapp)
ifndef NAME
	@echo "Usage: make gen NAME=<project-name>"
	@exit 1
endif
	@echo "$(GREEN)Generating FastAPI project: $(NAME)$(NC)"
	@mkdir -p $(NAME)
	@cd $(NAME) && python3 -m venv .venv
	@cd $(NAME) && . .venv/bin/activate && pip install fastapi uvicorn sqlalchemy aiosqlite pydantic-settings alembic python-dotenv
	@bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"
	@echo "$(GREEN)FastAPI project $(NAME) created!$(NC)"

test: ## Run tests
	@. .venv/bin/activate && pytest
