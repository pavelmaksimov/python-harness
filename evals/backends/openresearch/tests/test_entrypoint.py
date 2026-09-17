"""The in-node entry point: fingerprint guard, artifacts and exit codes."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from evals.backends.openresearch.tests import fixtures
from evals.orx_entrypoint import main

REPO_ROOT = fixtures.REPO_ROOT
SUBJECT = (sys.executable, '-c', (
    "import json, pathlib; "
    "pathlib.Path('orders.py').write_text('ORDERS = [1]\\n'); "
    "print(json.dumps({'type': 'text', 'part': {'text': 'built the CLI'}}))"
))
JUDGE = (sys.executable, '-c', (
    "import json\n"
    "text = json.dumps({'criteria': [{'id': 'c', 'score': 3, 'evidence': "
    "[{'file': 'orders.py', 'line': 1, 'description': 'module present'}]}]})\n"
    "print(json.dumps({'type': 'text', 'part': {'id': 'p', 'text': text}}))"
))
BAD_SUBJECT = (sys.executable, '-c', (
    "import json, pathlib; "
    "pathlib.Path('orders.py').write_text('NOPE = 1\\n'); "
    "print(json.dumps({'type': 'text', 'part': {'text': 'wrote the wrong module'}}))"
))
GOOD_CHECK = [{'id': 'orders-constant', 'kind': 'shell',
               'command': ['/bin/sh', '-c', 'grep -q GOOD orders.py']}]


def _isolation_available(root: Path) -> bool:
    """Shell checks need working bubblewrap; without it they fail closed."""
    from evals.core.checks import run_isolated
    workspace = root / 'isolation-probe'
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        return run_isolated(['/bin/sh', '-c', 'exit 0'], workspace, timeout=30).returncode == 0
    except Exception:  # IsolationError or a missing bwrap binary
        return False


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        base = REPO_ROOT / 'memory/.tmp/evals-orx-entry'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.head = fixtures.build_eval_repo(self.root)

    def fingerprint(self, repo_root=None):
        request = fixtures.make_request(repo_root or self.root,
                                        self.head if repo_root is None else
                                        fixtures.build_eval_repo(repo_root))
        return fixtures.fingerprint_for(request)

    def run_entry(self, *, repo_root, selection, source_commit, task='orders-cli',
                  include='25-26', subject=SUBJECT, judge=JUDGE):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(['execute', '--task', task, '--include', include,
                         '--subject-profile', fixtures.SUBJECT_ALIAS,
                         '--judge-profile', fixtures.JUDGE_ALIAS,
                         '--selection', selection,
                         '--source-commit', source_commit], repo_root=repo_root,
                        subject_command=subject, judge_command=judge)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_execute_writes_normalized_artifacts_and_summary(self):
        fingerprint = self.fingerprint()
        code, stdout, stderr = self.run_entry(repo_root=self.root,
                                              selection=fingerprint,
                                              source_commit=self.head)
        self.assertEqual((code, stderr), (0, ''))
        marker = next(line for line in stdout.splitlines()
                      if line.startswith('HARNESS_EVAL_ARTIFACT='))
        directory = Path(marker.split('=', 1)[1])
        self.assertTrue(directory.is_dir())
        for name in ('manifest.json', 'result.patch', 'report.md', 'status.json'):
            self.assertTrue((directory / name).is_file(), name)
        manifest = json.loads((directory / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'success')
        self.assertEqual(manifest['backend']['name'], 'openresearch')
        self.assertEqual(manifest['backend']['ids']['fingerprint'], fingerprint)
        self.assertEqual(manifest['source_commit'], self.head)
        self.assertEqual(manifest['backend']['ids']['local_run'], manifest['run_id'])
        self.assertEqual(manifest['task']['id'], 'orders-cli')
        self.assertEqual(manifest['include_numbers'], [25, 26])
        summary = json.loads(stdout.splitlines()[-1])
        self.assertEqual(summary['status'], 'success')
        self.assertEqual(summary['artifact_dir'], str(directory))

    def test_fingerprint_mismatch_is_refused_before_any_run(self):
        code, stdout, stderr = self.run_entry(repo_root=self.root,
                                              selection='0' * 16,
                                              source_commit=self.head)
        self.assertEqual(code, 2)
        self.assertIn('fingerprint mismatch', stderr)
        self.assertFalse((self.root / 'memory/.tmp/orx-runs/orders-cli').exists())

    def test_unknown_task_is_refused(self):
        code, _, stderr = self.run_entry(repo_root=self.root, selection='0' * 16,
                                         source_commit=self.head,
                                         task='missing-probe')
        self.assertEqual(code, 2)
        self.assertIn('unknown task', stderr)

    def test_execute_runs_from_an_archive_without_git_metadata(self):
        """orx nodes run from an extracted archive: no .git, commit comes as an argument."""
        shutil.rmtree(self.root / '.git')
        fingerprint = fixtures.fingerprint_for(
            fixtures.make_request(self.root, self.head))
        code, stdout, stderr = self.run_entry(repo_root=self.root,
                                              selection=fingerprint,
                                              source_commit=self.head)
        self.assertEqual((code, stderr), (0, ''))
        directory = Path(next(line for line in stdout.splitlines()
                              if line.startswith('HARNESS_EVAL_ARTIFACT=')
                              ).split('=', 1)[1])
        manifest = json.loads((directory / 'manifest.json').read_text())
        self.assertEqual(manifest['source_commit'], self.head)
        self.assertEqual(manifest['status'], 'success')

    def test_failed_checks_exit_one_with_failed_status(self):
        root = Path(self.temp.name) / 'failing'
        head = fixtures.build_eval_repo(root, checks=GOOD_CHECK)
        if not _isolation_available(root):
            self.skipTest('deterministic shell checks require working bubblewrap')
        request = fixtures.make_request(root, head)
        code, stdout, stderr = self.run_entry(repo_root=root,
                                              selection=fixtures.fingerprint_for(request),
                                              source_commit=head, subject=BAD_SUBJECT)
        self.assertEqual((code, stderr), (1, ''))
        directory = Path(next(line for line in stdout.splitlines()
                              if line.startswith('HARNESS_EVAL_ARTIFACT=')
                              ).split('=', 1)[1])
        manifest = json.loads((directory / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'failed')
        self.assertEqual(manifest['checks'][0]['status'], 'fail')


if __name__ == '__main__':
    unittest.main()
