"""OpenResearch backend behavior against a fake orx CLI installed on PATH."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from evals.backends.openresearch.backend import OpenResearchBackend, OrxError
from evals.backends.openresearch.tests import fake_orx, fixtures
from evals.core.validate import validate_manifest

REPO_ROOT = fixtures.REPO_ROOT
PROJECT = {'id': 'evalpyh', 'name': 'python-harness', 'prefix': 'evalpyh_',
           'path': None, 'baselineBranch': 'main'}


class BackendTests(unittest.TestCase):
    def setUp(self):
        base = REPO_ROOT / 'memory/.tmp/evals-orx'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        base_path = Path(self.temp.name)
        self.root = base_path / 'repo'
        self.head = fixtures.build_eval_repo(self.root)
        self.project_repo = fixtures.build_project_repo(base_path / 'project.git',
                                                        self.root)
        self.project = dict(PROJECT, path=str(self.project_repo))
        self.artifacts = str(base_path / 'artifacts')
        original = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, original)

    def state_dir(self) -> Path:
        return Path(self.temp.name) / 'orx-state'

    def fingerprint(self) -> str:
        return fixtures.fingerprint_for(fixtures.make_request(self.root, self.head))

    def run_backend(self, run_id='run-1', **overrides):
        request = fixtures.make_request(self.root, self.head, run_id=run_id,
                                        **overrides)
        return OpenResearchBackend().run(request), request

    # ------------------------------------------------------------- project
    def test_run_fails_closed_without_a_registered_project(self):
        with fake_orx.install(Path(self.temp.name)):
            with self.assertRaises(OrxError) as failure:
                self.run_backend()
        message = str(failure.exception)
        self.assertIn('orx up --no-agent --no-telemetry', message)
        self.assertIn('import this repository', message)

    def test_project_cache_hit_and_stale_re_resolution(self):
        cache = self.root / 'memory/.tmp/orx-project.json'
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              artifact_root=self.artifacts,
                              artifact_files=fixtures.artifact_payloads(
                                  '__FINGERPRINT__')):
            self.run_backend()
            self.assertEqual(json.loads(cache.read_text())['project_id'], 'evalpyh')
            resolved_at = json.loads(cache.read_text())['resolved_at']
            self.run_backend(run_id='run-2')
            self.assertEqual(json.loads(cache.read_text())['resolved_at'], resolved_at)
            cache.write_text(json.dumps({'project_id': 'gone', 'repo_path': 'x'}),
                             encoding='utf-8')
            self.run_backend(run_id='run-3')
        self.assertEqual(json.loads(cache.read_text())['project_id'], 'evalpyh')
        self.assertEqual(json.loads(cache.read_text())['repo_path'],
                         str(self.root.resolve()))

    def test_doctor_reports_blocked_with_registration_steps(self):
        with fake_orx.install(Path(self.temp.name)):
            report = OpenResearchBackend().doctor()
        self.assertEqual(report['status'], 'blocked')
        self.assertEqual(report['checks']['version']['version'], '0.2.4')
        self.assertEqual(report['checks']['telemetry']['value'], 'off')
        steps = '\n'.join(report['checks']['project']['steps'])
        self.assertIn('orx up --no-agent --no-telemetry', steps)
        self.assertIn('orx projects --json', steps)

    def test_doctor_smoke_records_health_through_the_knowledge_api(self):
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              artifact_root=str(Path(self.temp.name) / 'smoke'),
                              artifact_files={'marker.txt': 'ok'}):
            backend = OpenResearchBackend()
            first = backend.doctor(repair=True)
            second = backend.doctor(repair=True)
            argv = fake_orx.argv_calls(self.state_dir())
        self.assertEqual(first['status'], 'success')
        self.assertEqual(first['checks']['smoke']['status'], 'ok')
        self.assertEqual(second['checks']['smoke']['status'], 'ok')
        health = json.loads(
            (self.root / 'evals/knowledge/backends/openresearch.json').read_text())
        self.assertEqual(health['orx_version'], '0.2.4')
        self.assertEqual(health['smoke']['status'], 'success')
        self.assertEqual(health['verification']['status'], 'success')
        creates = [call for call in argv if call[:1] == ['create-experiment']]
        self.assertEqual(len(creates), 1)  # the smoke node is created once, reused after
        self.assertEqual(len([call for call in argv if call[:2] == ['exp', 'run']]), 2)

    # ----------------------------------------------------------------- nodes
    def test_baseline_created_once_and_variant_reused_by_fingerprint(self):
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              artifact_root=self.artifacts,
                              artifact_files=fixtures.artifact_payloads(
                                  '__FINGERPRINT__')):
            first, _ = self.run_backend()
            second, _ = self.run_backend(run_id='run-2')
            argv = fake_orx.argv_calls(self.state_dir())
        self.assertEqual((first.status, second.status), ('success', 'success'))
        creates = [call for call in argv if call[0] == 'create-experiment']
        self.assertEqual(len(creates), 2, 'one baseline root plus one variant node')
        self.assertTrue(creates[0][-1] == '--baseline' or '--baseline' in creates[0])
        self.assertEqual(creates[0][creates[0].index('--title') + 1], 'eval orders-cli')
        runs = [call for call in argv if call[:2] == ['exp', 'run']]
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0][2], runs[1][2], 'the same node is re-run')
        self.assertNotEqual(first.run_id, second.run_id)

    def test_configuration_change_creates_a_child_node(self):
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              artifact_root=self.artifacts,
                              artifact_files=fixtures.artifact_payloads(
                                  '__FINGERPRINT__')):
            first, request = self.run_backend()
            fixtures.write_profile(self.root / 'evals/knowledge/providers',
                                   'judge2', 'judge', 'fake/judge2')
            second, changed = self.run_backend(run_id='run-2', judge_profile='judge2')
            argv = fake_orx.argv_calls(self.state_dir())
        changed_fingerprint = fixtures.fingerprint_for(changed)
        self.assertNotEqual(fixtures.fingerprint_for(request), changed_fingerprint)
        self.assertEqual((first.status, second.status), ('success', 'success'))
        creates = [call for call in argv if call[0] == 'create-experiment']
        self.assertEqual(len(creates), 3)
        child = creates[2]
        self.assertEqual(child[child.index('--parent') + 1], 'evalpyh_1')
        self.assertIn('--selection ' + changed_fingerprint,
                      child[child.index('--run-command') + 1])

    # ------------------------------------------------------------------- run
    def test_run_exports_normalized_artifacts_carrying_the_orx_ids(self):
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              artifact_root=self.artifacts,
                              artifact_files=fixtures.artifact_payloads(
                                  '__FINGERPRINT__')):
            outcome, request = self.run_backend()
            argv = fake_orx.argv_calls(self.state_dir())
        self.assertIsNone(outcome.error)
        self.assertEqual(outcome.status, 'success')
        self.assertEqual(outcome.artifact_dir, request.workdir)
        self.assertEqual(outcome.manifest_path, request.workdir / 'manifest.json')
        run_argv = next(call for call in argv if call[:2] == ['exp', 'run'])
        self.assertEqual(run_argv[run_argv.index('--backend') + 1], 'local')
        self.assertEqual(run_argv[run_argv.index('--timeout') + 1], '30m')
        manifest = json.loads((request.workdir / 'manifest.json').read_text())
        self.assertEqual(manifest['run_id'], 'evalpyh_2_run_1')
        self.assertEqual(manifest['backend'], {
            'name': 'openresearch', 'version': '0.2.4',
            'ids': {'project': 'evalpyh', 'experiment': 'evalpyh_2',
                    'run': 'evalpyh_2_run_1', 'fingerprint': self.fingerprint()},
        })
        self.assertEqual(validate_manifest(manifest, self.root), [])
        self.assertEqual(
            json.loads((request.workdir / 'status.json').read_text())['run_id'],
            'evalpyh_2_run_1')
        self.assertTrue((request.workdir / 'result.patch').exists())

    def test_exporter_fallback_scans_orx_worktrees_when_the_marker_is_missing(self):
        artifacts = str(self.project_repo / 'memory/.tmp/orx-runs' / fixtures.TASK_ID)
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              artifact_root=artifacts, omit_marker=True,
                              artifact_files=fixtures.artifact_payloads(
                                  '__FINGERPRINT__')):
            outcome, request = self.run_backend()
        self.assertEqual(outcome.status, 'success')
        self.assertTrue((request.workdir / 'manifest.json').exists())
        retrieval = [attempt for attempt in outcome.attempts
                     if attempt['action'] == 'orx artifact-retrieval']
        self.assertEqual(retrieval[0]['result'], 'worktree scan for evalpyh_2_run_1')
        incidents = list((self.root / 'evals/knowledge/incidents').glob('*.json'))
        self.assertEqual(len(incidents), 1)
        record = json.loads(incidents[0].read_text())
        self.assertEqual(record['stage'], 'orx_artifact_retrieval')
        self.assertEqual(record['verification']['run_id'], 'evalpyh_2_run_1')

    def test_failed_run_reports_an_error_instead_of_artifacts(self):
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              artifact_root=self.artifacts, run_fails=True):
            outcome, _ = self.run_backend()
        self.assertEqual(outcome.status, 'error')
        self.assertIn('failed', outcome.error)
        self.assertIsNone(outcome.manifest_path)

    def test_status_maps_the_journal_to_orx_state(self):
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              artifact_root=self.artifacts,
                              artifact_files=fixtures.artifact_payloads(
                                  '__FINGERPRINT__')):
            outcome, request = self.run_backend()
            backend = OpenResearchBackend()
            known = backend.status(outcome.run_id)
            unknown = backend.status('nope_run_404')
        self.assertEqual(known, {'run_id': 'evalpyh_2_run_1', 'status': 'done',
                                 'project': 'evalpyh', 'experiment': 'evalpyh_2',
                                 'fingerprint': self.fingerprint(),
                                 'artifact_dir': str(request.workdir)})
        self.assertEqual(unknown, {'run_id': 'nope_run_404', 'status': 'unknown'})

    def test_telemetry_is_turned_off_and_versions_detected_first(self):
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              telemetry='on', artifact_root=self.artifacts,
                              artifact_files=fixtures.artifact_payloads(
                                  '__FINGERPRINT__')):
            outcome, _ = self.run_backend()
            argv = fake_orx.argv_calls(self.state_dir())
        self.assertEqual(outcome.status, 'success')
        self.assertEqual(argv[0], ['--version'])
        self.assertEqual(argv[1], ['telemetry', 'status'])
        self.assertEqual(argv[2], ['telemetry', 'off'])

    def test_forbidden_commands_are_refused_and_never_issued(self):
        backend = OpenResearchBackend()
        for forbidden in ('delete', 'update', 'login', 'logout', 'cancel'):
            with self.assertRaisesRegex(OrxError, 'forbidden'):
                backend._orx([forbidden, 'x'])
        with fake_orx.install(Path(self.temp.name), projects=[self.project],
                              artifact_root=self.artifacts,
                              artifact_files=fixtures.artifact_payloads(
                                  '__FINGERPRINT__')):
            self.run_backend()
            commands = fake_orx.commands(self.state_dir())
        self.assertEqual(set(commands) & {'delete', 'update', 'login', 'logout',
                                          'cancel'}, set())


if __name__ == '__main__':
    unittest.main()
