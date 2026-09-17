"""Backend-neutral run: materialize, subject, deterministic checks, judge, artifacts.

Status mapping is fixed: ``success`` (all stages completed, every check passed),
``failed`` (stages completed, a check failed), ``timeout`` (a command exceeded
its timeout), ``error`` (malformed JSON, missing model, unsupported variant,
isolation refusal or an invalid judge scorecard). Terminal artifacts are written
for every outcome, including failures that happen before the sandbox exists.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import artifacts as artifacts_api
from .backend_api import RunRequest
from .checks import CommandError, parse_opencode, run_checks, run_isolated, run_process, timeout_seconds
from .judge import judge_workspace
from .profiles import load_profile
from .sandbox import IsolationError, materialize, opencode_command, safe_path

ARTIFACTS = {'patch': 'result.patch', 'report': 'report.md', 'status': 'status.json'}
_TIMEOUTS = {'subject': 900.0, 'check': 300.0, 'judge': 600.0}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _elapsed(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def _record(attempts: list[dict], action: str, result: str, duration_ms: int) -> None:
    attempts.append({'action': action, 'result': result, 'duration_ms': duration_ms, 'incident': None})


def _relative_files(root: Path) -> list[str]:
    found = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or '.git' in path.parts or not path.is_file():
            continue
        found.append(path.relative_to(root).as_posix())
    return found


def build_patch(baseline: Path, workspace: Path) -> str:
    """Deterministic unified diff of the sandbox against its materialized base."""
    lines = []
    for relative in sorted(set(_relative_files(baseline)) | set(_relative_files(workspace))):
        original, result = baseline / relative, workspace / relative
        old = original.read_bytes() if original.is_file() else b''
        new = result.read_bytes() if result.is_file() else b''
        if old == new:
            continue
        lines.append(f'diff --git a/{relative} b/{relative}\n')
        if b'\0' in old or b'\0' in new:
            lines.append(f'Binary files a/{relative} and b/{relative} differ\n')
            continue
        lines.extend(difflib.unified_diff(old.decode('utf-8', 'replace').splitlines(keepends=True),
                                          new.decode('utf-8', 'replace').splitlines(keepends=True),
                                          f'a/{relative}', f'b/{relative}'))
    text = ''.join(lines)
    return text if text.endswith('\n') or not text else text + '\n'


def _task_file(repo_root: Path, task_id: str) -> dict:
    data = json.loads((repo_root / 'evals/tasks' / task_id / 'task.json').read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Task manifest must be a JSON object')
    return data


def _rubric(repo_root: Path, task: dict) -> dict | list:
    if 'rubric' in task:
        value = task['rubric']
    elif task.get('rubric_file'):
        value = json.loads(safe_path(repo_root, task['rubric_file']).read_text(encoding='utf-8'))
    else:
        raise ValueError('Task manifest must define a rubric or rubric_file')
    if not isinstance(value, (dict, list)) or not value:
        raise ValueError('Rubric must be a nonempty object or list')
    return value


def _prompt(repo_root: Path, task: dict) -> str:
    if isinstance(task.get('prompt'), str) and task['prompt'].strip():
        return task['prompt']
    if task.get('prompt_file'):
        return safe_path(repo_root, task['prompt_file']).read_text(encoding='utf-8')
    raise ValueError('Task manifest must define a prompt or prompt_file')


def _timeout(task: dict, stage: str) -> float:
    return timeout_seconds(task.get(f'{stage}_timeout_seconds'), _TIMEOUTS[stage])


def _fallback_report(status: str, error: str | None, checks: list[dict]) -> str:
    lines = ['# Evaluation report', '', f'Status: {status}', '']
    if error:
        lines.extend([f'Error: `{error}`', ''])
    if checks:
        lines.extend(['## Deterministic checks', ''])
        lines.extend(f"- {check['id']}: {check['status']}" for check in checks)
    return '\n'.join(lines) + '\n'


def _base_manifest(request: RunRequest) -> dict:
    return {
        'schema_version': '1',
        'backend': {'name': 'core', 'version': '1', 'ids': {}},
        'run_id': request.run_id,
        'task': {'id': request.task_id, 'hash': '', 'rubric_hash': ''},
        'include_numbers': list(request.include),
        'exclude_numbers': list(request.exclude),
        'harness_ids': list(request.selection.harness_ids),
        'source_commit': request.source_commit,
        'catalog_version': '',
        'harness_hashes': {},
        'knowledge_revision': request.knowledge_revision,
        'subject_profile': {}, 'judge_profile': {},
        'model': {'provider': '', 'model': '', 'variant': None},
        'opencode_version': '',
        'attempts': [], 'checks': [], 'metrics': {}, 'judge_score': None,
        'artifacts': dict(ARTIFACTS), 'status': 'error',
        'started_at': '', 'finished_at': '',
    }


def _catalog_version(repo_root: Path) -> str:
    try:
        return (repo_root / 'VERSION').read_text(encoding='utf-8').strip()
    except OSError:
        return ''


def _harness_hashes(repo_root: Path, harness_ids: tuple[str, ...]) -> dict:
    hashes = {}
    for identifier in harness_ids:
        digest = hashlib.sha256()
        found = False
        for band in ('rules', 'skills', 'hooks', 'agents'):
            directory = repo_root / 'harnesses' / band / identifier
            if not directory.is_dir():
                continue
            found = True
            for relative in _relative_files(directory):
                digest.update(f'{band}/{relative}'.encode('utf-8') + b'\0')
                digest.update((directory / relative).read_bytes())
        if found:
            hashes[identifier] = digest.hexdigest()
    return hashes


def _subject(request: RunRequest, task: dict, profile: dict, prompt: str, workspace: Path) -> tuple[str, dict]:
    timeout = _timeout(task, 'subject')
    if request.subject_command:
        # Test override: never used for real runs, which always require isolation.
        result = run_process([*request.subject_command, prompt], cwd=workspace, timeout=timeout)
    else:
        result = run_isolated(opencode_command(profile, prompt), workspace, timeout=timeout, role='subject')
    return parse_opencode(result)


def _judge(request: RunRequest, task: dict, profile: dict, workspace: Path, rubric: dict | list,
           checks: list[dict]) -> tuple[dict, str, dict]:
    return judge_workspace(workspace, profile, rubric, checks,
                           command=request.judge_command, timeout=_timeout(task, 'judge'))


def _capture_patch(request: RunRequest, workspace: Path) -> str:
    try:
        return build_patch(Path(request.workdir) / 'baseline', workspace)
    except (OSError, ValueError):
        return ''


def execute_experiment(request: RunRequest, artifact_dir: Path) -> dict:
    """Run one experiment and always write terminal artifacts before returning."""
    artifact_dir = Path(artifact_dir)
    manifest = _base_manifest(request)
    manifest['started_at'] = _now()
    attempts, checks = manifest['attempts'], manifest['checks']
    metrics: dict = {}
    report, patch, scorecard = '', '', None
    captured = False
    status, error = 'error', None
    workspace = None
    stage, stage_started = 'task', time.monotonic()
    try:
        task = _task_file(request.repo_root, request.task_id)
        rubric = _rubric(request.repo_root, task)
        prompt = _prompt(request.repo_root, task)
        manifest['task'] = {'id': str(task.get('id', request.task_id)),
                            'hash': _digest(_canonical(task)),
                            'rubric_hash': _digest(_canonical(rubric))}
        manifest['catalog_version'] = _catalog_version(request.repo_root)
        manifest['harness_hashes'] = _harness_hashes(request.repo_root, request.selection.harness_ids)
        subject_profile = load_profile(request.repo_root, request.subject_profile, role='subject')
        judge_profile = load_profile(request.repo_root, request.judge_profile, role='judge')
        manifest['subject_profile'], manifest['judge_profile'] = subject_profile, judge_profile
        manifest['model'] = {'provider': subject_profile['provider'], 'model': subject_profile['model'],
                             'variant': subject_profile['variant']}
        manifest['opencode_version'] = subject_profile['opencode_version']

        stage, stage_started = 'materialize', time.monotonic()
        workspace = materialize(request.repo_root, task, request.selection, Path(request.workdir))
        _record(attempts, 'materialize', 'ok', _elapsed(stage_started))

        stage, stage_started = 'subject', time.monotonic()
        _, subject_metrics = _subject(request, task, subject_profile, prompt, workspace)
        metrics['subject'] = subject_metrics
        _record(attempts, 'subject', 'ok', _elapsed(stage_started))
        # Snapshot before checks and judging: their own caches are not deliverables.
        patch, captured = _capture_patch(request, workspace), True

        stage, stage_started = 'checks', time.monotonic()
        checks.extend(run_checks(task.get('checks', []), workspace, default_timeout=_timeout(task, 'check')))
        failed = [check['id'] for check in checks if check['status'] != 'pass']
        _record(attempts, 'checks', 'fail' if failed else 'ok', _elapsed(stage_started))
        if any(check['status'] == 'error' for check in checks):
            status = 'error'
            error = 'deterministic check error'
        elif failed:
            status, error = 'failed', 'failed checks: ' + ', '.join(failed)
        else:
            status = 'success'

        stage, stage_started = 'judge', time.monotonic()
        if status in {'success', 'failed'}:
            try:
                scorecard, report, metrics['judge'] = _judge(request, task, judge_profile, workspace, rubric, checks)
                manifest['judge_score'] = scorecard['score']
                manifest['metrics'] = metrics
                _record(attempts, 'judge', 'ok', _elapsed(stage_started))
            except (CommandError, IsolationError, OSError, ValueError) as failure:
                kind = failure.kind if isinstance(failure, CommandError) else 'isolation_error'
                _record(attempts, 'judge', kind, _elapsed(stage_started))
                report = _fallback_report('judge ' + kind, str(failure), checks)
                if status == 'success':
                    status, error = 'error', f'judge {kind}'
    except (CommandError, IsolationError, OSError, ValueError, KeyError, TypeError) as failure:
        kind = failure.kind if isinstance(failure, CommandError) else ('isolation_error'
                                                                       if isinstance(failure, IsolationError) else 'invalid_task')
        _record(attempts, stage, kind, _elapsed(stage_started))
        if status != 'error' or error is None:
            status = 'timeout' if kind == 'timeout' else 'error'
            error = f'{stage} {kind}: {failure}'
    finally:
        if workspace is not None and not captured:
            patch = _capture_patch(request, workspace)
        if not report:
            report = _fallback_report(status, error, checks)
    started = datetime.fromisoformat(manifest['started_at']).timestamp()
    metrics['wall_time_ms'] = max(0, round((datetime.now(timezone.utc).timestamp() - started) * 1000))
    metrics['patch_bytes'] = len(patch.encode('utf-8'))
    metrics['checks'] = {outcome: sum(1 for check in checks if check['status'] == outcome)
                         for outcome in ('pass', 'fail', 'error')}
    manifest['metrics'] = metrics
    manifest['status'] = status
    manifest['finished_at'] = _now()
    artifacts_api.write_artifacts(artifact_dir, manifest, patch, report)
    return manifest
