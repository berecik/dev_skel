# JavaScript Skeleton - Makefile

.PHONY: gen test

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

MERGE := $(SKEL_DIR)/merge

gen: ## Generate JavaScript/Node project (NAME=myapp)
ifndef NAME
	@echo "Usage: make gen NAME=<project-name>"
	@exit 1
endif
	@echo "$(GREEN)Generating JavaScript project: $(NAME)$(NC)"
	@mkdir -p $(NAME)
	@cd $(NAME) && npm init -y
	@bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"
	@cd $(NAME) && npm install
	@echo "$(GREEN)JavaScript project $(NAME) created!$(NC)"

test: ## Generate a temp project and run its tests (e2e)
	@bash ./test
