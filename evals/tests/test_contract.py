"""Cross-backend and schema acceptance tests using only normalized artifacts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from evals.core.artifacts import write_artifacts, read_manifest
from evals.core.compare import compare_runs
from evals.core.validate import validate_manifest, validate_repository

ROOT = Path(__file__).resolve().parents[2]


def manifest(backend='custom', run_id='a'):
    return {
        'schema_version': '1', 'backend': {'name': backend, 'version': '1', 'ids': {}},
        'run_id': run_id, 'task': {'id': 'orders-cli', 'hash': 'abc', 'rubric_hash': 'def'},
        'include_numbers': [25], 'exclude_numbers': [], 'harness_ids': ['python-typer', 'cli-design'],
        'source_commit': 'abc123', 'catalog_version': '1.3.0', 'harness_hashes': {},
        'knowledge_revision': '000', 'subject_profile': {'model': 'subject'},
        'judge_profile': {'model': 'judge'}, 'model': {'provider': 'fake', 'model': 'fake', 'variant': None},
        'opencode_version': '1', 'attempts': [{'action': 'subject', 'result': 'success', 'duration_ms': 1, 'incident': None}],
        'checks': [{'id': 'cli', 'status': 'pass', 'evidence': 'exit 0'}], 'metrics': {'files': 1},
        'judge_score': 3, 'artifacts': {'patch': 'result.patch', 'report': 'report.md', 'status': 'status.json'},
        'status': 'success', 'started_at': '2026-09-17T10:00:00+00:00', 'finished_at': '2026-09-17T10:00:02+00:00',
    }


class ContractTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_cross_backend_comparison_preserves_cost_and_patch_evidence(self):
        a, b = self.root / 'a', self.root / 'b'
        left, right = manifest(), manifest('stub', 'b')
        right['attempts'].append({'action': 'repair_config', 'result': 'success', 'duration_ms': 2, 'incident': 'verified'})
        write_artifacts(a, left, '+old\n', 'score 3\n')
        write_artifacts(b, right, '+new\n', 'score 3\n')
        result = compare_runs(a, b)
        self.assertEqual(result['a']['backend']['name'], 'custom')
        self.assertEqual(result['b']['backend']['name'], 'stub')
        self.assertEqual(result['b']['repair_steps'], 1)
        self.assertEqual(result['b']['attempt_count'], 2)
        self.assertEqual(result['a']['wall_time_seconds'], 2)
        self.assertIn('-+old', result['patch_diff'])
        self.assertIn('++new', result['patch_diff'])
        self.assertEqual(read_manifest(a)['status'], 'success')

    def test_comparison_rejects_different_task_and_rubric(self):
        for field in ('id', 'hash', 'rubric_hash'):
            with self.subTest(field=field):
                a, b = self.root / 'a', self.root / 'b'
                left, right = manifest(), manifest('stub', 'b')
                right['task'][field] = 'other'
                write_artifacts(a, left, '', '')
                write_artifacts(b, right, '', '')
                with self.assertRaisesRegex(ValueError, 'task or rubric'):
                    compare_runs(a, b)

    def test_schema_rejects_invalid_score_types_status_and_missing_fields(self):
        self.assertEqual(validate_manifest(manifest()), [])
        mutations = [('judge_score', 5), ('judge_score', True), ('judge_score', float('nan')),
                     ('status', 'maybe'), ('include_numbers', [True]), ('started_at', 'yesterday')]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                data = manifest()
                data[field] = value
                self.assertTrue(validate_manifest(data))
        data = manifest()
        del data['knowledge_revision']
        self.assertTrue(validate_manifest(data))

    def test_repository_without_tasks_is_not_invalid(self):
        (self.root / 'evals').mkdir()
        (self.root / 'evals/HARNESS_MATRIX.md').write_text((ROOT / 'evals/HARNESS_MATRIX.md').read_text())
        (self.root / 'README.md').write_text((ROOT / 'README.md').read_text())
        result = validate_repository(self.root)
        self.assertEqual(result['errors'], [])
        self.assertIn('No probes yet', result['notes'][0])

    def test_unknown_coverage_and_missing_materialization_are_rejected(self):
        (self.root / 'evals/tasks/example').mkdir(parents=True)
        (self.root / 'evals/HARNESS_MATRIX.md').write_text((ROOT / 'evals/HARNESS_MATRIX.md').read_text())
        (self.root / 'README.md').write_text((ROOT / 'README.md').read_text())
        (self.root / 'evals/tasks/example/task.json').write_text(json.dumps({
            'id': 'example', 'covered_numbers': [999], 'materialize': [{'kind': 'rule', 'from': 'missing', 'to': 'x'}],
        }))
        errors = validate_repository(self.root)['errors']
        self.assertTrue(any('unknown covered number' in error for error in errors))
        self.assertTrue(any('materialize.from' in error for error in errors))

    def matrix_root(self):
        (self.root / 'evals').mkdir(exist_ok=True)
        (self.root / 'evals/HARNESS_MATRIX.md').write_text((ROOT / 'evals/HARNESS_MATRIX.md').read_text())
        (self.root / 'README.md').write_text((ROOT / 'README.md').read_text())

    def write_task(self, name, data):
        (self.root / 'evals/tasks' / name).mkdir(parents=True, exist_ok=True)
        (self.root / 'evals/tasks' / name / 'task.json').write_text(
            json.dumps({**data, 'id': name}), encoding='utf-8')

    @staticmethod
    def probe(**overrides):
        base = {'id': 'demo', 'covered_numbers': [], 'materialize': []}
        base.update(overrides)
        return base

    def test_shared_harness_numbers_accept_multiple_probes(self):
        self.matrix_root()
        self.write_task('one', self.probe(covered_numbers=[3]))
        self.write_task('two', self.probe(covered_numbers=[3]))
        errors = validate_repository(self.root)['errors']
        self.assertEqual([error for error in errors if 'python-tooling' in error], [])

    def test_probe_specific_numbers_stay_single_coverage(self):
        self.matrix_root()
        self.write_task('domain-order-lifecycle', self.probe(covered_numbers=[6]))
        self.write_task('other', self.probe(covered_numbers=[6]))
        errors = validate_repository(self.root)['errors']
        self.assertTrue(any('number 6 belongs to domain-order-lifecycle' in error for error in errors))
        self.assertTrue(any('expected exactly one probe, found 2' in error for error in errors))

    def test_reserved_numbers_reject_probe_coverage(self):
        self.matrix_root()
        self.write_task('demo', self.probe(covered_numbers=[1, 13]))
        errors = validate_repository(self.root)['errors']
        self.assertTrue(any('reserved for Общий workflow' in error for error in errors))
        self.assertTrue(any('reserved for Будущая library-проба' in error for error in errors))

    def test_every_shared_harness_keeps_at_least_one_probe(self):
        self.matrix_root()
        self.write_task('demo', self.probe(covered_numbers=[6]))
        errors = validate_repository(self.root)['errors']
        self.assertTrue(any('python-tooling: no probe covers it' in error for error in errors))

    def test_task_manifest_shape_is_validated(self):
        self.matrix_root()
        self.write_task('broken', self.probe(checks=[
            {'id': 'no-command', 'kind': 'shell'},
            {'id': 'bad-fixture', 'kind': 'shell', 'command': 'true', 'on_fixture': 'maybe'},
            'not-a-dict',
        ]))
        errors = validate_repository(self.root)['errors']
        self.assertTrue(any('missing prompt or prompt_file' in error for error in errors))
        self.assertTrue(any('missing rubric or rubric_file' in error for error in errors))
        self.assertTrue(any('command must be a nonempty string' in error for error in errors))
        self.assertTrue(any('on_fixture must be' in error for error in errors))
        self.assertTrue(any('only shell checks are supported' in error for error in errors))

    def test_patch_cannot_escape_run_directory(self):
        a = self.root / 'a'
        data = manifest()
        data['artifacts']['patch'] = '../outside.patch'
        write_artifacts(a, data, '', '')
        with self.assertRaisesRegex(ValueError, 'inside the run'):
            compare_runs(a, a)


if __name__ == '__main__':
    unittest.main()
