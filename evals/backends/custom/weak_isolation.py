"""Explicitly approved degraded isolation for hosts without unprivileged namespaces.

Temporary by design. The host of the first eval laboratory blocks namespace
creation for unprivileged processes entirely (``unshare -Ur`` and ``unshare -n``
both fail with ``Operation not permitted``), so the shared core's bubblewrap
boundary cannot run there. With a recorded human approval this module swaps the
core's isolation boundary for plain processes while keeping everything that does
not need namespaces:

- the materialized per-role OpenCode configuration (permission policy, sharing,
  auto-update and telemetry off, project-config discovery disabled),
- the narrow subject shell allowlist,
- the judge running read-only.

What is lost: pid/network/filesystem namespaces, capability dropping and
environment clearing for checks. This mode must be retired once the host runs
namespaces again — the follow-up task on MY-45 tracks that, and the module
refuses to activate while bubblewrap works.

Activation requires an approval record in the knowledge base
(``evals/knowledge/backends/custom.json`` → ``weak_isolation``) naming who
approved it, when and why. Without that record the core stays fail-closed.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import shutil

from evals.core import checks, sandbox
from evals.core.checks import run_process
from evals.core.knowledge import knowledge_path, sanitize
from evals.core.profiles import load_profile

_PROBE = ('bwrap', '--die-with-parent', '--unshare-pid', '--ro-bind', '/', '/',
          '--proc', '/proc', '--tmpfs', '/tmp', '--', '/bin/true')
_PROBE_NET = ('bwrap', '--die-with-parent', '--unshare-pid', '--ro-bind', '/', '/',
              '--proc', '/proc', '--tmpfs', '/tmp', '--unshare-net', '--', '/bin/true')
_PROBE_TIMEOUT = 20.0


def approval(repo_root) -> dict | None:
    """The recorded approval, or ``None``; malformed records never activate weak mode."""
    path = knowledge_path(Path(repo_root), 'backends', 'custom.json')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    record = data.get('weak_isolation') if isinstance(data, dict) else None
    if not isinstance(record, dict):
        return None
    if not isinstance(record.get('approved_by'), str) or not record['approved_by'].strip():
        return None
    if not isinstance(record.get('approved_at'), str) or not record['approved_at'].strip():
        return None
    return record


def namespace_probe(repo_root) -> tuple[bool, str]:
    """``(namespaces_ok, detail)`` from the probes the doctor reports."""
    if shutil.which('bwrap') is None:
        return False, 'bubblewrap (bwrap) is not installed'
    for label, probe in (('pid namespaces', _PROBE), ('network namespaces', _PROBE_NET)):
        result = run_process(list(probe), cwd=Path(repo_root), timeout=_PROBE_TIMEOUT)
        if result.returncode:
            detail = sanitize((result.stdout + result.stderr).strip())[:300]
            return False, f'{label} unavailable: {detail}'
    return True, 'bubblewrap isolates pid and network namespaces'


def host_namespaces_work(repo_root) -> bool:
    return namespace_probe(repo_root)[0]


def active(repo_root) -> bool:
    """Weak mode runs only with a recorded approval and only while bwrap cannot."""
    repo_root = Path(repo_root)
    return approval(repo_root) is not None and not host_namespaces_work(repo_root)


def _host_run_isolated(command, workspace, *, timeout, role='check', readonly=False):
    """The core boundary's contract, minus the namespace containment."""
    if role not in {'check', 'subject', 'judge'}:
        raise ValueError('Unknown sandbox role')
    return run_process(command, cwd=workspace, timeout=timeout)


@contextmanager
def host_execution():
    """Route the core's checks through plain processes while the block is held.

    Single-threaded swap of the core's isolation boundary — the same seam the
    core's own test suite substitutes; the CLI runs one experiment at a time.
    """
    original = checks.run_isolated
    checks.run_isolated = _host_run_isolated
    try:
        yield
    finally:
        checks.run_isolated = original


def command_for(request, alias: str, role: str) -> tuple[str, ...]:
    """Real OpenCode invocation with the materialized per-role policy pinned.

    The core appends the prompt as the last argument after this command, which is
    why the trailing ``--`` is already part of it. Environment pinning replaces
    the sandbox's ``--setenv``; the inherited host environment is what carries
    provider credentials, exactly as inside the bubblewrap subject role.
    """
    profile = load_profile(Path(request.repo_root), alias, role=role)
    control = Path(request.workdir) / 'control' / role
    settings = {
        'OPENCODE_CONFIG_DIR': str(control),
        'OPENCODE_CONFIG': str(control / 'opencode.json'),
        'OPENCODE_CONFIG_CONTENT': json.dumps(sandbox.configuration(readonly=role == 'judge')),
        'OPENCODE_DISABLE_PROJECT_CONFIG': 'true',
        'OPENCODE_DISABLE_AUTOUPDATE': 'true',
        'OPENCODE_DISABLE_MODELS_FETCH': 'true',
        'OPENCODE_PURE': '1',
        'SHELL': str(control / 'eval-shell'),
    }
    provider, model = profile['provider'], profile['model']
    model_id = model if model.startswith(provider + '/') else provider + '/' + model
    command = ['env', *[f'{key}={value}' for key, value in settings.items()],
               'opencode', 'run', '--pure', '--format', 'json', '--model', model_id]
    if profile.get('variant'):
        command += ['--variant', profile['variant']]
    return tuple([*command, '--'])
