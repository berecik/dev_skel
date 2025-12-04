# Java Spring Skeleton - Makefile

.PHONY: gen test

SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

MERGE := $(SKEL_DIR)/merge.sh

gen: ## Generate Spring Boot project (NAME=myapp)
ifndef NAME
	@echo "Usage: make gen NAME=<project-name>"
	@exit 1
endif
	@echo "$(GREEN)Generating Spring Boot project: $(NAME)$(NC)"
	@mkdir -p $(NAME)
	@tmpzip=$$(mktemp -t spring-XXXXXX.zip); tmpdir=$$(mktemp -dt spring-unzip-XXXXXX); \
	 echo "Downloading Spring Initializr..."; \
	 curl -fsSL "https://start.spring.io/starter.zip?type=maven-project&language=java&groupId=com.example&artifactId=$(notdir $(NAME))&name=$(notdir $(NAME))&packageName=com.example.$(notdir $(NAME))&packaging=jar&javaVersion=21&dependencies=web" -o $$tmpzip; \
	 unzip -q $$tmpzip -d $$tmpdir; \
	 rsync -a $$tmpdir/*/ $(NAME)/; \
	 rm -rf $$tmpzip $$tmpdir
	@bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"
	@cd $(NAME) && mvn -q -e -DskipTests dependency:resolve || true
	@echo "$(GREEN)Spring Boot project $(NAME) created!$(NC)"

test: ## Run tests
	@mvn test -q
