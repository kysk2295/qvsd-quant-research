import copy
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

from runner.future_data_importer import FutureImporter, NativeImportError, NativeImportTransport, NoRedirect
from runner.future_import_packet import stage_import
from runner.core import atomic
from runner.prospective_attempt import AttemptError
from tests.test_future_import_packet import make_fixture


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.health_value = dict(ok=True, pid=123, processStartUtc='2026-10-25T01:00:00Z',
            startedAt='2026-10-25T10:00:00', assemblyName='synthetic', assemblyLocation='synthetic.dll',
            connections=[], anyLive=False, anyNonSim=False)
        self.permission_value = {'armed': True}
        self.status = {'state': 'idle'}
        self.submit_hook = None
        self.health_hook = None
        self.receipt = None

    def health(self):
        self.calls.append('health')
        if self.health_hook:
            self.health_hook()
        return copy.deepcopy(self.health_value)

    def permission(self):
        self.calls.append('permission')
        return copy.deepcopy(self.permission_value)

    def poll(self):
        self.calls.append('poll')
        return copy.deepcopy(self.status)

    def submit(self, packet):
        self.calls.append('submit')
        self.packet = packet
        if self.submit_hook:
            self.submit_hook(packet)
        return copy.deepcopy(self.receipt) if self.receipt is not None else {'state': 'queued', 'path': packet['path']}


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = make_fixture(Path(self.tmp.name))
        self.transport = FakeTransport()
        self.importer = FutureImporter(self.f.intake, self.transport, lambda: self.f.now)

    def tearDown(self):
        self.tmp.cleanup()

    def submit(self):
        return self.importer.submit(self.f.day)

    def observe(self, **overrides):
        self.transport.status = dict(state='done', path=self.transport.packet['path'],
            points=self.transport.packet['rows'], instruments=['NQ DEC26'], **overrides)
        return self.importer.observe(self.f.day)

    def test_reserves_and_flushes_intent_before_submit(self):
        def check(packet):
            reservation, state = self.importer._paths(self.f.day)
            self.assertTrue(reservation.is_file())
            observed = json.loads(state.read_text())
            self.assertEqual(observed['post_attempt_intents'], 1)
            self.assertEqual(observed['status'], 'submitting')
            self.assertEqual(observed['packet'], packet)
        self.transport.submit_hook = check
        result = self.submit()
        self.assertEqual(result['status'], 'queued')
        self.assertEqual(self.transport.calls.count('submit'), 1)

    def test_same_date_is_never_resubmitted_after_restart(self):
        self.submit()
        fresh = FutureImporter(self.f.intake, self.transport, lambda: self.f.now)
        with self.assertRaisesRegex(NativeImportError, 'already reserved'):
            fresh.submit(self.f.day)
        self.assertEqual(self.transport.calls.count('submit'), 1)

    def test_before_close_reads_no_native_state(self):
        self.importer.clock = lambda: self.f.now-timedelta(microseconds=1)
        with self.assertRaises(ValueError):
            self.submit()
        self.assertEqual(self.transport.calls, [])

    def test_unknown_date_no_native_calls(self):
        with self.assertRaises(ValueError):
            self.importer.submit('2026-10-23')
        self.assertEqual(self.transport.calls, [])

    def test_missing_ack_no_native_calls(self):
        state = self.f.intake.load()
        state['entries'][self.f.day].pop('quality_ack')
        atomic(self.f.intake.path, state)
        with self.assertRaises(ValueError):
            self.submit()
        self.assertEqual(self.transport.calls, [])

    def test_permission_missing_does_not_arm_or_reserve(self):
        self.transport.permission_value = {'armed': False}
        with self.assertRaisesRegex(NativeImportError, 'permission'):
            self.submit()
        self.assertNotIn('submit', self.transport.calls)
        self.assertFalse(self.importer._paths(self.f.day)[0].exists())

    def test_connection_blocks_without_disconnect(self):
        self.transport.health_value['connections'] = [{'name': 'synthetic'}]
        with self.assertRaisesRegex(NativeImportError, 'connected feeds'):
            self.submit()
        self.assertEqual(self.transport.calls, ['health'])

    def test_running_import_blocks(self):
        self.transport.status = {'state': 'running', 'path': 'elsewhere'}
        with self.assertRaisesRegex(NativeImportError, 'unavailable'):
            self.submit()
        self.assertNotIn('submit', self.transport.calls)

    def test_existing_path_status_is_not_adopted(self):
        packet = stage_import(self.f.intake, self.f.day, self.f.now)
        self.transport.status = {'state': 'done', 'path': packet['path']}
        with self.assertRaises(NativeImportError):
            self.submit()
        self.assertNotIn('submit', self.transport.calls)

    def test_generation_change_preflight_no_post(self):
        def mutate():
            if self.transport.calls.count('health') == 2:
                self.transport.health_value['pid'] += 1
        self.transport.health_hook = mutate
        with self.assertRaisesRegex(NativeImportError, 'generation changed'):
            self.submit()
        self.assertNotIn('submit', self.transport.calls)

    def test_stage_changed_after_preflight_consumes_no_call_attempt(self):
        packet = stage_import(self.f.intake, self.f.day, self.f.now)
        def mutate():
            if self.transport.calls.count('health') == 2:
                Path(packet['path']).write_bytes(b'corrupt')
        self.transport.health_hook = mutate
        result = self.submit()
        self.assertEqual(result['status'], 'not_invoked_no_retry')
        self.assertEqual(result['post_attempt_intents'], 0)
        with self.assertRaises(NativeImportError):
            self.submit()
        self.assertNotIn('submit', self.transport.calls)

    def test_timeout_preserved_no_poll_or_retry(self):
        self.transport.submit_hook = Mock(side_effect=TimeoutError('synthetic'))
        result = self.submit()
        self.assertEqual(result['status'], 'submission_unknown')
        calls = list(self.transport.calls)
        self.assertEqual(self.importer.observe(self.f.day)['status'], 'submission_unknown')
        self.assertEqual(self.transport.calls, calls)
        with self.assertRaises(NativeImportError):
            self.submit()

    def test_server_denial_body_is_preserved(self):
        response = {'http_status': 403, 'body': '{"error":"research disabled"}'}
        self.transport.submit_hook = Mock(side_effect=NativeImportError('refused', response))
        result = self.submit()
        self.assertEqual(result['error_response'], response)
        self.assertEqual(result['status'], 'submission_unknown')
        self.assertEqual(result['post_attempt_intents'], 1)

    def test_wrong_receipt_path_is_unknown(self):
        self.transport.receipt = {'state': 'queued', 'path': 'wrong'}
        result = self.submit()
        self.assertEqual(result['status'], 'submission_unknown')
        self.assertEqual(result['raw_receipt'], self.transport.receipt)

    def test_restart_after_submit_cannot_bind_receipt(self):
        self.transport.submit_hook = lambda packet: self.transport.health_value.update(pid=999)
        self.assertEqual(self.submit()['status'], 'submission_unknown')

    def test_done_is_only_import_evidence(self):
        self.submit()
        result = self.observe()
        self.assertEqual(result['status'], 'native_done_pending_cache_parity')
        self.assertFalse(result['native_cache_parity'])
        self.assertFalse(result['strategy_validated'])
        self.assertEqual(self.f.intake.load()['entries'][self.f.day]['status'], 'quality_passed')
        calls = list(self.transport.calls)
        self.assertEqual(self.importer.observe(self.f.day), result)
        self.assertEqual(self.transport.calls, calls)

    def test_wrong_row_count_cannot_pass(self):
        self.submit()
        self.transport.status = {'state': 'done', 'path': self.transport.packet['path'],
                                 'points': self.transport.packet['rows']+1, 'instruments': ['NQ DEC26']}
        self.assertEqual(self.importer.observe(self.f.day)['status'], 'ambiguous_no_retry')

    def test_other_instrument_cannot_pass(self):
        self.submit()
        self.transport.status = {'state': 'done', 'path': self.transport.packet['path'],
                                 'points': self.transport.packet['rows'], 'instruments': ['MNQ DEC26']}
        self.assertEqual(self.importer.observe(self.f.day)['status'], 'ambiguous_no_retry')

    def test_global_status_path_overwritten_is_unknown(self):
        self.submit()
        self.transport.status = {'state': 'done', 'path': 'other'}
        result = self.importer.observe(self.f.day)
        self.assertEqual(result['status'], 'ambiguous_no_retry')
        self.assertEqual(result['last_raw_observation'], self.transport.status)

    def test_pathless_error_not_attributed(self):
        self.submit()
        self.transport.status = {'state': 'error', 'error': 'unbound global exception'}
        self.assertEqual(self.importer.observe(self.f.day)['status'], 'ambiguous_no_retry')

    def test_path_bound_error_terminal_no_retry(self):
        self.submit()
        self.transport.status = {'state': 'error', 'path': self.transport.packet['path']}
        self.assertEqual(self.importer.observe(self.f.day)['status'], 'native_error_no_retry')

    def test_changed_engine_before_poll_cannot_adopt_result(self):
        self.submit()
        count = self.transport.calls.count('poll')
        self.transport.health_value['pid'] += 1
        result = self.importer.observe(self.f.day)
        self.assertEqual(result['status'], 'ambiguous_no_retry')
        self.assertEqual(self.transport.calls.count('poll'), count)

    def test_payload_changed_before_poll_blocks_result(self):
        self.submit()
        Path(self.transport.packet['path']).write_bytes(b'changed')
        result = self.importer.observe(self.f.day)
        self.assertEqual(result['status'], 'ambiguous_no_retry')

    def test_engine_changes_after_payload_before_post_no_call(self):
        def mutate():
            if self.transport.calls.count('health') == 3:
                self.transport.health_value['pid'] += 1
        self.transport.health_hook = mutate
        result = self.submit()
        self.assertEqual(result['status'], 'not_invoked_no_retry')
        self.assertEqual(result['post_attempt_intents'], 0)
        self.assertNotIn('submit', self.transport.calls)

    def test_engine_changes_during_poll_cannot_bind_done(self):
        self.submit()
        target = self.transport.calls.count('health')+2
        def mutate():
            if self.transport.calls.count('health') == target:
                self.transport.health_value['pid'] += 1
        self.transport.health_hook = mutate
        self.assertEqual(self.observe()['status'], 'ambiguous_no_retry')

    def test_damaged_terminal_evidence_blocks_next_date(self):
        self.submit()
        self.observe()
        _, path = self.importer._paths(self.f.day)
        state = json.loads(path.read_text())
        state['last_raw_observation']['points'] += 1
        atomic(path, state)
        with self.assertRaisesRegex(ValueError, 'completion evidence'):
            self.importer.submit('2026-10-27')

    def test_reservation_corruption_blocks_observe(self):
        self.submit()
        reservation, state = self.importer._paths(self.f.day)
        doc = json.loads(reservation.read_text())
        doc['packet']['rows'] += 1
        atomic(reservation, doc)
        with self.assertRaises(ValueError):
            self.importer.observe(self.f.day)

    def test_partial_crashed_reservation_blocks_new_date(self):
        reservation, state = self.importer._paths(self.f.day)
        atomic(reservation, {'synthetic': 'crashed'})
        with self.assertRaises(AttemptError):
            self.importer.submit('2026-10-27')
        self.assertEqual(self.transport.calls, [])

    def test_live_transport_cannot_attach_to_temp_root(self):
        with self.assertRaises(ValueError):
            FutureImporter(self.f.intake)


class TransportScopeTests(unittest.TestCase):
    def test_endpoint_allowlist_no_calls(self):
        t = NativeImportTransport()
        t.opener = Mock()
        for method, path in [('POST', '/backtest'), ('POST', '/research/connect'),
                             ('GET', '/accounts'), ('POST', '/orders')]:
            with self.assertRaises(NativeImportError):
                t._call(method, path, {})
        t.opener.open.assert_not_called()

    def test_post_body_exact_schema(self):
        t = NativeImportTransport()
        t.opener = Mock()
        with self.assertRaises(NativeImportError):
            t._call('POST', '/research/import', {'path': 'x', 'sha256': 'y', 'force': True})
        t.opener.open.assert_not_called()

    def test_redirect_is_never_followed(self):
        with self.assertRaises(NativeImportError):
            NoRedirect().redirect_request(None, None, 307, '', {}, 'https://example.com')


if __name__ == '__main__':
    unittest.main()
