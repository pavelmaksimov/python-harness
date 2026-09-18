"""Provider quota holds: refusal before an attempt, the wait, and its record."""
from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from evals.backends.custom import quota
from evals.backends.custom.backend import BACKEND
from evals.backends.custom.tests import harness
from evals.core import checks
from evals.core.artifacts import DIAGNOSTICS, read_manifest, write_diagnostic
from evals.core.validate import validate_manifest

QUOTA_SENTENCE = 'Usage limit reached for 5 hour. Your limit will reset at 2026-09-18 20:18:27'
QUOTA_EVENT = {
    'type': 'error', 'timestamp': 1789721530425, 'sessionID': 'ses_f4c49d5b5ffeXaFUg1mx89QkUS',
    'error': {'name': 'APIError', 'data': {
        'message': QUOTA_SENTENCE, 'statusCode': 429, 'isRetryable': True,
        'responseHeaders': {'date': 'Fri, 18 Sep 2026 08:52:10 GMT',
                            'x-log-id': '2026091816521079e240a0691045bb'},
        'responseBody': '{"error":{"code":"1308","message":"' + QUOTA_SENTENCE + '"}}',
        'metadata': {'url': 'https://api.z.ai/api/coding/paas/v4/chat/completions'}}},
}


def moment(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat(timespec='seconds')


def diagnostic(run_dir: Path, *, run_id: str, reset_at: str | None, role: str = 'judge',
               provider: str = 'fake', reset_hint: str | None = '2026-09-18 20:18:27') -> dict:
    """The core's quota diagnostic, exactly as a finished run leaves it behind."""
    payload = {'run_id': run_id, 'stage': role, 'role': role, 'observed_at': '2026-09-18T08:52:10+00:00',
               'provider': provider, 'model': 'fake-model', 'provider_said': QUOTA_SENTENCE,
               'reset_hint': reset_hint, 'reset_at': reset_at, 'reset_timezone': 'local'}
    write_diagnostic(run_dir, DIAGNOSTICS['provider_quota'], json.dumps(payload) + '\n')
    return payload


class HoldTests(unittest.TestCase):
    """The record itself: what is kept, when it expires, and what a refusal says."""

    def setUp(self):
        base = harness.ROOT / 'memory/.tmp/evals'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.scratch = Path(self.temp.name)
        self.root = self.scratch / 'repo'
        self.root.mkdir()
        self.run = self.scratch / 'run-1'
        self.run.mkdir()
        self.context = {'backend': 'custom', 'opencode_version': harness.PROFILE_VERSION}

    def test_observation_keeps_the_statement_and_shapes_a_promotable_record(self):
        diagnostic(self.run, run_id='quota-1', reset_at=moment(timedelta(hours=2)))

        hold = quota.observe(self.root, self.run, context=self.context)

        self.assertEqual(quota.path(self.root, 'fake').name, 'fake.json')
        self.assertEqual(quota.read(self.root, 'fake'), hold)
        self.assertEqual((hold['stage'], hold['symptom']), ('custom_judge', 'judge provider_quota'))
        self.assertEqual(hold['applicability'],
                         {'backend': 'custom', 'opencode_version': harness.PROFILE_VERSION, 'provider': 'fake'})
        self.assertEqual(hold['remedy']['kind'], 'quota_wait')
        self.assertEqual(hold['message'], QUOTA_SENTENCE)
        self.assertEqual(hold['run_id'], 'quota-1')

    def test_a_hold_expires_only_at_a_moment_the_provider_stated(self):
        future = {'reset_at': moment(timedelta(hours=2))}
        past = {'reset_at': moment(timedelta(hours=-1))}
        self.assertFalse(quota.expired(future))
        self.assertTrue(quota.expired(past))
        self.assertFalse(quota.expired({}), 'a reset the provider never stated is never invented')
        self.assertFalse(quota.expired({'reset_at': 'sometime soon'}))
        self.assertTrue(quota.expired(past, now=datetime.now(timezone.utc)))

    def test_a_refusal_names_the_provider_its_words_and_the_file_that_clears_it(self):
        diagnostic(self.run, run_id='quota-1', reset_at=None, reset_hint=None)
        hold = quota.observe(self.root, self.run, context=self.context)
        message = quota.refusal(hold)

        self.assertIn('provider fake', message)
        self.assertIn(QUOTA_SENTENCE, message)
        self.assertIn('No attempt was started', message)
        self.assertIn('rm memory/.tmp/evals/quota/fake.json', message)
        self.assertIn('human decision', message, 'a profile switch is never a substitution')
        self.assertIn('no reset moment stated', message)


class QuotaRunTests(unittest.TestCase):
    """The rule in a run: refuse a closed window, wait out a stated reset."""

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

    def seed_hold(self, reset_at: str | None, *, reset_hint: str | None = '2026-09-18 20:18:27') -> dict:
        """The hold a previous run left behind when the provider refused it."""
        previous = self.root / 'evals/history/demo/previous'
        diagnostic(previous, run_id='previous', reset_at=reset_at, reset_hint=reset_hint)
        return quota.observe(self.root, previous, context={'backend': 'custom',
                                                           'opencode_version': harness.PROFILE_VERSION})

    def subject(self, name: str = 'subject.py', body: str = harness.SUBJECT) -> tuple[str, ...]:
        return harness.script(self.scratch, name, body)

    def test_a_closed_window_refuses_before_any_attempt(self):
        self.seed_hold(moment(timedelta(hours=2)))
        marker = self.scratch / 'subject-ran'
        subject = self.subject('subject.py', f'''
            import pathlib
            pathlib.Path({str(marker)!r}).write_text("ran")
        ''')

        result, output = self.run_backend(harness.request(
            self.root, 'quota-closed', subject_command=subject,
            judge_command=harness.judge(self.scratch)))

        self.assertEqual(result.status, 'error')
        self.assertFalse(marker.exists(), 'a closed provider window spends no subject run')
        self.assertEqual([attempt['action'] for attempt in result.attempts], ['quota_hold'])
        self.assertEqual(result.attempts[0]['result'], 'active')
        self.assertIn('provider quota hold', result.error)
        self.assertIn(QUOTA_SENTENCE, result.error)
        self.assertEqual(output.count('HARNESS_EVAL_ARTIFACT='), 1)
        self.assertEqual(sorted(path.name for path in result.artifact_dir.iterdir()),
                         ['manifest.json', 'report.md', 'result.patch', 'status.json'])
        self.assertEqual(validate_manifest(read_manifest(result.artifact_dir)), [])
        report = (result.artifact_dir / 'report.md').read_text(encoding='utf-8')
        self.assertIn('provider quota hold', report)
        self.assertIn('No attempt was started', report)

    def test_a_hold_without_a_stated_reset_is_never_expired_by_the_clock(self):
        self.seed_hold(None, reset_hint=None)

        result, _ = self.run_backend(harness.request(
            self.root, 'quota-unstated', subject_command=self.subject(),
            judge_command=harness.judge(self.scratch)))

        self.assertEqual(result.status, 'error')
        self.assertEqual([attempt['action'] for attempt in result.attempts], ['quota_hold'])
        self.assertIn('no reset moment stated', result.error)

    def test_a_stated_reset_is_waited_out_and_becomes_a_verified_incident(self):
        self.seed_hold(moment(timedelta(hours=-1)))

        result, _ = self.run_backend(harness.request(
            self.root, 'quota-open', subject_command=self.subject(),
            judge_command=harness.judge(self.scratch)))

        self.assertEqual(result.status, 'success')
        actions = [attempt['action'] for attempt in result.attempts]
        self.assertEqual(actions[:2], ['quota_wait', 'attempt-1'])
        stored = harness.incidents(self.root)
        self.assertEqual(len(stored), 1)
        record = stored[0]
        self.assertEqual((record['stage'], record['symptom']), ('custom_judge', 'judge provider_quota'))
        self.assertEqual(record['remedy']['kind'], 'quota_wait')
        self.assertEqual(record['applicability'],
                         {'backend': 'custom', 'opencode_version': harness.PROFILE_VERSION, 'provider': 'fake'})
        self.assertEqual(record['verification']['status'], 'success')
        self.assertEqual(record['verification']['run_id'], 'quota-open')
        self.assertIsNone(quota.read(self.root, 'fake'), 'the run that succeeded clears the hold')

    def test_a_fresh_quota_answer_is_recorded_and_never_retried(self):
        payload = self.scratch / 'quota-event.json'
        payload.write_text(json.dumps(QUOTA_EVENT), encoding='utf-8')
        judge = harness.script(self.scratch, 'quota-judge.py',
                               f'print(open({str(payload)!r}, encoding="utf-8").read().strip())')

        result, _ = self.run_backend(harness.request(
            self.root, 'quota-hit', subject_command=self.subject(), judge_command=judge))

        actions = [attempt['action'] for attempt in result.attempts]
        self.assertEqual(result.status, 'error')
        self.assertEqual(actions.count('attempt-1'), 1)
        self.assertNotIn('attempt-2', actions, 'an exhausted quota is never retried')
        self.assertIn(('quota_hold', 'recorded'),
                      [(attempt['action'], attempt['result']) for attempt in result.attempts])
        self.assertIn('provider_quota', result.error)
        self.assertIn(QUOTA_SENTENCE, result.error)
        hold = quota.read(self.root, 'fake')
        self.assertEqual((hold['stage'], hold['symptom']), ('custom_judge', 'judge provider_quota'))
        self.assertEqual(hold['reset_hint'], '2026-09-18 20:18:27')
        self.assertEqual(validate_manifest(read_manifest(result.artifact_dir)), [])


if __name__ == '__main__':
    unittest.main()
