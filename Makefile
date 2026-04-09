# Developer Projects - Common Makefile
# Generate, test, and run projects across all skeleton templates

.PHONY: help list test test-all run info info-all clean clean-all status \
        gen-fastapi gen-flask gen-django gen-django-bolt gen-react gen-js gen-spring gen-actix gen-axum \
        test-fastapi test-flask test-django test-django-bolt test-react test-js test-spring test-actix test-axum \
        test-ai-generators test-ai-generators-dry \
        test-gen-ai-fastapi test-gen-ai-django test-gen-ai-django-bolt test-gen-ai-flask \
        test-gen-ai-spring test-gen-ai-actix test-gen-ai-axum test-gen-ai-js test-gen-ai-react \
        test-shared-db test-shared-db-keep test-shared-db-python \
        test-react-django-bolt test-react-django-bolt-keep \
        test-react-fastapi test-react-fastapi-keep

# Skeleton directories
SKEL_DIR := _skels
FASTAPI_SKEL := $(SKEL_DIR)/python-fastapi-skel
FLASK_SKEL := $(SKEL_DIR)/python-flask-skel
DJANGO_SKEL := $(SKEL_DIR)/python-django-skel
DJANGO_BOLT_SKEL := $(SKEL_DIR)/python-django-bolt-skel
REACT_SKEL := $(SKEL_DIR)/ts-react-skel
JS_SKEL := $(SKEL_DIR)/js-skel
SPRING_SKEL := $(SKEL_DIR)/java-spring-skel
ACTIX_SKEL := $(SKEL_DIR)/rust-actix-skel
AXUM_SKEL := $(SKEL_DIR)/rust-axum-skel

# All skeletons
SKELETONS := $(FASTAPI_SKEL) $(FLASK_SKEL) $(DJANGO_SKEL) $(DJANGO_BOLT_SKEL) $(REACT_SKEL) $(JS_SKEL) $(SPRING_SKEL) $(ACTIX_SKEL) $(AXUM_SKEL)

# Test output directory
TEST_OUTPUT := _test_projects

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
RED := \033[0;31m
NC := \033[0m

help: ## Show this help
	@echo "Developer Projects - Skeleton Generator Makefile"
	@echo ""
	@echo "Skeletons: $(SKELETONS)"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'

list: ## List all skeleton projects
	@echo "Available skeletons:"
	@for skel in $(SKELETONS); do \
		echo "  - $$skel"; \
	done

#
# === PROJECT GENERATORS (delegate to skel Makefiles) ===
#
# Usage:
#   make gen-<skel> NAME=myapp                          # default service dir
#   make gen-<skel> NAME=myapp SERVICE="Ticket Service" # → myapp/ticket_service/
#
# When SERVICE is set its slug becomes the on-disk service directory; when
# absent the per-skeleton default base (`backend` / `frontend` / `service`)
# is used so legacy `make gen-*` invocations keep working.
#
gen-fastapi: ## Generate FastAPI project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(FASTAPI_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-flask: ## Generate Flask project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(FLASK_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-django: ## Generate Django project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(DJANGO_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-django-bolt: ## Generate Django-Bolt project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(DJANGO_BOLT_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-react: ## Generate React+Vite+TypeScript project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(REACT_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-js: ## Generate JavaScript/Node project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(JS_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-spring: ## Generate Spring Boot project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(SPRING_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-actix: ## Generate Rust Actix-web project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(ACTIX_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-axum: ## Generate Rust Axum project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(AXUM_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

#
# === TEST ALL GENERATORS ===
#
test-generators: ## Test all generators by creating test projects
	@echo "$(GREEN)=== Testing all generators ===$(NC)"
	@rm -rf $(TEST_OUTPUT)
	@mkdir -p $(TEST_OUTPUT)
	$(MAKE) test-gen-fastapi
	$(MAKE) test-gen-flask
	$(MAKE) test-gen-django
	$(MAKE) test-gen-django-bolt
	$(MAKE) test-gen-react
	$(MAKE) test-gen-js
	$(MAKE) test-gen-spring
	$(MAKE) test-gen-actix
	$(MAKE) test-gen-axum
	@echo ""
	@echo "$(GREEN)=== All generators tested successfully! ===$(NC)"

test-gen-fastapi: ## Test FastAPI generator
	@echo "$(YELLOW)>>> Testing FastAPI generator$(NC)"
	@$(MAKE) gen-fastapi NAME=$(TEST_OUTPUT)/test-fastapi-ddd-app
	@cd $(TEST_OUTPUT)/test-fastapi-ddd-app/backend && . .venv/bin/activate && python -c "from app import get_app; from core.repository import AbstractRepository; print('FastAPI import OK')"
	@echo "$(GREEN)FastAPI generator test passed$(NC)"

test-gen-flask: ## Test Flask generator
	@echo "$(YELLOW)>>> Testing Flask generator$(NC)"
	@$(MAKE) gen-flask NAME=$(TEST_OUTPUT)/test-flask-app
	@cd $(TEST_OUTPUT)/test-flask-app/backend && . .venv/bin/activate && python -c "from flask import Flask; print('Flask import OK')"
	@echo "$(GREEN)Flask generator test passed$(NC)"

test-gen-django: ## Test Django generator
	@echo "$(YELLOW)>>> Testing Django generator$(NC)"
	@$(MAKE) gen-django NAME=$(TEST_OUTPUT)/test-django-app
	@cd $(TEST_OUTPUT)/test-django-app/backend && . .venv/bin/activate && python -c "import django; print('Django import OK')"
	@echo "$(GREEN)Django generator test passed$(NC)"

test-gen-django-bolt: ## Test Django-Bolt generator
	@echo "$(YELLOW)>>> Testing Django-Bolt generator$(NC)"
	@$(MAKE) gen-django-bolt NAME=$(TEST_OUTPUT)/test-django-bolt-app
	@cd $(TEST_OUTPUT)/test-django-bolt-app/backend && . .venv/bin/activate && python -c "import django, django_bolt, msgspec; print('Django-Bolt import OK')" && python manage.py check
	@echo "$(GREEN)Django-Bolt generator test passed$(NC)"

test-gen-react: ## Test React+Vite generator
	@echo "$(YELLOW)>>> Testing React+Vite generator$(NC)"
	@$(MAKE) gen-react NAME=$(TEST_OUTPUT)/test-react-app
	@cd $(TEST_OUTPUT)/test-react-app/frontend && npm run build
	@echo "$(GREEN)React+Vite generator test passed$(NC)"

test-gen-js: ## Test JavaScript generator
	@echo "$(YELLOW)>>> Testing JavaScript generator$(NC)"
	@$(MAKE) gen-js NAME=$(TEST_OUTPUT)/test-js-app
	@cd $(TEST_OUTPUT)/test-js-app/app && node -e "console.log('Node.js OK')"
	@echo "$(GREEN)JavaScript generator test passed$(NC)"

test-gen-spring: ## Test Spring Boot generator
	@echo "$(YELLOW)>>> Testing Spring Boot generator$(NC)"
	@$(MAKE) gen-spring NAME=$(TEST_OUTPUT)/test-spring-app
	@cd $(TEST_OUTPUT)/test-spring-app/service && mvn compile -q
	@echo "$(GREEN)Spring Boot generator test passed$(NC)"

test-gen-actix: ## Test Rust Actix generator
	@echo "$(YELLOW)>>> Testing Rust Actix generator$(NC)"
	@$(MAKE) gen-actix NAME=$(TEST_OUTPUT)/test-actix-app
	@cd $(TEST_OUTPUT)/test-actix-app/service && cargo build --release 2>/dev/null
	@echo "$(GREEN)Rust Actix generator test passed$(NC)"

test-gen-axum: ## Test Rust Axum generator
	@echo "$(YELLOW)>>> Testing Rust Axum generator$(NC)"
	@$(MAKE) gen-axum NAME=$(TEST_OUTPUT)/test-axum-app
	@cd $(TEST_OUTPUT)/test-axum-app/service && cargo build --release 2>/dev/null
	@echo "$(GREEN)Rust Axum generator test passed$(NC)"

#
# === AI-AUGMENTED GENERATORS (Ollama) ===
#
# Opt-in target — these run `_bin/skel-gen-ai` for every skeleton that has
# an AI manifest in `_skels/_common/manifests/`. They are NOT part of
# `test-generators` because they require a local Ollama daemon and can take
# several minutes per file.
#
# See: _docs/LLM-MAINTENANCE.md and `_bin/test-ai-generators --help`.
#

test-ai-generators: ## Run skel-gen-ai against every AI-supported skeleton (needs Ollama)
	@echo "$(GREEN)=== Running AI generators (requires Ollama) ===$(NC)"
	@_bin/test-ai-generators

test-ai-generators-dry: ## Dry-run the AI test pipeline (no Ollama calls)
	@echo "$(GREEN)=== Dry-run AI generators ===$(NC)"
	@_bin/test-ai-generators --dry-run

test-gen-ai-fastapi: ## AI-generate a FastAPI service in _test_projects/
	@_bin/test-ai-generators --skel python-fastapi-skel

test-gen-ai-django: ## AI-generate a Django service in _test_projects/
	@_bin/test-ai-generators --skel python-django-skel

test-gen-ai-django-bolt: ## AI-generate a Django-Bolt service in _test_projects/
	@_bin/test-ai-generators --skel python-django-bolt-skel

test-gen-ai-flask: ## AI-generate a Flask service in _test_projects/
	@_bin/test-ai-generators --skel python-flask-skel

test-gen-ai-spring: ## AI-generate a Spring Boot service in _test_projects/
	@_bin/test-ai-generators --skel java-spring-skel

test-gen-ai-actix: ## AI-generate a Rust Actix-web service in _test_projects/
	@_bin/test-ai-generators --skel rust-actix-skel

test-gen-ai-axum: ## AI-generate a Rust Axum service in _test_projects/
	@_bin/test-ai-generators --skel rust-axum-skel

test-gen-ai-js: ## AI-generate a Node service in _test_projects/
	@_bin/test-ai-generators --skel js-skel

test-gen-ai-react: ## AI-generate a React frontend in _test_projects/
	@_bin/test-ai-generators --skel ts-react-skel

#
# === SHARED-DB INTEGRATION TEST ===
#
# Generates a wrapper containing every backend skeleton, seeds the
# shared SQLite items table, then runs a per-stack verifier against
# every service to confirm they all read the same DB via DATABASE_URL.
#
# Backends whose toolchain is missing on the host (no JDK, no Rust,
# no Node) are SKIPPED gracefully so the test runs on minimal CI.
#
test-shared-db: ## Verify every backend skel sees the same shared items table
	@echo "$(GREEN)=== Shared-DB integration test ===$(NC)"
	@_bin/test-shared-db

test-shared-db-keep: ## Same as test-shared-db but leave _test_projects/test-shared-db on disk
	@_bin/test-shared-db --keep

test-shared-db-python: ## Run only the Python backends through the shared-DB test
	@_bin/test-shared-db \
		--skel python-django-skel \
		--skel python-django-bolt-skel \
		--skel python-fastapi-skel \
		--skel python-flask-skel

#
# === REACT + DJANGO-BOLT INTEGRATION TEST ===
#
# Cross-stack proof that the canonical full-stack pair works end-to-end.
# Generates a wrapper containing python-django-bolt-skel + ts-react-skel,
# rewrites BACKEND_URL to a non-conflicting port, builds the React
# frontend, starts the django-bolt backend, and exercises the
# register → login → create → list → complete items flow over real HTTP.
#
# Skipped gracefully when Node/npm is not installed.
#
test-react-django-bolt: ## Cross-stack integration test (django-bolt + ts-react)
	@echo "$(GREEN)=== React + Django-Bolt integration test ===$(NC)"
	@_bin/test-react-django-bolt-integration

test-react-django-bolt-keep: ## Same, but leave _test_projects/test-react-django-bolt on disk
	@_bin/test-react-django-bolt-integration --keep

test-react-fastapi: ## Cross-stack integration test (fastapi + ts-react)
	@echo "$(GREEN)=== React + FastAPI integration test ===$(NC)"
	@_bin/test-react-fastapi-integration

test-react-fastapi-keep: ## Same, but leave _test_projects/test-react-fastapi on disk
	@_bin/test-react-fastapi-integration --keep

#
# === SKELETON TEST TARGETS ===
#
test: ## Run all skeleton e2e tests (generates projects and runs their tests)
	@./test

test-all: ## Alias for 'test'
	@./test

test-fastapi: ## Run FastAPI skeleton tests
	@echo "$(GREEN)Running FastAPI tests...$(NC)"
	$(MAKE) -C $(FASTAPI_SKEL) test

test-flask: ## Run Flask skeleton tests
	@echo "$(GREEN)Running Flask tests...$(NC)"
	$(MAKE) -C $(FLASK_SKEL) test

test-django: ## Run Django skeleton tests
	@echo "$(GREEN)Running Django tests...$(NC)"
	$(MAKE) -C $(DJANGO_SKEL) test

test-django-bolt: ## Run Django-Bolt skeleton tests
	@echo "$(GREEN)Running Django-Bolt tests...$(NC)"
	$(MAKE) -C $(DJANGO_BOLT_SKEL) test

test-react: ## Run React+Vite skeleton tests
	@echo "$(GREEN)Running React+Vite tests...$(NC)"
	$(MAKE) -C $(REACT_SKEL) test

test-js: ## Run JavaScript skeleton tests
	@echo "$(GREEN)Running JavaScript tests...$(NC)"
	$(MAKE) -C $(JS_SKEL) test

test-spring: ## Run Spring Boot skeleton tests
	@echo "$(GREEN)Running Spring Boot tests...$(NC)"
	$(MAKE) -C $(SPRING_SKEL) test

test-actix: ## Run Rust Actix skeleton tests
	@echo "$(GREEN)Running Rust Actix tests...$(NC)"
	$(MAKE) -C $(ACTIX_SKEL) test

test-axum: ## Run Rust Axum skeleton tests
	@echo "$(GREEN)Running Rust Axum tests...$(NC)"
	$(MAKE) -C $(AXUM_SKEL) test

#
# === INFO TARGETS ===
#
info-all: ## Show info for all skeleton projects
	@echo "$(GREEN)=== All Skeleton Info ===$(NC)"
	@for skel in $(SKELETONS); do \
		echo ""; \
		echo "$(YELLOW)>>> $$skel$(NC)"; \
		$(MAKE) -C $$skel info 2>/dev/null || echo "No info target"; \
	done

#
# === CLEAN TARGETS ===
#
clean-all: ## Clean all skeleton projects
	@echo "$(GREEN)=== Cleaning all projects ===$(NC)"
	@for skel in $(SKELETONS); do \
		echo "$(YELLOW)>>> Cleaning $$skel$(NC)"; \
		$(MAKE) -C $$skel clean 2>/dev/null || true; \
	done
	@echo "$(GREEN)=== All projects cleaned ===$(NC)"

clean-test: ## Clean test output directory
	@echo "$(GREEN)Cleaning test output...$(NC)"
	@rm -rf $(TEST_OUTPUT)
	@echo "$(GREEN)Test output cleaned$(NC)"

#
# === STATUS ===
#
status: ## Show status of all skeleton directories
	@echo "$(GREEN)=== Skeleton Status ===$(NC)"
	@for skel in $(SKELETONS); do \
		if [ -d "$$skel" ]; then \
			echo "  $(GREEN)✓$(NC) $$skel"; \
		else \
			echo "  $(RED)✗$(NC) $$skel (missing)"; \
		fi \
	done
