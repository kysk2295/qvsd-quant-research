"""Production path integration with actual-schema synthetic disk and fake HTTP."""
import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from runner.core import ROOT, atomic, ProcessLock
from runner.prospective_executor import ProspectiveExecutor, NativeResearch, dispatch_bound
from runner.prospective_attempt import AttemptError
from tests.test_prospective_dataset import make_dataset_fixture
from tests.test_prospective_postrun import fixture as postrun_fixture


class FakeNative:
    def __init__(self, nt_dir):
        self.calls = []
        self.health = dict(ok=True, pid=1, processStartUtc='2026-11-07T00:00:00Z',
            startedAt='2026-11-07T09:00:00', assemblyName='synthetic',
            assemblyLocation=str(nt_dir/'tmp/synthetic.dll'), connections=[],
            anyLive=False, anyNonSim=False, standingModal=None)
        self.jobs = []
        self.status = {'verdict': 'current'}
        self.catalog = [dict(fullName='NinjaTrader.NinjaScript.Strategies.CodexBollingerClock',
                             inputs={'BandLength': {'type': 'Int32', 'default': 20}})]
        self.import_status = {'state': 'done'}
        self.before_post = self.on_get = None
        _, self.document, _, _, _ = postrun_fixture()
        for i, line in enumerate(self.document['output']):
            for field in ('close', 'mean', 'lower', 'upper'):
                line = line.replace(field+'=100.0', field+'=20000.25')
            self.document['output'][i] = line

    def submit_bound(self, root, packet, preflight, clock):
        return dispatch_bound(root, packet, preflight, clock,
                              lambda body: self.call('POST', '/backtest', body))

    def call(self, method, path, body=None):
        self.calls.append((method, path))
        if self.on_get and method == 'GET':
            self.on_get(path)
        if method == 'POST':
            if self.before_post:
                self.before_post(body)
            return {'id': 'b1', 'state': 'queued'}
        result = {'/health': self.health, '/ntstatus': self.status,
                  '/strategies': self.catalog, '/backtests': self.jobs,
                  '/research/import': self.import_status, '/backtest/b1': self.document}[path]
        return copy.deepcopy(result)


def fixture(root):
    f = make_dataset_fixture(root)
    for name in ('campaign-search-control.json', 'bollinger-return-manifest.json',
                 'campaign-trial-registry.json', 'data-role-registry.json'):
        (f.root/'research'/name).write_bytes((ROOT/'research'/name).read_bytes())
    with closing(sqlite3.connect(f.queue_db)) as c, c:
        c.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,status TEXT)")
        c.executemany('INSERT OR REPLACE INTO control VALUES(?,?)', [('mode', 'running'), ('uncertain', '')])
    f.nt_dir = f.root/'synthetic-nt'
    for name, sub in [('CodexBollingerClock.cs', 'Strategies'),
                       ('NT8Bridge.Backtest.cs', 'AddOns'), ('NT8Bridge.ResearchControl.cs', 'AddOns')]:
        data = (ROOT/'native'/name).read_bytes()
        source, installed = f.root/'native'/name, f.nt_dir/'bin/Custom'/sub/name
        source.parent.mkdir(parents=True, exist_ok=True)
        installed.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(data)
        installed.write_bytes(data)
    (f.nt_dir/'Config.xml').write_text('<Config><TimeZoneInfoSerializable /></Config>')
    dll = f.nt_dir/'tmp/synthetic.dll'
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b'synthetic assembly identity fixture, not executable')
    for day in f.records:
        for kind, suffix in [('minute', '.Last.ncd'), ('tick', '1300.Last.ncd')]:
            p = f.nt_dir/'db'/kind/'NQ 12-26'/(day.replace('-', '')+suffix)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'synthetic native store; only hash/metadata checked')
    f.native = FakeNative(f.nt_dir)
    f.executor = ProspectiveExecutor(f.root, f.native, lambda: f.now, f.nt_dir, lambda: 'Korea Standard Time')
    # The import fixture intentionally uses an isolated downloads directory.
    f.executor.intake = f.intake
    return f


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = fixture(self.tmp.name)
        self.e = self.f.executor

    def tearDown(self):
        self.tmp.cleanup()

    def control(self, key, value):
        with closing(sqlite3.connect(self.f.queue_db)) as c, c:
            c.execute('INSERT OR REPLACE INTO control VALUES(?,?)', (key, value))

    def posts(self):
        return [c for c in self.f.native.calls if c[0] == 'POST']

    def test_early_time_blocks_before_dataset_or_native_access(self):
        self.f.now -= timedelta(microseconds=1)
        with patch('runner.prospective_executor.load_imported_dataset') as load:
            with self.assertRaisesRegex(RuntimeError, 'decision'):
                self.e.submit()
            load.assert_not_called()
        self.assertEqual(self.f.native.calls, [])
        self.assertFalse((self.e.folder/(self.f.intake.plan['id']+'.reservation.json')).exists())

    def test_missing_control_blocks_not_generic_escape(self):
        (self.f.root/'research/campaign-search-control.json').unlink()
        with self.assertRaises(RuntimeError):
            self.e.prepare()
        self.assertEqual(self.f.native.calls, [])

    def test_paused_stopped_or_uncertain_do_not_auto_resume(self):
        for key, value in [('mode', 'paused'), ('mode', 'stopped'), ('uncertain', 'b-old')]:
            self.control('mode', 'running')
            self.control('uncertain', '')
            self.control(key, value)
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.e.prepare()
        self.assertEqual(self.f.native.calls, [])

    def test_missing_one_import_blocks_before_native(self):
        self.f.importer._paths('2026-11-06')[1].unlink()
        with self.assertRaises(ValueError):
            self.e.prepare()
        self.assertEqual(self.f.native.calls, [])

    def test_missing_store_or_installed_source_rejects(self):
        (self.f.nt_dir/'db/minute/NQ 12-26/20261026.Last.ncd').unlink()
        with self.assertRaisesRegex(ValueError, 'stores missing'):
            self.e.prepare()
        self.assertEqual(self.f.native.calls, [])

    def test_installed_source_change_blocks(self):
        p = self.f.nt_dir/'bin/Custom/Strategies/CodexBollingerClock.cs'
        p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError, 'source differ'):
            self.e.prepare()
        self.assertEqual(self.f.native.calls, [])

    def test_matching_modified_backends_still_fail_review_pin(self):
        for p in (self.f.root/'native/NT8Bridge.Backtest.cs',
                  self.f.nt_dir/'bin/Custom/AddOns/NT8Bridge.Backtest.cs'):
            p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError, 'reviewed source'):
            self.e.prepare()
        self.assertEqual(self.f.native.calls, [])

    def test_production_clock_injection_refused_without_native_calls(self):
        with self.assertRaisesRegex(ValueError, 'real clock'):
            ProspectiveExecutor(ROOT, native=self.f.native, clock=lambda:self.f.now)
        self.assertEqual(self.f.native.calls, [])

    def test_prepare_cannot_overwrite_during_submission_lock(self):
        with ProcessLock(self.e.folder/'executor.lock'):
            with self.assertRaisesRegex(RuntimeError, 'already active'):
                self.e.prepare()
        self.assertEqual(self.f.native.calls, [])

    def test_connected_feed_blocks_without_control_actions(self):
        self.f.native.health['connections'] = ['synthetic-connected']
        with self.assertRaises(AttemptError):
            self.e.prepare()
        self.assertEqual(self.f.native.calls, [('GET', '/health')])

    def test_native_job_busy_or_source_stale_blocks(self):
        self.f.native.jobs = [{'id': 'b-old', 'state': 'running'}]
        with self.assertRaisesRegex(AttemptError, 'job state'):
            self.e.prepare()
        self.f.native.jobs = []
        self.f.native.status['verdict'] = 'stale'
        with self.assertRaisesRegex(AttemptError, 'freshness'):
            self.e.prepare()
        self.assertEqual(self.posts(), [])

    def test_empty_config_system_timezone_is_only_expectation(self):
        p = self.e.prepare()
        self.assertIsNone(p['evidence']['disk']['saved_time_zone'])
        self.assertIn('does not prove', p['evidence']['disk']['timezone_basis'])
        self.assertEqual(p['native_time_zone'], 'Korea Standard Time')
        self.assertFalse(p['evidence']['disk']['cache_content_parity'])
        self.assertEqual(self.posts(), [])

    def test_one_dispatch_is_on_disk_before_the_single_post(self):
        def verify(body):
            p = self.e.folder/(self.f.intake.plan['id']+'.dispatch.json')
            self.assertTrue(p.exists())
            self.assertEqual(body, self.f.intake.plan['request'])
        self.f.native.before_post = verify
        state = self.e.submit()
        self.assertEqual(state['status'], 'running')
        self.assertEqual(len(self.posts()), 1)
        with self.assertRaises(AttemptError):
            self.e.submit()
        with self.assertRaises(RuntimeError):
            self.e.transport.submit(self.e.packet['request'])
        self.assertEqual(len(self.posts()), 1)

    def test_unknown_submission_is_never_retried(self):
        self.f.native.before_post = Mock(side_effect=TimeoutError('synthetic receipt lost'))
        state = self.e.submit()
        self.assertEqual(state['status'], 'submission_unknown')
        self.assertEqual(self.e.observe()['observer_status'], 'unresolved_handle')
        with self.assertRaises(AttemptError):
            self.e.submit()
        self.assertEqual(len(self.posts()), 1)
        self.assertFalse(json.loads((self.e.folder/'dispatch-response.json').read_text())['received'])

    def test_stop_arriving_before_dispatch_prevents_post(self):
        original = self.e.transport.submit
        def stopped(request):
            self.control('mode', 'stopped')
            return original(request)
        with patch.object(self.e.transport, 'submit', side_effect=stopped):
            state = self.e.submit()
        self.assertEqual(state['status'], 'submission_unknown')
        self.assertEqual(self.posts(), [])

    def test_native_import_starting_before_dispatch_prevents_post(self):
        original = self.e.transport.submit
        def busy(request):
            self.f.native.import_status = {'state': 'running'}
            return original(request)
        with patch.object(self.e.transport, 'submit', side_effect=busy):
            state = self.e.submit()
        self.assertEqual(state['status'], 'submission_unknown')
        self.assertEqual(self.posts(), [])

    def test_native_job_starting_before_dispatch_prevents_post(self):
        original = self.e.transport.submit
        def busy(request):
            self.f.native.jobs = [{'id': 'b-other', 'state': 'running'}]
            return original(request)
        with patch.object(self.e.transport, 'submit', side_effect=busy):
            state = self.e.submit()
        self.assertEqual(state['status'], 'submission_unknown')
        self.assertEqual(self.posts(), [])

    def test_dispatch_persistence_expiry_consumes_without_post(self):
        from runner.campaign_gate import _exclusive as exclusive
        def slow_dispatch(path, value):
            exclusive(path, value)
            self.f.now += timedelta(seconds=61)
        with patch('runner.campaign_gate._exclusive', side_effect=slow_dispatch):
            state = self.e.submit()
        self.assertEqual(state['status'], 'submission_unknown')
        self.assertTrue((self.e.folder/(self.f.intake.plan['id']+'.dispatch.json')).exists())
        self.assertEqual(self.posts(), [])

    def test_engine_restart_after_post_keeps_uncertain_receipt(self):
        self.f.native.before_post = lambda body: self.f.native.health.update(pid=2)
        self.assertEqual(self.e.submit()['status'], 'submission_unknown')
        self.assertEqual(len(self.posts()), 1)

    def test_transient_poll_error_can_reobserve_same_job_without_repost(self):
        self.e.submit()
        def fail(path):
            if path == '/backtest/b1':
                raise TimeoutError('synthetic observation timeout')
        self.f.native.on_get = fail
        self.assertEqual(self.e.observe()['observer_status'], 'unavailable')
        self.f.native.on_get = None
        self.assertEqual(self.e.observe()['status'], 'terminal')
        self.assertEqual(len(self.posts()), 1)

    def test_restart_before_poll_never_adopts_reused_id(self):
        self.e.submit()
        self.f.native.health['pid'] = 3
        state = self.e.observe()
        self.assertEqual(state['observer_status'], 'unresolved_handle')
        self.assertNotIn(('GET', '/backtest/b1'), self.f.native.calls)

    def test_complete_bound_pipeline_stays_unvalidated(self):
        self.e.submit()
        state = self.e.observe()
        self.assertEqual(state['status'], 'terminal')
        result = self.e.assess()
        self.assertFalse(result['strategy_validated'])
        self.assertFalse(result['prospective_candidate_promoted'])
        self.assertEqual(result['evaluation']['errors'], [])
        self.assertEqual(result['evaluation']['decision'], 'condition_absent_not_performance_evaluable')
        self.assertEqual(result['evaluation']['entries']['verified_bars'], 3900)
        calls = list(self.f.native.calls)
        self.assertEqual(self.e.assess(), result)
        self.assertEqual(calls, self.f.native.calls)

    def test_result_time_zone_disagreement_is_incomplete(self):
        self.e.submit()
        self.f.native.document['timeZone'] = 'Eastern Standard Time'
        self.e.observe()
        result = self.e.assess()
        self.assertEqual(result['evaluation']['decision'], 'incomplete_evidence')
        self.assertFalse(result['strategy_validated'])

    def test_changed_source_after_run_cannot_be_assessed(self):
        self.e.submit()
        self.e.observe()
        self.f.records['2026-10-26'].last.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'file changed'):
            self.e.assess()
        self.assertFalse((self.e.folder/'assessment.json').exists())

    def test_unbound_or_corrupt_result_state_refused(self):
        self.e.submit()
        self.e.observe()
        path = self.e.folder/(self.f.intake.plan['id']+'.state.json')
        state = json.loads(path.read_text())
        state['terminal_document']['id'] = 'b-other'
        atomic(path, state)
        with self.assertRaises(AttemptError):
            self.e.assess()

    def test_arbitrary_endpoints_rejected_without_network(self):
        native = NativeResearch()
        native.opener = Mock()
        for method, path in [('POST', '/backtest'), ('POST', '/orders'), ('POST', '/research/import'),
                             ('POST', '/playback/control'), ('DELETE', '/backtest/b1')]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                native.call(method, path)
        native.opener.open.assert_not_called()


if __name__ == '__main__':
    unittest.main()
