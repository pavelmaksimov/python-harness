"""Approved degraded isolation: gating, policy pinning, doctor and run wiring."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from evals.backends.custom import doctor as doctor_module
from evals.backends.custom import weak_isolation
from evals.backends.custom.backend import BACKEND
from evals.backends.custom.tests import harness
from evals.core import checks
from evals.core.artifacts import read_manifest
from evals.core.knowledge import record_backend_health
from evals.core.validate import validate_manifest


def approve(root: Path, *, approved_by: str | None = 'vur21 (test)') -> None:
    record = {'backend': 'custom', 'recorded_at': '2026-09-17T12:00:00+00:00'}
    if approved_by is not None:
        record['weak_isolation'] = {'approved_by': approved_by,
                                    'approved_at': '2026-09-17T12:00:00+00:00',
                                    'reason': 'test approval'}
    record_backend_health(root, 'custom', record)


class GatingTests(unittest.TestCase):
    def setUp(self):
        base = harness.ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = harness.repository(Path(self.temp.name) / 'repo')

    def test_activation_needs_approval_and_a_broken_namespace_host(self):
        self.assertFalse(weak_isolation.active(self.root))
        approve(self.root, approved_by=None)
        self.assertFalse(weak_isolation.active(self.root),
                         'a backend health record without approval is not consent')
        approve(self.root)
        with mock.patch.object(weak_isolation, 'host_namespaces_work', return_value=True):
            self.assertFalse(weak_isolation.active(self.root), 'healthy namespaces keep the sandbox')
        with mock.patch.object(weak_isolation, 'host_namespaces_work', return_value=False):
            self.assertTrue(weak_isolation.active(self.root))

    def test_host_execution_swaps_the_boundary_only_inside_the_block(self):
        original = checks.run_isolated
        with weak_isolation.host_execution():
            self.assertIs(checks.run_isolated, weak_isolation._host_run_isolated)
        self.assertIs(checks.run_isolated, original)

    def test_the_launcher_pins_the_role_policy_and_leaves_the_model_to_the_core(self):
        request = harness.request(self.root, 'weak-cmd')
        subject = weak_isolation.command_for(request, 'subject')
        judge = weak_isolation.command_for(request, 'judge')
        for command, role in ((subject, 'subject'), (judge, 'judge')):
            self.assertEqual(command[0], 'env')
            settings = dict(item.split('=', 1) for item in command[1:] if '=' in item)
            self.assertEqual(settings['OPENCODE_CONFIG_DIR'], str(request.workdir / 'control' / role))
            self.assertIn('"edit"', settings['OPENCODE_CONFIG_CONTENT'])
            self.assertEqual(settings['OPENCODE_DISABLE_PROJECT_CONFIG'], 'true')
            self.assertEqual(settings['OPENCODE_PURE'], '1')
            self.assertEqual(settings['SHELL'], str(weak_isolation.shell_path(request.repo_root)))
            config = json.loads(settings['OPENCODE_CONFIG_CONTENT'])
            self.assertEqual(config['instructions'], [str(request.workdir / 'workspace' / 'AGENTS.md')],
                             'weak mode points the policy at the real workspace')
            self.assertIn(str(weak_isolation.shim_path(request.repo_root)), command)
            self.assertIn(str(weak_isolation.transcript_path(request, role)), command)
            self.assertNotIn('--model', command,
                             'the core appends the invocation of the profile it chose')
            self.assertEqual(command[-1], str(weak_isolation.transcript_path(request, role)))
        self.assertIn('"edit": "deny"', ' '.join(judge), 'the judge policy stays read-only')

    def test_transcript_shim_forwards_stream_and_exit_code(self):
        request = harness.request(self.root, 'weak-shim')
        transcript = weak_isolation.transcript_path(request, 'subject')
        script = harness.script(self.root, 'noisy.py', '''
            import json, sys
            print(json.dumps({"type": "text", "part": {"text": "hello"}}))
            sys.stderr.write("noise")
            sys.exit(3)
        ''')
        outcome = subprocess.run([sys.executable, str(weak_isolation.shim_path(self.root)),
                                  str(transcript), *script], capture_output=True, text=True, timeout=60)
        self.assertEqual(outcome.returncode, 3, 'the shim keeps the real exit code')
        self.assertIn('hello', outcome.stdout)
        self.assertIn('hello', transcript.read_text(encoding='utf-8'))
        self.assertIn('noise', transcript.read_text(encoding='utf-8'))

    def test_weak_shell_enforces_the_allowlist_without_bubblewrap(self):
        shell = weak_isolation.shell_path(self.root)
        self.assertTrue(shell.is_file() and shell.stat().st_mode & 0o111)
        rejected = subprocess.run([str(shell), '-c', 'echo hi'], capture_output=True, text=True, timeout=30)
        self.assertIn('not allowlisted', rejected.stdout + rejected.stderr)
        outside = subprocess.run([str(shell), '-c', 'git status /etc'], capture_output=True, text=True, timeout=30)
        self.assertIn('external paths', outside.stdout + outside.stderr)
        allowed = subprocess.run([str(shell), '-c', 'git status --short'], cwd=self.root,
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)


class DoctorWeakTests(unittest.TestCase):
    def setUp(self):
        base = harness.ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = harness.repository(Path(self.temp.name) / 'repo')

    def test_doctor_reports_weak_isolation_only_with_approval(self):
        probe = mock.patch.object(weak_isolation, 'namespace_probe',
                                  return_value=(False, 'pid namespaces unavailable: forced'))
        approve(self.root)
        with probe:
            report = doctor_module.inspect(self.root, harness.IDENTITY)
        sandbox = next(check for check in report['checks'] if check['id'] == 'sandbox')
        self.assertEqual((report['isolation'], sandbox['status']), ('weak', 'ok'))
        self.assertIn('vur21 (test)', sandbox['detail'])
        self.assertTrue(any('temporary' in note for note in report['notes']))

        fresh = harness.repository(Path(self.temp.name) / 'repo-no-approval')
        with probe:
            report = doctor_module.inspect(fresh, harness.IDENTITY)
        sandbox = next(check for check in report['checks'] if check['id'] == 'sandbox')
        self.assertEqual((report['isolation'], sandbox['status'], sandbox['blocking']),
                         ('sandbox', 'fail', True))


class WeakRunTests(unittest.TestCase):
    def setUp(self):
        base = harness.ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.scratch = Path(self.temp.name)
        self.root = harness.repository(self.scratch / 'repo')

    def test_approved_weak_run_records_degraded_identity(self):
        approve(self.root)
        request = harness.request(self.root, 'weak-run',
                                  subject_command=harness.script(self.scratch, 'subject.py', harness.SUBJECT),
                                  judge_command=harness.judge(self.scratch))
        stdout = io.StringIO()
        with mock.patch.object(weak_isolation, 'host_namespaces_work', return_value=False), \
                contextlib.redirect_stdout(stdout):
            result = BACKEND.run(request)

        self.assertEqual(result.status, 'success')
        manifest = read_manifest(result.artifact_dir)
        self.assertEqual(validate_manifest(manifest), [])
        self.assertEqual(manifest['backend']['ids']['isolation'], 'weak-approved')
        self.assertEqual(manifest['backend']['ids']['supervision'], 'wall-clock-process-group')
        self.assertEqual([attempt['action'] for attempt in manifest['attempts']],
                         ['attempt-1', 'materialize', 'subject', 'checks', 'judge'])


if __name__ == '__main__':
    unittest.main()
