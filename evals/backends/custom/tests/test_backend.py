"""Backend contract: discovery, the run catalog, patch reproduction, status, doctor."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from evals.backends.custom import doctor as doctor_module
from evals.backends.custom.backend import BACKEND, repo_root
from evals.backends.custom.tests import harness
from evals.core import checks
from evals.core.artifacts import read_manifest
from evals.core.backend_api import discover_backends
from evals.core.validate import validate_manifest


class DiscoveryTests(unittest.TestCase):
    def test_the_repository_exports_the_custom_backend(self):
        backend = discover_backends(harness.ROOT)['custom']
        self.assertEqual((backend.name, backend.version), ('custom', '1'))
        for method in ('doctor', 'run', 'status'):
            self.assertTrue(callable(getattr(backend, method)))


class CatalogTests(unittest.TestCase):
    """One full run through the backend, then the contract of what it left behind."""

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

    def run_backend(self, run: str = 'cat-1', **overrides):
        request = harness.request(self.root, run,
                                  subject_command=harness.script(self.scratch, f'{run}-subject.py',
                                                                 harness.SUBJECT),
                                  judge_command=harness.judge(self.scratch), **overrides)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = BACKEND.run(request)
        return result, stdout.getvalue()

    def test_run_writes_the_catalog_and_prints_exactly_one_marker(self):
        result, text = self.run_backend()

        self.assertEqual(result.status, 'success')
        markers = [line for line in text.splitlines() if line.startswith('HARNESS_EVAL_ARTIFACT=')]
        self.assertEqual(len(markers), 1)
        directory = Path(markers[0].split('=', 1)[1])
        self.assertTrue(directory.is_absolute())
        self.assertEqual(directory, result.artifact_dir)
        self.assertEqual(result.manifest_path, directory / 'manifest.json')

        manifest = read_manifest(directory)
        self.assertEqual(validate_manifest(manifest), [])
        self.assertEqual(manifest['backend']['name'], 'custom')
        self.assertEqual(manifest['run_id'], 'cat-1')
        self.assertEqual(manifest['judge_score'], 3)
        self.assertEqual(manifest['metrics']['checks'], {'pass': 1, 'fail': 0, 'error': 0})
        self.assertEqual(json.loads((directory / 'status.json').read_text(encoding='utf-8'))['status'],
                         'success')
        self.assertIn('structure: 4', (directory / 'report.md').read_text(encoding='utf-8'))
        self.assertEqual([attempt['action'] for attempt in manifest['attempts']],
                         ['attempt-1', 'materialize', 'subject', 'checks', 'judge'])
        self.assertEqual(manifest['attempts'][0]['result'], 'success')
        for payload in (json.dumps(manifest), (directory / 'report.md').read_text(encoding='utf-8')):
            self.assertNotIn('/home/', payload)

    def test_result_patch_reapplies_to_the_materialized_fixture(self):
        result, _ = self.run_backend('cat-patch')

        replayed = self.scratch / 'replayed'
        shutil.copytree(result.artifact_dir / 'baseline', replayed)
        # The core's patch carries no `new file mode` header, so GNU patch replays it and
        # `git apply` refuses; recorded here as a shared-core observation, not worked around.
        subprocess.run(('patch', '-p1', '--no-backup-if-mismatch', '-i',
                        str(result.artifact_dir / 'result.patch')),
                       cwd=replayed, check=True, capture_output=True, timeout=60)
        self.assertEqual((replayed / 'service.py').read_text(encoding='utf-8'),
                         (result.artifact_dir / 'workspace/service.py').read_text(encoding='utf-8'))
        self.assertEqual((replayed / 'orders.py').read_text(encoding='utf-8'), 'ORDERS = []\n')

    def test_status_reads_only_the_run_catalog(self):
        result, _ = self.run_backend('cat-status')
        package = self.root / 'evals/backends/custom'
        package.mkdir(parents=True)
        shutil.copyfile(Path(repo_root()) / 'evals/backends/custom/backend.py', package / 'backend.py')
        backend = discover_backends(self.root)['custom']

        reported = backend.status('cat-status')
        self.assertEqual(reported['status'], 'success')
        self.assertEqual(reported['artifact_dir'], str(result.artifact_dir))
        self.assertEqual(reported['archived_attempts'], [])

        unfinished = self.root / 'evals/history/demo/cat-unfinished'
        unfinished.mkdir(parents=True)
        (unfinished / 'manifest.json').write_text('{}\n', encoding='utf-8')
        self.assertEqual(backend.status('cat-unfinished')['status'], 'unfinished')
        (self.root / 'evals/history/demo/cat-running').mkdir(parents=True)
        self.assertEqual(backend.status('cat-running')['status'], 'running')
        self.assertEqual(backend.status('cat-missing')['status'], 'unknown')
        with self.assertRaises(ValueError):
            backend.status('../escape')

    def test_fake_subject_failure_modes_are_terminal_needs_human_without_retries(self):
        for index, kind in enumerate(('malformed_json', 'missing_model', 'unsupported_variant')):
            with self.subTest(kind=kind):
                subject = harness.script(self.scratch, f'{kind}.py', harness.FAILING[kind])
                request = harness.request(self.root, f'mode-{index}', subject_command=subject,
                                          judge_command=harness.judge(self.scratch))
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    result = BACKEND.run(request)
                actions = [attempt['action'] for attempt in result.attempts]
                self.assertEqual(result.status, 'error')
                self.assertEqual(actions.count('attempt-1'), 1)
                self.assertNotIn('attempt-2', actions)
                self.assertIn(kind, [attempt['result'] for attempt in result.attempts])
                expected = {'malformed_json': 'shared-core parser',
                            'missing_model': 'ask the human',
                            'unsupported_variant': 'with the human'}
                self.assertIn(expected[kind], result.error)
                self.assertEqual(validate_manifest(read_manifest(result.artifact_dir)), [])
                self.assertTrue((result.artifact_dir / 'result.patch').is_file())


class DoctorTests(unittest.TestCase):
    def setUp(self):
        base = harness.ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = harness.repository(Path(self.temp.name) / 'repo')

    def test_doctor_returns_a_structured_read_only_report(self):
        report = BACKEND.doctor()

        self.assertEqual(report['name'], 'custom')
        self.assertIn(report['status'], {'success', 'error'})
        self.assertEqual([check['id'] for check in report['checks']],
                         ['opencode', 'sandbox', 'uv_cache', 'profiles', 'config_scope', 'history'])
        for check in report['checks']:
            self.assertLessEqual({'id', 'status', 'detail', 'blocking'}, set(check))
            self.assertIn(check['status'], {'ok', 'fail'})
        self.assertEqual(report['repairs'], [])
        self.assertFalse(report['repair'])

    def test_missing_prerequisites_fail_closed_and_repair_touches_only_owned_paths(self):
        blocked = doctor_module.inspect(self.root, harness.IDENTITY)
        self.assertEqual(blocked['status'], 'error', 'a missing history directory must block a run')
        self.assertIn('history', [check['id'] for check in blocked['checks'] if check['status'] == 'fail'])

        before = {path.relative_to(self.root).as_posix() for path in self.root.rglob('*')}
        repaired = doctor_module.inspect(self.root, harness.IDENTITY, repair=True)
        after = {path.relative_to(self.root).as_posix() for path in self.root.rglob('*')}
        created = after - before

        self.assertEqual([entry['action'] for entry in repaired['repairs']],
                         ['generate_knowledge_index', 'create_history_directory'])
        self.assertEqual(created, {'evals/history', 'evals/knowledge/INDEX.md'})
        self.assertEqual([check['status'] for check in repaired['checks'] if check['id'] == 'history'],
                         ['ok'])


if __name__ == '__main__':
    unittest.main()
