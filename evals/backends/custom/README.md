# `custom` backend

Repository-owned runner for the experiment laboratory (plan A). It implements the
`Backend` protocol from `evals/core/backend_api.py` and is discovered by scanning
`evals/backends/*/backend.py` for the `BACKEND` export; `evals/RUNBOOK.md` covers
the backend-neutral workflow, so this file documents only what is specific here.

```bash
uv --cache-dir "$HOME/.cache/uv" run --no-project python -m evals.core.cli doctor --backend custom
uv --cache-dir "$HOME/.cache/uv" run --no-project python -m evals.core.cli doctor --backend custom --repair
uv --cache-dir "$HOME/.cache/uv" run --no-project python -m evals.core.cli \
    run --backend custom --task <probe> --subject-profile <alias> --judge-profile <alias> --include ...
```

## What this backend owns

| Concern | Where | Notes |
|---|---|---|
| Wall-clock supervision, cancellation | `supervisor.py` | one attempt = a forked child, process-group leader |
| Terminal artifacts on kill/crash | `supervisor.py` | the core's `finally` cannot run after `SIGKILL` |
| Attempts journal, incidents, bounded remedies | `repair.py` | knowledge API only, sanitized before writing |
| Readiness checks and safe repairs | `doctor.py` | read-only by default, `--repair` touches only owned paths |
| Run catalog, `status`, the operator marker | `backend.py` | `evals/history/<task>/<run-id>/` |

The core still owns materialization, the subject, deterministic checks, the judge
and the four normalized artifacts. This backend never re-implements them.

## Supervision

One attempt runs `evals.core.execute.execute_experiment` in a forked child that
calls `os.setsid()` first, so the whole tree (subject, checks, judge) is one
process group. The wall-clock budget is derived from the task's own stage
timeouts plus 300 s overhead; the supervisor never overrides a stage timeout,
because those are task data.

When the budget expires the group is killed with `SIGKILL`, and the supervisor
writes the run's terminal artifacts itself (`manifest.json`, `result.patch`,
`report.md`, `status.json`) with status `timeout`, including a partial patch of
whatever the attempt had produced. The same fallback covers a child that died
before writing artifacts (status `error`). A run directory therefore always ends
in a terminal state; core artifacts are never left half-written.

The budget is derived once, from the task's stage timeouts plus overhead, and the
supervisor never overrides a stage timeout. When the core asks a judge once more
for a rejected scorecard that stage may spend a second judge timeout; an attempt
that then outlives the whole budget is cancelled like any other overrun, with its
artifacts kept.

The child's stdout/stderr, including tracebacks, go to a raw log at
`memory/.tmp/evals/supervisor/<run-id>-attempt-<n>.log` (git-ignored scratch).
The operator-facing `HARNESS_EVAL_ARTIFACT=<run dir>` line is printed once per
run, by the parent, at the end — so a retried run still has exactly one canonical
handle.

Retries never reuse a run directory (`materialize` requires an empty one). The
previous attempt is renamed next to the canonical directory as `<run-id>.a1`,
`.a2`, …; those archives carry their own complete artifact set and are the
diagnostic history of the run.

## History and `status`

```text
evals/history/<task>/<run-id>/                 canonical run (last attempt)
                     <run-id>.a1/ …            archived earlier attempts
```

`status(run_id)` reads only that catalog: the terminal status from `status.json`,
`unfinished` when a manifest exists without a terminal marker, `running` when the
directory exists with no artifacts yet, `unknown` when nothing matches. Run
history is git-ignored and is never committed; the knowledge base holds only
sanitized, verified records.

## Repair loop

API: `python -m evals.core.cli ...` has no repair switch — the loop is part of
`run`. Order of operations for one run:

1. **Known incident.** Incidents whose `applicability` is a subset of
   `{backend, opencode_version}` are read from `evals/knowledge/incidents/`.
   A remedy this backend can apply is replayed *before* the first attempt and
   journalled as `incident_replay`; anything else is journalled as `skipped`.
2. **Attempt.** One supervised experiment. A deterministic `failed` run (checks
   failed) is the experiment's answer and ends the run — the repair loop does not
   chase it.
3. **Bounded remedies.** Only safe, distinct, backend-owned remedies are tried,
   at most three, and the same remedy never repeats:

   | Symptom kind | Remedy | Effect |
   |---|---|---|
   | `timeout` | `supervision_budget` | doubles the whole-attempt wall clock |
   | `command_failed` | `clean_retry` | retries from a clean run directory |
   | `provider_quota` | `quota_wait` | preflight only, never proposed as a retry: credited when a run is built on a reset that has already been waited out |
   | `provider_quota` | `judge_fallback` | preflight only: credited when the core judged with the fallback profile the fixed judge declares |

4. **Needs human.** `missing_model`, `unsupported_variant`, `malformed_json`,
   `isolation_error`, `invalid_task`, `invalid_scorecard`, `provider_quota`,
   `judge_fallback`, `output_limit`, `crash` stop immediately with the exact
   decision being asked for; the runner never picks a model, edits auth or global
   config, installs or updates OpenCode, or weakens permissions. The same stop
   happens when the remedies are exhausted (`repair loop stopped after …`).

After an attempt succeeded, `record_success` writes one incident through
`evals.core.knowledge.record_incident`. A replayed incident is credited only when
the first attempt succeeded; a remedy is credited when a later attempt succeeded.
Records are fingerprint-stable: stage, a normalized symptom and applicability
only — durations and error dumps stay in the run history — so repeating the same
defect increments `occurrences` and merges `failed_attempts` instead of creating
parallel records. Nothing is recorded for a failure that was never fixed.

## Provider quota holds

A provider that answers `429` with its own quota wording (`usage limit`, `quota`)
is not throttling: the shared core classifies it as `provider_quota`, keeps the
provider's sentence and stated reset in the run's `provider-quota.json`, and ends
the run as `error` even when the deterministic checks had already failed it. This
backend then owns the rule around it, in three steps:

1. **Record.** Every attempt is read for that diagnostic, which becomes a hold at
   `memory/.tmp/evals/quota/<provider>.json` (git-ignored scratch, replaced
   whenever the provider states a newer window). The hold is shaped like an
   incident — stage `custom_judge` / `custom_subject`, symptom
   `<role> provider_quota`, applicability `{backend, opencode_version, provider}`,
   remedy `quota_wait` — so the successful run can promote it through the shared
   knowledge API instead of a second format existing for the same fact.

2. **Refuse only when nothing can answer.** A closed window on the *subject*
   provider always refuses, because no profile can stand in for the subject. A
   closed *judge* provider refuses only when the fixed judge profile declares no
   usable fallback; with one declared, the run proceeds and the core judges with
   that profile (below). A refusal writes its terminal artifacts and stops before
   the first attempt, printing the provider's own sentence and the moment it
   named — the journal holds one `quota_hold` entry with result `active`, and the
   error names the file that clears it early. A provider that stated no reset
   leaves a hold that never expires on the clock — the backend never invents a
   moment the provider did not state.
3. **Wait it out, or use the declared fallback.** Once the stated moment has
   passed, the next run waits the window out; while it is closed and a fallback
   is declared, the run expects the fallback. Which of the two the run actually
   proved is read from its own evidence afterwards — `metrics.judge_fallback`
   says the fallback scored — and only that remedy is stored as the verified
   incident, after which the hold is removed. An intent is never credited, so a
   run that succeeded with the primary judge records nothing.

The provider's clock often carries no zone (`reset at 2026-09-18 20:18:27`). Such
a hint is read on the local clock — the one an operator compares it against — and
the record says so in `reset_timezone`, together with the verbatim `reset_hint`.
A wrong reading costs one attempt, never a silent loop, and
`rm memory/.tmp/evals/quota/<provider>.json` clears the hold by hand. The
fallback is declared in the judge profile (`fallback: <alias>`) and resolved by
`evals.core.profiles.resolve_fallback`: a missing, self-referential or unverified
alias is reported in the refusal instead of being used, so this backend never
substitutes a model — it waits, or uses the pair a human selected.

## Weak isolation (temporary, approval-gated)

This host cannot create unprivileged user/network namespaces at all (`unshare -Ur`
and `unshare -n` fail with `Operation not permitted`), which would keep every real
run fail-closed forever. With a **recorded human approval** —
`evals/knowledge/backends/custom.json` → `weak_isolation` (`approved_by`,
`approved_at`, `reason`), written through `record_backend_health` — runs use a
degraded boundary instead:

| Still enforced | Lost |
|---|---|
| materialized per-role OpenCode policy (`OPENCODE_CONFIG_DIR`/`OPENCODE_CONFIG_CONTENT`: permissions, sharing/auto-update/telemetry off, project-config discovery off) | pid/network/filesystem namespaces |
| subject shell allowlist, judge read-only | capability dropping, environment clearing for checks |
| run catalog, supervision, repair, sanitization | `/tmp` and `/workspace` mount isolation |

`doctor` reports `isolation: weak` while this is active and keeps a restoration
reminder in its notes; the manifest records `backend.ids.isolation = weak-approved`
so history never confuses degraded runs with sandboxed ones. An explicit
`subject_command`/`judge_command` (the core's override hook, used by tests) is
never overridden.

This module is temporary by design: the follow-up task on MY-45 removes it once
the host runs unprivileged namespaces again. Without the approval record nothing
changes — the core stays fail-closed.

Diagnosability on this host: the core reads subject and judge output through
pipes and keeps only the parsed result, so weak mode runs the real command
through a tee shim that appends the raw stream to
`memory/.tmp/evals/transcripts/<run-id>-<role>.jsonl` (git-ignored scratch, same
policy as the attempt logs) while forwarding the unchanged stream and exit code
to the parser.

## Doctor

`doctor` (no `--repair`) checks OpenCode, isolation (`bwrap` pid and network
namespace probes), the uv cache, the recorded profiles, the core's isolation
policy (it rebuilds the subject/check commands and asserts the pinned
`OPENCODE_CONFIG_DIR`, project-config and pure-mode settings plus the check
network namespace) and history writability. `status` is `success` only when
every blocking check passes — the CLI refuses to start a run otherwise, so a
broken prerequisite fails closed.

`doctor --repair` applies only what this backend owns: creating the git-ignored
`evals/history` directory and generating `evals/knowledge/INDEX.md` when missing.
Everything else is reported under `needs_human` with the exact command, because
it writes outside the workspace (prewarming the uv cache), changes the host
(namespaces, bubblewrap), or is a human decision (model selection).

Honest limits of the checks: the runner does not inspect the inherited
environment or auth files, so `OPENCODE_CONFIG_DIR` is verified as the *sandbox's*
guarantee for a run rather than as a host variable; and the network-namespace
probe observes this host, so a fail here is an environment prerequisite, not a
code defect.

## Gaps in the shared core (not forked here)

These remedies are listed by plan A but cannot be applied by a backend without
forking core behaviour, so they stop at the human boundary and are reported as
needs-human:

- **stage budgets** — per-stage timeouts come from `evals/tasks/<id>/task.json`;
  a backend cannot override them for one attempt. Only the whole-attempt wall
  clock is adjustable here.
- **JSON format** — OpenCode output is parsed inside `evals/core/checks.py`. The
  core keeps every judge reply as `judge-response.txt` and asks exactly once more
  with an explicit only-a-JSON-object instruction, so a final `malformed_json`
  reaches this backend with its raw evidence already on disk.
- **variant and argument order** — `opencode_command` composition lives in
  `evals/core/sandbox.py`, and the profile is a human-verified record; changing
  either silently would be a model change.
- **local OpenCode configuration** — the core materializes an isolated config per
  role; editing the host's config is a human action.

`malformed_json` (after the core's single retry), `unsupported_variant` and
`missing_model` are therefore classified as needs-human rather than retried.

## Tests

```bash
uv --cache-dir "$HOME/.cache/uv" run --no-project python -m unittest discover \
    -s evals/backends/custom/tests -t .
```

The suite uses a throwaway repository under `memory/.tmp/evals/` and scripted
subject/judge commands (`RunRequest.subject_command` / `judge_command`, the core's
test override), with the isolation boundary replaced exactly as
`evals/tests/test_execution.py` does. Because supervision forks, the inherited
`mock.patch.object(checks, 'run_isolated', …)` reaches the child; marker
assertions read the parent's single `HARNESS_EVAL_ARTIFACT` line.
