"""Read-only readiness checks and the small set of safe, ownable repairs.

Nothing here reads credentials, auth files or the inherited environment:
OpenCode reads its own credentials, and every environment question is answered
by asking a tool (`opencode --version`, `uv cache dir`, a `bwrap` probe) rather
than by inspecting variables. `doctor --repair` only touches what this backend
owns — the git-ignored history directory and the generated knowledge index.
Anything else becomes an explicit request for the human, with the exact command.

The run gate in ``evals/core/cli.py`` refuses to start unless this report says
``success``, so a broken prerequisite (no OpenCode, no usable isolation, a
corrupt profile record) fails closed instead of running with weaker isolation.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil

from evals.core import sandbox
from evals.core.checks import run_process
from evals.core.knowledge import generate_index, knowledge_path, sanitize
from evals.core.profiles import load_profile

_HISTORY = ('evals', 'history')
_PROBE = ('bwrap', '--die-with-parent', '--unshare-pid', '--ro-bind', '/', '/',
          '--proc', '/proc', '--tmpfs', '/tmp', '--', '/bin/true')
_CONFIG_MARKERS = ('OPENCODE_CONFIG_DIR', 'OPENCODE_DISABLE_PROJECT_CONFIG', 'OPENCODE_PURE')


def _check(identifier: str, status: str, detail: str, *, blocking: bool, remedy: str | None = None) -> dict:
    return {'id': identifier, 'status': status, 'detail': detail, 'blocking': blocking, 'remedy': remedy}


def _run(command: list[str], repo_root: Path, timeout: float = 20.0) -> tuple[int, str]:
    result = run_process(command, cwd=repo_root, timeout=timeout)
    return result.returncode, (result.stdout + result.stderr).strip()


def _opencode(repo_root: Path) -> dict:
    if shutil.which('opencode') is None:
        return _check('opencode', 'fail', 'opencode is not on PATH', blocking=True,
                      remedy='install OpenCode with the human; installation and updates are never automatic')
    code, output = _run(['opencode', '--version'], repo_root)
    if code:
        return _check('opencode', 'fail', f'opencode --version exited {code}: {sanitize(output)[:300]}',
                      blocking=True,
                      remedy='repair the OpenCode installation with the human before running')
    version = output.splitlines()[0] if output else 'unknown'
    return _check('opencode', 'ok', f'opencode {version}', blocking=True)


def _sandbox(repo_root: Path) -> dict:
    if shutil.which('bwrap') is None:
        return _check('sandbox', 'fail', 'bubblewrap (bwrap) is not installed', blocking=True,
                      remedy='install bubblewrap with the human; host execution is never a fallback')
    for label, probe in (('pid namespaces', _PROBE),
                         ('network namespaces', (*_PROBE[:-2], '--unshare-net', *_PROBE[-2:]))):
        code, output = _run(list(probe), repo_root)
        if code:
            return _check('sandbox', 'fail', f'{label} unavailable: {sanitize(output)[:300]}', blocking=True,
                          remedy='fix unprivileged namespaces or kernel settings on the host '
                                 '(a host change the human must approve)')
    return _check('sandbox', 'ok', 'bubblewrap isolates pid and network namespaces', blocking=True)


def _uv_cache(repo_root: Path) -> dict:
    if shutil.which('uv') is None:
        return _check('uv_cache', 'fail', 'uv is not on PATH', blocking=False,
                      remedy='install uv; the runbook command and the runner both use it')
    code, output = _run(['uv', 'cache', 'dir'], repo_root)
    if code:
        return _check('uv_cache', 'fail', f'uv cache dir exited {code}: {sanitize(output)[:300]}', blocking=False,
                      remedy='inspect the uv installation with the human')
    directory = Path(output.splitlines()[0].strip()) if output else None
    populated = directory is not None and directory.is_dir() and any(directory.iterdir())
    if not populated:
        return _check('uv_cache', 'fail', 'the uv cache is missing or empty', blocking=False,
                      remedy='prewarm the cache with network access and the human\'s approval; '
                             'the sandbox mounts it read-only and refreshing it writes outside the workspace')
    return _check('uv_cache', 'ok', 'a warmed uv cache is present', blocking=False)


def _profiles(repo_root: Path) -> dict:
    root = knowledge_path(repo_root, 'providers')
    files = sorted(root.glob('*.json')) if root.is_dir() else []
    if not files:
        return _check('profiles', 'fail', 'no verified provider/model profile is recorded', blocking=False,
                      remedy='run cli.py profiles --provider <alias>, let the human choose, then record the '
                             'profile after a successful smoke run')
    found, invalid = [], []
    for path in files:
        try:
            profile = load_profile(repo_root, path.stem)
        except (ValueError, OSError) as error:
            invalid.append(f'{path.stem}: {sanitize(str(error))[:200]}')
            continue
        found.append(f"{path.stem} ({profile['role']}, {profile['provider']}/{profile['model']})")
    if invalid:
        return _check('profiles', 'fail', 'invalid profile records: ' + '; '.join(invalid), blocking=True,
                      remedy='repair or remove the invalid profile record; a corrupt record can never be used')
    return _check('profiles', 'ok', 'verified profiles: ' + ', '.join(found), blocking=False)


def _config_scope(repo_root: Path) -> dict:
    """Prove the shared core still pins OpenCode policy, instead of trusting it."""
    try:
        subject = sandbox.isolated_command(['opencode', 'run', '--help'], repo_root, role='subject')
        checks = sandbox.isolated_command(['/bin/true'], repo_root, role='check')
    except (ValueError, OSError) as error:
        return _check('config_scope', 'fail', f'isolation policy cannot be built: {error}', blocking=True,
                      remedy='the shared core isolation contract changed; review evals/core/sandbox.py')
    problems = [marker for marker in _CONFIG_MARKERS if marker not in subject]
    if '--unshare-net' not in checks or '--clearenv' not in checks:
        problems.append('network namespace and cleared environment for checks')
    if problems:
        return _check('config_scope', 'fail', 'isolated configuration is no longer enforced: '
                      + ', '.join(problems), blocking=True,
                      remedy='the shared core isolation contract changed; review evals/core/sandbox.py')
    return _check('config_scope', 'ok',
                  'the core pins OPENCODE_CONFIG_DIR, project-config discovery, pure mode and an '
                  'isolated config per role; provider credentials are read only by OpenCode', blocking=True)


def _history(repo_root: Path) -> dict:
    directory = repo_root.joinpath(*_HISTORY)
    if directory.is_dir() and os.access(directory, os.W_OK):
        return _check('history', 'ok', 'the run history directory is writable', blocking=True)
    return _check('history', 'fail', 'the run history directory is missing or read-only', blocking=True,
                  remedy='create the git-ignored evals/history directory (doctor --repair does it)')


def _repairs(repo_root: Path, checks: list[dict]) -> list[dict]:
    """Apply only what this backend owns; everything else stays a human request."""
    applied = []
    if not knowledge_path(repo_root, 'INDEX.md').is_file():
        generate_index(repo_root)
        applied.append({'action': 'generate_knowledge_index', 'result': 'created'})
    if next(check for check in checks if check['id'] == 'history')['status'] == 'fail':
        try:
            repo_root.joinpath(*_HISTORY).mkdir(parents=True, exist_ok=True)
        except OSError:
            # The check keeps reporting the problem; a failed repair is not claimed as applied.
            return applied
        applied.append({'action': 'create_history_directory', 'result': 'created'})
    return applied


def inspect(repo_root: Path, identity: dict, *, repair: bool = False) -> dict:
    """Structured readiness report for ``cli.py doctor --backend custom``.

    Checks always run read-only first; repairs happen after, and the affected
    checks are re-run so the report shows what is true now, not what was true
    before the repair.
    """
    repo_root = Path(repo_root)
    checks = [_opencode(repo_root), _sandbox(repo_root), _uv_cache(repo_root),
              _profiles(repo_root), _config_scope(repo_root), _history(repo_root)]
    repairs = []
    if repair:
        repairs = _repairs(repo_root, checks)
        if repairs:
            checks = [check if check['id'] != 'history' else _history(repo_root) for check in checks]
    blocking = [check['id'] for check in checks if check['blocking'] and check['status'] == 'fail']
    return {
        'name': identity['name'],
        'version': identity['version'],
        'status': 'error' if blocking else 'success',
        'repair': repair,
        'checks': checks,
        'repairs': repairs,
        'needs_human': [check['remedy'] for check in checks if check['status'] == 'fail' and check['remedy']],
        'notes': ['the runner never reads auth files or the process environment; OpenCode owns credentials',
                  'cancelled and failed attempts keep their artifacts under evals/history'],
    }
