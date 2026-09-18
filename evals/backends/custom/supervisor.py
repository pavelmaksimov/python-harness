"""Wall-clock supervision and hard cancellation around one experiment attempt.

The shared core executes every stage of an experiment and owns the domain
decisions (materialization, subject, checks, judge, artifacts). This supervisor
owns the lifecycle around it: one wall-clock budget for the whole attempt,
cancellation of the entire process tree when that budget expires, and a terminal
artifact set even when the attempt is killed mid-flight.

An attempt runs ``evals.core.execute.execute_experiment`` in a forked child that
becomes its own process-group leader, so an expired budget is one signal to the
group. Results travel through the filesystem, never through an in-memory
channel: the run directory is the single source of truth and it survives the
kill. The child's own stdout/stderr go to a raw log under ``memory/.tmp/evals/``
(git-ignored scratch), which keeps the operator-facing marker printed exactly
once, by the parent, at the end of the run.

Linux-only by design: the fork start method and process-group signalling are the
mechanisms, and the shared core's isolation is Linux-only as well.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from evals.core import artifacts as artifacts_api
from evals.core.execute import build_patch, execute_experiment
from evals.core.knowledge import sanitize

_OVERHEAD_SECONDS = 300.0
_STAGE_DEFAULTS = {'subject': 900.0, 'check': 300.0, 'judge': 600.0}
_FALLBACK_WALL_SECONDS = 2400.0
_LOGS = ('memory/.tmp/evals/supervisor')
_ARTIFACTS = {'patch': 'result.patch', 'report': 'report.md', 'status': 'status.json'}


@dataclass(frozen=True)
class Outcome:
    """What one supervised attempt left behind, read back from the run directory."""

    status: str
    error: str | None
    duration_ms: int
    killed: bool
    artifact_dir: Path
    manifest: dict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def wall_budget(request) -> float:
    """Whole-attempt wall clock derived from the task's own per-stage budgets.

    The supervisor never overrides a stage timeout: those are task data owned by
    the shared core. Expiry here only means the attempt outlived every stage
    budget plus overhead, so it is cancelled and reported as one whole attempt.
    """
    try:
        task = json.loads((Path(request.repo_root) / 'evals/tasks' / request.task_id
                           / 'task.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return _FALLBACK_WALL_SECONDS
    total = _OVERHEAD_SECONDS
    for stage, default in _STAGE_DEFAULTS.items():
        value = task.get(f'{stage}_timeout_seconds')
        total += float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else default
    return total


def archive_previous(workdir) -> Path | None:
    """Move an existing run directory aside so the next attempt starts clean.

    ``materialize`` requires an empty run directory, and reusing an explicit
    ``--run-id`` must not destroy diagnostic history, so the previous attempt is
    renamed next to the canonical directory instead of deleted.
    """
    directory = Path(workdir)
    if not directory.exists() or not any(directory.iterdir()):
        return None
    suffix = 1
    while True:
        target = directory.with_name(f'{directory.name}.a{suffix}')
        if not target.exists():
            break
        suffix += 1
    os.rename(directory, target)
    return target


def log_path(request, attempt: int) -> Path | None:
    directory = Path(request.repo_root) / _LOGS[0]
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return directory / f'{request.run_id}-attempt-{attempt}.log'


def _child(request, artifact_dir: Path, identity: dict, logfile: Path | None) -> None:
    os.setsid()
    if logfile is not None:
        handle = os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.dup2(handle, 1)
        os.dup2(handle, 2)
        os.close(handle)
    execute_experiment(request, artifact_dir, backend=identity)


def _cancel(process: multiprocessing.process.BaseProcess) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        process.terminate()


def _recorded_manifest(directory: Path) -> dict | None:
    try:
        return artifacts_api.read_manifest(directory)
    except (OSError, ValueError):
        return None


def _recorded_status(directory: Path) -> str | None:
    try:
        status = json.loads((directory / 'status.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return status.get('status') if isinstance(status, dict) else None


def _message(manifest: dict) -> str | None:
    """Compose the run's failure message from structured attempts, never free text."""
    failed = [attempt for attempt in manifest.get('attempts', []) if attempt.get('result') != 'ok']
    if not failed:
        return None
    attempt = failed[0]
    stage, kind = attempt.get('action'), attempt.get('result')
    message = f'{stage} {kind}'
    broken = [check['id'] for check in manifest.get('checks', []) if check.get('status') != 'pass']
    if broken:
        message += ': ' + ', '.join(broken)
    return message


def _fallback_manifest(request, identity: dict, status: str, error: str, duration_ms: int) -> dict:
    manifest = {
        'schema_version': '1',
        'backend': dict(identity),
        'run_id': request.run_id,
        'task': {'id': request.task_id, 'hash': '', 'rubric_hash': ''},
        'include_numbers': list(request.include),
        'exclude_numbers': list(request.exclude),
        'harness_ids': list(request.selection.harness_ids),
        'source_commit': request.source_commit,
        'catalog_version': '',
        'harness_hashes': {},
        'knowledge_revision': request.knowledge_revision,
        'subject_profile': {},
        'judge_profile': {},
        'model': {'provider': '', 'model': '', 'variant': None},
        'opencode_version': '',
        'attempts': [],
        'checks': [],
        'metrics': {'wall_time_ms': duration_ms, 'supervised': True},
        'judge_score': None,
        'artifacts': dict(_ARTIFACTS),
        'status': status,
        'started_at': _now(),
        'finished_at': _now(),
    }
    return manifest


def _write_fallback(request, identity: dict, status: str, error: str, duration_ms: int) -> dict:
    directory = Path(request.workdir)
    manifest = _fallback_manifest(request, identity, status, error, duration_ms)
    baseline, workspace = directory / 'baseline', directory / 'workspace'
    patch = ''
    if baseline.is_dir() and workspace.is_dir():
        try:
            # Save whatever the cancelled attempt produced; a partial patch is
            # diagnostic evidence, so it is never dropped silently.
            patch = build_patch(baseline, workspace)
        except (OSError, ValueError):
            patch = ''
    report = '\n'.join(['# Evaluation report', '', f'Status: {status}', '', f'Error: `{error}`', '',
                        'The shared core did not finish this attempt; the supervisor wrote the '
                        'terminal artifacts so the run stays diagnosable.', '']) + '\n'
    artifacts_api.write_artifacts(directory, manifest, patch, report)
    return _recorded_manifest(directory) or manifest


def supervise(request, identity: dict, *, attempt: int, wall_seconds: float) -> Outcome:
    """Run one attempt under a wall clock and always leave terminal artifacts."""
    directory = Path(request.workdir)
    logfile = log_path(request, attempt)
    context = multiprocessing.get_context('fork')
    process = context.Process(target=_child, args=(request, directory, identity, logfile),
                              name=f'{request.run_id}-attempt-{attempt}')
    started = time.monotonic()
    process.start()
    process.join(wall_seconds)
    killed = process.is_alive()
    if killed:
        _cancel(process)
    process.join(timeout=60)
    duration_ms = round((time.monotonic() - started) * 1000)
    manifest = _recorded_manifest(directory)
    status = _recorded_status(directory)
    if killed:
        status = 'timeout'
        error = (f'supervisor wall clock of {wall_seconds:.0f}s expired; attempt cancelled '
                 f'after {duration_ms} ms')
        manifest = _write_fallback(request, identity, status, error, duration_ms)
    elif status is None:
        status = 'error'
        error = (f'attempt ended without terminal artifacts (child exit code {process.exitcode}); '
                 'see the raw attempt log under memory/.tmp/evals/supervisor')
        manifest = _write_fallback(request, identity, status, error, duration_ms)
    else:
        error = _message(manifest or {})
        if process.exitcode:
            error = f'{error or "attempt"}; child exit code {process.exitcode}'
    return Outcome(status, error, duration_ms, killed, directory, manifest or {})


def merge_journal(directory, *, entries: list[dict]) -> dict:
    """Prepend supervisor entries to the stored attempts journal.

    The core records one entry per stage of the finished attempt; supervisor
    entries (incident replay, attempt summary, applied remedy) belong in front of
    them so the journal reads as pre-flight work, attempts, then stage detail.
    """
    directory = Path(directory)
    manifest = artifacts_api.read_manifest(directory)
    manifest['attempts'] = [*entries, *manifest.get('attempts', [])]
    payload = json.dumps(sanitize(manifest), ensure_ascii=False, indent=2) + '\n'
    target = directory / 'manifest.json'
    temporary = directory / 'manifest.json.tmp'
    temporary.write_text(payload, encoding='utf-8')
    temporary.replace(target)
    return manifest
