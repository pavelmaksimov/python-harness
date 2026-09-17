"""Repair policy and loop: knowledge replay, bounded remedies, honest records."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from evals.backends.custom import repair
from evals.backends.custom.backend import BACKEND
from evals.backends.custom.tests import harness
from evals.core import checks
from evals.core.artifacts import read_manifest
from evals.core.validate import validate_manifest


class PolicyTests(unittest.TestCase):
    def state(self) -> repair.AttemptState:
        return repair.AttemptState(wall_seconds=100.0, context={'backend': 'custom'})

    def test_matching_remedies_are_proposed_once_each(self):
        state = self.state()
        timeout = repair.Symptom('custom_subject', 'timeout', 'subject timeout')
        remedy = repair.next_remedy(timeout, state)
        self.assertEqual(remedy.name, 'supervision_budget')
        repair.apply_remedy(remedy, state)
        self.assertEqual(state.wall_seconds, 200.0)
        self.assertIsNone(repair.next_remedy(timeout, state), 'a remedy never repeats')

    def test_the_remedy_cap_stops_the_loop_at_three_distinct_attempts(self):
        state = self.state()
        transient = repair.Symptom('custom_subject', 'command_failed', 'subject command_failed')
        probes = tuple(repair.Remedy(f'probe-{index}', ('command_failed',), 'test probe',
                                     repair.no_parameter_change) for index in range(5))
        with mock.patch.object(repair, 'REMEDIES', probes):
            proposed = []
            while (remedy := repair.next_remedy(transient, state)) is not None:
                repair.apply_remedy(remedy, state)
                proposed.append(remedy.name)
        self.assertEqual(proposed, ['probe-0', 'probe-1', 'probe-2'])
        self.assertEqual(len(state.used), repair.MAX_REMEDIES)

    def test_classification_uses_structured_attempts_and_names_human_decisions(self):
        manifest = {'attempts': [{'action': 'materialize', 'result': 'ok'},
                                 {'action': 'subject', 'result': 'missing_model'}]}
        symptom = repair.classify(status='error', killed=False, manifest=manifest)
        self.assertEqual((symptom.stage, symptom.kind), ('custom_subject', 'missing_model'))
        self.assertIn('human', repair.human_required(symptom))
        self.assertIsNone(repair.human_required(repair.Symptom('custom_subject', 'timeout', 'x')))
        killed = repair.classify(status='timeout', killed=True, manifest={'attempts': []})
        self.assertEqual((killed.stage, killed.kind), ('custom_supervisor', 'timeout'))

    def test_only_replayable_incidents_are_applied(self):
        state = self.state()
        budget = {'stage': 'custom_subject', 'symptom': 'subject timeout',
                  'applicability': {'backend': 'custom'}, 'remedy': {'kind': 'supervision_budget'}}
        retry = dict(budget, remedy={'kind': 'clean_retry'})
        self.assertTrue(repair.replayable(budget))
        self.assertFalse(repair.replayable(retry))
        repair.apply_incident(budget, state)
        self.assertEqual(state.wall_seconds, 200.0)
        with self.assertRaises(ValueError):
            repair.apply_incident(retry, state)


class RepairLoopTests(unittest.TestCase):
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

    def run_backend(self, request):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = BACKEND.run(request)
        return result, stdout.getvalue()

    def subject(self, name: str = 'subject.py', body: str = harness.SUBJECT) -> tuple[str, ...]:
        return harness.script(self.scratch, name, body)

    def test_known_incident_is_replayed_before_the_first_attempt(self):
        record = harness.incident(self.root)
        result, _ = self.run_backend(harness.request(
            self.root, 'rep-replay', subject_command=self.subject(),
            judge_command=harness.judge(self.scratch)))

        self.assertEqual(result.status, 'success')
        self.assertEqual(result.attempts[0]['action'], 'incident_replay')
        self.assertEqual(result.attempts[0]['result'], 'ok')
        self.assertEqual(result.attempts[0]['incident'], record['fingerprint'])
        self.assertEqual(result.attempts[1]['action'], 'attempt-1')
        stored = harness.incidents(self.root)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]['occurrences'], 2, 'a replayed remedy proven by the first attempt gains evidence')

    def test_timeout_burns_the_wall_clock_remedy_once_and_then_stops(self):
        harness.repository(self.root, harness.task(subject_timeout_seconds=0.3))
        result, _ = self.run_backend(harness.request(
            self.root, 'rep-timeout', subject_command=self.subject('hang.py', harness.FAILING['timeout']),
            judge_command=harness.judge(self.scratch)))

        actions = [attempt['action'] for attempt in result.attempts]
        self.assertEqual(result.status, 'timeout')
        self.assertEqual(actions.count('attempt-1'), 1)
        self.assertIn('remedy-supervision_budget', actions)
        self.assertEqual(actions.count('attempt-2'), 1)
        self.assertNotIn('attempt-3', actions, 'the same remedy is never applied twice')
        self.assertIn('repair loop stopped after 1 distinct remedies', result.error)
        self.assertEqual(validate_manifest(read_manifest(result.artifact_dir)), [])
        archived = sorted(path.name for path in result.artifact_dir.parent.glob('rep-timeout.a*'))
        self.assertEqual(archived, ['rep-timeout.a1'])
        self.assertTrue((result.artifact_dir.parent / 'rep-timeout.a1' / 'status.json').is_file())
        self.assertEqual(harness.incidents(self.root), [], 'an unfixed failure is never recorded as a remedy')

    def test_three_distinct_remedies_then_the_loop_stops(self):
        subject, state = harness.counting_subject(self.scratch, name='always-failing.py', fail_until=99)
        probes = tuple(repair.Remedy(f'probe-{index}', ('command_failed',), 'test probe',
                                     repair.no_parameter_change) for index in range(3))
        with mock.patch.object(repair, 'REMEDIES', probes):
            result, _ = self.run_backend(harness.request(
                self.root, 'rep-cap', subject_command=subject,
                judge_command=harness.judge(self.scratch)))

        actions = [attempt['action'] for attempt in result.attempts]
        self.assertEqual(result.status, 'error')
        self.assertEqual([name for name in actions if name.startswith('attempt-')],
                         ['attempt-1', 'attempt-2', 'attempt-3', 'attempt-4'])
        self.assertEqual(state.read_text(encoding='utf-8'), '4', 'the loop stops after three remedies')
        self.assertIn('stopped after 3 distinct remedies', result.error)
        self.assertEqual(validate_manifest(read_manifest(result.artifact_dir)), [])

    def test_deterministic_check_failure_is_the_experiment_answer_not_a_defect(self):
        harness.repository(self.root, harness.task(
            checks=[{'id': 'smoke', 'kind': 'shell', 'command': ['/bin/sh', '-c', 'exit 1']}]))
        result, _ = self.run_backend(harness.request(
            self.root, 'rep-failed', subject_command=self.subject(),
            judge_command=harness.judge(self.scratch)))

        actions = [attempt['action'] for attempt in result.attempts]
        self.assertEqual(result.status, 'failed')
        self.assertEqual(actions.count('attempt-1'), 1)
        self.assertNotIn('attempt-2', actions)
        self.assertIn('checks fail', result.error)
        self.assertEqual(harness.incidents(self.root), [])

    def test_needs_human_failures_stop_before_any_remedy(self):
        result, _ = self.run_backend(harness.request(
            self.root, 'rep-human', subject_command=self.subject('variant.py', harness.FAILING['unsupported_variant']),
            judge_command=harness.judge(self.scratch)))

        actions = [attempt['action'] for attempt in result.attempts]
        self.assertEqual(result.status, 'error')
        self.assertEqual(actions.count('attempt-1'), 1)
        self.assertNotIn('attempt-2', actions, 'a human decision is never guessed')
        self.assertIn('human', result.error)
        self.assertEqual(harness.incidents(self.root), [])

    def test_repair_records_are_idempotent_across_runs(self):
        subject, state = harness.counting_subject(self.scratch, name='odd.py', fail_while_modulo=0)
        judge = harness.judge(self.scratch)
        first, _ = self.run_backend(harness.request(self.root, 'rep-idem-1', subject_command=subject,
                                                    judge_command=judge))
        second, _ = self.run_backend(harness.request(self.root, 'rep-idem-2', subject_command=subject,
                                                     judge_command=judge))

        self.assertEqual((first.status, second.status), ('success', 'success'))
        self.assertIn(('attempt-1', 'error'), [(attempt['action'], attempt['result'])
                                               for attempt in first.attempts])
        stored = harness.incidents(self.root)
        self.assertEqual(len(stored), 1, 'the same defect keeps one record')
        record = stored[0]
        self.assertEqual(record['occurrences'], 2)
        self.assertEqual(record['stage'], 'custom_subject')
        self.assertEqual(record['symptom'], 'subject command_failed')
        self.assertEqual(record['failed_attempts'],
                         [{'action': 'attempt-1', 'result': 'error:command_failed',
                           'duration_ms': 0, 'incident': None}])
        self.assertEqual(record['applicability'],
                         {'backend': 'custom', 'opencode_version': harness.PROFILE_VERSION})
        # a clean-retry record is never replayed pre-attempt; the second run reports it as skipped
        self.assertIn(('incident_replay', 'skipped'),
                      [(attempt['action'], attempt['result']) for attempt in second.attempts])


if __name__ == '__main__':
    unittest.main()
