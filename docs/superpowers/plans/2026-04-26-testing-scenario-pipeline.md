# Testing Scenario Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--testing-scenario` flag + Step 7 dialog to skel-gen-ai, restructure the pipeline to separate code generation from test generation, and implement Phase 6 (test generation + fix loop).

**Architecture:** Three changes: (1) plumb `testing_scenario` through the data model and CLI, (2) reorder phases so tests come last, (3) implement `run_test_generation_phase()` with the staged 6a-6h loop. Old test-fix loop preserved behind `--legacy-test-fix`.

**Tech Stack:** Python 3, skel_ai_lib.py, skel-gen-ai CLI, Ollama LLM client

**Spec:** `docs/superpowers/specs/2026-04-26-testing-scenario-pipeline-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `_bin/skel_ai_lib.py` | Add `testing_scenario` to dataclasses + `as_template_vars()`. Add `run_test_generation_phase()`. |
| Modify | `_bin/skel-gen-ai` | Add `--testing-scenario` + `--legacy-test-fix` flags, Step 7 dialog, reorder phases, call Phase 6 |
| Modify | `_bin/skel-add` | Pass `--testing-scenario` through (automatic via execv) |

---

## Task 1: Add `testing_scenario` to data model

**Files:**
- Modify: `_bin/skel_ai_lib.py`

- [ ] **Step 1: Add `testing_scenario` to `FullstackChoices`**

At line ~918 in the `FullstackChoices` dataclass, add after `integration_extra: str`:

```python
    testing_scenario: str = ""
```

- [ ] **Step 2: Add `testing_scenario` to `GenerationContext`**

At line ~189 in the `GenerationContext` dataclass, add after `integration_extra: str = ""`:

```python
    testing_scenario: str = ""
```

- [ ] **Step 3: Add `testing_scenario` to `as_template_vars()`**

In the return dict at line ~293, add after the `integration_extra` entry:

```python
        "testing_scenario": self.testing_scenario or "(no testing scenario provided)",
```

- [ ] **Step 4: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('_bin/skel_ai_lib.py').read()); print('OK')"
```

---

## Task 2: Add CLI flags to skel-gen-ai

**Files:**
- Modify: `_bin/skel-gen-ai`

- [ ] **Step 1: Add `--testing-scenario` argument**

After the `--integration-extra` argument definition (line ~330), add:

```python
    fs.add_argument(
        "--testing-scenario",
        help=(
            "Testing scenario description for Phase 6 test generation. "
            "Describes what the generated tests should verify. Available "
            "to test generation prompts via the {testing_scenario} placeholder."
        ),
    )
```

- [ ] **Step 2: Add `--legacy-test-fix` flag**

After the `--no-test-fix` argument, add:

```python
    fs.add_argument(
        "--legacy-test-fix",
        action="store_true",
        help=(
            "Use the old Phase 4 test-fix behavior (patch all files on "
            "failure) instead of the new Phase 6 staged test generation."
        ),
    )
```

- [ ] **Step 3: Verify help output**

```bash
python3 _bin/skel-gen-ai --help | grep -A 2 "testing-scenario\|legacy-test-fix"
```

---

## Task 3: Add Step 7 to interactive dialog

**Files:**
- Modify: `_bin/skel_ai_lib.py`

- [ ] **Step 1: Update `prompt_fullstack_dialog()` to collect testing_scenario**

Find the Step 6 code block (line ~1178). After the integration_extra collection (line ~1206), add:

```python
    # Step 7: testing scenario ------------------------------------------- #
    print()
    print("  Step 7/7: Testing scenario (optional, blank to skip)")
    print()
    print('  Describe what the generated tests should verify. Example:')
    print('  "Create 3 menu items, place an order with 2 items,')
    print('   set delivery address, submit, approve with 25min wait"')
    print()
    chosen_testing_scenario = (
        testing_scenario
        if testing_scenario is not None
        else ask("Testing scenario", "")
    )
```

- [ ] **Step 2: Add `testing_scenario` parameter to the function signature**

Add `testing_scenario: Optional[str] = None` to the function's parameters.

- [ ] **Step 3: Include `testing_scenario` in the returned `FullstackChoices`**

In the return statement, add `testing_scenario=chosen_testing_scenario`.

- [ ] **Step 4: Update the summary printout**

After the line that prints `integration_extra` (if it exists), add:

```python
    if choices.testing_scenario:
        print(f"  Testing scenario  : {choices.testing_scenario}")
```

- [ ] **Step 5: Update the caller in skel-gen-ai**

In `_bin/skel-gen-ai`, where `prompt_fullstack_dialog()` is called, pass `testing_scenario=args.testing_scenario`.

- [ ] **Step 6: Pass `testing_scenario` to `GenerationContext`**

Where `GenerationContext` is constructed (in `_generate_per_target_overlay` or the full-stack flow), add `testing_scenario=choices.testing_scenario`.

- [ ] **Step 7: Verify dialog works**

```bash
echo "" | python3 _bin/skel-gen-ai --help 2>&1 | grep "Step 7"
```

---

## Task 4: Implement `run_test_generation_phase()`

**Files:**
- Modify: `_bin/skel_ai_lib.py`

- [ ] **Step 1: Add the function**

After `run_test_and_fix_loop()`, add the new function:

```python
def run_test_generation_phase(
    *,
    client: OllamaClient,
    ctx: GenerationContext,
    manifest: IntegrationManifest,
    progress: Optional[Any] = None,
) -> TestRunResult:
    """Phase 6: staged test generation + fix loop.

    6a: Generate cross-stack integration tests
    6b: Generate E2E tests
    6c: Run all tests
    6d: If fail -> fix referenced files -> goto 6a
    6e: When green -> generate scenario tests from {testing_scenario}
    6f-6h: Run + fix loop until green or timeout
    """
    import time

    timeout_s = manifest.fix_timeout_m * 60
    started = time.monotonic()
    test_cmd = manifest.test_command
    service_dir = ctx.project_dir

    def elapsed() -> float:
        return time.monotonic() - started

    def time_left() -> bool:
        return elapsed() < timeout_s

    if progress:
        progress.write("\n  ===== Phase 6: Test generation + fix loop =====\n")

    # --- 6a: Generate cross-stack integration tests ---
    if progress:
        progress.write("  [6a] Generating cross-stack integration tests...\n")
    _generate_test_file(
        client=client, ctx=ctx,
        test_type="cross-stack integration",
        instruction=(
            "Generate a cross-stack integration test that exercises the "
            "API via HTTP. Cover: register, login, CRUD for the main "
            "entity, auth enforcement (401 on anonymous). "
            f"Domain context: {{backend_extra}}\n"
            f"Testing scenario: {{testing_scenario}}"
        ),
        progress=progress,
    )

    # --- 6b: Generate E2E tests ---
    if progress:
        progress.write("  [6b] Generating E2E tests...\n")
    _generate_test_file(
        client=client, ctx=ctx,
        test_type="E2E browser/widget",
        instruction=(
            "Generate an E2E test that exercises the UI flow in a real "
            "browser or widget tree. Cover: login, navigate, create, "
            "verify. Testing scenario: {testing_scenario}"
        ),
        progress=progress,
    )

    # --- 6c-6d: Run tests + fix loop ---
    iteration = 0
    last_result = None
    while time_left():
        iteration += 1
        if progress:
            progress.write(
                f"\n  [6c] Running tests (iteration {iteration}, "
                f"{elapsed():.0f}s elapsed)...\n"
            )
        result = _run_service_tests(service_dir, test_cmd, progress=progress)
        last_result = result
        if result.passed:
            if progress:
                progress.write(f"  [6c] PASS in {result.duration:.1f}s\n")
            break
        if progress:
            progress.write(
                f"  [6d] FAIL (exit {result.returncode}), "
                f"asking AI to fix...\n"
            )
        if not time_left():
            break
        _fix_failing_files(
            client=client, ctx=ctx,
            test_output=result.output,
            progress=progress,
        )

    # --- 6e: Generate scenario tests (if testing_scenario provided) ---
    if (
        last_result and last_result.passed
        and ctx.testing_scenario
        and time_left()
    ):
        if progress:
            progress.write(
                "\n  [6e] Generating complex scenario tests from "
                "testing_scenario...\n"
            )
        _generate_test_file(
            client=client, ctx=ctx,
            test_type="complex scenario",
            instruction=(
                "Generate a comprehensive multi-step test that follows "
                "this testing scenario EXACTLY:\n\n"
                f"{ctx.testing_scenario}\n\n"
                "The test should exercise the full business flow "
                "described above, step by step, with assertions at each "
                "stage."
            ),
            progress=progress,
        )

        # --- 6f-6h: Run + fix loop for scenario tests ---
        while time_left():
            iteration += 1
            if progress:
                progress.write(
                    f"\n  [6f] Running all tests (iteration {iteration}, "
                    f"{elapsed():.0f}s elapsed)...\n"
                )
            result = _run_service_tests(
                service_dir, test_cmd, progress=progress,
            )
            last_result = result
            if result.passed:
                if progress:
                    progress.write(
                        f"  [6f] ALL PASS in {result.duration:.1f}s\n"
                    )
                break
            if progress:
                progress.write(
                    f"  [6g] FAIL (exit {result.returncode}), fixing...\n"
                )
            if not time_left():
                break
            _fix_failing_files(
                client=client, ctx=ctx,
                test_output=result.output,
                progress=progress,
            )

    if progress:
        status = "PASS" if (last_result and last_result.passed) else "FAIL"
        progress.write(
            f"\n  Phase 6 complete: {status} "
            f"({iteration} iterations, {elapsed():.0f}s)\n"
        )
    return last_result or TestRunResult(passed=False, returncode=1, output="", duration=0.0)
```

- [ ] **Step 2: Add helper `_generate_test_file()`**

```python
def _generate_test_file(
    *,
    client: OllamaClient,
    ctx: GenerationContext,
    test_type: str,
    instruction: str,
    progress: Optional[Any] = None,
) -> None:
    """Ask Ollama to generate a test file for the given service."""
    variables = ctx.as_template_vars()
    rendered_instruction = instruction.format_map(
        {k: v for k, v in variables.items()}
    )

    # Discover existing test files for context
    service_dir = ctx.project_dir
    test_files = []
    for ext in ("*.py", "*.ts", "*.dart"):
        test_files.extend(service_dir.rglob(f"test*/{ext}"))
        test_files.extend(service_dir.rglob(f"*test*.{ext.lstrip('*.')}"))

    existing_tests = ""
    for tf in test_files[:5]:  # limit context size
        try:
            content = tf.read_text(encoding="utf-8")
            if len(content) > 2000:
                content = content[:2000] + "\n... (truncated)"
            existing_tests += f"\n--- {tf.relative_to(service_dir)} ---\n{content}\n"
        except (OSError, UnicodeDecodeError):
            pass

    # Discover source files for API surface
    source_files = ""
    for pattern in ("app/**/*.py", "src/**/*.ts", "lib/**/*.dart"):
        for sf in service_dir.glob(pattern):
            if "__pycache__" in str(sf) or "node_modules" in str(sf):
                continue
            try:
                content = sf.read_text(encoding="utf-8")
                if len(content) > 3000:
                    content = content[:3000] + "\n... (truncated)"
                source_files += f"\n--- {sf.relative_to(service_dir)} ---\n{content}\n"
            except (OSError, UnicodeDecodeError):
                pass
            if len(source_files) > 20000:
                break

    system_prompt = (
        f"You are generating a {test_type} test for the "
        f"{ctx.skeleton_name} skeleton.\n\n"
        f"Service: {ctx.service_label} ({ctx.service_subdir})\n"
        f"Item entity: {variables['item_class']}\n"
        f"Auth: {ctx.auth_type}\n\n"
        f"EXISTING TEST FILES (for reference — follow the same patterns):\n"
        f"{existing_tests}\n\n"
        f"SOURCE FILES (API surface):\n"
        f"{source_files[:15000]}\n\n"
        f"Output ONLY the test file contents. No markdown fences."
    )

    response = client.chat(system_prompt, rendered_instruction)
    response = clean_response(response, _guess_language(ctx.skeleton_name))

    # Determine output file path
    test_dir = _find_test_dir(service_dir, ctx.skeleton_name)
    filename = _test_filename(test_type, ctx.skeleton_name)
    output_path = test_dir / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(response, encoding="utf-8")

    if progress:
        progress.write(f"    wrote {output_path.relative_to(service_dir)} ({len(response)} chars)\n")
```

- [ ] **Step 3: Add helper `_fix_failing_files()`**

```python
def _fix_failing_files(
    *,
    client: OllamaClient,
    ctx: GenerationContext,
    test_output: str,
    progress: Optional[Any] = None,
) -> None:
    """Parse test output for failing files, ask Ollama to fix them."""
    import re

    service_dir = ctx.project_dir
    # Extract file paths from error output
    file_pattern = re.compile(
        r'(?:File ["\']|at |in )([^\s"\']+\.(?:py|ts|tsx|dart|java|rs|go))'
    )
    mentioned = set()
    for match in file_pattern.finditer(test_output[-4000:]):
        path_str = match.group(1)
        # Resolve relative to service_dir
        for candidate in [
            service_dir / path_str,
            service_dir / path_str.lstrip("/"),
        ]:
            if candidate.is_file():
                mentioned.add(candidate)
                break

    if not mentioned:
        # Fallback: fix all test files
        for ext in ("*.py", "*.ts", "*.dart"):
            for tf in service_dir.rglob(f"test*/{ext}"):
                mentioned.add(tf)

    for fpath in sorted(mentioned)[:10]:  # cap at 10 files
        try:
            content = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        system = (
            f"Fix the errors in {fpath.name}. The test output shows:\n\n"
            f"{test_output[-3000:]}\n\n"
            f"Output ONLY the fixed file contents. No markdown fences."
        )
        fixed = client.chat(system, content)
        lang = fpath.suffix.lstrip(".")
        fixed = clean_response(fixed, lang)
        fpath.write_text(fixed, encoding="utf-8")

        if progress:
            progress.write(f"    fixed {fpath.relative_to(service_dir)}\n")
```

- [ ] **Step 4: Add helpers `_find_test_dir()`, `_test_filename()`, `_guess_language()`**

```python
def _find_test_dir(service_dir: Path, skeleton_name: str) -> Path:
    """Return the conventional test directory for the skeleton."""
    if "flutter" in skeleton_name:
        return service_dir / "test"
    if "react" in skeleton_name or "ts-" in skeleton_name:
        return service_dir / "src"
    if "spring" in skeleton_name or "java" in skeleton_name:
        return service_dir / "src" / "test" / "java"
    # Python / Rust / Go default
    for candidate in ["tests", "test", "app/tests"]:
        d = service_dir / candidate
        if d.is_dir():
            return d
    return service_dir / "tests"


def _test_filename(test_type: str, skeleton_name: str) -> str:
    """Return the filename for a generated test."""
    slug = test_type.replace(" ", "_").replace("-", "_")
    if "flutter" in skeleton_name:
        return f"{slug}_test.dart"
    if "react" in skeleton_name or "ts-" in skeleton_name:
        return f"{slug}.test.ts"
    if "spring" in skeleton_name or "java" in skeleton_name:
        return f"{slug.title().replace('_', '')}Test.java"
    if "rust" in skeleton_name:
        return f"{slug}_test.rs"
    if "go" in skeleton_name:
        return f"{slug}_test.go"
    return f"test_{slug}.py"


def _guess_language(skeleton_name: str) -> str:
    if "flutter" in skeleton_name:
        return "dart"
    if "react" in skeleton_name or "ts-" in skeleton_name or "next" in skeleton_name:
        return "typescript"
    if "spring" in skeleton_name or "java" in skeleton_name:
        return "java"
    if "rust" in skeleton_name:
        return "rust"
    if "go" in skeleton_name:
        return "go"
    return "python"
```

- [ ] **Step 5: Add `_run_service_tests()` helper** (if not already existing)

Check if there's an existing helper. If not:

```python
def _run_service_tests(
    service_dir: Path, test_cmd: str, *, progress: Optional[Any] = None,
) -> TestRunResult:
    """Run the service's test command and return the result."""
    import shlex, subprocess, time as _time

    cmd = shlex.split(test_cmd)
    if cmd and cmd[0].startswith("./"):
        cmd[0] = str((service_dir / cmd[0][2:]).resolve())

    start = _time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=service_dir,
            capture_output=True, text=True, timeout=300,
        )
        duration = _time.monotonic() - start
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return TestRunResult(
            passed=(proc.returncode == 0),
            returncode=proc.returncode,
            output=output[-4000:],
            duration=duration,
        )
    except subprocess.TimeoutExpired:
        return TestRunResult(
            passed=False, returncode=-1,
            output="Test command timed out after 300s",
            duration=300.0,
        )
```

- [ ] **Step 6: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('_bin/skel_ai_lib.py').read()); print('OK')"
```

---

## Task 5: Reorder phases + call Phase 6 in skel-gen-ai

**Files:**
- Modify: `_bin/skel-gen-ai`

- [ ] **Step 1: Move docs before test-fix, add Phase 6 call**

In the full-stack orchestration section (~line 1342), restructure:

```python
    # ----- Phase 4 (was 5): Documentation -------------------------------- #
    if not args.no_docs:
        # ... existing docs generation code ...
        pass

    # ----- Phase 5 (was 6): Kubernetes lifecycle ------------------------- #
    if not args.dry_run and not args.no_kube:
        # ... existing kube code ...
        pass

    # ----- Phase 6 (NEW): Test generation + fix loop -------------------- #
    if not args.no_test_fix:
        if args.legacy_test_fix:
            # Old behavior: patch-all-files loop
            final = run_test_and_fix_loop(
                client=client,
                ctx=backend_ctx,
                manifest=backend_integration,
                integration_results=integration_results,
                progress=_PROGRESS,
            )
        else:
            # New behavior: staged test generation
            from skel_ai_lib import run_test_generation_phase
            final = run_test_generation_phase(
                client=client,
                ctx=backend_ctx,
                manifest=backend_integration,
                progress=_PROGRESS,
            )
```

- [ ] **Step 2: Pass `testing_scenario` when constructing GenerationContext**

Find all places where `GenerationContext(...)` is constructed and add `testing_scenario=choices.testing_scenario`.

- [ ] **Step 3: Verify the script loads and --help works**

```bash
python3 _bin/skel-gen-ai --help | grep -E "testing-scenario|legacy-test-fix"
```

---

## Task 6: Verify end-to-end with a dry run

- [ ] **Step 1: Test the dialog with --testing-scenario flag**

```bash
echo "" | python3 _bin/skel-gen-ai test-dry \
    --backend python-fastapi-skel \
    --backend-service-name "Test API" \
    --item-name Task \
    --auth-type jwt \
    --testing-scenario "Create 3 tasks, complete 2, verify list" \
    --no-input --no-frontend --no-integrate --no-test-fix --no-docs \
    --dry-run 2>&1 | grep -i "testing scenario"
```

Expected: shows the testing scenario in the summary.

- [ ] **Step 2: Run existing test suites to verify no regressions**

```bash
./test
make test-generators
```

Expected: 8/8 skeleton e2e pass, 10/10 generators pass.
