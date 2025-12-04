# Python Django Skeleton - Makefile

.PHONY: gen test

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

# Merges non-existing files from skeleton to target directory
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

gen: ## Generate Django project (NAME=myapp)
ifndef NAME
	@echo "Usage: make gen NAME=<project-name>"
	@exit 1
endif
	@echo "$(GREEN)Generating Django project: $(NAME)$(NC)"
	@mkdir -p $(NAME)
	@cd $(NAME) && python3 -m venv .venv
	@cd $(NAME) && . .venv/bin/activate && pip install django python-dotenv gunicorn
	@cd $(NAME) && . .venv/bin/activate && django-admin startproject myproject .
	@rm -f $(NAME)/myproject/urls.py
	$(call merge_skel,$(SKEL_DIR),$(NAME))
	@echo "$(GREEN)Django project $(NAME) created!$(NC)"

test: ## Run tests
	@. .venv/bin/activate && pytest
