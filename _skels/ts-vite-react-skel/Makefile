# TypeScript Vite React Skeleton - Makefile

.PHONY: gen test

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

MERGE := $(SKEL_DIR)/merge

gen: ## Generate Vite+React+TypeScript project (NAME=myapp)
ifndef NAME
	@echo "Usage: make gen NAME=<project-name>"
	@exit 1
endif
	@echo "$(GREEN)Generating Vite+React+TypeScript project: $(NAME)$(NC)"
	@mkdir -p $(dir $(NAME))
	@cd $(dir $(NAME)) && printf 'n\nn\n' | npm create vite@latest $(notdir $(NAME)) -- --template react-ts
	@cd $(NAME) && npm install
	@bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"
	@cd $(NAME) && npm install vitest @testing-library/react @testing-library/jest-dom jsdom --save-dev
	@cd $(NAME) && npm pkg set scripts.test="vitest run" scripts.test:watch="vitest"
	@echo "$(GREEN)Vite+React+TypeScript project $(NAME) created!$(NC)"

test: ## Generate a temp project and run its tests (e2e)
	@bash ./test
