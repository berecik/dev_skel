# Iterative-`./ai` Test Playbook: Pizza Reservation

> **Canonical reference for the pizza-reservation scenario** — the
> companion to `_docs/PIZZERIA-TEST-PLAYBOOK.md` that exercises the
> built-in `./ai` agent's *iterative refactor capability* on a
> non-trivial multi-file change.
>
> **Audience:** Claude Code, Junie, and any LLM agent tasked with
> running or extending this scenario.

---

## 1. Purpose

The original pizzeria playbook (`_bin/skel-test-pizzeria-orders`)
proves the *one-shot* AI generation pipeline can produce a domain-
specific app from prompts. This playbook proves something different:
**given a working pizzeria app, can the built-in service-level
`./ai` agent iteratively refactor it to add a new feature without
breaking what was already there?**

This is a regression-and-extension contract:

* **V_pizza** (regression) — every check from the pizzeria flow must
  still pass after the refactor. The user must still be able to
  query the catalog and place pizza orders.
* **V_reservation** (new feature) — the system must accept a table
  booking with a valid date + time, persist it, and reject malformed
  payloads.

The scenario is one of the canonical signals that the `./ai` agent
is production-grade enough to drive incremental development on a
generated project.

---

## 2. Files

| Path | Purpose |
|------|---------|
| `_bin/skel-test-pizza-reservation` | Runner script (executable Python 3) |
| `_docs/PIZZA-RESERVATION-PLAYBOOK.md` | This document |
| `Makefile` | `test-pizza-reservation` / `-keep` targets |

The runner **reuses** the pizzeria generation step + the 14-step HTTP
exercise via `importlib.SourceFileLoader`, so any prompt or contract
change in `_bin/skel-test-pizzeria-orders` automatically flows
through. There is no copy-pasted state to keep in sync.

The generated wrapper lands at `_test_projects/test-pizza-reservation/`
— a separate directory from `test-pizzeria-orders/` so both scenarios
can run concurrently and neither stomps on the other's `--keep`
artefacts.

---

## 3. Execution Flow

```
Phase 0: Pre-flight
  - Ollama reachable at $OLLAMA_HOST (skip otherwise).

Phase 1: Generate the pizzeria baseline
  - Delegates to skel-test-pizzeria-orders' generate_pizzeria_project()
    so the starting state IS the pizzeria playbook's end state.
  - Same backend/frontend skeletons, same prompts, different wrapper
    directory.

Phase 2: V_pizza baseline (the starting state must be healthy)
  - Start backend on port 18792.
  - Run the canonical 14-step HTTP order lifecycle.
  - If this fails, the generated app is broken; bail before invoking
    the agent on a broken base.
  - Stop the backend (./ai will restart it).

Phase 3: git init the wrapper
  - ./ai apply refuses to run against a dirty git tree without
    --allow-dirty. Make the wrapper a fresh repo so the agent's
    diff is reviewable against a known checkpoint.

Phase 4: Invoke ./ai with the reservation prompt
  - ./ai <backend_slug> apply "<RESERVATION_PROMPT>"
  - The agent runs the LM, applies diffs, then loops the service's
    own ./test command with a fix model until tests pass (or
    --fix-timeout-m is exhausted).
  - Default timeout: 30 minutes (override with --ai-timeout-m).

Phase 5: V_pizza regression
  - Restart backend (./ai may have added migrations or new tables).
  - Re-run the same 14 HTTP steps.
  - If the first attempt fails (typical: agent left an unresolved
    import or removed a wrapper-shared helper), the runner triggers
    `_recover_pizza_baseline_files`:
        * `git diff --name-only baseline` to find every file the
          agent touched.
        * Restrict to files under `_PIZZA_BASELINE_PREFIXES`
          (`app/wrapper_api/`, `app/orders_api/`, `core/`, etc.).
        * Restore each candidate via `git checkout baseline -- <path>`.
        * Untracked files in guarded prefixes are DELETED (the
          agent shouldn't be adding modules inside wrapper-shared
          code anyway).
        * Files OUTSIDE the guarded prefixes (typically the agent's
          new reservation module if it chose a sensible location)
          are preserved.
  - The shared SQLite is wiped before each attempt so the
    `register` step doesn't 409 on the previous run's seeded user.
  - MUST pass. The agent prompt explicitly asks for the ordering
    contract to remain intact.

Phase 6: V_reservation
  - Probe RESERVATION_ENDPOINT_CANDIDATES x _candidate_bodies() until
    one accepts a valid booking (POST <endpoint> -> 2xx).
  - Soft-check persistence (GET <endpoint>/{id} or GET <endpoint>).
  - POST with the date field missing  -> assert 4xx.
  - POST with the date field set to garbage -> assert 4xx.
```

Exit codes:

| Code | Meaning |
|------|---------|
| 0 | every check passed (V_pizza baseline + regression + V_reservation) |
| 1 | at least one assertion failed |
| 2 | Ollama unreachable (setup skip — safe for CI) |

---

## 4. The Agent Prompt

The literal prompt passed to `./ai apply`:

> Modify the existing pizzeria application to implement a table
> reservation system. Customers must be able to book a table for a
> specific date and time (hour) in addition to ordering pizzas. Ensure
> that all existing pizza ordering endpoints, logic, and tests remain
> fully functional. Do not break compatibility or change existing API
> contracts for ordering.

This is intentionally **high-level natural language**. The scenario
tests whether `./ai` can:

1. Read the existing project tree (catalog + orders backend).
2. Decide a sensible API shape for reservations.
3. Add the new endpoints, models, and persistence.
4. Keep the original ordering endpoints working.
5. Self-verify by running `./test` and looping with the fix model
   if the generated code breaks anything.

`V_reservation` is deliberately tolerant of multiple plausible
endpoint + body shapes (see `RESERVATION_ENDPOINT_CANDIDATES` and
`_candidate_bodies()`) — the scenario does not prescribe the API; it
verifies the *behaviour*.

---

## 5. Running

```bash
export OLLAMA_HOST=paul                         # or localhost
make test-pizza-reservation                     # full run, cleans on exit
make test-pizza-reservation-keep                # leaves wrapper on disk

# Direct invocation with options:
_bin/skel-test-pizza-reservation --keep --ai-timeout-m 45

# Iterating on the agent prompt + V_reservation only:
_bin/skel-test-pizza-reservation --keep --skip-baseline-check
```

Typical wall-clock budget:

* Phase 1 (gen): 5–10 min (model dependent)
* Phase 2 (baseline): 30–60 s
* Phase 4 (./ai apply): 5–20 min (heavily prompt + model dependent)
* Phase 5 + 6 (verification): 60–90 s

Total: 12–30 min per full run.

---

## 6. Definition of Done

The scenario is complete only when ALL of these are true:

1. `make test-pizza-reservation` exits 0 against a reachable Ollama.
2. The runner prints `=== ALL CHECKS PASSED (V_pizza + V_reservation) ===`.
3. The wrapper-shared 14-step HTTP exercise passes BOTH before AND
   after `./ai apply` runs (the regression contract).
4. The new reservation endpoint accepts a valid `{date, time, ...}`
   POST and rejects bodies with the date field missing or malformed.
5. The runner is registered in `Makefile`'s `.PHONY` list and visible
   in `make help`.
6. This document and `CLAUDE.md` section 2 accurately describe the
   scenario.

---

## 7. Troubleshooting

**`./ai apply` exits non-zero / times out**
The agent's own fix-loop hit its budget without going green. Re-run
with `--keep --ai-timeout-m 60`; inspect
`_test_projects/test-pizza-reservation/orders_api/.ai/HEAD/` for the
proposal + RATIONALE, and `.ai/memory.jsonl` for the per-run history.

**V_pizza baseline (Phase 2) fails**
The pizzeria generation itself is broken — fix that first via
`make test-pizzeria-orders-keep` before iterating on this playbook.

**V_pizza regression (Phase 5) fails**
The agent broke the ordering contract. Inspect the diff with
`git -C _test_projects/test-pizza-reservation diff baseline HEAD` to
see exactly what changed. Tighten the prompt if needed (but keeping
this scenario's prompt deliberately high-level is part of the test —
prefer fixing the agent's behaviour instead).

**V_reservation (Phase 6) fails on every endpoint candidate**
Add a new entry to `RESERVATION_ENDPOINT_CANDIDATES` or
`_candidate_bodies()` if the agent legitimately chose an unusual
shape; otherwise the agent failed to implement the feature.

A specific failure mode the runner has surfaced in practice: the
LLM places reservation routes inside `app/wrapper_api/` (e.g. as a
new `routes.py`) and modifies wrapper-shared modules
(`order_models.py`, `db.py`, etc.) to import them. When the agent
then leaves the wrapper-shared code in a broken state (e.g. a
half-extracted enum import), V_pizza fails on server-start; the
selective rollback restores `app/wrapper_api/` to baseline, which
also wipes the agent's reservation routes. V_reservation then
reports no endpoint candidate matched. This is an honest signal
that the iterative agent didn't pick an isolation boundary
compatible with the wrapper-shared layout — improvements should go
into the agent prompt or its retrieval context, NOT into the
playbook (the scenario's job is to report the gap).

**./ai apply spins on `AttributeError("'RagAgent' object has no
attribute 'agent'")`**
Pre-2026-05-20 regression that surfaced when wiring the runtime to
RagAgent directly. Fixed by duck-typing `_ask_ollama_to_fix` in
`_bin/skel_ai_lib.py` to accept either an `OllamaClient` (whose
`.agent` property yields a `RagAgent`) or a `RagAgent` directly. If
you see this again, verify the duck-type code is still present.
