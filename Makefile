# Developer Projects - Common Makefile
# Generate, test, and run projects across all skeleton templates

.PHONY: help list test test-all run info info-all clean clean-all status \
        gen-fastapi gen-fastapi-rag gen-flask gen-django gen-django-bolt gen-react gen-flutter gen-js gen-spring gen-actix gen-axum gen-go \
        test-fastapi test-fastapi-rag test-flask test-django test-django-bolt test-react test-flutter test-js test-spring test-actix test-axum test-go \
        test-ai-generators test-ai-generators-dry \
        test-gen-ai-fastapi test-gen-ai-django test-gen-ai-django-bolt test-gen-ai-flask \
        test-gen-ai-spring test-gen-ai-actix test-gen-ai-axum test-gen-ai-js test-gen-ai-react test-gen-ai-flutter \
        install-rag-deps install-deps rag-index-skels rag-clean-skels \
        test-shared-db test-shared-db-keep test-shared-db-python \
        test-react-django-bolt test-react-django-bolt-keep \
        test-react-fastapi test-react-fastapi-keep \
        test-react-actix test-react-actix-keep \
        test-react-axum test-react-axum-keep \
        test-react-spring test-react-spring-keep \
        test-react-flask test-react-flask-keep \
        test-react-go test-react-go-keep \
        test-react-django test-react-django-keep \
        test-flutter-django-bolt test-flutter-django-bolt-keep \
        test-flutter-fastapi test-flutter-fastapi-keep \
        test-cross-stack

# Skeleton directories
SKEL_DIR := _skels
FASTAPI_SKEL := $(SKEL_DIR)/python-fastapi-skel
FLASK_SKEL := $(SKEL_DIR)/python-flask-skel
DJANGO_SKEL := $(SKEL_DIR)/python-django-skel
DJANGO_BOLT_SKEL := $(SKEL_DIR)/python-django-bolt-skel
REACT_SKEL := $(SKEL_DIR)/ts-react-skel
FLUTTER_SKEL := $(SKEL_DIR)/flutter-skel
JS_SKEL := $(SKEL_DIR)/js-skel
SPRING_SKEL := $(SKEL_DIR)/java-spring-skel
ACTIX_SKEL := $(SKEL_DIR)/rust-actix-skel
AXUM_SKEL := $(SKEL_DIR)/rust-axum-skel
FASTAPI_RAG_SKEL := $(SKEL_DIR)/python-fastapi-rag-skel
GO_SKEL := $(SKEL_DIR)/go-skel

# All skeletons
SKELETONS := $(FASTAPI_SKEL) $(FLASK_SKEL) $(DJANGO_SKEL) $(DJANGO_BOLT_SKEL) $(REACT_SKEL) $(FLUTTER_SKEL) $(JS_SKEL) $(SPRING_SKEL) $(ACTIX_SKEL) $(AXUM_SKEL) $(FASTAPI_RAG_SKEL) $(GO_SKEL)

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

gen-fastapi-rag: ## Generate FastAPI RAG project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(FASTAPI_RAG_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-flask: ## Generate Flask project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(FLASK_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-django: ## Generate Django project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(DJANGO_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-django-bolt: ## Generate Django-Bolt project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(DJANGO_BOLT_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-react: ## Generate React+Vite+TypeScript project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(REACT_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-flutter: ## Generate Flutter project (NAME=myapp [SERVICE="display name"] [PLATFORMS=web,android,...])
	@$(MAKE) -C $(FLUTTER_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)" PLATFORMS="$(PLATFORMS)"

gen-js: ## Generate JavaScript/Node project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(JS_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-spring: ## Generate Spring Boot project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(SPRING_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-actix: ## Generate Rust Actix-web project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(ACTIX_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-axum: ## Generate Rust Axum project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(AXUM_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

gen-go: ## Generate Go (net/http) project (NAME=myapp [SERVICE="display name"])
	@$(MAKE) -C $(GO_SKEL) gen NAME=$(abspath $(NAME)) SERVICE="$(SERVICE)"

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
	$(MAKE) test-gen-go
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

test-gen-flutter: ## Test Flutter generator (smoke build via skel test_skel)
	@echo "$(YELLOW)>>> Testing Flutter generator$(NC)"
	@if ! command -v flutter >/dev/null 2>&1; then \
		echo "$(YELLOW)>>> flutter SDK not on PATH — skipping (install: https://docs.flutter.dev/get-started/install)$(NC)"; \
		exit 0; \
	fi
	@$(MAKE) -C $(FLUTTER_SKEL) test
	@echo "$(GREEN)Flutter generator test passed$(NC)"

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

test-gen-go: ## Test Go generator
	@echo "$(YELLOW)>>> Testing Go generator$(NC)"
	@$(MAKE) gen-go NAME=$(TEST_OUTPUT)/test-go-app
	@cd $(TEST_OUTPUT)/test-go-app/service && go build ./...
	@echo "$(GREEN)Go generator test passed$(NC)"

#
# === AI-AUGMENTED GENERATORS (Ollama) ===
#
# Opt-in target — these run `_bin/skel-gen-ai` for every skeleton that has
# an AI manifest in `_skels/_common/manifests/`. They are NOT part of
# `test-generators` because they require a local Ollama daemon and can take
# several minutes per file.
#
# See: _docs/LLM-MAINTENANCE.md and `_bin/skel-test-ai-generators --help`.
#

test-ai-generators: ## Run skel-gen-ai against every AI-supported skeleton (needs Ollama)
	@echo "$(GREEN)=== Running AI generators (requires Ollama) ===$(NC)"
	@_bin/skel-test-ai-generators

test-ai-generators-dry: ## Dry-run the AI test pipeline (no Ollama calls)
	@echo "$(GREEN)=== Dry-run AI generators ===$(NC)"
	@_bin/skel-test-ai-generators --dry-run

test-gen-ai-fastapi: ## AI-generate a FastAPI service in _test_projects/
	@_bin/skel-test-ai-generators --skel python-fastapi-skel

test-gen-ai-django: ## AI-generate a Django service in _test_projects/
	@_bin/skel-test-ai-generators --skel python-django-skel

test-gen-ai-django-bolt: ## AI-generate a Django-Bolt service in _test_projects/
	@_bin/skel-test-ai-generators --skel python-django-bolt-skel

test-gen-ai-flask: ## AI-generate a Flask service in _test_projects/
	@_bin/skel-test-ai-generators --skel python-flask-skel

test-gen-ai-spring: ## AI-generate a Spring Boot service in _test_projects/
	@_bin/skel-test-ai-generators --skel java-spring-skel

test-gen-ai-actix: ## AI-generate a Rust Actix-web service in _test_projects/
	@_bin/skel-test-ai-generators --skel rust-actix-skel

test-gen-ai-axum: ## AI-generate a Rust Axum service in _test_projects/
	@_bin/skel-test-ai-generators --skel rust-axum-skel

test-gen-ai-js: ## AI-generate a Node service in _test_projects/
	@_bin/skel-test-ai-generators --skel js-skel

test-gen-ai-react: ## AI-generate a React frontend in _test_projects/
	@_bin/skel-test-ai-generators --skel ts-react-skel

test-gen-ai-flutter: ## AI-generate a Flutter frontend in _test_projects/
	@_bin/skel-test-ai-generators --skel flutter-skel

#
# === RAG AGENT (`_bin/skel_rag/`) ===
#
# The RAG agent indexes each skeleton's reference templates with
# tree-sitter + FAISS so skel-gen-ai retrieves only the most relevant
# code into Ollama prompts (instead of stuffing whole files). The
# package lives at `_bin/skel_rag/` and is exposed as a CLI via
# `_bin/skel-rag` (subcommands: index / search / info / clean).
#
# Dependencies are heavy (sentence-transformers, faiss-cpu,
# tree-sitter, langchain-*). Install them into a dedicated venv
# with `make install-rag-deps` (or `_bin/skel-install-rag` directly).
# The venv defaults to ~/.local/share/dev-skel/venv — override with
# SKEL_VENV.  The legacy ``{template}`` / ``{wrapper_snapshot}``
# placeholders keep working without the deps; only manifests using the
# new ``{retrieved_context}`` placeholder require the install.
#
# For a full system install (core tools + all skeleton toolchains + RAG)
# use `make install-deps` which auto-detects the platform and runs the
# matching `_bin/skel-install-<platform>` script.
#

install-rag-deps: ## Install RAG agent dependencies into a venv (no global pip)
	@_bin/skel-install-rag

install-deps: ## Install ALL dev_skel dependencies (system packages + RAG venv)
	@case "$$(uname -s)" in \
		Darwin) _bin/skel-install-macos ;; \
		Linux) \
			if command -v pacman >/dev/null 2>&1; then \
				_bin/skel-install-arch; \
			elif command -v dnf >/dev/null 2>&1; then \
				_bin/skel-install-fedora; \
			elif command -v apt-get >/dev/null 2>&1; then \
				_bin/skel-install-ubuntu; \
			else \
				echo "$(RED)Unsupported Linux distro — run one of _bin/skel-install-{arch,fedora,ubuntu} manually$(NC)"; \
				exit 1; \
			fi ;; \
		*) echo "$(RED)Unsupported OS: $$(uname -s). Run one of _bin/skel-install-{macos,arch,fedora,ubuntu} manually$(NC)"; exit 1 ;; \
	esac

rag-index-skels: ## Build the FAISS index for every skeleton (CI warm-up)
	@echo "$(GREEN)=== Indexing all skeletons with skel-rag ===$(NC)"
	@for skel in $(SKELETONS); do \
		echo "  - $$skel"; \
		_bin/skel-rag index $$skel || exit $$?; \
	done

rag-clean-skels: ## Wipe the cached FAISS index from every skeleton
	@for skel in $(SKELETONS); do \
		_bin/skel-rag clean --path $$skel >/dev/null || true; \
	done
	@echo "$(GREEN)Removed .skel_rag_index/ from every skeleton$(NC)"

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
	@_bin/skel-test-shared-db

test-shared-db-keep: ## Same as test-shared-db but leave _test_projects/test-shared-db on disk
	@_bin/skel-test-shared-db --keep

test-shared-db-python: ## Run only the Python backends through the shared-DB test
	@_bin/skel-test-shared-db \
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
	@_bin/skel-test-react-django-bolt

test-react-django-bolt-keep: ## Same, but leave _test_projects/test-react-django-bolt on disk
	@_bin/skel-test-react-django-bolt --keep

test-react-fastapi: ## Cross-stack integration test (fastapi + ts-react)
	@echo "$(GREEN)=== React + FastAPI integration test ===$(NC)"
	@_bin/skel-test-react-fastapi

test-react-fastapi-keep: ## Same, but leave _test_projects/test-react-fastapi on disk
	@_bin/skel-test-react-fastapi --keep

test-react-actix: ## Cross-stack integration test (rust-actix + ts-react)
	@echo "$(GREEN)=== React + Actix integration test ===$(NC)"
	@_bin/skel-test-react-actix

test-react-actix-keep: ## Same, but leave _test_projects/test-react-actix on disk
	@_bin/skel-test-react-actix --keep

test-react-axum: ## Cross-stack integration test (rust-axum + ts-react)
	@echo "$(GREEN)=== React + Axum integration test ===$(NC)"
	@_bin/skel-test-react-axum

test-react-axum-keep: ## Same, but leave _test_projects/test-react-axum on disk
	@_bin/skel-test-react-axum --keep

test-react-spring: ## Cross-stack integration test (java-spring + ts-react)
	@echo "$(GREEN)=== React + Spring Boot integration test ===$(NC)"
	@_bin/skel-test-react-spring

test-react-spring-keep: ## Same, but leave _test_projects/test-react-spring on disk
	@_bin/skel-test-react-spring --keep

test-react-flask: ## Cross-stack integration test (python-flask + ts-react)
	@echo "$(GREEN)=== React + Flask integration test ===$(NC)"
	@_bin/skel-test-react-flask

test-react-flask-keep: ## Same, but leave _test_projects/test-react-flask on disk
	@_bin/skel-test-react-flask --keep

test-react-go: ## Cross-stack integration test (go-skel + ts-react)
	@echo "$(GREEN)=== React + Go integration test ===$(NC)"
	@_bin/skel-test-react-go

test-react-go-keep: ## Same, but leave _test_projects/test-react-go on disk
	@_bin/skel-test-react-go --keep

test-react-django: ## Cross-stack integration test (python-django + ts-react)
	@echo "$(GREEN)=== React + Django integration test ===$(NC)"
	@_bin/skel-test-react-django

test-react-django-keep: ## Same, but leave _test_projects/test-react-django on disk
	@_bin/skel-test-react-django --keep

#
# === FLUTTER + BACKEND CROSS-STACK INTEGRATION TESTS ===
#
# Same shape as the React tests but for the Flutter frontend. Each one
# generates a wrapper containing the backend skeleton + flutter-skel,
# rewrites BACKEND_URL in <wrapper>/.env, re-copies that .env into the
# Flutter project's bundled asset (so flutter_dotenv reads the new
# value at runtime), runs `flutter pub get` + `flutter build web`,
# inspects the bundled .env asset and the compiled main.dart.js, then
# starts the backend and exercises the canonical 9-step items API
# flow over real HTTP. The HTTP exercise hits the BACKEND directly,
# proving the same items API contract works for both frontends.
#
# Skipped gracefully when the Flutter SDK is not on the PATH.
#

test-flutter-django-bolt: ## Cross-stack integration test (django-bolt + flutter)
	@echo "$(GREEN)=== Flutter + Django-Bolt integration test ===$(NC)"
	@_bin/skel-test-flutter-django-bolt

test-flutter-django-bolt-keep: ## Same, but leave _test_projects/test-flutter-django-bolt on disk
	@_bin/skel-test-flutter-django-bolt --keep

test-flutter-fastapi: ## Cross-stack integration test (fastapi + flutter)
	@echo "$(GREEN)=== Flutter + FastAPI integration test ===$(NC)"
	@_bin/skel-test-flutter-fastapi

test-flutter-fastapi-keep: ## Same, but leave _test_projects/test-flutter-fastapi on disk
	@_bin/skel-test-flutter-fastapi --keep

#
# === ALL CROSS-STACK TESTS (one shot) ===
#
test-cross-stack: ## Run every cross-stack integration test in sequence
	@echo "$(GREEN)=== Running all cross-stack integration tests ===$(NC)"
	@$(MAKE) test-shared-db
	@$(MAKE) test-react-django-bolt
	@$(MAKE) test-react-fastapi
	@$(MAKE) test-flutter-django-bolt
	@$(MAKE) test-flutter-fastapi
	@echo "$(GREEN)All cross-stack tests passed.$(NC)"

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

test-fastapi-rag: ## Run FastAPI RAG skeleton tests
	@echo "$(GREEN)Running FastAPI RAG tests...$(NC)"
	$(MAKE) -C $(FASTAPI_RAG_SKEL) test

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

test-flutter: ## Run Flutter skeleton tests
	@echo "$(GREEN)Running Flutter tests...$(NC)"
	$(MAKE) -C $(FLUTTER_SKEL) test

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

test-go: ## Run Go skeleton tests
	@echo "$(GREEN)Running Go tests...$(NC)"
	$(MAKE) -C $(GO_SKEL) test

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
