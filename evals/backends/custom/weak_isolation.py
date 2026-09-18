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
import sys

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


# The materialized eval-shell execs bubblewrap for every permitted command, which
# is exactly what a namespaceless host cannot do. The weak shell enforces the same
# contract — single command, no shell operators, the same allowlist, no external
# paths — and then executes on the host: the degradation the approval covers.
_WEAK_SHELL = r'''#!/usr/bin/python3
import os
import shlex
import sys

if len(sys.argv) != 3 or sys.argv[1] not in ('-c', '-lc'):
    sys.exit('eval shell: only a single command is supported')
text = sys.argv[2]
if any(c in text for c in ';|&<>`$\\\n\r\x00'):
    sys.exit('eval shell: shell operators are forbidden')
args = shlex.split(text)
allowed = any(args[:len(prefix)] == prefix for prefix in (
    ['uv', 'run', 'pytest'], ['uv', 'run', 'ruff', 'check'],
    ['git', 'status'], ['git', 'diff']))
if not allowed:
    sys.exit('eval shell: command is not allowlisted')
if any(a.startswith('/') or '..' in a.split('/') for a in args[1:]):
    sys.exit('eval shell: external paths are forbidden')
if args[0] == 'git':
    args[1:1] = ['--no-pager', '-c', 'core.fsmonitor=false',
                 '-c', 'core.hooksPath=/dev/null', '-c', 'diff.external=']
    if 'diff' in args:
        args.extend(['--no-ext-diff', '--no-textconv'])
os.execvp(args[0], args)
'''


def shell_path(repo_root) -> Path:
    """Write (once per host) and return the shared weak allowlist shell."""
    path = Path(repo_root) / 'memory/.tmp/evals/shells/eval-shell-weak'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8') != _WEAK_SHELL:
        path.write_text(_WEAK_SHELL, encoding='utf-8')
        path.chmod(0o755)
    return path


# The core reads a subject's and judge's stdout through pipes and keeps only the
# parsed result, so a run that ends with an empty patch or an unparseable
# scorecard cannot be diagnosed after the fact. This shim runs the real command
# unchanged — same argv, same exit code, same stdout stream for the parser — and
# appends the raw output to a git-ignored transcript next to the attempt logs.
_SHIM = '''import subprocess
import sys

transcript, argv = sys.argv[1], sys.argv[2:]
done = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
with open(transcript, 'ab') as handle:
    handle.write(b'\\n=== attempt ===\\n')
    handle.write(done.stdout)
sys.stdout.buffer.write(done.stdout)
sys.exit(done.returncode)
'''


def shim_path(repo_root) -> Path:
    path = Path(repo_root) / 'memory/.tmp/evals/shells/transcript-shim.py'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8') != _SHIM:
        path.write_text(_SHIM, encoding='utf-8')
    return path


def transcript_path(request, role: str) -> Path:
    directory = Path(request.repo_root) / 'memory/.tmp/evals/transcripts'
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f'{request.run_id}-{role}.jsonl'


def configuration_for(workspace, role: str) -> dict:
    """The core's policy with sandbox-only paths rewritten to the real workspace.

    The materialized policy points at ``/workspace/AGENTS.md`` because bubblewrap
    mounts the workspace there; without bubblewrap the subject runs in the real
    directory, so the instruction path must be the real one or OpenCode never
    finds the materialized rules.
    """
    config = sandbox.configuration(readonly=role == 'judge')
    config['instructions'] = [str(Path(workspace) / 'AGENTS.md')]
    return config


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
    provider credentials, exactly as inside the bubblewrap subject role. The
    policy and the shell are the weak-mode equivalents of the sandbox layout:
    real workspace paths instead of ``/workspace``, and the bubblewrap-free
    allowlist shell instead of ``/control/eval-shell``.
    """
    profile = load_profile(Path(request.repo_root), alias, role=role)
    control = Path(request.workdir) / 'control' / role
    workspace = Path(request.workdir) / 'workspace'
    settings = {
        'OPENCODE_CONFIG_DIR': str(control),
        'OPENCODE_CONFIG': str(control / 'opencode.json'),
        'OPENCODE_CONFIG_CONTENT': json.dumps(configuration_for(workspace, role)),
        'OPENCODE_DISABLE_PROJECT_CONFIG': 'true',
        'OPENCODE_DISABLE_AUTOUPDATE': 'true',
        'OPENCODE_DISABLE_MODELS_FETCH': 'true',
        'OPENCODE_PURE': '1',
        'SHELL': str(shell_path(request.repo_root)),
    }
    provider, model = profile['provider'], profile['model']
    model_id = model if model.startswith(provider + '/') else provider + '/' + model
    command = ['env', *[f'{key}={value}' for key, value in settings.items()],
               sys.executable, str(shim_path(request.repo_root)), str(transcript_path(request, role)),
               'opencode', 'run', '--pure', '--format', 'json', '--model', model_id]
    if profile.get('variant'):
        command += ['--variant', profile['variant']]
    return tuple([*command, '--'])
