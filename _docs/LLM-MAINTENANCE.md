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
5. **`_docs/DEPENDENCIES.md`** - Dependency management system documentation
6. **`_bin/skel-gen`** - Relocatable generator tool (prefers per-skeleton `gen` script)
7. **`skel-deps`** - Main dependency installer
8. **`_skels/*/deps`** - Per-skeleton dependency installers

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

6. **Add dependency installers**:
   - **System deps** (`_skels/new-framework-skel/deps`): Installs framework tools (Node.js, Python, etc.)
     - Follow the deps script template (see "Task: Add or Update Dependency Scripts")
     - Make executable: `chmod +x _skels/new-framework-skel/deps`
     - Test on supported platforms

   - **Project deps** (`_skels/new-framework-skel/install-deps`): Installs project packages
     - This script is copied to generated projects
     - Installs npm packages, pip packages, Maven dependencies, etc.
     - Make executable: `chmod +x _skels/new-framework-skel/install-deps`
     - Should detect if tools are missing and give helpful error messages

7. **Test**: `make test-generators`

8. **Update documentation** in `_docs/SKELETONS.md` and `_docs/DEPENDENCIES.md`

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

### Task: Add or Update Dependency Scripts

The project includes a comprehensive dependency management system with per-skeleton `deps` scripts and a main `skel-deps` orchestrator.

#### Dependency System Architecture

**Main Components**:
1. **`skel-deps`** - Central dependency installer at project root
   - Auto-detects OS (macOS, Ubuntu/Debian, Arch Linux, Fedora/RHEL)
   - Lists all skeletons with dependency script status
   - Installs dependencies for all or specific skeletons
   - Provides unified interface and help

2. **`_skels/*/deps`** - Per-skeleton dependency installers
   - Bash scripts that install system dependencies for that framework
   - OS detection and platform-specific installation
   - Dependency verification after installation
   - Colored output for better UX

#### deps Script Template

Each skeleton should have a `deps` script following this pattern:

```bash
#!/usr/bin/env bash
# Dependency installer for <Framework Name> skeleton
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Detect OS
detect_os() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macos"
  elif [[ -f /etc/os-release ]]; then
    . /etc/os-release
    case "$ID" in
      ubuntu|debian) echo "ubuntu" ;;
      arch|manjaro) echo "arch" ;;
      fedora|rhel|centos) echo "fedora" ;;
      *) echo "unknown" ;;
    esac
  else
    echo "unknown"
  fi
}

# Check if command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Install dependencies based on OS
install_deps() {
  local os="$1"

  info "Installing <Framework> dependencies for $os..."

  case "$os" in
    macos)
      if ! command_exists brew; then
        error "Homebrew is required but not installed. Visit https://brew.sh"
        exit 1
      fi
      info "Installing packages..."
      brew install package1 package2
      ;;

    ubuntu)
      info "Installing packages..."
      sudo apt-get update
      sudo apt-get install -y package1 package2
      ;;

    arch)
      info "Installing packages..."
      sudo pacman -S --needed --noconfirm package1 package2
      ;;

    fedora)
      info "Installing packages..."
      sudo dnf install -y package1 package2
      ;;

    *)
      error "Unsupported OS: $os"
      exit 1
      ;;
  esac
}

# Verify installation
verify_deps() {
  info "Verifying installations..."

  if command_exists tool1; then
    info "Tool1: $(tool1 --version)"
  else
    error "Tool1 not found"
    return 1
  fi

  info "All dependencies verified successfully!"
}

# Main
main() {
  local os
  os=$(detect_os)

  if [[ "$os" == "unknown" ]]; then
    error "Unable to detect OS"
    exit 1
  fi

  info "Detected OS: $os"
  install_deps "$os"
  verify_deps
}

main "$@"
```

#### Adding deps to a New Skeleton

When creating a new skeleton, add a `deps` script:

1. **Create the script**: `_skels/new-framework-skel/deps`
2. **Make it executable**: `chmod +x _skels/new-framework-skel/deps`
3. **Follow the template** above
4. **Define dependencies** in `install_deps()` for each OS
5. **Add verification** in `verify_deps()` to check installations
6. **Test on each supported platform** if possible

The `skel-deps` script will automatically detect the new `deps` script.

#### Current Skeleton Dependencies

**Java Spring** (`java-spring-skel/deps`):
- JDK (OpenJDK 21+)
- Maven

**JavaScript/Node.js** (`js-skel/deps`, `ts-vite-react-skel/deps`):
- Node.js 20+
- npm

**Python** (`python-*-skel/deps`):
- Python 3.10+
- pip
- venv module

**Rust** (`rust-*-skel/deps`):
- Rust via rustup
- Build tools (platform-specific: build-essential, base-devel, etc.)
- OpenSSL development libraries

#### Updating Existing deps Scripts

**When to update**:
- Minimum version requirements change
- New OS support needed
- Package names change on a platform
- Additional tools required

**How to update**:
1. Edit the relevant `_skels/*/deps` script
2. Update version checks in `verify_deps()` if needed
3. Test on the target platform
4. Update `_docs/DEPENDENCIES.md` documentation

**Example - Updating minimum Node.js version**:
```bash
# In verify_deps() function
local node_version
node_version=$(node --version | sed 's/v//' | cut -d. -f1)
if [[ "$node_version" -lt 22 ]]; then  # Changed from 20 to 22
  warn "Node.js version is $node_version, but >= 22 is recommended"
fi
```

#### OS-Specific Considerations

**macOS**:
- Requires Homebrew pre-installed
- Check with `command_exists brew` and provide install URL if missing
- Some packages need Xcode Command Line Tools

**Ubuntu/Debian**:
- Always run `sudo apt-get update` before install
- Node.js from default repos may be old - warn users about NodeSource
- Python venv requires separate `python3-venv` package

**Arch Linux**:
- Use `--needed` to skip already-installed packages
- Use `--noconfirm` for non-interactive installation
- Python venv is included with Python package

**Fedora/RHEL**:
- Use `dnf` instead of older `yum`
- Development tools often in group: `dnf groupinstall "Development Tools"`
- Java package naming: `java-21-openjdk-devel` (note `-devel` suffix)

**Rust (All Platforms)**:
- Don't use system package managers
- Use rustup installer: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y`
- Remind users to source `~/.cargo/env` or restart shell

#### Common Pitfalls to Avoid

1. **Don't use `((counter++))` with `set -e`**:
   ```bash
   # WRONG - exits when counter is 0
   ((counter++))

   # CORRECT
   counter=$((counter + 1))
   ```

2. **Don't assume sudo is available**:
   ```bash
   # Check if needed and provide clear error
   if ! command_exists sudo && [[ "$os" != "macos" ]]; then
     error "sudo is required for package installation"
     exit 1
   fi
   ```

3. **Don't hardcode package versions unless necessary**:
   ```bash
   # WRONG
   brew install node@20

   # BETTER - get latest LTS
   brew install node
   ```

4. **Always verify installations**:
   - Check that commands exist after installation
   - Show version information to user
   - Return error if verification fails

5. **Handle missing package managers gracefully**:
   - For macOS, check for Homebrew and provide install URL
   - For other systems, clear error message about unsupported OS

#### Testing deps Scripts

**Manual testing**:
```bash
# Test on your current system
cd _skels/java-spring-skel
./deps

# Test via main script
./skel-deps java-spring-skel

# Test listing
./skel-deps --list
```

**Integration testing**:
```bash
# Ensure all deps scripts are executable
ls -l _skels/*/deps

# Test that skel-deps detects all scripts
./skel-deps --list | grep -c "✓"  # Should equal number of skeletons
```

**Platform testing**:
- Test on each supported OS if possible
- Use Docker/VMs for other platforms
- At minimum, verify script syntax: `bash -n _skels/*/deps`

#### Updating skel-deps Main Script

The `skel-deps` script rarely needs updates, but if adding new OS support:

1. **Update `detect_os()` function**:
   ```bash
   detect_os() {
     # Add new OS detection
     if [[ -f /etc/os-release ]]; then
       . /etc/os-release
       case "$ID" in
         ubuntu|debian) echo "ubuntu" ;;
         arch|manjaro) echo "arch" ;;
         fedora|rhel|centos) echo "fedora" ;;
         opensuse*) echo "opensuse" ;;  # New OS
         *) echo "unknown" ;;
       esac
     fi
   }
   ```

2. **Update `get_os_name()` for display**:
   ```bash
   get_os_name() {
     local os="$1"
     case "$os" in
       # ... existing cases ...
       opensuse) echo "openSUSE" ;;  # New OS
       *) echo "Unknown" ;;
     esac
   }
   ```

3. **Update each skeleton's deps script** with new OS support

4. **Update documentation** in `_docs/DEPENDENCIES.md`

5. **Test the full workflow**:
   ```bash
   ./skel-deps --list
   ./skel-deps --help
   # Test on new OS
   ./skel-deps --all
   ```

#### Documentation Updates

When changing deps scripts, update:

1. **`_docs/DEPENDENCIES.md`**:
   - Installation commands for each OS
   - Version requirements
   - Troubleshooting tips

2. **`README.md`**:
   - Quick start examples
   - Supported systems list
   - Requirements section

3. **This file (`LLM-MAINTENANCE.md`)**:
   - Current dependencies list
   - OS-specific notes
   - Common patterns

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
| Main dependency installer | `./skel-deps` |
| Helper tools | `_bin/` |
| Skeletons | `_skels/*/` |
| Skeleton Makefiles | `_skels/*/Makefile` |
| Skeleton generators | `_skels/*/gen` |
| Skeleton merge scripts | `_skels/*/merge` |
| Skeleton test scripts | `_skels/*/test` |
| System dependency installers | `_skels/*/deps` |
| Project dependency installers | `_skels/*/install-deps` (copied to projects) |
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
- [ ] All 8 dependency scripts are executable: `ls -l _skels/*/deps`
- [ ] No hardcoded absolute paths in Makefiles or scripts
- [ ] `merge` scripts' exclusions are up to date
- [ ] `deps` scripts support all target platforms (macOS, Ubuntu, Arch, Fedora)
- [ ] Documentation reflects current state
- [ ] Skeleton source code is functional and follows best practices
- [ ] Dependencies are reasonably current (check for security issues)
- [ ] `skel-deps --list` shows all skeletons with ✓ status

---

## Contact

This project is maintained by the repository owner. For issues:
1. Check existing documentation
2. Run `make test-generators` to identify problems
3. Review recent changes to Makefiles
