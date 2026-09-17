"""Cross-backend parity: one schema and one compare command for both backends."""
import json
from pathlib import Path
import tempfile
import unittest

from evals.backends.openresearch.tests import fixtures
from evals.core.compare import compare_runs
from evals.core.validate import validate_manifest

REPO_ROOT = fixtures.REPO_ROOT


def write_run(directory: Path, manifest: dict, patch: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (directory / 'result.patch').write_text(patch, encoding='utf-8')
    (directory / 'report.md').write_text('# Evaluation report\n', encoding='utf-8')
    (directory / 'status.json').write_text(json.dumps({'run_id': manifest['run_id'],
                                                       'status': manifest['status']}),
                                           encoding='utf-8')
    return directory


class ParityTests(unittest.TestCase):
    """A synthetic orx manifest must validate and compare beside a custom one."""

    def setUp(self):
        base = REPO_ROOT / 'memory/.tmp/evals-parity'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def manifests(self):
        orx = fixtures.sample_manifest(
            'a1b2c3d4e5f60718', run_id='orx-run-1',
            backend={'name': 'openresearch', 'version': '0.2.4',
                     'ids': {'project': 'evalpyh', 'experiment': 'evalpyh_2',
                             'run': 'evalpyh_2_run_1', 'fingerprint': 'a1b2c3d4e5f60718'}})
        custom = fixtures.sample_manifest(
            'feedfacecafebeef', run_id='custom-run-1',
            backend={'name': 'custom', 'version': '1', 'ids': {'run': 'custom-run-1'}})
        return orx, custom

    def test_both_backends_share_one_schema_and_compare(self):
        orx, custom = self.manifests()
        a = write_run(self.directory / 'orx', orx,
                      'diff --git a/orders.py b/orders.py\n+ORX = 1\n')
        b = write_run(self.directory / 'custom', custom,
                      'diff --git a/orders.py b/orders.py\n+CUSTOM = 1\n')
        self.assertEqual(validate_manifest(orx, REPO_ROOT), [])
        self.assertEqual(validate_manifest(custom, REPO_ROOT), [])
        report = compare_runs(a, b)
        self.assertEqual(report['a']['backend']['name'], 'openresearch')
        self.assertEqual(report['a']['backend']['version'], '0.2.4')
        self.assertEqual(report['b']['backend']['name'], 'custom')
        self.assertEqual(report['a']['run_id'], 'orx-run-1')
        self.assertIn('+CUSTOM = 1', report['patch_diff'])
        self.assertEqual(report['task'], orx['task'])

    def test_compare_refuses_a_different_task_or_rubric_hash(self):
        orx, custom = self.manifests()
        custom['task'] = dict(custom['task'], rubric_hash='9' * 64)
        a = write_run(self.directory / 'orx', orx, 'diff --git a/orders.py b/orders.py\n')
        b = write_run(self.directory / 'custom', custom,
                      'diff --git a/orders.py b/orders.py\n')
        with self.assertRaisesRegex(ValueError, 'different task or rubric'):
            compare_runs(a, b)

    def test_schema_rejects_an_orx_manifest_without_its_ids(self):
        orx, _ = self.manifests()
        orx['backend'] = {'name': 'openresearch', 'version': '0.2.4'}
        errors = validate_manifest(orx, REPO_ROOT)
        self.assertIn('$.backend.ids: required', errors)


if __name__ == '__main__':
    unittest.main()
