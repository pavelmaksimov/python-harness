# OpenResearch backend (`openresearch`)

Orchestration adapter that runs the shared evaluation core through the installed
OpenResearch CLI (`orx 0.2.4`, plan B of the experiment lab). The workflow itself
lives in `evals/RUNBOOK.md`; this file documents only what is specific to this
backend.

Boundary: this adapter owns direction numbers, task/profile resolution, the
experiment node lifecycle, run supervision and evidence normalization.
OpenResearch owns the local project, the experiment tree, experiment branches and
worktrees, recorded commits, local execution supervision and run logs.

## Prerequisites

- `orx` on `PATH` (`orx --version` must report `0.2.4`); `orx telemetry status`
  must stay `off` — the adapter turns it off when needed and always passes
  `--no-telemetry`.
- A registered local project for this repository. There is no CLI to create one:

  ```bash
  orx up --no-agent --no-telemetry          # open the dashboard
  # import this repository in the dashboard, then:
  orx projects --json                       # confirm the project id and path
  ```

  This import is the only step that needs a human; the backend prints these exact
  steps from `doctor` and from a failed run, and never creates a project, edits
  the OpenResearch database or reads its SQLite store.
- Only `--backend local` compute is used. OpenResearch managed compute, `ssh`,
  `slurm`, `k8s`, `ray`, `modal`, `hf`, `tinker` and the autoresearch loop are
  out of scope for this version.
- Bubblewrap must be able to create unprivileged user namespaces. Under Ubuntu's
  default `kernel.apparmor_restrict_unprivileged_userns=1` it cannot, and every
  isolated stage then fails closed with
  `bwrap: setting up uid map: Permission denied` (a live run reproduced this).
  Check the host with `unshare --user --map-root-user true`; if it fails, allow
  unprivileged user namespaces (or load an AppArmor profile for bubblewrap)
  before running. The backend never executes a stage on the host to work around
  this: the core owns that decision and fails closed.

## Project resolution

`doctor` and `run` resolve the project in this order, then cache the id in
`memory/.tmp/orx-project.json` (git-ignored, never committed: it refers to the
machine-local OpenResearch store):

1. cached id, accepted only while it still exists in `orx projects --json` and
   still serves this repository;
2. otherwise the project whose repository *is* this one — same git common
   directory, same `origin` URL, or an `origin` that is a path to a checkout of
   this repository. Worktrees of one repository therefore resolve to the same
   project;
3. otherwise the run fails closed with the registration steps above.

A stale or absent cache is re-resolved through the public CLI; nothing else is
written.

## Experiment tree

- One baseline root per probe: `orx create-experiment <project> --baseline
  --title "eval <task-id>"`. Roots are created once and reused.
- A configuration variant is a **child** node of that root, titled
  `eval <task-id> <fingerprint>`; the full contract is written with
  `orx exp desc --stdin`: task, source and expanded harness numbers, harness IDs,
  source commit, catalog `VERSION`, both profile aliases, knowledge revision,
  selection fingerprint and the artifact contract.
- The fingerprint is `sha256(task + include + exclude + harness IDs + source
  commit + subject profile + judge profile)` truncated to 16 hex characters.
  Whether a variant node already exists is decided by re-reading each node's
  description, so repeated runs with an unchanged fingerprint are several runs of
  the *same* node, while any harness, model, judge, task/rubric or command change
  creates a new child.
- A node that has already run is never edited (matching OpenResearch's own rule).
  Corrections become children: a new variant hangs under the **latest variant
  node of the same probe** (the tree grows downward, as orx expects), not under
  the root, so a fix for a node that already answered stays in that node's
  lineage and the failed path remains visible.
- A node runs from an extracted source archive in the orx data directory
  (`~/.local/share/openresearch/local-runs/<run-id>/repo`), not from a Git
  checkout; the recorded commit therefore travels in the run command.
- Before the first run of a fresh node the recorded commit is pushed onto that
  node's branch (`git push --force <project-repo> <commit>:refs/heads/orx/<slug>`)
  from the checkout that owns the commit. The node has not run yet, so this is
  not an edit of answered evidence; a branch that is checked out in a session
  worktree refuses the push and that refusal is reported, never bypassed.

## Run command and supervision

Each node is frozen with exactly:

```text
uv run python evals/orx_entrypoint.py execute --task <task-id> \
  --include <canonical-numbers> --subject-profile <profile> \
  --judge-profile <profile> --selection <fingerprint> \
  --source-commit <recorded-commit>
```

The recorded commit is part of the command because a node does **not** run in a
Git checkout: orx executes an immutable source archive, so `git rev-parse` fails
inside the node and the commit can only come from the request. It is also part of
the fingerprint, so a new commit already produces a new node instead of an edited
command. Provider/model/variant never appear in the command: they are read from
the profile files of the recorded commit and recorded in the run manifest.
`--exclude` is appended only when the selection has exclusions. The adapter then
runs and supervises through the public CLI only:

```text
orx exp run --backend local --timeout 30m <experiment-id>
orx exp wait <experiment-id> --timeout 2400
orx runs <project-id> --experiment <experiment-id>
orx logs <run-id> --bytes 1000000
```

The orx run id is taken from the `runs` table (newest first) and kept in
`memory/.tmp/orx-runs-journal.json`, which is what `status(run_id)` reads back.

## Artifacts and the exporter

`evals/orx_entrypoint.py` runs the subject matter only and, through the shared
core, leaves `manifest.json`, `result.patch`, `report.md` and `status.json` in a
run directory, announcing it as `HARNESS_EVAL_ARTIFACT=<path>`. Because the log
also carries subject output, a marker is trusted only when its directory holds a
manifest whose `backend.ids.fingerprint` matches the node's fingerprint.

Retrieval order:

1. the last matching marker in `orx logs`;
2. **exporter fallback** — scan the orx worktrees of the project (plus the
   project repository) for `memory/.tmp/orx-runs/<task>/<run>/manifest.json` and
   export the newest fingerprint match. This is the operative path on orx 0.2.4,
   whose CLI exposes run logs but no arbitrary file-artifact retrieval. A
   successful fallback records an `orx_artifact_retrieval` incident through the
   knowledge API;
3. otherwise the run is reported as an error rather than as a partial success.

Export rewrites nothing but identity: the four files are copied into
`evals/history/<task>/<run-id>/`, `run_id` becomes the orx run id, and
`backend.ids` gains `project`, `experiment`, `run` and `fingerprint` before the
manifest is validated against `evals/schema/run-manifest.schema.json`. Failed or
timed-out runs keep their artifacts as diagnostic history: orx reports any
non-zero exit as a failed run, which also covers a legitimately failed
deterministic check, so the entrypoint manifest's status — not the orx run
status — decides the reported outcome.

## Doctor

`doctor` reports, in order: `orx --version`, telemetry state, project resolution,
and the latest smoke result. `doctor --repair` additionally runs the cheap smoke
node for this orx version: a node whose run command writes a marker file, which
must still be readable after the run finishes. The outcome is stored through the
knowledge API (`evals/knowledge/backends/openresearch.json`) — never by writing
knowledge files directly.

## Safety

- Every `orx` call carries `--no-telemetry`; persistent telemetry must stay off.
- `orx delete`, `orx update`, `orx login`, `orx logout` and `orx exp cancel` are
  refused by the adapter: they require an explicit user command.
- The subject and judge never reach OpenResearch knowledge, other nodes or global
  instructions; only declared task inputs are materialized, and the judge is
  read-only.
- Model selection stays human: the backend never picks or substitutes a
  provider, model or variant.
