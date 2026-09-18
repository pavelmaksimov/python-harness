# Harness evaluation runbook

Agent-facing workflow for the backend-neutral evaluation core in `evals/`. Read
this before testing a harness, module, provider, or repeating an experiment.

All commands run from the repository root:

```bash
uv --cache-dir "$HOME/.cache/uv" run --no-project python -m evals.core.cli <command> ...
```

The core is standard-library only; `--no-project` keeps the repository
`pyproject.toml` out of the way. `--cache-dir` points uv at the machine's
pre-warmed cache, which sandboxes that mount it read-only otherwise reject. Backends are discovered by scanning
`evals/backends/*/backend.py` for a `BACKEND` export, so this file never names a
backend-specific command; each backend documents its own prerequisites in
`evals/backends/<name>/README.md`.

## 1. Turn the request into a plan

```bash
... python -m evals.core.cli plan --module <alias> --subject-profile <alias> \
    --judge-profile <alias> --include '1-6,25-26' --exclude 2
```

`--include` / `--exclude` accept numbers, ranges, `всё`, `всё стандартное`,
`кроме` and `исключи`. The command prints one line with the source numbers and
the fully expanded catalog IDs, then the resolved task and profiles.

Completion criterion: the printed line lists exactly the requested numbers plus
the closed-over companions; `needs_human_choice` is empty.

Stop and explain the dependency instead of running when the output reports:

- a required companion was explicitly excluded (dependency conflict);
- a requested harness has no probe yet, or the probe does not cover the
  selected IDs (`нужно отдельное ограниченное задание`) — propose that narrower
  task instead of widening this one. `всё стандартное` therefore means every
  non-optional harness that a current probe can exercise.

Numbering and the "number → catalog ID" mapping live only in
`evals/HARNESS_MATRIX.md`.

## 2. Resolve the model profile

A profile is a verified `provider/model` + `variant` pair, stored per alias in
`evals/knowledge/providers/<alias>.json`.

```bash
... python -m evals.core.cli profiles                 # already verified profiles
... python -m evals.core.cli profiles --provider openrouter
```

With no verified profile the discovery command prints 2–5 candidates and
nothing runs yet: ask the human to pick one, then run a smoke experiment and
record the profile with `--record` and the required success proof
(`verification.status: success`, matching run id, provider, model, variant,
opencode version, `human_selected: true`). Never substitute a model silently.
The judge is a separate fixed profile; when it is missing, the same selection
process applies to it.

Completion criterion: `plan` reports a resolved subject and judge profile, and
each was recorded only after a successful run.

## 3. Run the experiment

```bash
... python -m evals.core.cli run --backend <name> --task <id> \
    --subject-profile <subject> --judge-profile <judge> --include ... --exclude ...
```

Prerequisites, in order:

1. `... python -m evals.core.cli doctor --backend <name>` reports readiness
   (`doctor --repair` only applies safe, documented remedies).
2. The Git checkout is clean — a run refuses to start otherwise.
3. The backend supports the required isolation on this host. If a backend
   cannot enforce its isolation (no user namespaces, no sandbox helper), the
   run fails closed; record that as a prerequisite in the backend README rather
   than running with weakened isolation.

The run materializes an isolated workspace from `evals/_fixtures/base-project`,
the task fixture and the task's `materialize` entries, executes the subject,
runs the task's deterministic `checks`, then a read-only judge. Subject
commands are limited to the workspace and the narrow allowlist; the judge never
writes. The CLI puts run artifacts in `evals/history/<task>/<run-id>/`
(git-ignored, never committed); a backend passes its own name, version and IDs
to `execute_experiment(..., backend=...)` so the manifest names the producer.

Completion criterion: the process prints `HARNESS_EVAL_ARTIFACT=<run dir>` and
the run directory holds `manifest.json`, `result.patch`, `report.md` and
`status.json`. Failed and timed-out runs also produce artifacts — keep them as
diagnostic history.

## 4. Read the evidence

```bash
... python -m evals.core.cli validate <run dir>/manifest.json
```

Then read `manifest.json` for selection, profiles, attempts, checks and metrics,
`result.patch` for the produced diff, and `report.md` for the judge scorecard
(0–4 with per-file evidence). Run history for real experiments lives in
`evals/history/<task>/<run-id>/`; generated knowledge index:
`evals/knowledge/INDEX.md`.

Completion criterion: the manifest validates, and every check has evidence.

## 5. Compare runs

```bash
... python -m evals.core.cli compare <run-a> <run-b>
```

Comparison reads only normalized manifests, never backend storage, and refuses
when task or rubric hashes differ. It reports selection, source commits,
profiles, backend and version, checks, structural metrics, judge score, attempt
and repair counts, wall time and patch differences. Any pairing works:
custom↔custom, orx↔orx, custom↔orx.

Completion criterion: the report names the differing dimensions (harness,
model, knowledge revision) explicitly instead of a bare score delta.

## 6. Reuse accumulated experience

After a failure, look up the incident by stage, symptom and OpenCode version in
`evals/knowledge/incidents/<fingerprint>.json`; apply the verified remedy and
skip the recorded dead ends. Record an incident only after a later run
succeeded, with the confirmation proof. With no record, make at most three
distinct safe diagnostic attempts, then stop and ask.

Records are written through the core API only (`record_incident`,
`record_provider_profile`, `record_backend_health`) so sanitization always runs:
tokens, absolute home paths and environment contents never reach tracked files.
Knowledge never enters the subject prompt.

Completion criterion: a repeated failure with a known fingerprint costs one
remedy attempt, not a fresh investigation.

## 7. Re-check after a harness change

```bash
... python -m evals.core.cli select --changed-from <ref>
```

Lists the probes whose materialized harness sources changed, so only the
affected probes are re-run.

Completion criterion: each listed probe has a fresh run, or a stated reason it
is unaffected.

## task.json contract

`evals/tasks/<id>/task.json` is the probe definition the core consumes; keys:

| Key | Meaning |
|---|---|
| `id` | Probe ID; must equal the directory name. |
| `aliases` | Words a request may use instead of the ID. |
| `covered_numbers` | Matrix numbers this probe actually exercises. |
| `base_fixture` | Fixture copied first; defaults to `evals/_fixtures/base-project`. |
| `fixture` | Probe fixture copied over the base. |
| `materialize` | `{kind: rule\|skill\|template, from, to, harness_id?}` — repository source → workspace destination; `from` must exist in the repository. |
| `prompt` / `prompt_file` | Subject instruction. |
| `rubric` / `rubric_file` | Criteria the judge scores 0–4. |
| `checks` | `{id, kind: 'shell', command, timeout_seconds?}` run in the workspace root with no network. |
| `subject_timeout_seconds`, `check_timeout_seconds`, `judge_timeout_seconds` | Per-stage overrides. |

Numbers come only from `evals/HARNESS_MATRIX.md`; a probe declares which of them
it covers, and `validate` enforces the number→probe mapping in both directions.

