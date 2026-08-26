---
name: python-coverage
description: Runs the pytest coverage gate (coverage.py via pytest-cov) in full mode (fail_under 95% branch coverage) or diff mode (diff-cover over changed lines for legacy repos), reads term-missing output, and closes uncovered lines and branches with modular tests. Use when finishing a task that changed project code, measuring test coverage, introducing the coverage gate, or diagnosing a failing coverage run.
---

# python-coverage

Coverage gate for the Python stack: `pytest-cov` (coverage.py) with a
threshold enforced by exit code, not by agent judgment. This catalog owns the
skill; packages come from PyPI.

Packages: `uv add --dev pytest-cov` (pulls in `coverage`); add
`uv add --dev diff-cover` only when the repo runs the gate in **diff mode**.
Config: merge sibling `PYPROJECT.md` `[tool.coverage.*]` tables into repo-root
`pyproject.toml` (copy only missing tables/keys; catalog defaults:
`source = ["project"]`, `branch = true`, `fail_under = 95`). diff-cover reads
no pyproject config — its gate is passed as CLI flags in the command below.

Pairs with `python-tests` (layout, fixtures, no patch), `python-polyfactory`
(test data), `python-freezegun` (clock). This harness is optional: install it
only when the user approves the coverage-gate capability; without it no other
rule changes.

## When to use

- **Finish any task that changed Python modules under `project/`** — the gate
  run is part of the definition of done (patched `python-workflow`, "Coverage
  gate after a task").
- Introduce the gate to a repository: merge the config tables and add the dev
  dependency (ask before touching an existing `pyproject.toml`).
- Diagnose a failing gate locally or in CI.

## Gate modes

| Mode | When | Gate |
|---|---|
| **full** | Greenfield repos, or baseline already at/above `fail_under` | pytest exit code: total branch coverage ≥ `fail_under` |
| **diff** | Legacy repos whose baseline cannot reach `fail_under` soon | `diff-cover`: every line changed vs `compare_branch` covered at 100% |

Pick the mode once when introducing the gate, not per run: if the full gate
passes on the current baseline, stay in full mode. Switch to diff mode only
with user approval. Diff mode keeps every new line covered while the total
creeps toward `fail_under`; re-evaluate occasionally — return to full mode
when the total reaches it.

## Run

Full mode:

```bash
uv run pytest tests/test_modules/ --cov --cov-report=term-missing
```

Diff mode:
```bash
uv run pytest tests/test_modules/ --cov --cov-report=term-missing --cov-report=xml:coverage.xml
uv run diff-cover coverage.xml --compare-branch=origin/master --fail-under=100
```

Substitute the target's actual main branch for `origin/master`.

Both modes:

- The gate covers the **modular** suite. Include `tests/test_e2e/` only when
  the live stack is actually up; never let a skipped e2e suite silently lower
  the number.
- Full mode: exit code is non-zero when total coverage is below `fail_under`.
- Diff mode: exit code is non-zero while any changed line is uncovered;
  `diff-cover` prints per-file percentages for changed lines.
- Optional for humans: add `--cov-report=html` and open `htmlcov/index.html`.
  The agent works from `term-missing` (both modes) and from `diff-cover` output.

Diff mode compares the working tree (staged and unstaged changes) against the
base branch — no commit needed before running the gate.

## Read the report

`term-missing` appends a `Missing` column per file:

| Missing entry | Meaning |
|---|---|
| `12` | Line 12 never executed |
| `34-36` | Range never executed |
| `45->48` | Partial branch: the true path ran, the jump to 48 did not (or vice versa) |

Sort work by impact: whole ranges and business components first, single
partial branches last. In diff mode, only changed lines are reported — still
fix them through behavior tests, not by excluding.

## Workflow

1. Run the gate command for the current mode.
2. On failure, list uncovered files/lines (`term-missing`, plus `diff-cover`
   output in diff mode).
3. Close each gap with a **modular test** per `python-tests`: observable
   behavior through a use case or endpoint (`api_client`), stubs injected via
   `Container.local(...)`, data from Polyfactory factories, clock frozen with
   `freeze_time`. One behavior per test; no `unittest.mock.patch`.
4. Re-run the gate. Done when it exits 0.
5. Repeat after every task that touched `project/`.

A partial branch usually means a missing error path: feed the use case the
failing input (adapter raising, empty result, invalid payload) and assert the
observable outcome.

## Never weaken the gate

- Do not lower `fail_under`, remove `branch = true`, or lower the diff
  threshold without explicit user approval.
- Do not add `# pragma: no cover`, `exclude_also` entries, or omits without
  explicit user approval.
- Prefer deleting genuinely dead code over excluding it.
- Defensive branches that cannot be exercised: propose the narrowest possible
  exclusion to the user; apply only after approval, then move on.

## Definition of done

The task is complete when the gate command for the active mode exits 0 (or
every remaining exclusion is explicitly user-approved), and the run covered
the modules the task changed.
