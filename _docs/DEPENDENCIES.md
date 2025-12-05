# Dependency Management

This document describes the dependency installation system for dev_skel skeletons.

## Overview

The dev_skel project has two levels of dependency management:

1. **System Dependencies** - Install framework tools (Node.js, Python, Java, Rust, etc.)
   - Located in `_skels/*/deps` (for skeleton development)
   - Managed by `./skel-deps` script at project root

2. **Project Dependencies** - Install packages for a generated project
   - Located in generated projects as `install-deps`
   - Automatically included when you generate a new project
   - Installs npm packages, pip packages, Maven dependencies, etc.

## Supported Operating Systems

- **macOS** (via Homebrew)
- **Ubuntu/Debian** (via apt)
- **Arch Linux** (via pacman)
- **Fedora/RHEL** (via dnf)

## Usage

### Install Dependencies for All Skeletons

```bash
./skel-deps --all
```

This will install all required dependencies for every skeleton in the project.

### Install Dependencies for a Specific Skeleton

```bash
./skel-deps java-spring-skel
# or without the -skel suffix
./skel-deps java-spring
```

### List Available Skeletons

```bash
./skel-deps --list
```

Shows all skeletons with indicators showing whether they have a deps script.

### Get Help

```bash
./skel-deps --help
```

## Individual Skeleton Dependencies

Each skeleton can also be managed independently:

```bash
cd _skels/java-spring-skel
./deps
```

## Project Dependency Installation

Each generated project includes an `install-deps` script that installs project-specific dependencies.

### After Generating a Project

```bash
# Generate a new project
make gen-fastapi NAME=myapi

# Navigate to the project
cd myapi

# Install project dependencies
./install-deps
```

### What install-deps Does

**For Python projects** (Django, FastAPI, Flask):
- Creates Python virtual environment (`.venv`)
- Upgrades pip
- Installs packages from `requirements.txt` or `pyproject.toml`
- Provides instructions for activating venv

**For Node.js projects** (js-skel, ts-react-skel):
- Runs `npm install`
- Installs all packages from `package.json`
- Displays project info

**For Java Spring projects**:
- Runs `mvn dependency:resolve`
- Runs `mvn install -DskipTests`
- Compiles and caches all dependencies

**For Rust projects** (Actix, Axum):
- Runs `cargo fetch`
- Runs `cargo build`
- Downloads and compiles all dependencies

### Example Workflow

```bash
# 1. Install system dependencies (one-time setup)
./skel-deps --all

# 2. Generate a new project
make gen-django NAME=myblog

# 3. Install project dependencies
cd myblog
./install-deps

# 4. Start development
source .venv/bin/activate  # For Python projects
python manage.py runserver
```

## Dependencies by Skeleton

### Java Spring (`java-spring-skel`)
- **JDK** (OpenJDK 21+)
- **Maven**

**Installation:**
- macOS: `brew install openjdk maven`
- Ubuntu: `apt-get install openjdk-21-jdk maven`
- Arch: `pacman -S jdk-openjdk maven`
- Fedora: `dnf install java-21-openjdk-devel maven`

### JavaScript (`js-skel`)
- **Node.js** (v20+)
- **npm**

**Installation:**
- macOS: `brew install node`
- Ubuntu: `apt-get install nodejs npm`
- Arch: `pacman -S nodejs npm`
- Fedora: `dnf install nodejs npm`

### Python Skeletons (`python-django-skel`, `python-fastapi-skel`, `python-flask-skel`)
- **Python 3** (3.10+)
- **pip**
- **venv**

**Installation:**
- macOS: `brew install python3`
- Ubuntu: `apt-get install python3 python3-pip python3-venv`
- Arch: `pacman -S python python-pip`
- Fedora: `dnf install python3 python3-pip`

### Rust Skeletons (`rust-actix-skel`, `rust-axum-skel`)
- **Rust** (via rustup)
- **Cargo**
- **Build tools** (platform-specific)

**Installation:**
- All platforms: Uses [rustup](https://rustup.rs/) installer
- Additional build dependencies installed per platform

### TypeScript Vite React (`ts-react-skel`)
- **Node.js** (v20+)
- **npm**

**Installation:** Same as JavaScript skeleton

## Examples

```bash
# List all skeletons and their status
./skel-deps --list

# Install dependencies for Java Spring
./skel-deps java-spring-skel

# Install dependencies for all Python frameworks
./skel-deps python-django
./skel-deps python-fastapi
./skel-deps python-flask

# Install everything at once
./skel-deps --all
```

## Notes

### macOS Requirements
- Requires [Homebrew](https://brew.sh) to be installed first
- Xcode Command Line Tools may be required for some packages

### Linux Requirements
- Most operations require `sudo` privileges
- Package names may vary slightly between distributions

### Rust Installation
- Installs via rustup (the official Rust installer)
- Adds `~/.cargo/bin` to PATH
- May require shell restart to use `cargo` and `rustc` commands

### Node.js Version
- Skeletons require Node.js 20+
- Ubuntu/Debian users may need to use [NodeSource](https://github.com/nodesource/distributions) for newer versions
- Consider using [nvm](https://github.com/nvm-sh/nvm) for version management

## Troubleshooting

### Command Not Found After Installation

**Rust/Cargo:**
```bash
source $HOME/.cargo/env
# or restart your shell
```

**Node.js (Ubuntu):**
If Node.js version is too old, install from NodeSource:
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Permission Denied

Ensure the scripts are executable:
```bash
chmod +x skel-deps
chmod +x _skels/*/deps
```

### Unsupported OS

The scripts support macOS, Ubuntu/Debian, Arch Linux, and Fedora/RHEL. For other distributions:
1. Check the deps script for your skeleton to see required packages
2. Install equivalent packages using your system's package manager
3. Or contribute a PR to add support for your distribution!

## Contributing

To add support for a new OS or skeleton:

1. Edit the relevant `deps` script
2. Add detection in the `detect_os()` function
3. Add installation commands in the `install_deps()` function
4. Test on the target platform
5. Update this documentation
