"""Bounded, knowledge-driven recovery around supervised attempts.

Policy (plan A, "Самовосстановление"):

1. A known incident that applies to this backend and OpenCode version is
   replayed before the first attempt; recorded dead ends are not re-tried.
2. Without a known remedy, at most three distinct safe diagnostic attempts run.
   The safe set covers only what this backend owns: the whole-attempt wall clock
   and a clean run directory. Everything else is core or human territory.
3. Records are written only after a later attempt succeeded, through the core
   knowledge API so sanitization always runs. Repeating the same incident
   increments ``occurrences`` and merges ``failed_attempts`` instead of forking
   parallel records.
4. Anything outside the safe set — model or variant change, installation or
   update, auth or global configuration, permission weakening, isolation the
   host cannot provide — stops the loop and asks the human. The runner never
   selects a model, never opens credential files and never inspects the
   inherited environment.

Only normalized, fingerprint-stable facts are stored: stage, symptom and
applicability. Volatile text (durations, error dumps) stays in the run history,
so the same defect always hashes to the same record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
import json
from pathlib import Path
from datetime import datetime, timezone

from evals.core.knowledge import knowledge_path, record_incident
from evals.core.profiles import load_profile

MAX_ATTEMPTS = 4
MAX_REMEDIES = 3

# Failure kinds this backend cannot legally repair by itself. Each one names the
# human decision the run is waiting for, instead of burning diagnostic attempts.
HUMAN_KINDS = {
    'missing_model': 'the selected model is unavailable — ask the human to confirm a verified '
                     'provider/model profile; a substitution is never allowed',
    'unsupported_variant': 'the profile variant is rejected — confirm a supported variant with the '
                           'human before the profile changes',
    'malformed_json': 'OpenCode output could not be parsed — reformatting belongs to the shared-core parser; '
                      'stop and report the gap to the human instead of rewriting output',
    'isolation_error': 'the host cannot enforce sandbox isolation — unprivileged namespaces are a host '
                       'prerequisite; ask the human to fix the environment',
    'invalid_task': 'the task probe definition is invalid — evals/tasks is outside this backend',
    'invalid_scorecard': 'the judge returned a scorecard the core rejects — the judge profile or rubric '
                         'needs a human decision',
    'provider_quota': 'the provider quota window is exhausted — waiting for the stated reset is the only '
                      'remedy; a different judge profile is a human decision, never a substitution',
    'output_limit': 'a process exceeded the capture limit — changing that policy is a shared-core decision',
    'crash': 'the attempt ended before the shared core reported a stage — inspect the raw attempt log '
             'under memory/.tmp/evals/supervisor, then ask the human',
}


@dataclass(frozen=True)
class Remedy:
    """One safe, distinct diagnostic attempt this backend may apply by itself.

    ``effect`` carries the whole behaviour: the loop never dispatches on a name,
    so a remedy cannot silently do nothing (or something unexpected) just because
    its name is new. ``preflight`` marks remedies that are also meaningful before
    the first attempt and may therefore be replayed from a stored incident.
    """

    name: str
    kinds: tuple[str, ...]
    description: str
    effect: Callable[['AttemptState'], None]
    preflight: bool = False


def double_wall_clock(state: 'AttemptState') -> None:
    state.wall_seconds *= 2


def no_parameter_change(state: 'AttemptState') -> None:
    """Clean retry: the next attempt differs only by starting from a clean directory."""


REMEDIES = (
    Remedy('supervision_budget', ('timeout',), 'double the whole-attempt wall clock',
           double_wall_clock, preflight=True),
    Remedy('clean_retry', ('command_failed',), 'retry from a clean run directory',
           no_parameter_change),
    # Preflight only: a quota symptom stops the loop for a human, so this remedy
    # is never proposed as a retry — it is applied when a later run is built on a
    # reset that has already been waited out.
    Remedy('quota_wait', ('provider_quota',), 'wait for the provider quota window to reset before retrying',
           no_parameter_change, preflight=True),
)


@dataclass(frozen=True)
class Symptom:
    stage: str
    kind: str
    symptom: str


@dataclass
class AttemptState:
    """Mutable pre-flight and repair state for one run."""

    wall_seconds: float
    context: dict
    used: list[str] = field(default_factory=list)
    incidents: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    exhausted: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def entry(action: str, result: str, duration_ms: int, incident: str | None = None) -> dict:
    """One attempts-journal record, shaped exactly like the core's own entries."""
    return {'action': action, 'result': result, 'duration_ms': max(0, int(duration_ms)),
            'incident': incident}


def context(request, backend: str) -> dict:
    """Applicability of this run: backend identity plus the verified OpenCode version."""
    values = {'backend': backend}
    for alias in (request.subject_profile, request.judge_profile):
        try:
            profile = load_profile(Path(request.repo_root), alias)
        except (ValueError, OSError):
            continue
        version = profile.get('opencode_version')
        if isinstance(version, str) and version.strip():
            values['opencode_version'] = version
            break
    return values


def lookup(repo_root: Path, context_values: dict) -> list[dict]:
    """Known incidents whose applicability holds for this run, most proven first."""
    root = knowledge_path(Path(repo_root), 'incidents')
    if not root.is_dir():
        return []
    records = []
    for path in sorted(root.glob('*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(record, dict) or record.get('superseded_by'):
            continue
        applicability = record.get('applicability')
        if not isinstance(applicability, dict) or not applicability:
            continue
        if all(key in context_values and context_values[key] == value
               for key, value in applicability.items()):
            records.append(record)
    return sorted(records, key=lambda item: (-int(item.get('occurrences', 0)),
                                             str(item.get('fingerprint', ''))))


def incident_kind(record: dict) -> str | None:
    """Remedy kind of a stored incident; free text and unknown shapes are not applied."""
    remedy = record.get('remedy')
    if isinstance(remedy, str) and remedy.strip():
        return remedy.strip()
    if isinstance(remedy, dict):
        kind = remedy.get('kind')
        if isinstance(kind, str) and kind.strip():
            return kind.strip()
    return None


def _remedy(name: str | None) -> Remedy | None:
    return next((remedy for remedy in REMEDIES if remedy.name == name), None)


def replayable(record: dict) -> bool:
    remedy = _remedy(incident_kind(record))
    return remedy is not None and remedy.preflight


def apply_incident(record: dict, state: AttemptState) -> None:
    """Apply a replayed remedy before the first attempt."""
    remedy = _remedy(incident_kind(record))
    if remedy is None or not remedy.preflight:
        raise ValueError(f'incident remedy is not replayable by this backend: {record.get("remedy")!r}')
    remedy.effect(state)
    state.incidents.append(record)


def classify(*, status: str, killed: bool, manifest: dict) -> Symptom:
    """Name the failing stage and kind from structured evidence, never free text."""
    for attempt in manifest.get('attempts', []):
        result = attempt.get('result')
        if result != 'ok':
            action = str(attempt.get('action', 'unknown'))
            kind = str(result or 'error')
            return Symptom(f'custom_{action}', kind, f'{action} {kind}')
    if killed:
        return Symptom('custom_supervisor', 'timeout', 'supervisor timeout')
    return Symptom('custom_supervisor', 'crash', f'supervisor {status}' if status == 'error' else 'supervisor crash')


def human_required(symptom: Symptom) -> str | None:
    return HUMAN_KINDS.get(symptom.kind)


def next_remedy(symptom: Symptom, state: AttemptState) -> Remedy | None:
    """First distinct safe remedy for this symptom class, within the global cap."""
    if len(state.used) >= MAX_REMEDIES:
        return None
    for remedy in REMEDIES:
        if remedy.name in state.used or symptom.kind not in remedy.kinds:
            continue
        return remedy
    return None


def apply_remedy(remedy: Remedy, state: AttemptState) -> None:
    remedy.effect(state)
    state.used.append(remedy.name)


def record_success(repo_root: Path, symptom: Symptom | None, state: AttemptState, run_id: str) -> dict | None:
    """Store the proven solution, and only after an attempt succeeded.

    A replayed incident is credited when the very first attempt succeeded; a
    remedy applied in this run is credited when a later attempt succeeded. A run
    that needed no repair stores nothing.
    """
    if not state.statuses or state.statuses[-1] != 'success':
        return None
    first = state.statuses[0] == 'success'
    if state.incidents and first:
        record = state.incidents[0]
        data = {'stage': record['stage'], 'symptom': record['symptom'],
                'applicability': record['applicability'], 'remedy': record['remedy']}
    elif state.used and symptom is not None:
        remedy = next((item for item in REMEDIES if item.name == state.used[-1]), None)
        if remedy is None:
            return None
        data = {'stage': symptom.stage, 'symptom': symptom.symptom,
                'applicability': dict(state.context),
                'remedy': {'kind': remedy.name, 'description': remedy.description}}
    else:
        return None
    data['failed_attempts'] = state.failed
    data['verification'] = {'status': 'success', 'run_id': run_id, 'succeeded_at': _now()}
    return record_incident(Path(repo_root), data)


def note_failure(state: AttemptState, attempt: int, symptom: Symptom, status: str) -> None:
    """Deterministic dead-end summary; durations live in the run journal, not here."""
    state.failed.append(entry(f'attempt-{attempt}', f'{status}:{symptom.kind}', 0))


def note_incident_insufficient(state: AttemptState, record: dict) -> None:
    """A replayed incident that did not fix the run is evidence, never a trusted remedy."""
    state.failed.append(entry('incident_replay', 'insufficient', 0, str(record.get('fingerprint'))))
