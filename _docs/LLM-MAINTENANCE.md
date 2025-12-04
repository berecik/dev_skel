# LLM Maintenance Guide

Instructions for AI assistants (Claude, GPT, Gemini, etc.) maintaining this project.

## Project Overview

This is a **Makefile-based project generator system**. It creates new projects from skeleton templates. The architecture follows a delegation pattern where the main Makefile calls skeleton-specific Makefiles. Each skeleton also provides `gen` and `test` helper scripts, and an executable `merge` script used during generation.

## Key Files to Understand

Before making changes, read these files:

1. **`Makefile`** - Main orchestration file
2. **`_skels/*/Makefile`** - Individual skeleton Makefiles (8 total)
3. **`_docs/MAKEFILE.md`** - Makefile architecture documentation
4. **`_docs/SKELETONS.md`** - Skeleton template details
5. **`_bin/skel-gen`** - Relocatable generator tool (prefers per-skeleton `gen` script)

## Common Tasks

### Task: Add a New Skeleton

1. **Create skeleton directory**:
   ```bash
   mkdir -p _skels/language-framework-skel/src
   ```

2. **Add skeleton source files** with working example code

3. **Create skeleton Makefile** (`_skels/language-framework-skel/Makefile`):
  - Must define `gen` and `test` targets and set `MERGE := $(SKEL_DIR)/merge`.
  - Call the merge script as: `bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"`.
  - The `test` target should delegate to `bash ./test`.

  Example skeleton Makefile snippet:
  ```makefile
  .PHONY: gen test
  SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
  MERGE := $(SKEL_DIR)/merge

  gen: ## Generate project (NAME=myapp)
  ifndef NAME
  	@echo "Usage: make gen NAME=<project-name>"
  	@exit 1
  endif
  	# ... framework-specific setup ...
  	@bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"
  	# ... post-setup steps ...

  test: ## Generate a temp project and run its tests (e2e)
  	@bash ./test
  ```

4. **Update main Makefile**:
   - Add variable: `NEW_SKEL := $(SKEL_DIR)/language-framework-skel`
   - Add to SKELETONS list
   - Add to .PHONY
   - Add `gen-new` target
   - Add `test-gen-new` target
   - Add `test-new` target

5. **Add helper scripts** in the skeleton directory:
   - `merge` (executable Bash): copy auxiliary files; exclude generator-owned files.
   - `gen` (executable Bash): wrapper that runs `make -C "$SKEL_DIR" gen NAME="$TARGET"`.
   - `test` (executable Bash): generates into a temp dir, runs tests, performs a non-interactive run/build check.

6. **Test**: `make test-generators`

6. **Update documentation** in `_docs/SKELETONS.md`

---

### Task: Update Dependencies in a Skeleton

**For Python skeletons**:
- Update the pip install lines in the skeleton's Makefile `gen` target.
- Prefer Python 3.11+.
- Test with `make test-gen-<name>` and `make test-<name>`.

**For Node.js skeletons**:
- Update `package.json` in the skeleton when appropriate.
- Or update the `npm` commands in the skeleton Makefile.
- Test with `make test-gen-<name>` and `make test-<name>`.

**For Java skeletons**:
- Update `pom.xml` in the skeleton.
- Test with `make test-gen-spring` and `make test-spring`.

**For Rust skeletons**:
- Update `Cargo.toml` in the skeleton.
- Regenerate `Cargo.lock`: `cd _skels/rust-*-skel && cargo update`.
- Test with `make test-gen-<name>` and `make test-<name>`.

---

### Task: Fix Generator Bugs

**Debugging approach**:
1. Run the failing generator manually:
   ```bash
   make gen-<name> NAME=_test_projects/debug-app 2>&1 | tee debug.log
   ```

2. Check the skeleton Makefile and scripts for issues:
   - Path handling in `merge` script and its exclusions
   - Command sequences in `gen` target and pre/post steps
   - Test script behavior and non-interactive checks

3. Common issues:
   - **Path issues**: Ensure `SKEL_DIR` is resolved via `$(dir $(abspath $(lastword $(MAKEFILE_LIST))))`.
   - **File not copied**: Check exclusion patterns in the `merge` script.
   - **File overwritten**: `merge` must only copy when destination does not exist.
   - **Wrong directory**: Ensure commands use `$(NAME)` or absolute paths, not relative ones.

4. After fixing, run full test suite:
   ```bash
   make clean-test && make test-generators
   ```

---

### Task: Update Skeleton Source Code

1. **Modify files** in `_skels/<name>/`

2. **Important**: Don't modify:
   - `node_modules/`
   - `.venv/`
   - `target/`
   - Any build artifacts

3. **Test the generator**:
   ```bash
   make clean-test && make test-gen-<name>
   ```

4. **For ts-vite-react-skel** specifically:
   - Do not overwrite generator-owned files: `package.json`, `package-lock.json`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts` (see the skeleton `merge` script for exact rules).

---

## Critical Implementation Details

### merge script contract

- The `merge` script signature is: `merge <SKEL_DIR> <TARGET_DIR>`.
- It must:
  - Echo progress and copied relative paths (optional but helpful).
  - Exclude generator-owned files for that stack (see `_skels/*/merge`).
  - Only copy if destination file does not exist (never overwrite).
  - Create parent directories as needed.

### Framework-Specific Considerations

**ts-vite-react-skel**:
- Uses `npm create vite@latest` which creates its own config files
- Excludes `package.json`, `package-lock.json`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts` from merge

**python-django-skel**:
- Uses `django-admin startproject` then overlays skeleton
- Excludes `manage.py` and key `myproject/*` files from merge

**rust-*-skel**:
- Uses `cargo new` then overlays skeleton
- Excludes `Cargo.toml` and `src/main.rs` from merge

---

## Testing Protocol

### After Any Change

1. **Clean test environment**:
   ```bash
   make clean-test
   ```

2. **Run all generator tests**:
   ```bash
   make test-generators
   ```

3. **Verify output**:
   - All 8 generators should pass
   - Check for any warnings or unexpected output

### Test Output Expectations

```
=== Testing all generators ===
>>> Testing FastAPI generator
...
FastAPI generator test passed
>>> Testing Flask generator
...
Flask generator test passed
... (6 more) ...
=== All generators tested successfully! ===
```

---

## File Locations Quick Reference

| Purpose | Location |
|---------|----------|
| Main Makefile | `./Makefile` |
| Skeletons | `_skels/*/` |
| Skeleton Makefiles | `_skels/*/Makefile` |
| Documentation | `_docs/` |
| Test output | `_test_projects/` |

---

## Do NOT

- **Do NOT** modify files in `_test_projects/` - it's auto-generated
- **Do NOT** commit `node_modules/`, `.venv/`, `target/` directories
- **Do NOT** change the `SKEL_DIR` detection pattern - it's carefully designed
- Prefer absolute/abspath usage to avoid relative path issues
- **Do NOT** add interactive prompts to generators (must work non-interactively)

---

## Maintenance Checklist

When maintaining this project, ensure:

- [ ] All 8 generators pass: `make test-generators`
- [ ] No hardcoded absolute paths in Makefiles
- [ ] `merge` scripts' exclusions are up to date
- [ ] Documentation reflects current state
- [ ] Skeleton source code is functional and follows best practices
- [ ] Dependencies are reasonably current (check for security issues)

---

## Contact

This project is maintained by the repository owner. For issues:
1. Check existing documentation
2. Run `make test-generators` to identify problems
3. Review recent changes to Makefiles
