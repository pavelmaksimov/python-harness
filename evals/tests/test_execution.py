"""Execution-layer tests: sandbox materialization, isolation, processes and runs."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

from evals.core import checks, execute, sandbox
from evals.core.artifacts import read_manifest
from evals.core.backend_api import RunRequest
from evals.core.checks import CommandError, ProcessResult, parse_opencode, run_process
from evals.core.judge import normalize_scorecard
from evals.core.selection import Selection

ROOT = Path(__file__).resolve().parents[2]
SELECTION = Selection(include_numbers=(6, 7, 9), exclude_numbers=(),
                      numbers=(6, 7, 9),
                      harness_ids=('python-architecture', 'python-fsm', 'python-stdlib-first-review'))
STREAM = '{"type":"text","part":{"text":"%s"}}\n{"type":"step_finish","part":{"tokens":{"input":5,"output":7},"cost":0.25}}\n'


def profile(role: str) -> dict:
    """A verified fake profile: real proof fields are mandatory, never assumed."""
    stamp = '2026-09-17T00:00:00+00:00'
    return {
        'provider': 'fake', 'model': 'fake-model', 'variant': None,
        'friendly_name': 'Fake model', 'role': role, 'opencode_version': '0.0.0-test',
        'metadata': {'source': 'test'}, 'verification_run_id': 'verify-1',
        'succeeded_at': stamp, 'human_selected': True,
        'verification': {'status': 'success', 'run_id': 'verify-1', 'succeeded_at': stamp,
                         'provider': 'fake', 'model': 'fake-model', 'variant': None,
                         'opencode_version': '0.0.0-test'},
    }


def task(**overrides) -> dict:
    base = {
        'id': 'demo', 'base_fixture': 'evals/_fixtures/base-project',
        'fixture': 'evals/tasks/demo/fixture',
        'materialize': [
            {'kind': 'rule', 'from': 'harnesses/rules/python-architecture', 'to': 'AGENTS.md',
             'harness_id': 'python-architecture'},
            {'kind': 'rule', 'from': 'harnesses/rules/python-fsm/python-fsm.mdc', 'to': 'AGENTS.md',
             'harness_id': 'python-fsm'},
            {'kind': 'skill', 'from': 'harnesses/skills/python-stdlib-first-review',
             'to': '.opencode/skills/python-stdlib-first-review',
             'harness_id': 'python-stdlib-first-review'},
            {'kind': 'template', 'from': 'harnesses/rules/python-tooling/PYPROJECT.toml',
             'to': 'pyproject.toml'},
        ],
        'checks': [{'id': 'smoke', 'kind': 'shell', 'command': ['/bin/sh', '-c', 'exit 0']}],
        'prompt': 'Implement the order domain.', 'rubric': {'criteria': [{'id': 'structure'}, {'id': 'tests'}]},
    }
    base.update(overrides)
    return base


def flag_values(argv: list[str], flag: str) -> dict:
    """Read `flag value` pairs from a constructed command line."""
    return {argv[index + 1]: argv[index + 2] for index, item in enumerate(argv) if item == flag}


def repository(root: Path, probe: dict | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / 'VERSION').write_text('1.3.0\n', encoding='utf-8')
    fixture = root / 'evals/_fixtures/base-project'
    fixture.mkdir(parents=True, exist_ok=True)
    (fixture / 'app.py').write_text('print("base")\n', encoding='utf-8')
    probe_fixture = root / 'evals/tasks/demo/fixture'
    probe_fixture.mkdir(parents=True, exist_ok=True)
    (probe_fixture / 'orders.py').write_text('ORDERS = []\n', encoding='utf-8')
    rules = root / 'harnesses/rules/python-architecture'
    rules.mkdir(parents=True, exist_ok=True)
    (rules / 'python-architecture.mdc').write_text(
        '---\ndescription: MUST USE for architecture\n---\nRule body alpha.\n', encoding='utf-8')
    (rules / 'python-entity.mdc').write_text('Rule body beta.\n', encoding='utf-8')
    tooling = root / 'harnesses/rules/python-tooling'
    tooling.mkdir(parents=True, exist_ok=True)
    (tooling / 'PYPROJECT.toml').write_text('[project]\nname = "demo"\n', encoding='utf-8')
    fsm = root / 'harnesses/rules/python-fsm'
    fsm.mkdir(parents=True, exist_ok=True)
    (fsm / 'python-fsm.mdc').write_text('FSM body.\n', encoding='utf-8')
    skill = root / 'harnesses/skills/python-stdlib-first-review'
    skill.mkdir(parents=True, exist_ok=True)
    (skill / 'SKILL.md').write_text('# stdlib first\n', encoding='utf-8')
    tasks = root / 'evals/tasks/demo'
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / 'task.json').write_text(json.dumps(probe if probe is not None else task()), encoding='utf-8')
    providers = root / 'evals/knowledge/providers'
    providers.mkdir(parents=True, exist_ok=True)
    for alias, role in (('subject', 'subject'), ('judge', 'judge')):
        (providers / f'{alias}.json').write_text(json.dumps(profile(role)), encoding='utf-8')
    return root


class SandboxTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        repository(self.root)
        self.workdir = self.root / 'runs/run-1'

    def materialize(self, probe: dict | None = None, selection: Selection = SELECTION) -> Path:
        return sandbox.materialize(self.root, probe or task(), selection, self.workdir)

    def test_materialize_builds_workspace_from_fixture_rules_skills_and_templates(self):
        workspace = self.materialize()
        self.assertEqual((workspace / 'app.py').read_text(encoding='utf-8'), 'print("base")\n')
        self.assertEqual((workspace / 'orders.py').read_text(encoding='utf-8'), 'ORDERS = []\n')
        self.assertEqual((workspace / 'pyproject.toml').read_text(encoding='utf-8'), '[project]\nname = "demo"\n')
        agents = (workspace / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertEqual(agents, 'Rule body alpha.\n\nRule body beta.\n\nFSM body.\n')
        self.assertNotIn('---', agents)
        self.assertTrue((workspace / '.opencode/skills/python-stdlib-first-review/SKILL.md').is_file())
        self.assertTrue((self.workdir / 'control/subject/skills/python-stdlib-first-review/SKILL.md').is_file())
        self.assertEqual(list((self.workdir / 'control/judge/skills').iterdir()), [])
        self.assertEqual(sorted(p.name for p in (self.workdir / 'control').iterdir()),
                         ['eval-shell', 'judge', 'subject'])
        self.assertTrue(os.access(self.workdir / 'control/eval-shell', os.X_OK))
        self.assertEqual(sorted(execute._relative_files(self.workdir / 'baseline')),
                         sorted(execute._relative_files(workspace)))

    def test_probe_specific_entries_are_filtered_by_selection(self):
        probe = task(materialize=[
            {'kind': 'rule', 'from': 'harnesses/rules/python-architecture', 'to': 'AGENTS.md',
             'harness_id': 'python-architecture'},
            {'kind': 'rule', 'from': 'harnesses/rules/python-fsm/python-fsm.mdc', 'to': 'AGENTS.md',
             'harness_id': 'python-fsm'},
        ])
        narrow = Selection(include_numbers=(6,), exclude_numbers=(), numbers=(6,),
                           harness_ids=('python-architecture',))
        workspace = self.materialize(probe, narrow)
        self.assertEqual((workspace / 'AGENTS.md').read_text(encoding='utf-8').strip(),
                         'Rule body alpha.\n\nRule body beta.')

    def test_materialize_rejects_escapes_symlinks_and_secret_inputs(self):
        cases = (
            ({'kind': 'rule', 'from': 'harnesses/rules/python-fsm/../../../../etc/passwd',
              'to': 'AGENTS.md'}, 'confined'),
            ({'kind': 'rule', 'from': 'evals/knowledge/providers/subject.json', 'to': 'AGENTS.md'}, 'knowledge'),
            ({'kind': 'rule', 'from': 'harnesses/rules/python-fsm/python-fsm.mdc', 'to': '.git/config'}, '.git'),
            ({'kind': 'skill', 'from': 'harnesses/skills/python-stdlib-first-review',
              'to': 'skills'}, 'opencode'),
        )
        for index, (entry, message) in enumerate(cases):
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, message):
                sandbox.materialize(self.root, task(materialize=[entry]), SELECTION,
                                    self.root / 'runs' / f'reject-{index}')
        link = self.root / 'harnesses/rules/python-tooling/link.mdc'
        link.symlink_to(self.root / 'harnesses/rules/python-fsm/python-fsm.mdc')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            sandbox.materialize(self.root, task(materialize=[
                {'kind': 'rule', 'from': 'harnesses/rules/python-tooling', 'to': 'AGENTS.md',
                 'harness_id': 'python-architecture'}]), SELECTION, self.root / 'runs/link')
        # A probe that ships its own manifest would hand the subject the rubric
        # and the exact check commands, so the manifest is never an input.
        with self.assertRaisesRegex(ValueError, 'task.json'):
            sandbox.materialize(self.root, task(fixture='evals/tasks/demo'), SELECTION,
                                self.root / 'runs/manifest')
        (self.root / 'evals/tasks/demo/fixture/AGENTS.md').write_text('hijacked\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'instructions'):
            self.materialize()

    def test_materialize_rejects_unknown_entry_kinds_and_nonempty_run_dirs(self):
        with self.assertRaisesRegex(ValueError, 'Unknown materialize entry kind'):
            sandbox.materialize(self.root, task(materialize=[
                {'kind': 'docs', 'from': 'harnesses/rules/python-fsm', 'to': 'docs'}]), SELECTION,
                self.root / 'runs/kind')
        occupied = self.root / 'runs/occupied'
        occupied.mkdir(parents=True)
        (occupied / 'stray.txt').write_text('x', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'must be empty'):
            sandbox.materialize(self.root, task(), SELECTION, occupied)

    def test_configuration_denies_by_default_and_blocks_external_surfaces(self):
        subject = sandbox.configuration()
        self.assertEqual(subject['permission']['*'], 'deny')
        self.assertEqual(subject['permission']['external_directory'], 'deny')
        self.assertEqual(subject['permission']['bash'],
                         {'*': 'deny', 'uv run pytest': 'allow', 'uv run pytest *': 'allow',
                          'uv run ruff check': 'allow', 'uv run ruff check *': 'allow',
                          'git status': 'allow', 'git status *': 'allow',
                          'git diff': 'allow', 'git diff *': 'allow'})
        for tool in ('webfetch', 'websearch', 'task', 'lsp', 'question'):
            self.assertNotIn(tool, subject['permission'])
        self.assertEqual(subject['share'], 'disabled')
        self.assertIs(subject['autoupdate'], False)
        self.assertEqual(subject['plugin'], [])
        self.assertEqual(subject['mcp'], {})
        self.assertEqual(subject['experimental'], {'openTelemetry': False})
        self.assertEqual(subject['permission']['edit']['AGENTS.md'], 'deny')
        judge = sandbox.configuration(readonly=True)
        self.assertEqual(judge['permission']['edit'], 'deny')
        self.assertEqual(judge['permission']['bash'], 'deny')
        self.assertEqual(judge['permission']['read'], {'*': 'allow', '*.env*': 'deny'})


class ShellWrapperTests(unittest.TestCase):
    """The subject's SHELL is a single-command allowlist, not a shell parser."""

    def setUp(self):
        base = ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        repository(self.root)
        self.workspace = sandbox.materialize(self.root, task(), SELECTION, Path(self.temp.name) / 'run')
        self.shell = str(Path(self.temp.name) / 'run/control/eval-shell')

    def evaluate(self, text: str):
        return run_process([sys.executable, self.shell, '-c', text], cwd=self.workspace, timeout=30)

    def test_operators_unknown_commands_and_external_paths_are_refused(self):
        for text, message in (
            ('git status; rm -rf /', 'shell operators'),
            ('git status && rm -rf /', 'shell operators'),
            ('git log', 'not allowlisted'),
            ('uv run python -c "print(1)"', 'not allowlisted'),
            ('cat /etc/passwd', 'not allowlisted'),
            ('git diff /etc/passwd', 'external paths'),
            ('git diff ../../etc/passwd', 'external paths'),
        ):
            with self.subTest(text=text):
                result = self.evaluate(text)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)

    def test_allowlisted_command_is_forwarded_to_the_isolated_runner(self):
        result = self.evaluate('git status')
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, 'bwrap|bubblewrap|namespace|isolation',
                         'allowlisted commands must still run under bubblewrap')

    def test_only_single_command_invocations_are_accepted(self):
        result = run_process([sys.executable, self.shell, '--version'], cwd=self.workspace, timeout=30)
        self.assertEqual((result.returncode, result.stderr.strip()),
                         (1, 'eval shell: only a single command is supported'))


class IsolationTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / 'run/workspace'
        (Path(self.temp.name) / 'run/control').mkdir(parents=True)

    def test_checks_require_a_network_namespace_and_a_clean_environment(self):
        argv = sandbox.isolated_command(['/bin/sh', '-c', 'exit 0'], self.workspace)
        self.assertIn('--unshare-net', argv)
        self.assertIn('--clearenv', argv)
        self.assertIn('--die-with-parent', argv)
        for role in ('subject', 'judge'):
            shared = sandbox.isolated_command(['opencode', 'run'], self.workspace, role=role,
                                              readonly=role == 'judge')
            self.assertNotIn('--unshare-net', shared)
            settings = flag_values(shared, '--setenv')
            unset = [shared[index + 1] for index, item in enumerate(shared) if item == '--unsetenv']
            for key in ('OPENCODE_PERMISSION', 'OTEL_EXPORTER_OTLP_ENDPOINT',
                        'NODE_OPTIONS', 'LD_PRELOAD'):
                self.assertIn(key, unset)
            self.assertEqual(settings['OPENCODE_DISABLE_PROJECT_CONFIG'], 'true')
            self.assertEqual(settings['OPENCODE_DISABLE_AUTOUPDATE'], 'true')
            self.assertEqual(settings['OPENCODE_PURE'], '1')
            self.assertEqual(settings['OPENCODE_CONFIG_DIR'], f'/control/{role}')
            self.assertEqual(settings['OPENCODE_CONFIG'], f'/control/{role}/opencode.json')
            self.assertEqual(settings['SHELL'], '/control/eval-shell')
            self.assertIn('/run/xdg/config/opencode/skills', shared)
            self.assertEqual(json.loads(settings['OPENCODE_CONFIG_CONTENT'])['share'], 'disabled')
        readonly = sandbox.isolated_command(['opencode', 'run'], self.workspace, role='judge', readonly=True)
        self.assertIn('--ro-bind', readonly)
        self.assertEqual(readonly[readonly.index(str(self.workspace)) - 1], '--ro-bind')
        with self.assertRaises(ValueError):
            sandbox.isolated_command([], self.workspace)
        with self.assertRaises(ValueError):
            sandbox.isolated_command(['true'], self.workspace, role='unknown')

    def test_missing_bubblewrap_fails_closed_instead_of_running_on_the_host(self):
        empty = Path(self.temp.name) / 'empty-path'
        empty.mkdir()
        with mock.patch.dict(os.environ, {'PATH': str(empty)}):
            with self.assertRaisesRegex(checks.IsolationError, 'bubblewrap'):
                checks.run_isolated(['/bin/sh', '-c', 'exit 0'], self.workspace, timeout=5)

    def test_bubblewrap_setup_failure_is_never_reported_as_a_check_result(self):
        failure = ProcessResult(1, '', 'bwrap: setting up uid map: Permission denied\n', 4)
        with mock.patch.object(checks, 'run_process', return_value=failure):
            with self.assertRaisesRegex(checks.IsolationError, 'setting up uid map'):
                checks.run_isolated(['/bin/sh', '-c', 'exit 0'], self.workspace, timeout=5)

    def test_checks_fail_closed_when_the_host_cannot_create_namespaces(self):
        """Either isolation works, or the check is an error naming isolation."""
        results = checks.run_checks([{'id': 'smoke', 'kind': 'shell', 'command': ['/bin/sh', '-c', 'exit 0']}],
                                    self.workspace)
        if results[0]['status'] != 'pass':
            self.assertEqual(results[0]['status'], 'error')
            self.assertRegex(results[0]['evidence'], 'bwrap|bubblewrap|namespac')
        nonshell = checks.run_checks([{'id': 'api', 'kind': 'http', 'command': 'curl'}], self.workspace)
        self.assertEqual(nonshell, [{'id': 'api', 'status': 'error',
                                     'evidence': 'Only shell checks are supported'}])


class ProcessTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def script(self, name: str, body: str) -> tuple[str, ...]:
        path = self.root / name
        path.write_text(textwrap.dedent(body), encoding='utf-8')
        return (sys.executable, str(path))

    def test_run_process_reports_status_output_and_duration(self):
        result = run_process(self.script('ok.py', '''
            import sys
            print("out")
            print("err", file=sys.stderr)
            sys.exit(3)
        '''), cwd=self.root, timeout=30)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (3, 'out\n', 'err\n'))
        self.assertFalse(result.timed_out)
        self.assertGreaterEqual(result.duration_ms, 0)

    def test_timeout_kills_the_whole_process_group_and_leaves_nothing_behind(self):
        marker = self.root / 'leaked'
        command = self.script('slow.py', f'''
            import subprocess, sys, time
            subprocess.Popen([sys.executable, "-c",
                "import time,pathlib;time.sleep(1.2);pathlib.Path({str(marker)!r}).write_text('x')"])
            print("started", flush=True)
            time.sleep(30)
        ''')
        result = run_process(command, cwd=self.root, timeout=0.4)
        self.assertTrue(result.timed_out)
        self.assertLess(result.returncode, 0)
        time.sleep(1.6)
        self.assertFalse(marker.exists())

    def test_output_beyond_the_capture_limit_is_rejected(self):
        with self.assertRaises(CommandError) as error:
            run_process(self.script('loud.py', 'print("x" * 100000)'), cwd=self.root,
                        timeout=30, output_limit=32)
        self.assertEqual(error.exception.kind, 'output_limit')


class ParsingTests(unittest.TestCase):
    def parse(self, result: ProcessResult):
        return parse_opencode(result)

    def test_successful_stream_keeps_text_and_token_metrics(self):
        text, metrics = self.parse(ProcessResult(0, STREAM % 'done', '', 12))
        self.assertEqual(text, 'done')
        self.assertEqual(metrics, {'input_tokens': 5, 'output_tokens': 7, 'cost': 0.25})

    def test_streamed_part_updates_are_not_duplicated(self):
        stream = '\n'.join((
            '{"type":"text","part":{"id":"p1","text":"Hel"}}',
            '{"type":"step_finish","part":{"id":"p2","tokens":{"input":5,"output":7},"cost":0.25}}',
            '{"type":"text","part":{"id":"p1","text":"Hello"}}',
            '{"type":"step_finish","part":{"id":"p2","tokens":{"input":5,"output":7},"cost":0.25}}',
            '{"type":"reasoning","part":{"id":"p3","text":"thinking"}}',
            '{"type":"text","part":{"id":"p1","text":"Hello world"}}',
        )) + '\n'
        text, metrics = self.parse(ProcessResult(0, stream, '', 5))
        self.assertEqual(text, 'Hello world')
        self.assertEqual(metrics, {'input_tokens': 5, 'output_tokens': 7, 'cost': 0.25})

    def test_malformed_and_empty_streams_are_distinguished(self):
        for stdout in ('not json\n', '', '{"type": 7}\n', '[]\n'):
            with self.subTest(stdout=stdout), self.assertRaises(CommandError) as error:
                self.parse(ProcessResult(0, stdout, '', 1))
            self.assertEqual(error.exception.kind, 'malformed_json')
        with self.assertRaises(CommandError) as error:
            self.parse(ProcessResult(0, '{"type":"step_finish","part":{"tokens":{"input":-1}}}\n', '', 1))
        self.assertEqual(error.exception.kind, 'malformed_json')

    def test_missing_model_and_unsupported_variant_are_distinguished(self):
        cases = (
            (1, 'Wrong model: openrouter/ghost is not available', '', 'missing_model'),
            (1, 'Unsupported variant fast for model openai/gpt', '', 'unsupported_variant'),
            (0, '', '{"type":"error","error":{"message":"Model openrouter/ghost not found"}}\n', 'missing_model'),
            (0, '', '{"type":"error","error":{"message":"invalid variant turbo"}}\n', 'unsupported_variant'),
        )
        for code, stderr, stdout, kind in cases:
            with self.subTest(stderr=stderr, stdout=stdout), self.assertRaises(CommandError) as error:
                self.parse(ProcessResult(code, stdout, stderr, 1))
            self.assertEqual(error.exception.kind, kind)
        with self.assertRaises(CommandError) as error:
            self.parse(ProcessResult(1, '', 'boom', 1))
        self.assertEqual(error.exception.kind, 'command_failed')
        with self.assertRaises(CommandError) as error:
            self.parse(ProcessResult(-9, 'partial', '', 40, timed_out=True))
        self.assertEqual(error.exception.kind, 'timeout')


class ScorecardTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        (self.workspace / 'orders.py').write_text('ORDERS = []\n', encoding='utf-8')
        self.rubric = {'criteria': [{'id': 'structure'}, {'id': 'tests'}]}

    def scorecard(self, **overrides) -> dict:
        value = {'criteria': [
            {'id': 'structure', 'score': 4, 'evidence': [{'file': 'orders.py', 'line': 1, 'description': 'module'}]},
            {'id': 'tests', 'score': 2, 'evidence': [{'file': 'orders.py', 'description': 'no tests'}]},
        ], 'summary': 'solid'}
        value.update(overrides)
        return value

    def test_valid_scorecard_is_normalized_to_zero_through_four(self):
        result = normalize_scorecard(self.scorecard(), self.rubric, self.workspace)
        self.assertEqual(result['score'], 3)
        self.assertEqual([row['id'] for row in result['criteria']], ['structure', 'tests'])

    def test_invalid_scorecards_are_rejected_rather_than_scored(self):
        cases = (
            (self.scorecard(criteria=[]), 'nonempty'),
            (self.scorecard(criteria=[dict(self.scorecard()['criteria'][0], score=5)]), '0 through 4'),
            (self.scorecard(criteria=[dict(self.scorecard()['criteria'][0], score=None)]), '0 through 4'),
            (self.scorecard(criteria=[dict(self.scorecard()['criteria'][0], evidence=[])]), 'file evidence'),
            (self.scorecard(criteria=[dict(self.scorecard()['criteria'][0],
                                           evidence=[{'file': '../outside.py', 'description': 'x'}])]), 'confined'),
            (self.scorecard(criteria=[dict(self.scorecard()['criteria'][0],
                                           evidence=[{'file': 'missing.py', 'description': 'x'}])]), 'does not exist'),
            (self.scorecard(criteria=[self.scorecard()['criteria'][0]]), 'fixed rubric'),
            (self.scorecard(criteria=[dict(self.scorecard()['criteria'][0], id='extra')]), 'fixed rubric'),
        )
        for value, message in cases:
            with self.subTest(value=value), self.assertRaisesRegex(CommandError, message):
                normalize_scorecard(value, self.rubric, self.workspace)


class ExecuteTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        repository(self.root)

    def script(self, name: str, body: str) -> tuple[str, ...]:
        path = Path(self.temp.name) / name
        path.write_text(textwrap.dedent(body), encoding='utf-8')
        return (sys.executable, str(path))

    def request(self, probe: dict | None = None, run: str = 'run-1', **overrides) -> RunRequest:
        if probe is not None:
            (self.root / 'evals/tasks/demo/task.json').write_text(json.dumps(probe), encoding='utf-8')
        values = {
            'task_id': 'demo', 'include': (6, 7, 9), 'exclude': (), 'selection': SELECTION,
            'subject_profile': 'subject', 'judge_profile': 'judge',
            'workdir': Path(self.temp.name) / 'runs' / run, 'run_id': run, 'repo_root': self.root,
            'source_commit': 'abc123', 'knowledge_revision': 'deadbeef',
        }
        values.update(overrides)
        return RunRequest(**values)

    def run_experiment(self, request: RunRequest, isolated_checks: bool = True) -> tuple[dict, str, Path]:
        directory = Path(self.temp.name) / 'artifacts' / request.run_id
        stream = io.StringIO()
        patch = mock.patch.object(checks, 'run_isolated', self._direct) if isolated_checks else contextlib.nullcontext()
        with patch, contextlib.redirect_stdout(stream):
            manifest = execute.execute_experiment(request, directory)
        return manifest, stream.getvalue(), directory

    @staticmethod
    def _direct(command, workspace, *, timeout, role='check', readonly=False):
        """Test double for the isolation boundary, itself proven fail-closed above."""
        return run_process(command, cwd=workspace, timeout=timeout)

    def judge_script(self, payload: dict, name: str = 'judge.py') -> tuple[str, ...]:
        target = Path(self.temp.name) / 'scorecard.json'
        target.write_text(json.dumps(payload), encoding='utf-8')
        return self.script(name, f'''
            import json
            payload = open({str(target)!r}, encoding="utf-8").read()
            print(json.dumps({{"type": "text", "part": {{"text": payload}}}}))
            print(json.dumps({{"type": "step_finish",
                               "part": {{"tokens": {{"input": 3, "output": 4}}, "cost": 0.5}}}}))
        ''')

    def valid_scorecard(self) -> dict:
        return {'criteria': [
            {'id': 'structure', 'score': 4, 'evidence': [{'file': 'orders.py', 'line': 1, 'description': 'module'}]},
            {'id': 'tests', 'score': 2, 'evidence': [{'file': 'orders.py', 'description': 'no tests'}]},
        ], 'summary': 'solid'}

    def test_successful_run_writes_schema_shaped_manifest_report_and_patch(self):
        subject = self.script('subject.py', '''
            import json, pathlib
            pathlib.Path("service.py").write_text("def create_order():\\n    return {}\\n")
            print(json.dumps({"type": "text", "part": {"text": "implemented"}}))
            print(json.dumps({"type": "step_finish",
                              "part": {"tokens": {"input": 11, "output": 22}, "cost": 0.75}}))
        ''')
        manifest, printed, directory = self.run_experiment(self.request(
            subject_command=subject, judge_command=self.judge_script(self.valid_scorecard())))

        self.assertEqual(manifest['status'], 'success')
        self.assertEqual([attempt['action'] for attempt in manifest['attempts']],
                         ['materialize', 'subject', 'checks', 'judge'])
        self.assertTrue(all(attempt['result'] == 'ok' for attempt in manifest['attempts']))
        self.assertEqual(manifest['judge_score'], 3)
        self.assertEqual(manifest['model'], {'provider': 'fake', 'model': 'fake-model', 'variant': None})
        self.assertEqual(manifest['catalog_version'], '1.3.0')
        self.assertEqual(manifest['harness_hashes'].keys(), set(SELECTION.harness_ids))
        self.assertEqual(manifest['metrics']['subject'], {'input_tokens': 11, 'output_tokens': 22, 'cost': 0.75})
        self.assertEqual(manifest['metrics']['checks'], {'pass': 1, 'fail': 0, 'error': 0})
        self.assertTrue(manifest['started_at'] and manifest['finished_at'])
        self.assertEqual(printed.strip(), f'HARNESS_EVAL_ARTIFACT={directory}')

        stored = read_manifest(directory)
        self.assertEqual(stored['status'], 'success')
        self.assertEqual(json.loads((directory / 'status.json').read_text(encoding='utf-8'))['status'], 'success')
        report = (directory / 'report.md').read_text(encoding='utf-8')
        self.assertIn('structure: 4', report)
        self.assertIn('`orders.py:1`', report)
        patch = (directory / 'result.patch').read_text(encoding='utf-8')
        self.assertIn('diff --git a/service.py b/service.py', patch)
        self.assertIn('+def create_order():', patch)
        for payload in (json.dumps(stored), report, patch):
            self.assertNotIn('/home/', payload)
        from evals.core.validate import validate_manifest
        self.assertEqual(validate_manifest(stored), [])

    def test_failed_check_is_recorded_with_evidence_and_fails_the_run(self):
        subject = self.script('subject.py', '''
            import json
            print(json.dumps({"type": "text", "part": {"text": "did nothing"}}))
        ''')
        probe = task(checks=[{'id': 'pytest', 'kind': 'shell',
                              'command': ['/bin/sh', '-c', 'echo noise; echo cache > check-cache.txt; exit 1']}])
        manifest, _, directory = self.run_experiment(self.request(
            probe, subject_command=subject, judge_command=self.judge_script(self.valid_scorecard())))
        self.assertEqual(manifest['status'], 'failed')
        self.assertEqual(manifest['checks'], [{'id': 'pytest', 'status': 'fail', 'evidence': 'noise'}])
        self.assertEqual(manifest['metrics']['checks'], {'pass': 0, 'fail': 1, 'error': 0})
        self.assertEqual([attempt['result'] for attempt in manifest['attempts']], ['ok', 'ok', 'fail', 'ok'])
        self.assertEqual(read_manifest(directory)['status'], 'failed')
        # Check-time side effects are captured before checks run, never in the patch.
        self.assertEqual((directory / 'result.patch').read_text(encoding='utf-8'), '')
        self.assertTrue((Path(self.temp.name) / 'runs/run-1/workspace/check-cache.txt').is_file())

    def test_subject_timeout_stops_the_run_and_still_writes_artifacts(self):
        subject = self.script('hang.py', 'import time; time.sleep(30)')
        manifest, _, directory = self.run_experiment(self.request(
            task(subject_timeout_seconds=0.3), subject_command=subject,
            judge_command=self.judge_script(self.valid_scorecard())))
        self.assertEqual(manifest['status'], 'timeout')
        self.assertEqual(manifest['attempts'][1]['result'], 'timeout')
        self.assertNotIn('judge', [attempt['action'] for attempt in manifest['attempts']])
        self.assertIsNone(manifest['judge_score'])
        self.assertIn('timeout', (directory / 'report.md').read_text(encoding='utf-8'))
        self.assertEqual((directory / 'result.patch').read_text(encoding='utf-8'), '')

    def test_malformed_json_missing_model_and_bad_variant_are_distinguished(self):
        cases = (
            (('print("not json")'), 'malformed_json'),
            (('import sys; sys.stderr.write("Model fake/ghost not found\\n"); sys.exit(1)'), 'missing_model'),
            (('import sys; sys.stderr.write("Unsupported variant turbo\\n"); sys.exit(1)'), 'unsupported_variant'),
        )
        for index, (body, kind) in enumerate(cases):
            with self.subTest(kind=kind):
                manifest, _, directory = self.run_experiment(self.request(
                    run=f'case-{index}', subject_command=self.script(f'fake-{index}.py', body),
                    judge_command=self.judge_script(self.valid_scorecard())))
                self.assertEqual(manifest['status'], 'error')
                self.assertEqual(manifest['attempts'][1]['result'], kind)
                self.assertEqual(read_manifest(directory)['status'], 'error')
                self.assertIn(kind, (directory / 'report.md').read_text(encoding='utf-8'))

    def test_missing_isolation_fails_closed_before_any_subject_runs(self):
        manifest, _, directory = self.run_experiment(self.request(), isolated_checks=False)
        self.assertEqual(manifest['status'], 'error')
        self.assertEqual([attempt['action'] for attempt in manifest['attempts']], ['materialize', 'subject'])
        self.assertEqual(manifest['attempts'][0]['result'], 'ok')
        self.assertEqual(manifest['attempts'][1]['result'], 'isolation_error')
        self.assertRegex((directory / 'report.md').read_text(encoding='utf-8'), '(?i)bubblewrap|isolat')
        self.assertEqual(read_manifest(directory)['status'], 'error')

    def test_isolated_checks_fail_closed_and_keep_sanitized_evidence(self):
        subject = self.script('subject.py', '''
            import json
            print(json.dumps({"type": "text", "part": {"text": "ok"}}))
        ''')
        manifest, _, directory = self.run_experiment(self.request(
            subject_command=subject, judge_command=self.judge_script(self.valid_scorecard())),
            isolated_checks=False)
        self.assertEqual(manifest['status'], 'error')
        self.assertEqual(manifest['checks'][0]['id'], 'smoke')
        self.assertEqual(manifest['checks'][0]['status'], 'error')
        self.assertRegex(manifest['checks'][0]['evidence'], 'bwrap|bubblewrap')
        self.assertNotIn('judge', [attempt['action'] for attempt in manifest['attempts']])
        self.assertEqual(read_manifest(directory)['checks'], manifest['checks'])

    def test_invalid_judge_scorecard_degrades_to_a_fallback_report(self):
        subject = self.script('subject.py', '''
            import json
            print(json.dumps({"type": "text", "part": {"text": "ok"}}))
        ''')
        for index, payload in enumerate(({'criteria': [], 'summary': 'x'},
                                         self.valid_scorecard() | {'criteria': [
                                             dict(self.valid_scorecard()['criteria'][0], score=9)]})):
            with self.subTest(payload=payload):
                manifest, _, directory = self.run_experiment(self.request(
                    run=f'judge-bad-{index}', subject_command=subject,
                    judge_command=self.judge_script(payload, f'bad-judge-{index}.py')))
                self.assertEqual(manifest['status'], 'error')
                self.assertIsNone(manifest['judge_score'])
                self.assertEqual(manifest['attempts'][3]['result'], 'invalid_scorecard')
                report = (directory / 'report.md').read_text(encoding='utf-8')
                self.assertIn('judge invalid_scorecard', report)
                self.assertIn('smoke: pass', report)

    def test_missing_task_or_unverified_profile_still_writes_terminal_artifacts(self):
        empty = Path(self.root)
        (empty / 'evals/tasks/demo/task.json').unlink()
        manifest, _, directory = self.run_experiment(self.request(judge_command=self.judge_script(self.valid_scorecard())))
        self.assertEqual(manifest['status'], 'error')
        self.assertEqual(manifest['task'], {'id': 'demo', 'hash': '', 'rubric_hash': ''})
        self.assertEqual(manifest['attempts'][0]['action'], 'task')
        self.assertEqual(sorted(path.name for path in directory.iterdir()),
                         ['manifest.json', 'report.md', 'result.patch', 'status.json'])

        repository(self.root)
        (self.root / 'evals/knowledge/providers/subject.json').write_text(
            json.dumps(profile('subject') | {'human_selected': False}), encoding='utf-8')
        manifest, _, directory = self.run_experiment(self.request(run='run-2'))
        self.assertEqual(manifest['status'], 'error')
        self.assertEqual(manifest['attempts'][0]['result'], 'invalid_task')
        self.assertIn('human model selection', (directory / 'report.md').read_text(encoding='utf-8'))
        self.assertEqual(manifest['subject_profile'], {})

    def test_patch_isolates_subject_changes_and_is_reproducible(self):
        subject = self.script('subject.py', '''
            import pathlib
            pathlib.Path("orders.py").write_text("ORDERS = [1]\\n")
            (pathlib.Path("notes") ).mkdir()
            pathlib.Path("notes/log.txt").write_text("done\\n")
        ''')
        manifest, _, directory = self.run_experiment(self.request(
            subject_command=subject, judge_command=self.judge_script(self.valid_scorecard())))
        patch = (directory / 'result.patch').read_text(encoding='utf-8')
        self.assertIn('-ORDERS = []', patch)
        self.assertIn('+ORDERS = [1]', patch)
        self.assertIn('diff --git a/notes/log.txt b/notes/log.txt', patch)
        self.assertIn('+done', patch)
        self.assertNotIn('AGENTS.md', patch)
        self.assertNotIn('.opencode', patch)
        workspace = Path(self.temp.name) / 'runs/run-1/workspace'
        baseline = Path(self.temp.name) / 'runs/run-1/baseline'
        self.assertEqual(execute.build_patch(baseline, workspace), patch)
        self.assertEqual(manifest['metrics']['patch_bytes'], len(patch.encode('utf-8')))


if __name__ == '__main__':
    unittest.main()
