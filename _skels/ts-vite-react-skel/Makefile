# TypeScript Vite React Skeleton - Makefile

.PHONY: gen test

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

# Merges non-existing files from skeleton to target directory
# Excludes package.json, package-lock.json, tsconfig.json (created by vite)
define merge_skel
	@echo "$(YELLOW)Merging skeleton files from $(1) to $(2)...$(NC)"
	@find $(1) -type f \
		-not -path "*/.venv/*" \
		-not -path "*/node_modules/*" \
		-not -path "*/target/*" \
		-not -path "*/__pycache__/*" \
		-not -path "*/.git/*" \
		-not -path "*/dist/*" \
		-not -path "*/build/*" \
		-not -path "*/.pytest_cache/*" \
		-not -path "*/.mypy_cache/*" \
		-not -path "*/.ruff_cache/*" \
		-not -path "*.egg-info/*" \
		-not -name "*.pyc" \
		-not -name "*.pyo" \
		-not -name "*.class" \
		-not -name "*.db" \
		-not -name "*.sqlite" \
		-not -name "*.sqlite3" \
		-not -name "Makefile" \
		-not -name "package.json" \
		-not -name "package-lock.json" \
		-not -name "tsconfig.json" \
		| while read src; do \
		rel=$${src#$(1)}; \
		dst="$(2)/$$rel"; \
		if [ ! -f "$$dst" ]; then \
			mkdir -p "$$(dirname "$$dst")"; \
			cp "$$src" "$$dst"; \
			echo "  + $$rel"; \
		fi; \
	done
endef

gen: ## Generate Vite+React+TypeScript project (NAME=myapp)
ifndef NAME
	@echo "Usage: make gen NAME=<project-name>"
	@exit 1
endif
	@echo "$(GREEN)Generating Vite+React+TypeScript project: $(NAME)$(NC)"
	@mkdir -p $(dir $(NAME))
	@cd $(dir $(NAME)) && npm create vite@latest $(notdir $(NAME)) -- --template react-ts
	@cd $(NAME) && npm install
	@rm -f $(NAME)/vite.config.ts $(NAME)/tsconfig.node.json
	$(call merge_skel,$(SKEL_DIR),$(NAME))
	@cd $(NAME) && npm install vitest @testing-library/react @testing-library/jest-dom jsdom --save-dev
	@cd $(NAME) && npm pkg set scripts.test="vitest run" scripts.test:watch="vitest"
	@echo "$(GREEN)Vite+React+TypeScript project $(NAME) created!$(NC)"

test: ## Run tests
	@npm run test
