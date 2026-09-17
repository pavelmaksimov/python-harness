"""Compare normalized artifacts without reaching into backend storage."""
from datetime import datetime
import difflib
from pathlib import Path

from .artifacts import read_manifest
from .validate import validate_manifest


def _summary(manifest: dict) -> dict:
    started = datetime.fromisoformat(manifest['started_at'].replace('Z', '+00:00'))
    finished = datetime.fromisoformat(manifest['finished_at'].replace('Z', '+00:00'))
    return {key: manifest[key] for key in (
        'run_id', 'harness_ids', 'include_numbers', 'exclude_numbers', 'source_commit',
        'subject_profile', 'judge_profile', 'backend', 'checks', 'metrics',
        'judge_score', 'knowledge_revision', 'status',
    )} | {
        'attempt_count': len(manifest['attempts']),
        'repair_steps': sum(attempt['action'].startswith('repair') for attempt in manifest['attempts']),
        'wall_time_seconds': (finished - started).total_seconds(),
    }


def _patch(run: Path, manifest: dict) -> str:
    directory = run if run.is_dir() else run.parent
    name = Path(manifest['artifacts']['patch'])
    target = directory / name
    if name.is_absolute() or not target.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Patch artifact must remain inside the run directory')
    return target.read_text(encoding='utf-8')


def compare_runs(run_a: Path, run_b: Path) -> dict:
    a, b = read_manifest(run_a), read_manifest(run_b)
    for manifest in (a, b):
        errors = validate_manifest(manifest)
        if errors:
            raise ValueError('Invalid manifest: ' + '; '.join(errors))
    if a['task'] != b['task']:
        raise ValueError('Cannot compare different task or rubric hashes')
    patch_a, patch_b = _patch(Path(run_a), a), _patch(Path(run_b), b)
    return {'task': a['task'], 'a': _summary(a), 'b': _summary(b),
            'patch_diff': ''.join(difflib.unified_diff(
                patch_a.splitlines(keepends=True), patch_b.splitlines(keepends=True),
                fromfile=f'{a["run_id"]}/result.patch', tofile=f'{b["run_id"]}/result.patch'))}
