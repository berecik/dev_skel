# Python Flask Skeleton - Makefile

.PHONY: gen test

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

MERGE := $(SKEL_DIR)/merge

gen: ## Generate Flask project (NAME=myapp)
ifndef NAME
	@echo "Usage: make gen NAME=<project-name>"
	@exit 1
endif
	@echo "$(GREEN)Generating Flask project: $(NAME)$(NC)"
	@mkdir -p $(NAME)
	@cd $(NAME) && python3 -m venv .venv
	@cd $(NAME) && . .venv/bin/activate && pip install flask flask-sqlalchemy flask-migrate python-dotenv gunicorn
	@bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"
	@echo "$(GREEN)Flask project $(NAME) created!$(NC)"

test: ## Generate a temp project and run its tests (e2e)
	@bash ./test
