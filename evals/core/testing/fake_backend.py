"""Scripted backend used by tests and smoke runs.

This lives outside ``evals/backends/`` on purpose: repository backends own their
own directories, so a stub must never be discoverable as a real backend. Tests
copy a one-line adapter into a throwaway repository root instead.
"""
from dataclasses import replace
from pathlib import Path
import sys

from evals.core.backend_api import BackendResult
from evals.core.execute import execute_experiment

SUBJECT = (sys.executable, '-c', (
    "import json, pathlib; "
    "pathlib.Path('orders.py').write_text('ORDERS = [1]\\n'); "
    "print(json.dumps({'type': 'text', 'part': {'text': 'built the CLI'}}))"
))
JUDGE = (sys.executable, '-c', (
    "import json; "
    "print(json.dumps({'criteria': [{'id': 'c', 'score': 3, 'evidence': 'orders.py:1'}]}))"
))


class FakeBackend:
    """Drives the real core with scripted subject and judge commands."""

    name = 'fake'
    version = '0'

    def __init__(self, subject=SUBJECT, judge=JUDGE):
        self.subject = tuple(subject)
        self.judge = tuple(judge)
        self.runs: dict[str, Path] = {}

    def doctor(self, *, repair: bool = False) -> dict:
        return {'status': 'success', 'repair': repair, 'name': self.name}

    def run(self, request) -> BackendResult:
        request = replace(request, subject_command=self.subject, judge_command=self.judge)
        directory = Path(request.workdir)
        manifest = execute_experiment(request, directory, backend={
            'name': self.name, 'version': self.version, 'ids': {'stub': True},
        })
        self.runs[request.run_id] = directory
        return BackendResult(request.run_id, manifest['status'], directory,
                             directory / 'manifest.json', manifest['attempts'], None)

    def status(self, run_id: str) -> dict:
        directory = self.runs.get(run_id)
        return {'run_id': run_id, 'status': 'unknown' if directory is None else 'finished',
                'artifact_dir': None if directory is None else str(directory)}


BACKEND = FakeBackend()
