# Developer Projects - Common Makefile
# Generate, test, and run projects across all skeleton templates

.PHONY: help list test test-all run info info-all clean clean-all status \
        gen-fastapi gen-flask gen-django gen-vite-react gen-js gen-spring gen-actix gen-axum \
        test-fastapi test-flask test-django test-vite-react test-js test-spring test-actix test-axum

# Skeleton directories
SKEL_DIR := _skels
FASTAPI_SKEL := $(SKEL_DIR)/python-fastapi-skel
FLASK_SKEL := $(SKEL_DIR)/python-flask-skel
DJANGO_SKEL := $(SKEL_DIR)/python-django-skel
VITE_REACT_SKEL := $(SKEL_DIR)/ts-vite-react-skel
JS_SKEL := $(SKEL_DIR)/js-skel
SPRING_SKEL := $(SKEL_DIR)/java-spring-skel
ACTIX_SKEL := $(SKEL_DIR)/rust-actix-skel
AXUM_SKEL := $(SKEL_DIR)/rust-axum-skel

# All skeletons
SKELETONS := $(FASTAPI_SKEL) $(FLASK_SKEL) $(DJANGO_SKEL) $(VITE_REACT_SKEL) $(JS_SKEL) $(SPRING_SKEL) $(ACTIX_SKEL) $(AXUM_SKEL)

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
gen-fastapi: ## Generate FastAPI project (NAME=myapp)
	@$(MAKE) -C $(FASTAPI_SKEL) gen NAME=$(abspath $(NAME))

gen-flask: ## Generate Flask project (NAME=myapp)
	@$(MAKE) -C $(FLASK_SKEL) gen NAME=$(abspath $(NAME))

gen-django: ## Generate Django project (NAME=myapp)
	@$(MAKE) -C $(DJANGO_SKEL) gen NAME=$(abspath $(NAME))

gen-vite-react: ## Generate Vite+React+TypeScript project (NAME=myapp)
	@$(MAKE) -C $(VITE_REACT_SKEL) gen NAME=$(abspath $(NAME))

gen-js: ## Generate JavaScript/Node project (NAME=myapp)
	@$(MAKE) -C $(JS_SKEL) gen NAME=$(abspath $(NAME))

gen-spring: ## Generate Spring Boot project (NAME=myapp)
	@$(MAKE) -C $(SPRING_SKEL) gen NAME=$(abspath $(NAME))

gen-actix: ## Generate Rust Actix-web project (NAME=myapp)
	@$(MAKE) -C $(ACTIX_SKEL) gen NAME=$(abspath $(NAME))

gen-axum: ## Generate Rust Axum project (NAME=myapp)
	@$(MAKE) -C $(AXUM_SKEL) gen NAME=$(abspath $(NAME))

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
	$(MAKE) test-gen-vite-react
	$(MAKE) test-gen-js
	$(MAKE) test-gen-spring
	$(MAKE) test-gen-actix
	$(MAKE) test-gen-axum
	@echo ""
	@echo "$(GREEN)=== All generators tested successfully! ===$(NC)"

test-gen-fastapi: ## Test FastAPI generator
	@echo "$(YELLOW)>>> Testing FastAPI generator$(NC)"
	@$(MAKE) gen-fastapi NAME=$(TEST_OUTPUT)/test-fastapi-app
	@cd $(TEST_OUTPUT)/test-fastapi-app && . .venv/bin/activate && python -c "from fastapi import FastAPI; print('FastAPI import OK')"
	@echo "$(GREEN)FastAPI generator test passed$(NC)"

test-gen-flask: ## Test Flask generator
	@echo "$(YELLOW)>>> Testing Flask generator$(NC)"
	@$(MAKE) gen-flask NAME=$(TEST_OUTPUT)/test-flask-app
	@cd $(TEST_OUTPUT)/test-flask-app && . .venv/bin/activate && python -c "from flask import Flask; print('Flask import OK')"
	@echo "$(GREEN)Flask generator test passed$(NC)"

test-gen-django: ## Test Django generator
	@echo "$(YELLOW)>>> Testing Django generator$(NC)"
	@$(MAKE) gen-django NAME=$(TEST_OUTPUT)/test-django-app
	@cd $(TEST_OUTPUT)/test-django-app && . .venv/bin/activate && python -c "import django; print('Django import OK')"
	@echo "$(GREEN)Django generator test passed$(NC)"

test-gen-vite-react: ## Test Vite+React generator
	@echo "$(YELLOW)>>> Testing Vite+React generator$(NC)"
	@$(MAKE) gen-vite-react NAME=$(TEST_OUTPUT)/test-vite-react-app
	@cd $(TEST_OUTPUT)/test-vite-react-app && npm run build
	@echo "$(GREEN)Vite+React generator test passed$(NC)"

test-gen-js: ## Test JavaScript generator
	@echo "$(YELLOW)>>> Testing JavaScript generator$(NC)"
	@$(MAKE) gen-js NAME=$(TEST_OUTPUT)/test-js-app
	@cd $(TEST_OUTPUT)/test-js-app && node -e "console.log('Node.js OK')"
	@echo "$(GREEN)JavaScript generator test passed$(NC)"

test-gen-spring: ## Test Spring Boot generator
	@echo "$(YELLOW)>>> Testing Spring Boot generator$(NC)"
	@$(MAKE) gen-spring NAME=$(TEST_OUTPUT)/test-spring-app
	@cd $(TEST_OUTPUT)/test-spring-app && mvn compile -q
	@echo "$(GREEN)Spring Boot generator test passed$(NC)"

test-gen-actix: ## Test Rust Actix generator
	@echo "$(YELLOW)>>> Testing Rust Actix generator$(NC)"
	@$(MAKE) gen-actix NAME=$(TEST_OUTPUT)/test-actix-app
	@cd $(TEST_OUTPUT)/test-actix-app && cargo build --release 2>/dev/null
	@echo "$(GREEN)Rust Actix generator test passed$(NC)"

test-gen-axum: ## Test Rust Axum generator
	@echo "$(YELLOW)>>> Testing Rust Axum generator$(NC)"
	@$(MAKE) gen-axum NAME=$(TEST_OUTPUT)/test-axum-app
	@cd $(TEST_OUTPUT)/test-axum-app && cargo build --release 2>/dev/null
	@echo "$(GREEN)Rust Axum generator test passed$(NC)"

#
# === SKELETON TEST TARGETS ===
#
test-all: ## Run tests for all skeleton projects
	@echo "$(GREEN)=== Running all skeleton tests ===$(NC)"
	@for skel in $(SKELETONS); do \
		echo ""; \
		echo "$(YELLOW)>>> Testing $$skel$(NC)"; \
		$(MAKE) -C $$skel test || echo "$(RED)Tests failed for $$skel$(NC)"; \
	done
	@echo ""
	@echo "$(GREEN)=== All tests completed ===$(NC)"

test-fastapi: ## Run FastAPI skeleton tests
	@echo "$(GREEN)Running FastAPI tests...$(NC)"
	@cd $(FASTAPI_SKEL) && . .venv/bin/activate && pytest

test-flask: ## Run Flask skeleton tests
	@echo "$(GREEN)Running Flask tests...$(NC)"
	@cd $(FLASK_SKEL) && . .venv/bin/activate && pytest

test-django: ## Run Django skeleton tests
	@echo "$(GREEN)Running Django tests...$(NC)"
	@cd $(DJANGO_SKEL) && . .venv/bin/activate && pytest

test-vite-react: ## Run Vite+React skeleton tests
	@echo "$(GREEN)Running Vite+React tests...$(NC)"
	$(MAKE) -C $(VITE_REACT_SKEL) test

test-js: ## Run JavaScript skeleton tests
	@echo "$(GREEN)Running JavaScript tests...$(NC)"
	$(MAKE) -C $(JS_SKEL) test

test-spring: ## Run Spring Boot skeleton tests
	@echo "$(GREEN)Running Spring Boot tests...$(NC)"
	@cd $(SPRING_SKEL) && mvn test -q

test-actix: ## Run Rust Actix skeleton tests
	@echo "$(GREEN)Running Rust Actix tests...$(NC)"
	@cd $(ACTIX_SKEL) && cargo test

test-axum: ## Run Rust Axum skeleton tests
	@echo "$(GREEN)Running Rust Axum tests...$(NC)"
	@cd $(AXUM_SKEL) && cargo test

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
