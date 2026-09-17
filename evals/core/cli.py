"""Agent-facing backend-neutral evaluation commands (stdlib only)."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

from .artifacts import read_manifest
from .backend_api import RunRequest, discover_backends
from .compare import compare_runs
from .knowledge import revision, sanitize, record_provider_profile
from .matrix import load_matrix
from .profiles import load_profile, discover_candidates
from .selection import resolve_selection, ensure_coverage, format_selection
from .validate import load_tasks, validate_manifest, validate_repository


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(('git', *args), cwd=root, capture_output=True, text=True,
                            timeout=30, check=False)
    if result.returncode:
        raise ValueError(result.stderr.strip())
    return result.stdout.strip()


def _task(tasks: list[dict], requested: str | None) -> dict:
    matches = [t for t in tasks if requested == t['id'] or requested in t.get('aliases', [])]
    if len(matches) != 1:
        raise ValueError(f'Choose one existing task or module alias: {requested!r}; '
                         f'available: {", ".join(t["id"] for t in tasks) or "no probes yet"}')
    return matches[0]


def _plan(args, root: Path) -> tuple:
    matrix = load_matrix(root)
    selection = resolve_selection(args.include, args.exclude, matrix)
    print(format_selection(selection))
    task = _task(load_tasks(root), args.task or args.module)
    ensure_coverage(selection, [task], matrix)
    profiles, unresolved = {}, {}
    for role, alias in [('subject', args.subject_profile or args.provider), ('judge', args.judge_profile)]:
        if not alias:
            unresolved[role] = 'Choose a separate fixed profile with --judge-profile' if role == 'judge' else 'Choose --subject-profile or --provider'
            continue
        try:
            profiles[role] = load_profile(root, alias, role=role)
        except ValueError as exc:
            unresolved[role] = str(exc)
    return selection, task, profiles, unresolved


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2])
    commands = result.add_subparsers(dest='command', required=True)
    for name in ('plan', 'run'):
        command = commands.add_parser(name)
        command.add_argument('--task')
        command.add_argument('--module')
        command.add_argument('--provider')
        command.add_argument('--subject-profile')
        command.add_argument('--judge-profile')
        command.add_argument('--include', default='всё стандартное')
        command.add_argument('--exclude', default='')
        if name == 'run':
            command.add_argument('--backend', required=True)
            command.add_argument('--run-id')
    command = commands.add_parser('doctor')
    command.add_argument('--backend')
    command.add_argument('--repair', action='store_true')
    command = commands.add_parser('profiles')
    command.add_argument('--provider', help='Discover candidates; never selects automatically')
    command.add_argument('--query', help='Optional words from the request to narrow a large catalog')
    command.add_argument('--record', type=Path, help='Record a human-selected profile with successful smoke proof')
    command.add_argument('--alias')
    command = commands.add_parser('select')
    command.add_argument('--changed-from', required=True)
    command = commands.add_parser('compare')
    command.add_argument('run_a', type=Path)
    command.add_argument('run_b', type=Path)
    command = commands.add_parser('validate')
    command.add_argument('manifests', nargs='*', type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.repo_root.resolve()
    try:
        if args.command in ('plan', 'run'):
            selection, task, profiles, unresolved = _plan(args, root)
            if args.command == 'plan':
                output = {'task': task['id'], 'selection': asdict(selection),
                          'profiles': profiles, 'needs_human_choice': unresolved}
            else:
                if unresolved:
                    raise ValueError('Profiles unresolved; run profiles --provider PROVIDER, '
                                     'get human selection and verified smoke proof: ' + str(unresolved))
                if _git(root, 'status', '--porcelain', '--untracked-files=normal'):
                    raise ValueError('Run requires a clean Git checkout; preserve or commit current changes first')
                backends = discover_backends(root)
                if args.backend not in backends:
                    raise ValueError(f'Unknown backend {args.backend}; available: {list(backends)}')
                backend = backends[args.backend]
                health = backend.doctor(repair=False)
                if health.get('status') not in ('success', 'ok', 'healthy') and health.get('ok') is not True:
                    raise ValueError(f'Backend doctor did not confirm readiness: {health}')
                run_id = args.run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
                if not run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run_id):
                    raise ValueError('run-id must be a safe single path component')
                request = RunRequest(task['id'], selection.include_numbers,
                                     selection.exclude_numbers, selection,
                                     args.subject_profile or args.provider, args.judge_profile,
                                     root / 'evals/history' / task['id'] / run_id, run_id, root,
                                     _git(root, 'rev-parse', 'HEAD'), revision(root))
                outcome = backend.run(request)
                output = asdict(outcome)
                _print(output)
                return 0 if outcome.status == 'success' else 1
        elif args.command == 'doctor':
            backends = discover_backends(root)
            if args.backend and args.backend not in backends:
                raise ValueError(f'Unknown backend: {args.backend}')
            output = {name: backend.doctor(repair=args.repair) for name, backend in backends.items()
                      if args.backend is None or name == args.backend}
            if not output:
                output = {'notes': ['No backends installed yet.']}
        elif args.command == 'profiles':
            if args.record:
                if not args.alias:
                    raise ValueError('--record requires --alias')
                data = json.loads(args.record.read_text(encoding='utf-8'))
                output = record_provider_profile(root, args.alias, data)
            elif args.provider:
                output = {'candidates': discover_candidates(args.provider, query=args.query),
                          'next': 'Ask the human to choose; verify exact model/variant before recording.'}
            else:
                output = [load_profile(root, p.stem) for p in sorted((root / 'evals/knowledge/providers').glob('*.json'))]
        elif args.command == 'select':
            changed = _git(root, 'diff', '--name-only', args.changed_from, '--', 'harnesses').splitlines()
            tasks = load_tasks(root)
            selected = []
            for task in tasks:
                sources = [item['from'].rstrip('/') for item in task.get('materialize', [])]
                if any(path == source or path.startswith(source + '/') for path in changed for source in sources):
                    selected.append(task['id'])
            output = {'changed_paths': changed, 'tasks': selected}
        elif args.command == 'compare':
            output = compare_runs(args.run_a, args.run_b)
        else:
            output = validate_repository(root)
            for path in args.manifests:
                output['errors'].extend(f'{path.name}: {error}' for error in validate_manifest(read_manifest(path), root))
            _print(output)
            return int(bool(output['errors']))
        _print(output)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(sanitize(f'error: {exc}'), file=sys.stderr)
        return 2


def _print(value) -> None:
    # Project to JSON-compatible data first (paths and tuples), then sanitize.
    payload = json.loads(json.dumps(value, default=str))
    print(json.dumps(sanitize(payload), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
