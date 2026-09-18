"""Filesystem isolation and explicit OpenCode policy; never fall back to host execution."""
import json
from pathlib import Path
import shutil
import stat

from .selection import Selection


class IsolationError(RuntimeError):
    """The host cannot enforce the experiment's isolation requirements."""


_FORBIDDEN = {'.git', '.cursor', '.claude', 'TODO.md', 'auth.json', 'task.json'}
_DISCOVERY = {'AGENTS.md', 'CLAUDE.md', 'opencode.json', 'opencode.jsonc', '.opencode'}


def safe_path(root: Path, relative: str) -> Path:
    """Resolve a repository/workspace path without traversing symlinks or secrets."""
    path = Path(relative)
    if path.is_absolute() or not path.parts or '..' in path.parts:
        raise ValueError('Expected a nonempty confined relative path')
    current = root
    for part in path.parts:
        if part in _FORBIDDEN or part.startswith('.env') or part == 'knowledge':
            raise ValueError(f'{part} is not an experiment input')
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlinks are not permitted in experiment inputs')
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escapes its root')
    return current


def _copy(source: Path, destination: Path, *, fixture: bool = False) -> None:
    if source.is_symlink():
        raise ValueError('Symlinks are not permitted in experiment inputs')
    if source.name in _FORBIDDEN or source.name.startswith('.env'):
        raise ValueError(f'{source.name} is not an experiment input')
    if fixture and source.name in _DISCOVERY:
        raise ValueError('Fixtures cannot supply agent instructions or configuration')
    mode = source.stat().st_mode
    if stat.S_ISDIR(mode):
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir()):
            _copy(child, destination / child.name, fixture=fixture)
    elif stat.S_ISREG(mode):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o755 if mode & 0o111 else 0o644)
    else:
        raise ValueError('Only regular files and directories are experiment inputs')


def selected_entries(task: dict, selection: Selection) -> list[dict]:
    entries = []
    for entry in task.get('materialize', []):
        if not isinstance(entry, dict) or entry.get('kind') not in {'rule', 'skill', 'template'}:
            raise ValueError('Unknown materialize entry kind')
        identifier = entry.get('harness_id')
        if identifier is None:
            # Only a harness root directory implies its ID; nested files stay explicit.
            parts = Path(entry['from']).parts
            if len(parts) == 3 and parts[0] == 'harnesses':
                identifier = parts[2]
        if identifier is not None and identifier not in selection.harness_ids:
            continue
        entries.append(entry)
    return entries


def _rule_body(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    if text.startswith('---\n'):
        _, separator, body = text[4:].partition('\n---\n')
        if not separator:
            raise ValueError('Unterminated rule frontmatter')
        return body.strip()
    return text.strip()


def configuration(*, readonly: bool = False) -> dict:
    permissions = {
        '*': 'deny', 'read': {'*': 'allow', '*.env*': 'deny'},
        'glob': 'allow', 'grep': 'allow', 'external_directory': 'deny',
        'skill': 'allow', 'edit': 'deny' if readonly else {
            '*': 'allow', 'AGENTS.md': 'deny', '.opencode/*': 'deny',
            'opencode.json*': 'deny', '.git/*': 'deny',
        },
        'bash': 'deny' if readonly else {
            '*': 'deny', 'uv run pytest': 'allow', 'uv run pytest *': 'allow',
            'uv run ruff check': 'allow', 'uv run ruff check *': 'allow',
            'git status': 'allow', 'git status *': 'allow',
            'git diff': 'allow', 'git diff *': 'allow',
        },
    }
    return {
        '$schema': 'https://opencode.ai/config.json', 'permission': permissions,
        'share': 'disabled', 'autoupdate': False, 'plugin': [], 'mcp': {},
        'lsp': False, 'formatter': False,
        'experimental': {'openTelemetry': False},
        'instructions': ['/workspace/AGENTS.md'],
    }


# This is a shell entry point, not a shell parser. No shell interpolation ever runs.
# Every permitted command gets a fresh network namespace and an empty environment.
_SHELL = r'''#!/usr/bin/python3
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
command = ['bwrap', '--die-with-parent', '--unshare-net',
    '--unshare-pid', '--new-session', '--ro-bind', '/', '/',
    '--bind', '/workspace', '/workspace', '--tmpfs', '/tmp',
    '--proc', '/proc', '--clearenv', '--setenv', 'PATH', '/usr/local/bin:/usr/bin:/bin',
    '--setenv', 'HOME', '/tmp', '--setenv', 'UV_OFFLINE', '1',
    '--setenv', 'UV_CACHE_DIR', '/tmp/uv-cache', '--setenv', 'GIT_CONFIG_NOSYSTEM', '1',
    '--setenv', 'GIT_CONFIG_GLOBAL', '/dev/null', '--chdir', '/workspace', '--'] + args
os.execvp(command[0], command)
'''


def materialize(repo_root: Path, task: dict, selection: Selection, workdir: Path) -> Path:
    """Copy only declared inputs into a new run directory, with separate trusted policy."""
    repo_root = repo_root.resolve()
    workdir = Path(workdir).absolute()
    if any(parent.is_symlink() for parent in (workdir, *workdir.parents)):
        raise ValueError('Run directory cannot traverse symlinks')
    workdir.mkdir(parents=True, exist_ok=True)
    if any(workdir.iterdir()):
        raise ValueError('Run workdir must be empty')
    workspace = workdir / 'workspace'
    workspace.mkdir()
    base = task.get('base_fixture', 'evals/_fixtures/base-project')
    source = safe_path(repo_root, base)
    if source.exists():
        _copy(source, workspace, fixture=True)
    elif 'base_fixture' in task:
        raise ValueError('Base fixture does not exist')
    if task.get('fixture'):
        _copy(safe_path(repo_root, task['fixture']), workspace, fixture=True)
    rules = []
    control = workdir / 'control'
    control.mkdir(mode=0o700)
    for role in ('subject', 'judge'):
        directory = control / role
        directory.mkdir()
        (directory / 'opencode.json').write_text(
            json.dumps(configuration(readonly=role == 'judge')), encoding='utf-8')
        (directory / 'skills').mkdir()
    for entry in selected_entries(task, selection):
        source = safe_path(repo_root, entry['from'])
        kind = entry['kind']
        destination = safe_path(workspace, entry['to'])
        if kind == 'rule':
            paths = sorted(source.glob('*.mdc')) if source.is_dir() else [source]
            if not paths:
                raise ValueError('Rule input contains no .mdc files')
            for path in paths:
                safe_path(repo_root, str(path.relative_to(repo_root)))
                if path.suffix != '.mdc':
                    raise ValueError('Rule inputs must be .mdc files')
                rules.append(_rule_body(path))
            if destination != workspace / 'AGENTS.md':
                if any(p in _DISCOVERY for p in destination.relative_to(workspace).parts):
                    raise ValueError('Rule destination overlaps protected configuration')
                _copy(source, destination)
        elif kind == 'skill':
            if not destination.is_relative_to(workspace / '.opencode/skills'):
                raise ValueError('Skills must be materialized under .opencode/skills')
            _copy(source, destination)
            # Also load the skill from the sandbox config dir, so project discovery
            # being disabled can never hide a selected skill from the subject.
            _copy(source, control / 'subject/skills' / destination.name)
        else:
            if any(p in _DISCOVERY for p in destination.relative_to(workspace).parts):
                raise ValueError('Template destination overlaps protected configuration')
            _copy(source, destination)
    (workspace / 'AGENTS.md').write_text('\n\n'.join(rules) + '\n', encoding='utf-8')
    (workspace / '.opencode/skills').mkdir(parents=True, exist_ok=True)
    shell = control / 'eval-shell'
    shell.write_text(_SHELL, encoding='utf-8')
    shell.chmod(0o755)
    # Snapshot the exact starting state so the final patch isolates subject work.
    _copy(workspace, workdir / 'baseline')
    return workspace


def opencode_command(profile: dict, prompt: str, *, variant: str | None = None) -> list[str]:
    """Exact provider/model/variant invocation; the variant is never inferred."""
    provider = profile['provider']
    model = profile['model']
    model_id = model if model.startswith(provider + '/') else provider + '/' + model
    command = ['opencode', 'run', '--pure', '--format', 'json', '--model', model_id]
    selected = profile.get('variant') if variant is None else variant
    if selected:
        command.extend(['--variant', selected])
    return command + ['--', prompt]


def isolated_command(command: list[str] | tuple[str, ...], workspace: Path, *,
                     role: str = 'check', readonly: bool = False) -> list[str]:
    """Construct a bwrap invocation. A missing/blocked bwrap is a hard error.

    OpenCode and uv must be installed under /usr (including /usr/local).
    Provider credentials may be inherited; no host HOME/auth/config is mounted.
    Shell checks have neither network nor inherited credentials. The provider
    process retains networking, but its tools are governed by immutable policy.
    """
    if role not in {'check', 'subject', 'judge'}:
        raise ValueError('Unknown sandbox role')
    if not command or any(not isinstance(arg, str) for arg in command):
        raise ValueError('Command must be a nonempty argument list')
    argv = ['bwrap', '--die-with-parent', '--unshare-pid', '--unshare-ipc',
            '--unshare-uts', '--new-session', '--cap-drop', 'ALL']
    if role == 'check':
        argv += ['--unshare-net', '--clearenv']
    for system in ('/usr', '/bin', '/sbin', '/lib', '/lib64'):
        if Path(system).exists():
            argv += ['--ro-bind', system, system]
    for system in ('/etc/ssl', '/etc/resolv.conf', '/etc/hosts', '/etc/nsswitch.conf',
                   '/etc/ld.so.cache'):
        if Path(system).exists():
            argv += ['--ro-bind', system, system]
    argv += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
             '--dir', '/run', '--dir', '/run/xdg',
             '--ro-bind' if readonly else '--bind', str(workspace), '/workspace',
             '--chdir', '/workspace', '--setenv', 'HOME', '/run/xdg',
             '--setenv', 'PATH', '/usr/local/bin:/usr/bin:/bin',
             '--setenv', 'XDG_CONFIG_HOME', '/run/xdg/config',
             '--setenv', 'XDG_DATA_HOME', '/run/xdg/data',
             '--setenv', 'XDG_CACHE_HOME', '/run/xdg/cache',
             '--setenv', 'XDG_STATE_HOME', '/run/xdg/state',
             '--setenv', 'GIT_CONFIG_NOSYSTEM', '1',
             '--setenv', 'GIT_CONFIG_GLOBAL', '/dev/null',
             '--setenv', 'UV_OFFLINE', '1', '--setenv', 'UV_CACHE_DIR', '/tmp/uv-cache']
    if role != 'check':
        control = workspace.parent / 'control'
        argv += ['--ro-bind', str(control), '/control']
        for protected in ('AGENTS.md', '.opencode', '.git'):
            path = workspace / protected
            if path.exists():
                argv += ['--ro-bind', str(path), '/workspace/' + protected]
        for key in ('OPENCODE_PERMISSION', 'OPENCODE_MODELS_URL', 'OPENCODE_MODELS_PATH',
                    'OTEL_EXPORTER_OTLP_ENDPOINT', 'OTEL_EXPORTER_OTLP_HEADERS',
                    'BASH_ENV', 'ENV', 'NODE_OPTIONS', 'BUN_OPTIONS', 'LD_PRELOAD',
                    'LD_LIBRARY_PATH'):
            argv += ['--unsetenv', key]
        config = f'/control/{role}'
        settings = {
            'OPENCODE_CONFIG_DIR': config, 'OPENCODE_CONFIG': config + '/opencode.json',
            'OPENCODE_CONFIG_CONTENT': json.dumps(configuration(readonly=readonly)),
            'OPENCODE_DISABLE_PROJECT_CONFIG': 'true', 'OPENCODE_DISABLE_AUTOUPDATE': 'true',
            'OPENCODE_DISABLE_MODELS_FETCH': 'true', 'OPENCODE_PURE': '1',
            'SHELL': '/control/eval-shell',
        }
        argv += ['--dir', '/run/xdg/config', '--dir', '/run/xdg/config/opencode',
                 '--dir', '/run/xdg/config/opencode/skills',
                 '--ro-bind', str(control / role / 'skills'), '/run/xdg/config/opencode/skills']
        for key, value in settings.items():
            argv += ['--setenv', key, value]
    return argv + ['--', *command]
