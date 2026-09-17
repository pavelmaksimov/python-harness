"""Shared fixtures for the custom-backend suite: a throwaway repository root.

The suite never touches the real repository's knowledge, history or harnesses.
Each test builds a minimal repository under ``memory/.tmp/evals`` with one probe,
two verified (fake) profiles and scripted subject/judge commands, exactly the way
the shared core's own tests do.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import textwrap

from evals.core.backend_api import RunRequest
from evals.core.checks import run_process
from evals.core.knowledge import record_incident
from evals.core.selection import Selection

ROOT = Path(__file__).resolve().parents[4]
IDENTITY = {'name': 'custom', 'version': 'test', 'ids': {'suite': True}}
SELECTION = Selection(include_numbers=(6, 7, 9), exclude_numbers=(), numbers=(6, 7, 9),
                      harness_ids=('python-architecture', 'python-fsm', 'python-stdlib-first-review'))
PROFILE_VERSION = '0.0.0-test'
SUBJECT = '''
    import json, pathlib
    pathlib.Path("service.py").write_text("def create_order():\\n    return {}\\n")
    print(json.dumps({"type": "text", "part": {"text": "implemented"}}))
    print(json.dumps({"type": "step_finish",
                      "part": {"tokens": {"input": 11, "output": 22}, "cost": 0.75}}))
'''

FAILING = {
    'malformed_json': 'print("not json")',
    'missing_model': 'import sys; sys.stderr.write("Model fake/ghost not found\\n"); sys.exit(1)',
    'unsupported_variant': 'import sys; sys.stderr.write("Unsupported variant turbo\\n"); sys.exit(1)',
    'command_failed': 'import sys; sys.stderr.write("transient boom\\n"); sys.exit(1)',
    'timeout': 'import time; time.sleep(60)',
}


def direct(command, workspace, *, timeout, role='check', readonly=False):
    """Test double for the isolation boundary, itself a hard boundary in production."""
    return run_process(command, cwd=workspace, timeout=timeout)


def profile(role: str) -> dict:
    """A verified fake profile: the real proof fields are mandatory, never assumed."""
    stamp = '2026-09-17T00:00:00+00:00'
    return {
        'provider': 'fake', 'model': 'fake-model', 'variant': None,
        'friendly_name': 'Fake model', 'role': role, 'opencode_version': PROFILE_VERSION,
        'metadata': {'source': 'test'}, 'verification_run_id': 'verify-1',
        'succeeded_at': stamp, 'human_selected': True,
        'verification': {'status': 'success', 'run_id': 'verify-1', 'succeeded_at': stamp,
                         'provider': 'fake', 'model': 'fake-model', 'variant': None,
                         'opencode_version': PROFILE_VERSION},
    }


def task(**overrides) -> dict:
    base = {
        'id': 'demo', 'base_fixture': 'evals/_fixtures/base-project',
        'fixture': 'evals/tasks/demo/fixture', 'materialize': [],
        'checks': [{'id': 'smoke', 'kind': 'shell', 'command': ['/bin/sh', '-c', 'exit 0']}],
        'prompt': 'Implement the order domain.',
        'rubric': {'criteria': [{'id': 'structure'}, {'id': 'tests'}]},
    }
    base.update(overrides)
    return base


def repository(root: Path, probe: dict | None = None) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / 'VERSION').write_text('1.3.0\n', encoding='utf-8')
    fixture = root / 'evals/_fixtures/base-project'
    fixture.mkdir(parents=True, exist_ok=True)
    (fixture / 'app.py').write_text('print("base")\n', encoding='utf-8')
    probe_fixture = root / 'evals/tasks/demo/fixture'
    probe_fixture.mkdir(parents=True, exist_ok=True)
    (probe_fixture / 'orders.py').write_text('ORDERS = []\n', encoding='utf-8')
    (root / 'evals/tasks/demo/task.json').write_text(json.dumps(probe or task()), encoding='utf-8')
    providers = root / 'evals/knowledge/providers'
    providers.mkdir(parents=True, exist_ok=True)
    for alias, role in (('subject', 'subject'), ('judge', 'judge')):
        (providers / f'{alias}.json').write_text(json.dumps(profile(role)), encoding='utf-8')
    return root


def request(root: Path, run: str = 'run-1', **overrides) -> RunRequest:
    values = {
        'task_id': 'demo', 'include': (6, 7, 9), 'exclude': (), 'selection': SELECTION,
        'subject_profile': 'subject', 'judge_profile': 'judge',
        'workdir': Path(root) / 'evals/history/demo' / run, 'run_id': run,
        'repo_root': Path(root), 'source_commit': 'abc123', 'knowledge_revision': 'deadbeef',
    }
    values.update(overrides)
    return RunRequest(**values)


def script(directory: Path, name: str, body: str) -> tuple[str, ...]:
    path = Path(directory) / name
    path.write_text(textwrap.dedent(body), encoding='utf-8')
    return (sys.executable, str(path))


def scorecard() -> dict:
    return {'criteria': [
        {'id': 'structure', 'score': 4,
         'evidence': [{'file': 'service.py', 'line': 1, 'description': 'module shape'}]},
        {'id': 'tests', 'score': 2,
         'evidence': [{'file': 'orders.py', 'description': 'fixture kept'}]},
    ], 'summary': 'solid'}


def judge(directory: Path, payload: dict | None = None) -> tuple[str, ...]:
    target = Path(directory) / 'scorecard.json'
    target.write_text(json.dumps(payload if payload is not None else scorecard()), encoding='utf-8')
    return script(directory, 'judge.py', f'''
        import json
        payload = open({str(target)!r}, encoding="utf-8").read()
        print(json.dumps({{"type": "text", "part": {{"text": payload}}}}))
    ''')


def counting_subject(directory: Path, *, name: str = 'subject.py', fail_while_modulo: int | None = None,
                     fail_until: int | None = None) -> tuple[tuple[str, ...], Path]:
    """Scripted subject that fails deterministically across attempts or odd runs."""
    state = Path(directory) / f'{Path(name).stem}-runs.txt'
    condition = 'count % 2 == 0' if fail_while_modulo is not None else f'count < {fail_until or 0}'
    command = script(directory, name, f'''
        import json, pathlib, sys
        state = pathlib.Path({str(state)!r})
        count = int(state.read_text(encoding="utf-8")) if state.exists() else 0
        state.write_text(str(count + 1), encoding="utf-8")
        if {condition}:
            sys.stderr.write("transient boom\\n")
            sys.exit(1)
        pathlib.Path("service.py").write_text("def create_order():\\n    return {{}}\\n")
        print(json.dumps({{"type": "text", "part": {{"text": "implemented"}}}}))
    ''')
    return command, state


def incident(root: Path, *, stage: str = 'custom_subject', symptom: str = 'subject command_failed',
             remedy: dict | None = None, applicability: dict | None = None) -> dict:
    """Seed one verified incident through the core knowledge API."""
    return record_incident(Path(root), {
        'stage': stage, 'symptom': symptom,
        'applicability': applicability if applicability is not None
        else {'backend': 'custom', 'opencode_version': PROFILE_VERSION},
        'failed_attempts': [{'action': 'attempt-1', 'result': 'error:command_failed'}],
        'remedy': remedy if remedy is not None else {'kind': 'supervision_budget',
                                                     'description': 'double the wall clock'},
        'verification': {'status': 'success', 'run_id': 'seed-1',
                         'succeeded_at': '2026-09-17T10:00:00+00:00'},
    })


def incidents(root: Path) -> list[dict]:
    directory = Path(root) / 'evals/knowledge/incidents'
    if not directory.is_dir():
        return []
    return [json.loads(path.read_text(encoding='utf-8')) for path in sorted(directory.glob('*.json'))]
