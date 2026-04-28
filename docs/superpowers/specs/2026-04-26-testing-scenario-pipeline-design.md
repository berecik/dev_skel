# Testing Scenario Pipeline -- Design Spec

## Summary

Add a `--testing-scenario` CLI flag and interactive dialog Step 7 to
`skel-gen-ai` and `skel-add`. Restructure the AI pipeline to separate
code generation (Phases 1-5) from test generation + fix loop (Phase 6).
The new Phase 6 generates tests in stages (cross-stack, E2E, then complex
scenario tests from `{testing_scenario}`), runs them, and iterates fixes
until green or timeout.

## 1. New CLI flag + dialog step

### CLI flag

```
--testing-scenario STRING
```

Added to both `skel-gen-ai` and `skel-add`. In `--no-input` mode, provides
the testing scenario directly. Exposed as `{testing_scenario}` placeholder
in prompts.

### Interactive dialog Step 7

```
Step 7/7: Testing scenario (optional, blank to skip)

  Describe what the generated tests should verify. Example:
  "Create 3 pizza menu items, place an order with 2 items,
   set delivery address, submit, approve with 25min wait time,
   reject a second order"

  Testing scenario: ___
```

### Data flow

- `FullstackChoices` dataclass gets `testing_scenario: str = ""`
- `GenerationContext` dataclass gets `testing_scenario: str = ""`
- `as_template_vars()` returns `"testing_scenario": self.testing_scenario
  or "(no testing scenario provided)"`
- Manifests can reference `{testing_scenario}` in any prompt template

## 2. Revised pipeline

```
Phase 1: Backend per-target generation         (unchanged)
Phase 2: Frontend per-target generation        (unchanged)
Phase 3: Integration -- sibling wiring         (unchanged)
Phase 4: Docs generation                       (was Phase 5)
Phase 5: Kubernetes lifecycle                  (was Phase 6)
Phase 6: Test generation + fix loop            (NEW)
```

### Phase 6 sub-steps

```
6a: Generate or update cross-stack integration tests
    - Backend: pytest test file exercising register, login,
      CRUD, order workflow via TestClient or live HTTP
    - Frontend React: vitest smoke test exercising the API
      client against live backend
    - Frontend Flutter: flutter_test smoke test exercising
      the API client against live backend

6b: Generate E2E tests
    - React: Playwright spec testing browser UI flow
    - Flutter: widget E2E test with LiveTestWidgetsFlutterBinding

6c: Run all tests (./test per service)

6d: If fail -> AI reads error output -> fixes ONLY the files
    referenced in the error -> goto 6a

6e: When 6a-6d loop is green -> generate complex scenario tests
    from {testing_scenario} (the main acceptance tests)
    - These are longer, multi-step integration tests that follow
      the user's described business flow

6f: Run all tests again (includes the new scenario tests)

6g: If fail -> AI reads errors -> fixes -> goto 6c

6h: Repeat 6a-6g until all green or timeout
```

### Skip flags

| Flag | Behavior |
|------|----------|
| `--no-test-fix` | Skip Phase 6 entirely |
| `--legacy-test-fix` | Run old Phase 4 behavior (patch-all-files) instead of new Phase 6 |
| `--no-integrate` | Skip Phase 3 (unchanged) |
| `--no-docs` | Skip Phase 4/docs (unchanged) |
| `--no-kube` | Skip Phase 5/k8s (unchanged) |

### Timeout

Phase 6 reuses `fix_timeout_m` from the integration manifest (default
120 min). The timeout covers the entire Phase 6, not each sub-step.

### Key difference from old Phase 4

Old: patches ALL source files on every failure (slow, unfocused).
New: generates specific test files first (6a, 6b, 6e), then when tests
fail it only fixes the files that error messages point to (targeted,
faster).

## 3. Test generation prompts

### 6a: Cross-stack integration test prompt

System prompt includes:
- The service's API surface (routes, models)
- `{testing_scenario}` for domain context
- `{backend_extra}` for domain model details
- Instruction: "Generate a test file that exercises the API via HTTP"

Per-stack targets:
- FastAPI/Django/Flask: `app/{service_slug}/tests/test_integration.py`
- Spring: `src/test/java/.../IntegrationTests.java`
- Rust: `tests/integration_test.rs`
- Go: `internal/handlers/handlers_test.go`
- React: `src/cross-stack.smoke.test.ts` (append to existing)
- Flutter: `test/cross_stack_smoke_test.dart` (append to existing)

### 6b: E2E test prompt

System prompt includes:
- The UI component structure
- `{testing_scenario}` for user journey flow
- Instruction: "Generate a browser/widget E2E test"

Per-stack targets:
- React: `e2e/scenario-e2e.spec.ts`
- Flutter: `test/scenario_e2e_test.dart`

### 6e: Complex scenario test prompt

System prompt includes:
- `{testing_scenario}` as the PRIMARY instruction
- All API endpoints and their request/response shapes
- Instruction: "Generate a comprehensive multi-step test that follows
  the testing scenario exactly"

Target: `test_scenario.py` / `scenario.test.ts` / `scenario_test.dart`
depending on the stack.

## 4. Fix loop mechanics (6d, 6g)

When tests fail:

1. Capture stderr + stdout (last 4000 chars)
2. Extract file names from error messages (tracebacks, compiler errors)
3. Read those specific files
4. Send to Ollama: "Here is the test output, here are the failing files.
   Fix the errors. Output only the fixed file contents."
5. Write the fixed files
6. Re-run tests

This is more targeted than the old Phase 4 which sent ALL service
files to Ollama on every failure.

## 5. Files to modify

| File | Change |
|------|--------|
| `_bin/skel-gen-ai` | Add `--testing-scenario` flag, Step 7 dialog, Phase 6 orchestration |
| `_bin/skel-add` | Pass `--testing-scenario` through to skel-gen-ai |
| `_bin/skel_ai_lib.py` | Add `testing_scenario` to `FullstackChoices`, `GenerationContext`, `as_template_vars()`. Add `run_test_generation_phase()` function. |
| `_bin/skel_rag/agent.py` | Support Phase 6 test generation via RagAgent |
| `_skels/_common/manifests/*.py` | Add `TEST_GENERATION_MANIFEST` with prompts for 6a/6b/6e |

## 6. Backwards compatibility

- Without `--testing-scenario`, Phase 6 still runs 6a-6d (generates
  basic cross-stack + E2E tests) but skips 6e (no scenario tests)
- `--legacy-test-fix` preserves the old behavior exactly
- `--no-test-fix` skips all testing as before
- Existing manifests that don't define `TEST_GENERATION_MANIFEST`
  fall back to the old Phase 4 behavior automatically
