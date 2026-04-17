# Claude Code Rules — `next-js-skel`

Claude-specific complement to `_skels/next-js-skel/AGENTS.md` and
`_skels/next-js-skel/JUNIE-RULES.md`. Read those first.

---

## 1. Read These Files First (in order)

1. `_skels/next-js-skel/CLAUDE.md` (this file)
2. `_skels/next-js-skel/AGENTS.md`
3. `_skels/next-js-skel/JUNIE-RULES.md`
4. `_docs/next-js-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Plain Node.js / JavaScript skeleton (used for backend tools, scripts,
  or simple Node services). Generates into `<wrapper>/<service_slug>/`
  (or `<wrapper>/app/` when no service name is given).
- **Shared env contract** (CRITICAL): `src/config.js` loads
  `<service>/.env` first then `<wrapper>/.env` via the `dotenv` package
  (`first wins`, so local overrides survive). It exposes a single `config`
  object with `databaseUrl`, `jwt.{secret,algorithm,issuer,accessTtl,
  refreshTtl}`, and `service.{host,port}`. Import it via
  `import { config } from './config.js'` — do not reach into
  `process.env` directly in handler code. Never hardcode a JWT secret or
  database URL: every service in the wrapper relies on the same
  env-driven values so a token issued by the JS service is accepted by
  every other service.

---

## 3. Claude Operational Notes

1. **`Read` before editing** any source file or generator script.
2. **Plan dependency bumps** (npm packages, Node version) and confirm
   scope with the user before editing `package.json`.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/next-js-skel && make test
   ```
4. Never hand-edit `_test_projects/test-js-app` — regenerate with
   `make gen-nextjs NAME=_test_projects/<name>`.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green.
- [ ] JS skeleton-specific tests pass.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
