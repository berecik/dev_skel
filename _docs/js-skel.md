# js-skel

**Location**: `_skels/js-skel/`

**Framework**: Plain JavaScript/Node.js

## Structure

```
js-skel/
├── Makefile
├── .gitignore
├── .editorconfig
├── .prettierrc
├── eslint.config.js
├── src/
│   ├── index.js
│   └── index.test.js
└── (node_modules, package-lock.json - copied)
```

## Generation Notes

- Uses `npm init -y` to create package.json
- Copies skeleton files
- Runs `npm install`

## Generation

From repo root:
```bash
make gen-js NAME=<target-path>
```

From anywhere:
```bash
_bin/skel-gen js <target-path>
```

From skeleton dir:
```bash
./gen <target-path>
```

## Generated Project Usage

```bash
cd myapp
node src/index.js
npm test
```

## Testing

Test the skeleton (E2E):
```bash
cd _skels/js-skel
make test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.

### Merge Script Exclusions

- `package.json`
- `package-lock.json`
