"""Deterministic repository, profile and manifest fixtures for backend tests."""
import json
from pathlib import Path
import shutil
import subprocess

REPO_ROOT = Path(__file__).resolve().parents[4]
TASK_ID = 'orders-cli'
SUBJECT_ALIAS, JUDGE_ALIAS = 'fake', 'fake-judge'


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(('git', '-c', 'user.email=test@example.com',
                             '-c', 'user.name=Test', *args), cwd=root,
                            capture_output=True, text=True, check=True, timeout=60)
    return result.stdout.strip()


def _covered_numbers(task_id: str) -> list[int]:
    from evals.core.matrix import load_matrix
    return [row.number for row in load_matrix(REPO_ROOT)
            if row.primary_probe.strip('`') == task_id]


def write_profile(directory: Path, alias: str, role: str, model: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f'{alias}.json').write_text(json.dumps({
        'provider': 'fake', 'model': model, 'variant': None, 'friendly_name': alias,
        'role': role, 'opencode_version': '0.0.0', 'metadata': {},
        'human_selected': True, 'verification_run_id': f'smoke-{alias}',
        'succeeded_at': '2026-09-17T10:00:00+00:00',
        'verification': {'status': 'success', 'run_id': f'smoke-{alias}',
                         'succeeded_at': '2026-09-17T10:00:00+00:00',
                         'provider': 'fake', 'model': model, 'variant': None,
                         'opencode_version': '0.0.0'},
    }), encoding='utf-8')


def build_eval_repo(root: Path, *, task_id: str = TASK_ID,
                    checks: list[dict] | None = None) -> str:
    """Materialize a minimal repository the core and entrypoint can run against."""
    root.mkdir(parents=True, exist_ok=True)
    (root / 'evals').mkdir(exist_ok=True)
    shutil.copyfile(REPO_ROOT / 'evals/HARNESS_MATRIX.md', root / 'evals/HARNESS_MATRIX.md')
    shutil.copytree(REPO_ROOT / 'evals/schema', root / 'evals/schema', dirs_exist_ok=True)
    (root / 'VERSION').write_text('9.9.9\n', encoding='utf-8')
    task = {
        'id': task_id,
        'covered_numbers': _covered_numbers(task_id),
        'materialize': [],
        'prompt': 'Build the CLI.',
        'rubric': {'criteria': [{'id': 'c', 'description': 'quality'}]},
        'checks': [] if checks is None else checks,
    }
    task_dir = root / 'evals/tasks' / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / 'task.json').write_text(json.dumps(task), encoding='utf-8')
    providers = root / 'evals/knowledge/providers'
    write_profile(providers, SUBJECT_ALIAS, 'subject', 'fake/tiny')
    write_profile(providers, JUDGE_ALIAS, 'judge', 'fake/judge')
    _git(root, 'init', '-q')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'fixture', '--no-gpg-sign')
    return _git(root, 'rev-parse', 'HEAD')


def build_project_repo(root: Path, source: Path) -> Path:
    """A bare clone of the eval repo, standing in for the registered orx project.

    Real registration imports (clones) the repository, so the project repo keeps
    its source in ``remote.origin.url`` — exactly the identity the adapter uses
    to resolve which local project serves a given checkout.
    """
    subprocess.run(('git', 'clone', '--bare', '--quiet', str(source), str(root)),
                   check=True, timeout=60)
    return root


def make_request(repo_root: Path, source_commit: str, run_id: str = 'run-1',
                 judge_profile: str = JUDGE_ALIAS):
    from evals.core.backend_api import RunRequest
    from evals.core.matrix import load_matrix
    from evals.core.selection import resolve_selection
    selection = resolve_selection('25-26', '', load_matrix(repo_root))
    return RunRequest(
        task_id=TASK_ID, include=selection.include_numbers,
        exclude=selection.exclude_numbers, selection=selection,
        subject_profile=SUBJECT_ALIAS, judge_profile=judge_profile,
        workdir=repo_root / 'evals/history' / TASK_ID / run_id, run_id=run_id,
        repo_root=repo_root, source_commit=source_commit, knowledge_revision='k' * 64,
    )


def fingerprint_for(request) -> str:
    from evals.backends.openresearch.backend import selection_fingerprint
    return selection_fingerprint(
        task_id=request.task_id, include=request.include, exclude=request.exclude,
        harness_ids=request.selection.harness_ids,
        source_commit=request.source_commit, subject_profile=request.subject_profile,
        judge_profile=request.judge_profile,
    )


def artifact_payloads(fingerprint: str, *, run_id: str = 'local-1',
                      status: str = 'success') -> dict[str, str]:
    """The four normalized files an entrypoint leaves in its artifact directory."""
    manifest = sample_manifest(fingerprint, run_id=run_id, status=status)
    return {
        'manifest.json': json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
        'result.patch': 'diff --git a/orders.py b/orders.py\n',
        'report.md': '# Evaluation report\n',
        'status.json': json.dumps({'run_id': run_id, 'status': status,
                                   'finished_at': manifest['finished_at']}) + '\n',
    }


def sample_manifest(fingerprint: str, *, run_id: str = 'local-1', status: str = 'success',
                    backend: dict | None = None) -> dict:
    """A minimal schema-valid manifest, used for export and parity tests."""
    return {
        'schema_version': '1',
        'backend': backend or {'name': 'openresearch', 'version': '',
                               'ids': {'fingerprint': fingerprint, 'local_run': run_id}},
        'run_id': run_id,
        'task': {'id': TASK_ID, 'hash': 'a' * 64, 'rubric_hash': 'b' * 64},
        'include_numbers': [25, 26], 'exclude_numbers': [],
        'harness_ids': ['python-typer', 'cli-design'],
        'source_commit': 'c' * 40, 'catalog_version': '9.9.9', 'harness_hashes': {},
        'knowledge_revision': 'k' * 64,
        'subject_profile': {'provider': 'fake', 'model': 'fake/tiny'},
        'judge_profile': {'provider': 'fake', 'model': 'fake/judge'},
        'model': {'provider': 'fake', 'model': 'fake/tiny', 'variant': None},
        'opencode_version': '0.0.0',
        'attempts': [{'action': 'materialize', 'result': 'ok', 'duration_ms': 5,
                      'incident': None}],
        'checks': [{'id': 'smoke', 'status': 'pass', 'evidence': 'exit 0'}],
        'metrics': {'wall_time_ms': 10}, 'judge_score': 3,
        'artifacts': {'patch': 'result.patch', 'report': 'report.md',
                      'status': 'status.json'},
        'status': status,
        'started_at': '2026-09-17T10:00:00+00:00',
        'finished_at': '2026-09-17T10:00:01+00:00',
    }
