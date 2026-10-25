"""Ten-day synthetic import lifecycles and raw Last; no native calls."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from runner.core import atomic, canonical, file_hash
from runner.future_data_importer import FutureImporter
from runner.future_import_packet import COHORT
from runner.prospective_dataset import DECISION_AT, _load_last, load_imported_dataset
from tests.test_future_data_importer import FakeTransport
from tests.test_future_import_packet import make_fixture


def make_dataset_fixture(root):
    """Create actual-schema ten-date local imports using only fake transport."""
    records = {day:make_fixture(root, day) for day in COHORT}
    intake = records[COHORT[0]].intake
    now = datetime.fromisoformat(DECISION_AT).astimezone(timezone.utc)
    transport = FakeTransport()
    importer = FutureImporter(intake, transport, lambda: now)
    states = {}
    for day in COHORT:
        submitted = importer.submit(day)
        if submitted['status'] != 'queued':
            raise AssertionError('Synthetic import fixture did not queue')
        transport.status = dict(state='done', path=transport.packet['path'],
                                points=transport.packet['rows'], instruments=['NQ DEC26'])
        states[day] = importer.observe(day)
        if states[day]['status'] != 'native_done_pending_cache_parity':
            raise AssertionError('Synthetic import fixture did not complete')
    return SimpleNamespace(root=Path(root).resolve(), intake=intake, now=now, records=records,
                           queue_db=records[COHORT[0]].queue_db,
                           importer=importer, transport=transport, import_states=states)


class ProspectiveDatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = make_dataset_fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, now=None):
        return load_imported_dataset(self.f.intake, self.f.now if now is None else now)

    def assert_no_market_read(self, action):
        paths = {path.resolve() for f in self.f.records.values() for path in (f.source, f.parquet, f.last)}
        calls = []
        original_open = Path.open
        def guarded(path, *args, **kwargs):
            if path.resolve() in paths:
                calls.append(str(path))
            return original_open(path, *args, **kwargs)
        def hashed(path):
            if Path(path).resolve() in paths:
                calls.append(str(path))
            return file_hash(path)
        with patch.object(Path, 'open', guarded), patch('runner.prospective_dataset.file_hash', side_effect=hashed), \
                patch('runner.future_import_packet.file_hash') as stage_hash:
            with self.assertRaises(ValueError):
                action()
            stage_hash.assert_not_called()
        self.assertEqual(calls, [])

    def test_exact_decision_loads_full_ordered_readonly_arrays_and_stable_digest(self):
        loaded = self.load()
        dataset = loaded['dataset']
        self.assertEqual(dataset['evaluation_dates'], list(COHORT))
        self.assertEqual(loaded['dataset_sha256'], hashlib.sha256(canonical(dataset).encode()).hexdigest())
        self.assertEqual(len(dataset['imports']), 10)
        self.assertEqual(len(dataset['files']), 92)
        self.assertTrue(all(Path(path).is_absolute() for path in dataset['files']))
        self.assertFalse(dataset['native_cache_parity'])
        self.assertFalse(dataset['strategy_validated'])
        self.assertEqual(set(loaded['last_by_date']), set(COHORT))
        for day, arrays in loaded['last_by_date'].items():
            self.assertEqual(len(arrays['timestamps_ns']), 394)
            self.assertEqual(arrays['timestamps_ns'].dtype, np.dtype('int64'))
            self.assertEqual(arrays['volumes'].dtype, np.dtype('int64'))
            self.assertEqual(arrays['prices'].dtype, np.dtype('float64'))
            self.assertTrue(np.all(arrays['timestamps_ns'] % 100 == 0))
            self.assertEqual(int(arrays['timestamps_ns'][2] % 10**9), 100)
            self.assertEqual(int(arrays['timestamps_ns'][1] % 10**9), 999999900)
            self.assertTrue(np.all(arrays['prices'] == 20000.25))
            self.assertTrue(np.all(arrays['volumes'] == 1))
            self.assertFalse(arrays['timestamps_ns'].flags.writeable)
        self.assertEqual(self.load()['dataset_sha256'], loaded['dataset_sha256'])

    def test_predecision_naive_clock_and_absent_intake_do_not_touch_files(self):
        for now in (self.f.now-timedelta(microseconds=1), self.f.now.replace(tzinfo=None)):
            with self.subTest(now=now):
                self.assert_no_market_read(lambda: self.load(now))
        with patch('runner.prospective_dataset._plan') as plan:
            with self.assertRaises(ValueError):
                load_imported_dataset(object(), self.f.now-timedelta(seconds=1))
            plan.assert_not_called()

    def test_missing_last_import_blocks_before_first_market_file(self):
        _, state_path = self.f.importer._paths(COHORT[-1])
        state_path.unlink()
        self.assert_no_market_read(self.load)

    def test_incomplete_last_import_blocks_before_first_market_file(self):
        _, state_path = self.f.importer._paths(COHORT[-1])
        state = json.loads(state_path.read_text())
        state['status'] = 'running'
        atomic(state_path, state)
        self.assert_no_market_read(self.load)

    def test_missing_last_quality_ack_blocks_before_first_market_file(self):
        state = self.f.intake.load()
        state['entries'][COHORT[-1]].pop('quality_ack')
        atomic(self.f.intake.path, state)
        self.assert_no_market_read(self.load)

    def test_import_receipt_or_terminal_observation_damage_is_rejected(self):
        _, path = self.f.importer._paths(COHORT[-1])
        original = path.read_bytes()
        for field in ('receipt_sha256', 'observation_sha256'):
            state = json.loads(original)
            state[field] = '0'*64
            atomic(path, state)
            with self.subTest(field=field):
                self.assert_no_market_read(self.load)
        path.write_bytes(original)

    def test_missing_staged_file_is_not_rebuilt(self):
        path = Path(self.f.import_states[COHORT[-1]]['packet']['path'])
        path.unlink()
        self.assert_no_market_read(self.load)
        self.assertFalse(path.exists())

    def test_source_parquet_full_last_and_stage_changes_fail(self):
        f = self.f.records[COHORT[0]]
        for path in (f.source, f.parquet, f.last, Path(self.f.import_states[f.day]['packet']['path'])):
            original = path.read_bytes()
            path.write_bytes(original+b'changed')
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                self.load()
            path.write_bytes(original)

    def test_loader_constructs_no_native_transport_or_new_files(self):
        before = sorted(str(p.relative_to(self.f.root)) for p in self.f.root.rglob('*'))
        calls = list(self.f.transport.calls)
        with patch('runner.future_data_importer.NativeImportTransport', side_effect=AssertionError('No native transport')):
            self.load()
        self.assertEqual(self.f.transport.calls, calls)
        self.assertEqual(sorted(str(p.relative_to(self.f.root)) for p in self.f.root.rglob('*')), before)

    def test_snapshot_detects_early_source_change_during_later_array_load(self):
        from runner import prospective_dataset as module
        original = module._load_last
        def changed(path, digest):
            result = original(path, digest)
            if path == self.f.records[COHORT[-1]].last:
                self.f.records[COHORT[0]].source.write_bytes(b'changed during array loading')
            return result
        with patch.object(module, '_load_last', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed during load'):
            self.load()

    def test_snapshot_detects_import_state_change_during_array_load(self):
        from runner import prospective_dataset as module
        original = module._load_last
        def changed(path, digest):
            result = original(path, digest)
            if path == self.f.records[COHORT[-1]].last:
                _, state_path = self.f.importer._paths(COHORT[0])
                state = json.loads(state_path.read_text())
                state['observations'] += 1
                atomic(state_path, state)
            return result
        with patch.object(module, '_load_last', side_effect=changed), self.assertRaisesRegex(ValueError, 'evidence changed'):
            self.load()

    def test_plan_change_rejected_before_market_bytes(self):
        self.f.intake.planpath.write_bytes(self.f.intake.planpath.read_bytes()+b' ')
        self.assert_no_market_read(self.load)


class RawLastArrayTests(unittest.TestCase):
    def test_equal_100ns_clock_order_and_int64_volume_are_exact(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'synthetic.Last.txt'
            path.write_bytes(b'20261026 133000 0000001;20000.25;9223372036854775807\r\n'
                             b'20261026 133000 0000001;20000.50;1\n'
                             b'20261026 133000 0000002;20000.75;2\n')
            values = _load_last(path, file_hash(path))
            self.assertEqual(values['timestamps_ns'][0], values['timestamps_ns'][1])
            self.assertEqual(int(values['timestamps_ns'][2])-int(values['timestamps_ns'][1]), 100)
            self.assertEqual(values['prices'].tolist(), [20000.25, 20000.50, 20000.75])
            self.assertEqual(values['volumes'].tolist(), [2**63-1, 1, 2])

    def test_full_context_invalid_size_order_or_price_is_rejected(self):
        variants = [b'20261026 133000 0000001;20000.25;9223372036854775808\n',
                    b'20261026 133000 0000001;20000.25;0\n',
                    b'20261026 133000 0000001;20000.10;1\n',
                    b'20261026 133000 0000002;20000.25;1\n20261026 133000 0000001;20000.25;1\n']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'synthetic.Last.txt'
            for raw in variants:
                path.write_bytes(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    _load_last(path, file_hash(path))


if __name__ == '__main__':
    unittest.main()
