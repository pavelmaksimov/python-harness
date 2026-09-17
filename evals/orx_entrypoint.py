#!/usr/bin/env python3
"""Subject-side entry point executed inside an OpenResearch experiment node.

This is the fixed in-node run contract of the OpenResearch backend (plan B).
Orchestrated by ``evals/backends/openresearch/backend.py``, a node runs:

    uv run python evals/orx_entrypoint.py execute \
      --task <task-id> --include <canonical-numbers> \
      --subject-profile <profile> --judge-profile <profile> \
      --selection <fingerprint> --source-commit <recorded-commit>

The script owns only the subject matter: it verifies the recorded commit, the
task manifest, the harness matrix and both profiles, resolves the selection,
checks the frozen selection fingerprint, then delegates to the backend-neutral
``evals.core.execute.execute_experiment`` (sandbox materialization, isolated
subject, deterministic checks, read-only judge, normalized artifacts). It ends
by printing a compact machine-readable summary; the shared core prints the
``HARNESS_EVAL_ARTIFACT=<path>`` marker that the backend retrieves from the
orx run log. Exit codes: 0 success, 1 failed checks, 2 configuration or
verification error. Subject and judge never see OpenResearch knowledge, other
experiment nodes or global instructions; backend-specific logic is forbidden
here beyond this frozen command contract.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.core.backend_api import RunRequest
from evals.core.execute import execute_experiment
from evals.core.knowledge import revision, sanitize
from evals.core.matrix import load_matrix
from evals.core.profiles import load_profile
from evals.core.selection import ensure_coverage, resolve_selection
from evals.backends.openresearch.backend import selection_fingerprint
from evals.core.validate import load_tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    execute = commands.add_parser('execute', help='run one probe inside this node')
    execute.add_argument('--task', required=True)
    execute.add_argument('--include', required=True,
                         help='canonical harness numbers, e.g. 25-26')
    execute.add_argument('--exclude', default='')
    execute.add_argument('--subject-profile', required=True)
    execute.add_argument('--judge-profile', required=True)
    execute.add_argument('--selection', required=True,
                         help='selection fingerprint frozen on the node')
    execute.add_argument('--source-commit', required=True,
                         help='recorded commit of this node (nodes run without '
                              'Git metadata, so it cannot be read from the tree)')
    return parser


def execute(args: argparse.Namespace, *, repo_root: Path | None = None,
            subject_command=None, judge_command=None) -> int:
    """One probe run.

    ``repo_root`` and the ``*_command`` overrides exist for the test suite only;
    a real node run leaves them unset and always uses this checkout plus the
    isolated OpenCode subject and judge.
    """
    repo_root = Path(repo_root or ROOT)
    matrix = load_matrix(repo_root)
    tasks = load_tasks(repo_root)
    if not any(task['id'] == args.task for task in tasks):
        raise ValueError(f'unknown task {args.task!r}')
    source_commit = args.source_commit.strip()
    if not re.fullmatch(r'[0-9a-f]{7,64}', source_commit):
        raise ValueError('--source-commit must be the recorded Git commit hash')
    # Loading with the role check doubles as the profile verification step.
    load_profile(repo_root, args.subject_profile, role='subject')
    load_profile(repo_root, args.judge_profile, role='judge')
    selection = resolve_selection(args.include, args.exclude, matrix)
    ensure_coverage(selection, tasks, matrix)
    fingerprint = selection_fingerprint(
        task_id=args.task, include=selection.include_numbers,
        exclude=selection.exclude_numbers, harness_ids=selection.harness_ids,
        source_commit=source_commit, subject_profile=args.subject_profile,
        judge_profile=args.judge_profile,
    )
    if fingerprint != args.selection:
        raise ValueError('selection fingerprint mismatch: this node is frozen for '
                         f'{args.selection!r}; branch a new node instead of editing it')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    artifact_dir = repo_root / 'memory/.tmp/orx-runs' / args.task / run_id
    request = RunRequest(
        task_id=args.task, include=selection.include_numbers,
        exclude=selection.exclude_numbers, selection=selection,
        subject_profile=args.subject_profile, judge_profile=args.judge_profile,
        workdir=artifact_dir, run_id=run_id, repo_root=repo_root,
        source_commit=source_commit, knowledge_revision=revision(repo_root),
    )
    if subject_command is not None:
        request = replace(request, subject_command=tuple(subject_command))
    if judge_command is not None:
        request = replace(request, judge_command=tuple(judge_command))
    manifest = execute_experiment(request, artifact_dir, backend={
        'name': 'openresearch', 'version': '',
        'ids': {'fingerprint': fingerprint, 'local_run': run_id},
    })
    print(json.dumps({
        'task': args.task, 'run_id': run_id, 'status': manifest['status'],
        'judge_score': manifest['judge_score'],
        'checks': manifest['metrics'].get('checks', {}),
        'artifact_dir': str(artifact_dir),
    }, ensure_ascii=False))
    return {'success': 0, 'failed': 1}.get(manifest['status'], 2)


def main(argv: list[str] | None = None, *, repo_root: Path | None = None,
         subject_command=None, judge_command=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return execute(args, repo_root=repo_root, subject_command=subject_command,
                       judge_command=judge_command)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(sanitize(f'error: {exc}'), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
