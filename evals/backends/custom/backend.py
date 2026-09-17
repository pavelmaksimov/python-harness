"""Repository-owned custom runner for the harness evaluation laboratory.

The backend-neutral core executes one experiment and owns its domain decisions
(sandbox, subject, checks, judge, normalized artifacts). This backend owns the
lifecycle around it:

- **supervision** — every attempt runs under one wall-clock budget in a killable
  process group, and always leaves terminal artifacts (``supervisor``);
- **recovery** — a known incident is replayed before the first attempt, then at
  most three distinct safe remedies, and only proven solutions are recorded
  (``repair``);
- **history** — ``evals/history/<task>/<run-id>/`` is the run catalog and the
  only state ``status`` reads; archived attempts keep diagnostic history; the
  run prints one ``HARNESS_EVAL_ARTIFACT=<run dir>`` line at the end;
- **readiness** — ``doctor [--repair]`` reports prerequisites and needs-human
  items, and the CLI refuses to run unless it says ``success`` (``doctor``).

The runner never selects a model, never opens credential files, never inspects
the inherited environment and never weakens isolation.
"""
from __future__ import annotations

import json
from pathlib import Path

from evals.backends.custom import doctor as doctor_module
from evals.backends.custom import repair, supervisor
from evals.core.backend_api import BackendResult
from evals.core.knowledge import validate_identifier

NAME = 'custom'
VERSION = '1'
IDENTITY = {'name': NAME, 'version': VERSION,
            'ids': {'supervision': 'wall-clock-process-group', 'repair': 'knowledge-incidents'}}


def repo_root() -> Path:
    """The repository this backend was loaded from (``evals/backends/custom/backend.py``)."""
    return Path(__file__).resolve().parents[3]


class CustomBackend:
    """`Backend` implementation discovered through ``evals/backends/custom/backend.py``."""

    name = NAME
    version = VERSION

    def doctor(self, *, repair: bool = False) -> dict:
        return doctor_module.inspect(repo_root(), IDENTITY, repair=repair)

    def run(self, request) -> BackendResult:
        state = repair.AttemptState(wall_seconds=supervisor.wall_budget(request),
                                    context=repair.context(request, NAME))
        journal: list[dict] = []
        incident = self._replay_known_incident(request, state, journal)
        symptom, outcome, error = None, None, None
        for attempt in range(1, repair.MAX_ATTEMPTS + 1):
            supervisor.archive_previous(request.workdir)
            outcome = supervisor.supervise(request, IDENTITY, attempt=attempt,
                                           wall_seconds=state.wall_seconds)
            journal.append(repair.entry(f'attempt-{attempt}', outcome.status, outcome.duration_ms,
                                        incident['fingerprint'] if incident and attempt == 1 else None))
            state.statuses.append(outcome.status)
            if outcome.status == 'success':
                break
            error = outcome.error
            if outcome.status == 'failed':
                # Deterministic checks failed: that is the experiment's answer, not a defect.
                break
            found = repair.classify(status=outcome.status, killed=outcome.killed, manifest=outcome.manifest)
            symptom = symptom or found
            repair.note_failure(state, attempt, found, outcome.status)
            if incident and attempt == 1:
                repair.note_incident_insufficient(state, incident)
            human = repair.human_required(found)
            if human:
                error = f'{human} [{found.stage}/{found.kind}]'
                break
            remedy = repair.next_remedy(found, state)
            if remedy is None:
                state.exhausted = True
                error = (f'repair loop stopped after {len(state.used)} distinct remedies '
                         f'({", ".join(state.used) or "none"}); last symptom '
                         f'{found.stage}/{found.kind} — ask the human before further attempts')
                break
            repair.apply_remedy(remedy, state)
            journal.append(repair.entry(f'remedy-{remedy.name}', 'applied', 0,
                                        incident['fingerprint'] if incident else None))
        if outcome is not None and outcome.status == 'success':
            repair.record_success(request.repo_root, symptom, state, request.run_id)
        directory = Path(outcome.artifact_dir) if outcome else Path(request.workdir)
        manifest = supervisor.merge_journal(directory, entries=journal)
        print(f'HARNESS_EVAL_ARTIFACT={directory}')
        return BackendResult(request.run_id, outcome.status if outcome else 'error', directory,
                             directory / 'manifest.json', manifest['attempts'], error)

    def status(self, run_id: str) -> dict:
        validate_identifier(run_id)
        history = repo_root() / 'evals/history'
        for directory in sorted(history.glob(f'*/{run_id}')):
            archived = sorted(path.name for path in directory.parent.glob(f'{run_id}.a*'))
            if (directory / 'status.json').is_file():
                recorded = json.loads((directory / 'status.json').read_text(encoding='utf-8'))
                status = recorded.get('status', 'unknown') if isinstance(recorded, dict) else 'unknown'
            elif (directory / 'manifest.json').is_file():
                status = 'unfinished'
            else:
                status = 'running'
            return {'run_id': run_id, 'status': status, 'artifact_dir': str(directory),
                    'archived_attempts': archived}
        return {'run_id': run_id, 'status': 'unknown', 'artifact_dir': None, 'archived_attempts': []}

    @staticmethod
    def _replay_known_incident(request, state: repair.AttemptState, journal: list[dict]) -> dict | None:
        """Apply the best known incident for this backend and version, before attempt one."""
        incident = None
        for record in repair.lookup(request.repo_root, state.context):
            fingerprint = str(record.get('fingerprint', ''))
            if incident is not None or not repair.replayable(record):
                journal.append(repair.entry('incident_replay', 'skipped', 0, fingerprint or None))
                continue
            repair.apply_incident(record, state)
            journal.append(repair.entry('incident_replay', 'ok', 0, fingerprint))
            incident = record
        return incident


BACKEND = CustomBackend()
