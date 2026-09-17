"""Backend discovery and the CLI wiring between backend, core, and artifacts."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evals.core import cli
from evals.core.backend_api import discover_backends
from evals.core.matrix import load_matrix

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = 'from evals.core.testing.fake_backend import BACKEND\n'


def _git(root: Path, *args: str) -> None:
    subprocess.run(('git', *args), cwd=root, check=True, capture_output=True, timeout=60)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def backend(self, name='fake', body=ADAPTER):
        directory = self.root / 'evals/backends' / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'backend.py').write_text(body, encoding='utf-8')
        return directory

    def test_discovery_loads_every_exported_backend(self):
        self.backend()
        found = discover_backends(self.root)
        self.assertEqual(list(found), ['fake'])
        self.assertEqual((found['fake'].name, found['fake'].version), ('fake', '0'))
        self.assertEqual(found['fake'].doctor(repair=True)['repair'], True)

    def test_modules_without_a_backend_export_are_rejected(self):
        self.backend(body='value = 1\n')
        with self.assertRaisesRegex(ValueError, 'BACKEND'):
            discover_backends(self.root)

    def test_duplicate_or_missing_identity_is_rejected(self):
        self.backend('first')
        self.backend('second')
        with self.assertRaisesRegex(ValueError, 'Duplicate backend name'):
            discover_backends(self.root)

    def test_symlinked_backend_files_are_rejected(self):
        directory = self.backend()
        (directory / 'backend.py').unlink()
        (directory / 'backend.py').symlink_to(self.root / 'outside.py')
        (self.root / 'outside.py').write_text(ADAPTER, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inside the repository'):
            discover_backends(self.root)


class CliRunTests(unittest.TestCase):
    """One end-to-end run through the CLI, discovery, core and artifacts."""

    def setUp(self):
        base = ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'evals').mkdir()
        (self.root / 'evals/HARNESS_MATRIX.md').write_text((ROOT / 'evals/HARNESS_MATRIX.md').read_text(encoding='utf-8'), encoding='utf-8')
        (self.root / 'README.md').write_text((ROOT / 'README.md').read_text(encoding='utf-8'), encoding='utf-8')
        numbers = sorted(row.number for row in load_matrix(ROOT)
                         if row.primary_probe.strip('`') == 'orders-cli')
        task = self.root / 'evals/tasks/orders-cli'
        task.mkdir(parents=True)
        (task / 'task.json').write_text(json.dumps({
            'id': 'orders-cli', 'aliases': ['cli'], 'covered_numbers': numbers,
            'materialize': [], 'prompt': 'Build the CLI.',
            'rubric': {'criteria': [{'id': 'c', 'description': 'quality'}]},
            'checks': [{'id': 'smoke', 'kind': 'shell', 'command': ['/bin/sh', '-c', 'exit 0']}],
        }), encoding='utf-8')
        for alias, model, role, run_id in (('fake', 'fake/tiny', 'subject', 'smoke-1'),
                                           ('fake-judge', 'fake/judge', 'judge', 'smoke-2')):
            providers = self.root / 'evals/knowledge/providers'
            providers.mkdir(parents=True, exist_ok=True)
            (providers / f'{alias}.json').write_text(json.dumps({
                'provider': 'fake', 'model': model, 'variant': None, 'friendly_name': alias,
                'role': role, 'opencode_version': '0.0.0', 'metadata': {}, 'human_selected': True,
                'verification_run_id': run_id, 'succeeded_at': '2026-09-17T10:00:00+00:00',
                'verification': {'status': 'success', 'run_id': run_id,
                                 'succeeded_at': '2026-09-17T10:00:00+00:00', 'provider': 'fake',
                                 'model': model, 'variant': None, 'opencode_version': '0.0.0'},
            }), encoding='utf-8')
        backends = self.root / 'evals/backends/fake'
        backends.mkdir(parents=True)
        (backends / 'backend.py').write_text(ADAPTER, encoding='utf-8')
        _git(self.root, 'init', '-q')
        _git(self.root, 'add', '-A')
        _git(self.root, '-c', 'user.email=test@example.com', '-c', 'user.name=Test',
             'commit', '-qm', 'smoke', '--no-gpg-sign')

    def test_run_writes_artifacts_and_prints_the_run_directory(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(['--repo-root', str(self.root), 'run', '--backend', 'fake',
                             '--task', 'orders-cli', '--subject-profile', 'fake',
                             '--judge-profile', 'fake-judge', '--include', '25-26',
                             '--run-id', 'cli-run'])
        text = stdout.getvalue()
        marker = next(line for line in text.splitlines() if line.startswith('HARNESS_EVAL_ARTIFACT='))
        directory = Path(marker.split('=', 1)[1])
        self.assertTrue(directory.is_absolute(), 'the marker must carry a usable local path')
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['run_id'], 'cli-run')
        self.assertEqual(manifest['harness_ids'], ['python-typer', 'cli-design'])
        self.assertEqual(manifest['include_numbers'], [25, 26])
        self.assertTrue((directory / 'result.patch').exists())
        self.assertTrue((directory / 'report.md').exists())
        self.assertTrue((directory / 'status.json').exists())
        self.assertIn(manifest['checks'][0]['status'], {'pass', 'error', 'fail'})
        if manifest['checks'][0]['status'] == 'pass':
            self.assertEqual((code, manifest['status']), (0, 'success'))
            self.assertEqual(manifest['judge_score'], 3)
        else:
            self.assertEqual((code, manifest['status']), (1, 'error'))
            self.assertRegex(manifest['checks'][0]['evidence'], 'bwrap|bubblewrap|namespac')
            self.assertNotIn('judge', [attempt['action'] for attempt in manifest['attempts']])

    def test_run_refuses_a_dirty_checkout_and_unknown_backend(self):
        (self.root / 'uncommitted.txt').write_text('x', encoding='utf-8')
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = cli.main(['--repo-root', str(self.root), 'run', '--backend', 'fake',
                             '--task', 'orders-cli', '--subject-profile', 'fake',
                             '--judge-profile', 'fake-judge', '--include', '25-26'])
        self.assertEqual(code, 2)
        self.assertIn('clean Git checkout', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
