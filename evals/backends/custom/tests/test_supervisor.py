"""Supervision: wall-clock cancellation, terminal artifacts and the raw attempt log."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from evals.backends.custom import supervisor
from evals.backends.custom.tests import harness
from evals.core import checks
from evals.core.artifacts import read_manifest
from evals.core.validate import validate_manifest


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        base = harness.ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.scratch = Path(self.temp.name)
        self.root = harness.repository(self.scratch / 'repo')
        isolation = mock.patch.object(checks, 'run_isolated', harness.direct)
        isolation.start()
        self.addCleanup(isolation.stop)

    def request(self, subject, run: str = 'sup-1', **overrides):
        return harness.request(self.root, run, subject_command=subject,
                               judge_command=harness.judge(self.scratch), **overrides)

    def test_successful_attempt_leaves_the_full_catalog_and_logs_the_child_output(self):
        request = self.request(harness.script(self.scratch, 'subject.py', harness.SUBJECT))
        outcome = supervisor.supervise(request, harness.IDENTITY, attempt=1, wall_seconds=120)

        self.assertEqual(outcome.status, 'success')
        self.assertFalse(outcome.killed)
        self.assertIsNone(outcome.error)
        directory = Path(request.workdir)
        for name in ('manifest.json', 'result.patch', 'report.md', 'status.json'):
            self.assertTrue((directory / name).is_file(), name)
        self.assertEqual(validate_manifest(read_manifest(directory)), [])
        self.assertEqual(json.loads((directory / 'status.json').read_text(encoding='utf-8'))['status'],
                         'success')
        self.assertIn('+def create_order():', (directory / 'result.patch').read_text(encoding='utf-8'))
        # The child's own marker belongs to the raw log, so stdout keeps exactly one line per run.
        log = supervisor.log_path(request, 1)
        self.assertIsNotNone(log)
        self.assertIn('HARNESS_EVAL_ARTIFACT=', log.read_text(encoding='utf-8'))

    def test_expired_wall_clock_cancels_the_attempt_and_still_writes_artifacts(self):
        request = self.request(harness.script(self.scratch, 'hang.py', harness.FAILING['timeout']))
        stdout = io.StringIO()
        started = time.monotonic()
        with contextlib.redirect_stdout(stdout):
            outcome = supervisor.supervise(request, harness.IDENTITY, attempt=1, wall_seconds=0.7)
        elapsed = time.monotonic() - started

        self.assertTrue(outcome.killed)
        self.assertEqual(outcome.status, 'timeout')
        self.assertLess(elapsed, 30, 'the cancelled attempt must not outlive its budget')
        directory = Path(request.workdir)
        manifest = read_manifest(directory)
        self.assertEqual(validate_manifest(manifest), [])
        self.assertEqual(manifest['status'], 'timeout')
        self.assertEqual(manifest['attempts'], [])
        self.assertIn('wall clock', outcome.error)
        self.assertIn('cancelled', (directory / 'report.md').read_text(encoding='utf-8'))
        # The parent owns the operator's handle: a killed attempt still names its run directory.
        self.assertEqual([line for line in stdout.getvalue().splitlines()
                          if line.startswith('HARNESS_EVAL_ARTIFACT=')],
                         [f'HARNESS_EVAL_ARTIFACT={directory}'])

    def test_child_dying_before_artifacts_is_reported_as_error(self):
        request = self.request(harness.script(self.scratch, 'subject.py', harness.SUBJECT))
        stdout = io.StringIO()
        with mock.patch.object(supervisor, 'execute_experiment', side_effect=RuntimeError('core exploded')), \
                contextlib.redirect_stdout(stdout):
            outcome = supervisor.supervise(request, harness.IDENTITY, attempt=1, wall_seconds=60)

        self.assertFalse(outcome.killed)
        self.assertEqual(outcome.status, 'error')
        self.assertIn('terminal artifacts', outcome.error)
        self.assertEqual(validate_manifest(read_manifest(Path(request.workdir))), [])
        self.assertEqual(json.loads((Path(request.workdir) / 'status.json').read_text(encoding='utf-8'))['status'],
                         'error')
        self.assertEqual([line for line in stdout.getvalue().splitlines()
                          if line.startswith('HARNESS_EVAL_ARTIFACT=')],
                         [f'HARNESS_EVAL_ARTIFACT={Path(request.workdir)}'])

    def test_archiving_keeps_earlier_attempts_beside_the_canonical_directory(self):
        workdir = Path(self.root) / 'evals/history/demo/archived'
        workdir.mkdir(parents=True)
        (workdir / 'manifest.json').write_text('{}\n', encoding='utf-8')
        self.assertIsNone(supervisor.archive_previous(workdir / 'never-created'))
        empty = workdir / 'empty'
        empty.mkdir()
        self.assertIsNone(supervisor.archive_previous(empty), 'an empty directory holds no history')
        first = supervisor.archive_previous(workdir)
        self.assertEqual(first.name, 'archived.a1')
        self.assertFalse(workdir.exists())
        workdir.mkdir()
        (workdir / 'manifest.json').write_text('{}\n', encoding='utf-8')
        second = supervisor.archive_previous(workdir)
        self.assertEqual(second.name, 'archived.a2')
        self.assertEqual(sorted(path.name for path in first.parent.iterdir() if '.a' in path.name),
                         ['archived.a1', 'archived.a2'])

    def test_wall_budget_follows_the_task_stage_timeouts(self):
        probe = harness.task(subject_timeout_seconds=10, check_timeout_seconds=20, judge_timeout_seconds=30)
        harness.repository(self.root, probe)
        request = self.request(harness.script(self.scratch, 'subject.py', harness.SUBJECT))
        self.assertEqual(supervisor.wall_budget(request), 360.0)

        (Path(self.root) / 'evals/tasks/demo/task.json').write_text('not json', encoding='utf-8')
        self.assertEqual(supervisor.wall_budget(request), 2400.0)


if __name__ == '__main__':
    unittest.main()
