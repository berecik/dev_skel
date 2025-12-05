# ts-react-skel

**Location**: `_skels/ts-react-skel/`

**Framework**: Vite + React + TypeScript + Vitest

## Structure

```
ts-react-skel/
├── Makefile
├── gen                  # Generator script
├── merge                # Merge overlay script
├── test                 # Test runner script (copied to generated project)
├── test_skel            # Skeleton E2E test script
├── deps                 # Check dependencies script
├── install-deps         # Install dependencies script
├── vite.config.ts       # Vite + Vitest config (overlay)
└── src/
    ├── App.tsx          # Sample App component (overlay)
    ├── App.css          # Sample App styles (overlay)
    ├── App.test.tsx     # Sample test file (overlay)
    ├── setupTests.ts    # Vitest setup (overlay)
    ├── components/
    │   └── .gitkeep
    └── hooks/
        └── .gitkeep
```

## How it Works

1. Uses `npm create vite@latest` (or pnpm/yarn/bun) to scaffold a base React+TypeScript project
2. Merges skeleton overlay files (vite.config.ts, src/App.*, setupTests.ts)
3. Patches package.json with project metadata and additional scripts
4. Installs additional dev dependencies (vitest, @testing-library/react, etc.)

## Dependencies Installed

Base (via create-vite):
- react, react-dom
- vite, @vitejs/plugin-react-swc
- typescript, eslint

Additional (installed by gen script):
- vitest
- @testing-library/react
- @testing-library/jest-dom
- jsdom
- @types/node

## Generation

From repo root:
```bash
make gen-react NAME=<target-path>
```

From skeleton dir:
```bash
./gen <target-path> [--name <project-name>] [--pm npm|pnpm|yarn|bun] [--template react-swc-ts|react-ts] [--no-install]
```

### Options

| Option | Description |
|--------|-------------|
| `--name` | Override project name (defaults to directory basename) |
| `--pm` | Package manager to use (defaults to npm or SKEL_PM env var) |
| `--template` | Vite template (defaults to react-swc-ts) |
| `--no-install` | Skip dependency installation |

## Generated Project Layout

When you generate a TS React project, the target path is the **wrapper directory** (`main_dir`) and the real Vite app lives in an inner `frontend/` directory (`project_dir`):

```text
myapp/
  README.md      # generic wrapper README (created by common-wrapper.sh)
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts that call ./frontend/run, ./frontend/test, ... (or underlying npm scripts)
  frontend/      # real Vite React project (package.json, src/, etc.)
```

Wrapper scripts in `myapp/` forward all arguments to the corresponding scripts in `frontend/`.

## Generated Project Usage

```bash
cd myapp

# Run tests (delegates to ./frontend/test / npm test)
./test

# Start development server (delegates to ./frontend/run / npm run dev)
./run dev

# Build for production (local Vite build)
./build --local

# Preview production build
npm run preview
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `./test` | Run Vitest tests, build, and lint |
| `npm run dev` | Start Vite dev server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run test` | Run Vitest tests |
| `npm run test:watch` | Run Vitest in watch mode |
| `npm run lint` | Run ESLint |
| `npm run format` | Run Prettier |

## Testing the Skeleton

```bash
cd _skels/ts-react-skel
make test
```

Or from repo root:
```bash
make test-react
```

## Configuration

The skeleton uses environment variables for project metadata (set in `_skels/_common/common-config.sh`):

| Variable | Description |
|----------|-------------|
| `SKEL_PROJECT_NAME` | Default project name |
| `SKEL_AUTHOR_NAME` | Author name for package.json |
| `SKEL_AUTHOR_EMAIL` | Author email |
| `SKEL_LICENSE` | License (defaults to MIT) |
| `SKEL_PM` | Default package manager |
| `SKEL_ORG` | GitHub organization |
| `SKEL_REPO` | Repository name |
