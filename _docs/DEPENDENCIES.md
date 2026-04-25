# Dependency Management

Dev Skel has **three** layers of dependencies:

1. **AI runtime** — Ollama + an instruction model (default
   `qwen3-coder:30b`). Required for `_bin/skel-gen-ai`, the per-service
   `./ai`, and the `./ai upgrade` flow. The static fallback
   (`_bin/skel-gen-static`) and the `./backport` flow do **not** need
   Ollama.
2. **Per-stack toolchains** — Python, Node, JDK, Rust, Flutter,
   `make`. Installed via `./skel-deps`.
3. **Per-project deps** — `pip install`, `npm install`, `mvn`,
   `cargo build`, `flutter pub get`. Installed via the per-project
   `install-deps` script that ships in every generated wrapper.

This document covers all three.

## Supported Operating Systems

- **macOS** (via Homebrew)
- **Ubuntu/Debian** (via apt)
- **Arch Linux** (via pacman)
- **Fedora/RHEL** (via dnf)

## AI runtime (Ollama + RAG)

The AI generator (`_bin/skel-gen-ai`) and the per-service `./ai`
runtime both call Ollama over HTTP. You need a running Ollama daemon
and at least one instruction model pulled.

### Install Ollama

* macOS: `brew install ollama`
* Linux: `curl -fsSL https://ollama.com/install.sh | sh`
* Other: see [ollama.com](https://ollama.com)

### Pull a model

```bash
ollama serve &                    # in another terminal (or as a service)
ollama pull qwen3-coder:30b            # default; ~19 GB; needs ~24 GB VRAM
# Lighter alternatives for slower hardware:
ollama pull qwen3-coder:30b
ollama pull qwen2.5-coder:7b
```

### Tune via env vars

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `OLLAMA_HOST` | `localhost:11434` | Primary knob (`host:port`). Set this for a remote Ollama. |
| `OLLAMA_BASE_URL` | _(derived from `OLLAMA_HOST`)_ | Optional override when you need a custom scheme or path. |
| `OLLAMA_MODEL` | `qwen3-coder:30b` | Use a smaller model on slower hardware. |
| `OLLAMA_TIMEOUT` | `1800` (s) | Sized for a 30B-class cold load + multi-minute completions on a long file. |
| `SKEL_REFACTOR_FIX_TIMEOUT_M` | `15` (min) | Fix-loop budget for `./ai apply`. |
| `SKEL_REFACTOR_MAX_FILES` | `8` | Hard cap on files the LLM may edit per `./ai` run. |
| `DEV_SKEL_ROOT` | unset | Force the in-service `./ai` into in-tree mode against a specific dev_skel checkout. |

### Optional: in-tree FAISS dependencies

In-tree mode (when a dev_skel checkout is reachable) uses a real RAG
pipeline — tree-sitter chunker + FAISS index + sentence-transformers
embedding model + LangChain Ollama chat. Install once:

```bash
make install-rag-deps
```

This adds `sentence-transformers`, `faiss-cpu`, `langchain-ollama`
(plus their tree-sitter friends). The default embedding model is
`BAAI/bge-small-en-v1.5`.

The **out-of-tree** `./ai` mode (when a service is detached from any
dev_skel checkout) does **not** need these — it uses ripgrep + a
pathlib fallback for retrieval and a stdlib-only `urllib.request`
call to Ollama. So you can ship a generated service to a colleague
without dev_skel installed and `./ai` keeps working.

### Verify the setup

```bash
curl -sf http://localhost:11434/api/tags > /dev/null && echo OK
ollama list

make test-ai-generators-dry      # always cheap; no LLM calls
_bin/skel-gen-ai myproj --no-input --dry-run  # full dialog scripted, no writes
```

## GitHub CLI (optional — for `make ci-status` / `ci-watch` / `ci-log`)

The CI inspection targets use the **GitHub CLI** (`gh`):

```bash
brew install gh          # macOS
# or: https://cli.github.com/ for other platforms
gh auth login            # one-time authentication
```

Not required for generation, testing, or the AI surfaces — only for
viewing CI run status from your terminal.

---

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

**For Node.js projects** (next-js-skel, ts-react-skel):
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

### JavaScript (`next-js-skel`)
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

### Flutter (`flutter-skel`)
- **Flutter SDK** (3.0+)
- **Dart** (bundled with Flutter)

**Installation:**
- All platforms: see [docs.flutter.dev/get-started/install](https://docs.flutter.dev/get-started/install)
- macOS: `brew install --cask flutter`
- Verify: `flutter doctor`

`make test-flutter-django-bolt` and `make test-flutter-fastapi`
auto-skip when the Flutter SDK is not on the PATH, so this dep is
only required if you want to generate Flutter projects.

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
