# Pizzeria Test Playbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `_bin/skel-test-pizzeria-orders` — a cross-stack integration test that generates a FastAPI + Flutter pizzeria ordering app via `skel-gen-ai` with domain-specific prompts, then exercises the full order lifecycle over real HTTP.

**Architecture:** Standalone Python script following the `_bin/skel-test-flutter-fastapi` pattern. Imports low-level helpers from `_bin/_frontend_backend_lib.py` (`http_request`, `wait_for_server`, `have_flutter`) but does NOT use `run_frontend_backend_integration()` — the pizzeria test calls `skel-gen-ai` (AI generation) instead of static `skel-gen`, and exercises a custom domain API instead of the generic items API. The script has three phases: generate (call skel-gen-ai with prompts), validate (run service tests), exercise (14-step HTTP flow against live backend).

**Tech Stack:** Python 3 stdlib, `_bin/_frontend_backend_lib.py` helpers, `_bin/skel-gen-ai` CLI, `_bin/dev_skel_lib.py` for `detect_root`/`load_config`.

**Spec:** `_docs/PIZZERIA-TEST-PLAYBOOK.md` — sections 3C, 4, and 9 define the deliverables.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `_bin/skel-test-pizzeria-orders` | Main test script (executable Python 3). Orchestrates: AI generation, service tests, server start, HTTP exercise, cleanup. |
| `Makefile` | Two new targets: `test-pizzeria-orders`, `test-pizzeria-orders-keep`. |

No other files are created or modified. The script produces artifacts under `_test_projects/test-pizzeria-orders/` (gitignored, cleaned on each run).

---

### Task 1: Create the test script with imports, constants, prompts, and arg parser

**Files:**
- Create: `_bin/skel-test-pizzeria-orders`

Steps cover: docstring, imports, constants, domain prompts from the playbook, test data, and argument parsing.

- [ ] **Step 1: Create the executable script file with all constants and arg parser**

Write the file with: shebang, module docstring, imports from `_frontend_backend_lib` (http_request, wait_for_server, have_flutter, EXIT_OK/FAIL/SETUP) and `dev_skel_lib` (detect_root, load_config, DevSkelConfig), project constants (PROJECT_NAME, skeletons, service names, port 18790), the three domain prompts (BACKEND_EXTRA, FRONTEND_EXTRA, INTEGRATION_EXTRA) verbatim from `_docs/PIZZERIA-TEST-PLAYBOOK.md` section 3B, test data constants (username, password, email, menu items list), and the `parse_args()` function with --keep, --port, --server-startup-timeout, --no-skip, --skip-flutter-build flags.

- [ ] **Step 2: Make the script executable**

Run: `chmod +x _bin/skel-test-pizzeria-orders`

- [ ] **Step 3: Verify the script parses args and imports cleanly**

Run: `python3 _bin/skel-test-pizzeria-orders --help`
Expected: usage text with all five flags shown, exit 0

---

### Task 2: Implement the Ollama probe and AI generation phase

**Files:**
- Modify: `_bin/skel-test-pizzeria-orders`

- [ ] **Step 1: Add ollama_reachable() helper**

Uses `http_request("GET", "http://localhost:11434/api/tags", timeout=5)` with try/except, returns bool.

- [ ] **Step 2: Add generate_pizzeria_project() function**

This function: cleans any existing wrapper, builds the skel-gen-ai command list with all --backend/--frontend/--backend-service-name/--frontend-service-name/--item-name/--auth-type/--backend-extra/--frontend-extra/--integration-extra/--no-input flags, sets SKEL_BACKEND_URL and PYTHONUNBUFFERED in env, runs via subprocess.run with 3600s timeout, prints elapsed time, then discovers service slugs by scanning .skel_context.json files in the wrapper subdirectories.

- [ ] **Step 3: Add _find_service_slug() helper**

Iterates wrapper subdirectories, reads .skel_context.json for service_name match. Falls back to slugified name. Raises RuntimeError if not found.

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import sys; sys.path.insert(0,'_bin'); exec(open('_bin/skel-test-pizzeria-orders').read()); print('syntax OK')"`
Expected: `syntax OK`

---

### Task 3: Implement the 14-step HTTP exercise function

**Files:**
- Modify: `_bin/skel-test-pizzeria-orders`

- [ ] **Step 1: Add exercise_pizzeria_api(backend_url) function**

Implements all 14 steps from `_docs/PIZZERIA-TEST-PLAYBOOK.md` section 4:
1. Register (POST /api/auth/register)
2. Login (POST /api/auth/login, extract JWT token)
3. Seed 3 menu positions (POST /api/menu)
4. List menu (GET /api/menu, assert >= 3)
5. Create order draft (POST /api/orders, assert status=draft)
6. Add 2 positions (POST /api/orders/{id}/positions)
7. Set delivery address (PUT /api/orders/{id}/address)
8. Verify order has positions + address (GET /api/orders/{id})
9. Update address (PUT /api/orders/{id}/address)
10. Submit order (POST /api/orders/{id}/submit, assert status=pending)
11. Approve with wait_minutes=25 + feedback (POST /api/orders/{id}/approve)
12. Create second order, submit, reject with feedback
13. Anonymous access rejected (GET /api/orders without token -> 401/403)
14. Invalid token rejected (GET /api/orders with bad Bearer -> 401/403)

Each step prints a numbered progress line on success. Assertion failures include the step context, expected vs actual, and raw response body. Tracks passed/total counter and prints summary.

Key robustness patterns from `exercise_items_api` in `_frontend_backend_lib.py`:
- Token extraction tries body["access"], body["access_token"], body["token"]
- List responses may be bare list or dict with "results"/"items" key
- Status checks accept 200 or 201 for creation endpoints
- Order detail positions may be under "positions" or "order_positions" key
- Address may be under "address" or "order_address" key

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import sys; sys.path.insert(0,'_bin'); exec(open('_bin/skel-test-pizzeria-orders').read()); print('syntax OK')"`
Expected: `syntax OK`

---

### Task 4: Implement the main() orchestrator

**Files:**
- Modify: `_bin/skel-test-pizzeria-orders`

- [ ] **Step 1: Add main() function with three phases and the if __name__ block**

Phase 0 (probes): Check ollama_reachable() — exit 2 if down and not --no-skip. Check have_flutter() — warn but continue if missing and not --no-skip.

Phase 1 (generate): Call generate_pizzeria_project(). Get back backend_slug and frontend_slug.

Phase 2 (service tests): Run backend's ./test script or .venv/bin/pytest if available. Run flutter test if Flutter is present. Print pass/fail but continue to Phase 3 even if AI-generated tests fail — the HTTP exercise is the authoritative check.

Phase 3 (HTTP exercise): Start uvicorn via subprocess.Popen with `[".venv/bin/python", "-m", "uvicorn", "app:get_app", "--factory", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"]`. Wait for server using wait_for_server() against /api/menu, then /api/health, then /docs as fallback probes. Call exercise_pizzeria_api().

Error handling: try/except for AssertionError, TimeoutExpired, RuntimeError, and generic Exception (matching the pattern from `run_frontend_backend_integration` in `_frontend_backend_lib.py`). On failure, dump last 4000 chars of server log.

Finally block: terminate server (SIGTERM then SIGKILL on timeout), close log file handle, clean up wrapper unless --keep.

- [ ] **Step 2: Verify the complete script loads and --help works**

Run: `python3 _bin/skel-test-pizzeria-orders --help`
Expected: full usage text, exit 0

---

### Task 5: Add Makefile targets and commit

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add test-pizzeria-orders to the .PHONY list**

On the lines around 35-37 that list `test-flutter-fastapi-keep test-flutter-cross-stack \`, add a new continuation line after it:

```
        test-pizzeria-orders test-pizzeria-orders-keep \
```

- [ ] **Step 2: Add the test targets after test-cross-stack (after line 593)**

```makefile

test-pizzeria-orders: ## AI-gen pizzeria integration test (FastAPI + Flutter, requires Ollama)
	@echo "$(GREEN)=== Pizzeria AI Generation + Integration test ===$(NC)"
	@_bin/skel-test-pizzeria-orders

test-pizzeria-orders-keep: ## Same, but leave _test_projects/test-pizzeria-orders on disk
	@_bin/skel-test-pizzeria-orders --keep
```

- [ ] **Step 3: Verify the targets are registered**

Run: `make -n test-pizzeria-orders`
Expected: prints the echo + script invocation commands without running them

- [ ] **Step 4: Verify the script exits cleanly when Ollama is down**

Run: `python3 _bin/skel-test-pizzeria-orders 2>&1; echo "exit=$?"`
Expected: if Ollama is not running, prints skip message and `exit=2`; if Ollama is running, the script will begin generation.

- [ ] **Step 5: Commit**

```bash
git add _bin/skel-test-pizzeria-orders Makefile
git commit -m "feat: add pizzeria AI generation + integration test

Add _bin/skel-test-pizzeria-orders: generates a FastAPI + Flutter
pizzeria ordering app via skel-gen-ai with domain-specific prompts,
then exercises the full order lifecycle (menu -> positions -> order ->
address -> submit -> approve/reject -> feedback) over real HTTP.

Makefile targets: test-pizzeria-orders, test-pizzeria-orders-keep.
Exits with code 2 when Ollama is unreachable (safe for CI).

Ref: _docs/PIZZERIA-TEST-PLAYBOOK.md"
```

---

### Task 6: Live integration test (requires running Ollama)

> **Note:** This task requires Ollama running with qwen3-coder:30b and Flutter SDK installed. Takes 10-30+ minutes. Skip if Ollama is not available.

- [ ] **Step 1: Verify Ollama is running**

Run: `curl -sf http://localhost:11434/api/tags | python3 -c "import sys,json; print([m['name'] for m in json.load(sys.stdin).get('models',[])])"`
Expected: list includes a qwen3 model

- [ ] **Step 2: Run the full test with --keep**

Run: `_bin/skel-test-pizzeria-orders --keep`
Expected: Phase 1 completes, Phase 2 runs tests, Phase 3 passes 14/14 HTTP checks, final: ALL CHECKS PASSED

- [ ] **Step 3: If any step fails, iterate on prompts**

Read the assertion message. Tighten BACKEND_EXTRA or FRONTEND_EXTRA prompts in the script constants to be more explicit about the failing endpoint's path/method/response shape. Re-run:
```bash
rm -rf _test_projects/test-pizzeria-orders
_bin/skel-test-pizzeria-orders --keep
```

- [ ] **Step 4: Verify no regressions in existing tests**

Run: `make test-ai-generators-dry`
Expected: passes

Run: `make test-generators`
Expected: passes
