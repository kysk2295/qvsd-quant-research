import copy
import hashlib
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from runner.prospective_attempt import (AttemptError, DuplicateAttempt, ProspectiveAttempt,
    AttemptTransport, packet_fingerprint)

NOW = datetime(2026, 11, 7, 1, tzinfo=timezone.utc)


class AdvancingClock:
    def __init__(self):
        self.value = NOW

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


def packet():
    return dict(plan_id='fixed-prospective', plan_sha256='a' * 64,
                request={'strategy': 'SyntheticFrozen', 'fillResolution': 'High',
                         'fillResolutionType': 'Tick', 'fillResolutionValue': 1},
                source_sha256='b' * 64, dataset_sha256='c' * 64, instance_id='instance-one')


def synthetic_attestation(bound, fingerprint, now):
    """Test-only callback evidence; does not implement production authorization."""
    encoded = json.dumps(bound, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return dict(scope='local_submission', approved=True, fingerprint=fingerprint,
                packet_sha256=hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
                checked_at_utc=now.isoformat())


class FakeAdapter(AttemptTransport):
    def __init__(self):
        self.instance = 'instance-one'
        self.receipt = {'id': 'b1', 'state': 'queued'}
        self.document = {'id': 'b1', 'state': 'running'}
        self.submits, self.polls = [], []
        self.before_submit = None
        self.before_poll = None

    def current_instance(self):
        if isinstance(self.instance, Exception):
            raise self.instance
        return self.instance

    def submit(self, request):
        self.submits.append(copy.deepcopy(request))
        if self.before_submit:
            self.before_submit()
        if isinstance(self.receipt, Exception):
            raise self.receipt
        return copy.deepcopy(self.receipt)

    def poll(self, native_id):
        self.polls.append(native_id)
        if self.before_poll:
            self.before_poll()
        if isinstance(self.document, Exception):
            raise self.document
        return copy.deepcopy(self.document)


class ProspectiveAttemptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.adapter = FakeAdapter()
        self.authorization = lambda p, fp: synthetic_attestation(p, fp, NOW)
        self.attempt = self.make()

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, bound=None, authorize=None):
        return ProspectiveAttempt(self.folder, bound or packet(), self.adapter,
                                authorize or self.authorization, clock=lambda: NOW)

    def observe(self, state, attempt=None):
        return (attempt or self.attempt).observe(state['token'], state['fingerprint'])

    def test_durable_reservation_precedes_transport(self):
        def inspect():
            reservation = json.loads(self.attempt.reservation_path.read_text())
            state = json.loads(self.attempt.state_path.read_text())
            self.assertEqual(reservation['local_submission_budget_consumed'], 1)
            self.assertEqual(state['status'], 'submitting')
            self.assertEqual(state['transport_attempt_intents'], 1)
            self.assertEqual(state['native_instance'], 'instance-one')
        self.adapter.before_submit = inspect
        state = self.attempt.submit()
        self.assertEqual(state['native_id'], 'b1')
        self.assertNotIn('ready_for_native', state)
        self.assertNotIn('production_native_calls', state)
        with self.assertRaises(DuplicateAttempt):
            self.attempt.submit()
        self.assertEqual(len(self.adapter.submits), 1)

    def test_post_timeout_never_resubmits_or_guesses_handle(self):
        self.adapter.receipt = TimeoutError()
        state = self.attempt.submit()
        self.assertEqual(state['status'], 'submission_unknown')
        self.assertIsNone(state['native_id'])
        self.observe(state)
        with self.assertRaises(DuplicateAttempt):
            self.make().submit()
        self.assertEqual(len(self.adapter.submits), 1)
        self.assertEqual(self.adapter.polls, [])

    def test_missing_or_malformed_receipt_is_unresolved(self):
        self.adapter.receipt = {'id': '../b1', 'state': 'queued'}
        state = self.attempt.submit()
        self.assertEqual(state['observer_status'], 'unresolved_handle')
        self.assertIsNone(state['native_id'])
        with self.assertRaises(DuplicateAttempt):
            self.attempt.submit()

    def test_transient_poll_timeout_is_nonterminal_then_same_handle_recovers(self):
        state = self.attempt.submit()
        self.adapter.document = TimeoutError()
        state = self.observe(state)
        self.assertEqual(state['status'], 'running')
        self.assertEqual(state['observer_status'], 'unavailable')
        self.assertEqual(state['native_id'], 'b1')
        self.adapter.document = {'id': 'b1', 'state': 'done'}
        state = self.observe(state, self.make())
        self.assertEqual(state['status'], 'terminal')
        self.assertNotIn('strategy_accepted', state)
        self.assertEqual(state['validation_status'], 'pending_post_run_contract')
        self.assertEqual(len(self.adapter.submits), 1)
        self.assertEqual(self.adapter.polls, ['b1', 'b1'])

    def test_native_timeout_is_explicit_terminal_not_transport_timeout(self):
        state = self.attempt.submit()
        self.adapter.document = {'id': 'b1', 'state': 'timeout'}
        result = self.observe(state)
        self.assertEqual(result['status'], 'terminal')
        self.assertEqual(result['last_native_state'], 'timeout')
        self.assertEqual(self.observe(result), result)
        self.assertEqual(self.adapter.polls, ['b1'])

    def test_instance_change_or_missing_never_polls_reused_native_id(self):
        state = self.attempt.submit()
        for instance in ('instance-two', None, ''):
            self.adapter.instance = instance
            state = self.observe(state)
            self.assertEqual(state['status'], 'running')
            self.assertEqual(state['observer_status'], 'unresolved_handle')
        self.assertEqual(self.adapter.polls, [])
        self.assertEqual(len(self.adapter.submits), 1)

    def test_unavailable_instance_observation_retains_handle(self):
        state = self.attempt.submit()
        self.adapter.instance = TimeoutError()
        state = self.observe(state)
        self.assertEqual(state['native_id'], 'b1')
        self.assertEqual(state['status'], 'running')
        self.assertEqual(state['observer_status'], 'unavailable')
        self.assertEqual(self.adapter.polls, [])

    def test_unsolicited_id_state_or_instance_does_not_finish(self):
        state = self.attempt.submit()
        for document in ({'id': 'b2', 'state': 'done'}, {'id': 'b1', 'state': 'mystery'},
                         {'id': 'b1', 'state': 'done', 'instance_id': 'elsewhere'}):
            self.adapter.document = document
            state = self.observe(state)
            self.assertEqual(state['status'], 'running')
            self.assertEqual(state['observer_status'], 'unresolved_handle')
            self.assertNotIn('terminal_document', state)

    def test_token_or_fingerprint_mismatch_rejected_without_poll(self):
        state = self.attempt.submit()
        for token, fp in (('wrong', state['fingerprint']), (state['token'], 'd' * 64)):
            with self.assertRaises(AttemptError):
                self.attempt.observe(token, fp)
        self.assertEqual(self.adapter.polls, [])

    def test_changed_packet_cannot_create_second_attempt_or_attach(self):
        state = self.attempt.submit()
        changed = packet(); changed['dataset_sha256'] = 'd' * 64
        other = self.make(changed)
        self.assertNotEqual(other.fingerprint, state['fingerprint'])
        with self.assertRaises(DuplicateAttempt):
            other.submit()
        with self.assertRaises(AttemptError):
            self.observe(state, other)
        self.assertEqual(len(self.adapter.submits), 1)

    def test_stale_future_wrong_scope_or_unbound_authorization_cannot_claim(self):
        valid = self.authorization(packet(), packet_fingerprint(packet()))
        for changes in ({'checked_at_utc': (NOW - timedelta(seconds=61)).isoformat()},
                        {'checked_at_utc': (NOW + timedelta(seconds=1)).isoformat()},
                        {'scope': 'production'}, {'approved': 1}, {'packet_sha256': 'f' * 64}):
            proof = {**valid, **changes}
            with self.assertRaises(AttemptError):
                self.make(authorize=lambda p, fp: proof).submit()
            self.assertFalse(self.attempt.reservation_path.exists())
        self.assertEqual(self.adapter.submits, [])

    def test_pre_submission_instance_mismatch_does_not_claim(self):
        self.adapter.instance = 'other'
        with self.assertRaises(AttemptError):
            self.attempt.submit()
        self.assertFalse(self.attempt.reservation_path.exists())
        self.assertEqual(self.adapter.submits, [])

    def test_callback_timestamp_after_entry_is_current_with_advancing_clock(self):
        clock = AdvancingClock()
        def authorize(bound, fingerprint):
            clock.advance(2)
            return synthetic_attestation(bound, fingerprint, clock())
        attempt = ProspectiveAttempt(self.folder, packet(), self.adapter, authorize, clock=clock)
        state = attempt.submit()
        self.assertEqual(state['status'], 'running')
        self.assertEqual(len(self.adapter.submits), 1)
        reservation = json.loads(attempt.reservation_path.read_text())
        self.assertEqual(reservation['authorization']['checked_at_utc'],
                         (NOW + timedelta(seconds=2)).isoformat())

    def test_slow_instance_check_expires_authorization_without_external_call(self):
        clock = AdvancingClock()
        attempt = ProspectiveAttempt(self.folder, packet(), self.adapter,
                                     self.authorization, clock=clock)
        def slow_instance():
            clock.advance(61)
            return 'instance-one'
        with patch.object(self.adapter, 'current_instance', side_effect=slow_instance):
            state = attempt.submit()
        self.assertEqual(state['status'], 'submission_not_invoked')
        self.assertEqual(state['observer_status'], 'authorization_not_current')
        self.assertEqual(state['transport_not_invoked_reason'], 'authorization_not_current_before_call')
        self.assertEqual(self.adapter.submits, [])
        reservation = json.loads(attempt.reservation_path.read_text())
        self.assertEqual(reservation['local_submission_budget_consumed'], 1)
        self.assertEqual(self.observe(state, attempt), state)
        with self.assertRaises(DuplicateAttempt):
            attempt.submit()

    def test_slow_intent_write_expires_authorization_but_keeps_reservation_consumed(self):
        from runner.prospective_attempt import _replace
        clock = AdvancingClock()
        attempt = ProspectiveAttempt(self.folder, packet(), self.adapter,
                                     self.authorization, clock=clock)
        def slow_intent_write(path, value):
            _replace(path, value)
            if value['status'] == 'submitting':
                clock.advance(61)
        with patch('runner.prospective_attempt._replace', side_effect=slow_intent_write):
            state = attempt.submit()
        self.assertEqual(state['status'], 'submission_not_invoked')
        self.assertEqual(state['observer_status'], 'authorization_not_current')
        self.assertEqual(state['transport_attempt_intents'], 1)
        self.assertTrue(attempt.reservation_path.exists())
        self.assertFalse(attempt.handle_path.exists())
        self.assertEqual(self.adapter.submits, [])
        self.assertEqual(self.observe(state, attempt), state)
        with self.assertRaises(DuplicateAttempt):
            self.make().submit()

    def test_concurrent_claim_has_one_transport_invocation(self):
        entered, release = threading.Event(), threading.Event()
        self.adapter.before_submit = lambda: (entered.set(), release.wait(5))
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.attempt.submit)
            self.assertTrue(entered.wait(5))
            second = pool.submit(self.make().submit)
            try:
                with self.assertRaises(RuntimeError):
                    second.result(timeout=5)
            finally:
                release.set()
            state = first.result(timeout=5)
        self.assertEqual(state['status'], 'running')
        self.assertEqual(len(self.adapter.submits), 1)

    def test_incomplete_claim_after_crash_is_never_retried(self):
        self.attempt.reservation_path.write_text('{incomplete', encoding='utf-8')
        with self.assertRaises(DuplicateAttempt):
            self.attempt.submit()
        with self.assertRaises(AttemptError):
            self.attempt.observe('unknown', self.attempt.fingerprint)
        self.assertEqual(self.adapter.submits, [])

    def test_crash_after_durable_intent_before_transport_consumes_without_call(self):
        from runner.prospective_attempt import _replace
        def crash_before_transport(path, value):
            _replace(path, value)
            if value['status'] == 'submitting':
                raise InterruptedError('Synthetic process interruption before transport')
        with patch('runner.prospective_attempt._replace', side_effect=crash_before_transport):
            with self.assertRaises(InterruptedError):
                self.attempt.submit()
        self.assertTrue(self.attempt.reservation_path.exists())
        self.assertEqual(self.adapter.submits, [])
        with self.assertRaises(DuplicateAttempt):
            self.make().submit()

    def test_possible_server_acceptance_then_lost_response_is_not_retried(self):
        accepted = []
        self.adapter.before_submit = lambda: accepted.append('b1')
        self.adapter.receipt = TimeoutError('Receipt lost after fake acceptance')
        state = self.attempt.submit()
        self.assertEqual(accepted, ['b1'])
        self.assertEqual(state['status'], 'submission_unknown')
        self.assertEqual(state['transport_attempt_intents'], 1)
        with self.assertRaises(DuplicateAttempt):
            self.make().submit()
        self.assertEqual(len(self.adapter.submits), 1)

    def test_instance_changes_during_submission_leave_receipt_untrusted(self):
        for index, changed in enumerate(('instance-two', None, TimeoutError())):
            with self.subTest(instance=changed):
                adapter = FakeAdapter()
                attempt = ProspectiveAttempt(self.folder / str(index), packet(), adapter,
                                             self.authorization, clock=lambda: NOW)
                adapter.before_submit = lambda: setattr(adapter, 'instance', changed)
                state = attempt.submit()
                self.assertEqual(state['status'], 'submission_unknown')
                self.assertEqual(state['observer_status'], 'unresolved_handle')
                self.assertIsNone(state['native_id'])
                self.assertFalse(attempt.handle_path.exists())
                self.assertEqual(state['untrusted_observation']['document']['id'], 'b1')
                self.assertNotIn('terminal_document', state)
                with self.assertRaises(DuplicateAttempt):
                    attempt.submit()
                self.assertEqual(len(adapter.submits), 1)

    def test_instance_changes_during_poll_preserve_handle_without_terminal_promotion(self):
        for index, changed in enumerate(('instance-two', None, TimeoutError())):
            with self.subTest(instance=changed):
                adapter = FakeAdapter()
                attempt = ProspectiveAttempt(self.folder / str(index), packet(), adapter,
                                             self.authorization, clock=lambda: NOW)
                state = attempt.submit()
                adapter.document = {'id': 'b1', 'state': 'done'}
                adapter.before_poll = lambda: setattr(adapter, 'instance', changed)
                state = self.observe(state, attempt)
                self.assertEqual(state['status'], 'running')
                self.assertEqual(state['native_id'], 'b1')
                self.assertIn(state['observer_status'], ('unresolved_handle', 'unavailable'))
                self.assertEqual(state['untrusted_observation']['document']['state'], 'done')
                self.assertNotIn('terminal_document', state)
                with self.assertRaises(DuplicateAttempt):
                    attempt.submit()
                self.assertEqual(len(adapter.submits), 1)
                self.assertEqual(adapter.polls, ['b1'])

    def test_mutated_persisted_native_id_is_rejected_before_poll(self):
        state = self.attempt.submit()
        altered = copy.deepcopy(state); altered['native_id'] = 'b2'
        self.attempt.state_path.write_text(json.dumps(altered), encoding='utf-8')
        with self.assertRaises(AttemptError):
            self.observe(state)
        self.assertEqual(self.adapter.polls, [])

    def test_explicit_transport_and_authorization_dependencies_required(self):
        with self.assertRaises(AttemptError):
            ProspectiveAttempt(self.folder, packet(), self.adapter, None)
        with self.assertRaises(AttemptError):
            ProspectiveAttempt(self.folder, packet(), object(), self.authorization)

    def test_only_finite_bound_json_packet_accepted(self):
        for changes in ({'plan_id': '../escape'}, {'source_sha256': 'invalid'},
                        {'request': {'bad': float('nan')}}, {'instance_id': ''}):
            with self.assertRaises(AttemptError):
                self.make({**packet(), **changes})


if __name__ == '__main__':
    unittest.main()
