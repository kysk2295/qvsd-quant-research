"""Synthetic fixtures only; no production market files or native calls."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from runner.core import atomic, file_hash
from runner.future_data_intake import FutureIntake
from runner.future_import_packet import PLAN_ID, stage_import


def _line(instant, fraction='0000000', price='20000.25', size='1', newline=b'\n'):
    return (instant.strftime('%Y%m%d %H%M%S')+' '+fraction+';'+price+';'+size).encode('ascii')+newline


def make_fixture(root, day='2026-10-26'):
    """Build synthetic sources and actual intake/quality/ACK schema in temp root."""
    root = Path(root).resolve()
    plan = root/'research/bollinger-prospective-plan.json'
    plan.parent.mkdir(parents=True, exist_ok=True)
    # Only frozen plan metadata is read from the repository.
    plan.write_bytes((Path(__file__).resolve().parents[1]/'research/bollinger-prospective-plan.json').read_bytes())
    intake = FutureIntake(root, root/'downloads')
    intake.initialize()
    date = datetime.strptime(day, '%Y-%m-%d').date()
    zone = ZoneInfo('America/New_York')
    opening = datetime.combine(date, time(9, 30), zone).astimezone(timezone.utc)
    close = datetime.combine(date, time(16), zone).astimezone(timezone.utc)
    folder = intake.folder/'quality'
    folder.mkdir(parents=True, exist_ok=True)
    source = root/'downloads'/(day.replace('-', '')+'.nrd')
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b'synthetic NRD source: not exchange data')
    parquet = folder/(day+'.parquet')
    parquet.write_bytes(b'synthetic parquet: only its binding is used')
    last = folder/(day+'.Last.txt')
    rth = b''.join(_line(opening+timedelta(minutes=i), fraction='0000001',
                         newline=b'\r\n' if i % 2 else b'\n') for i in range(390))
    before = _line(opening-timedelta(days=1)) + _line(opening-timedelta(seconds=1), '9999999')
    after = _line(close) + _line(close+timedelta(days=1))
    last.write_bytes(before+rth+after)
    run_id = 'bollinger-future-data-'+day
    telemetry_path = root/'data/runner/telemetry'/(hashlib.sha256(run_id.encode()).hexdigest()+'.json')
    f = SimpleNamespace(intake=intake, root=root, day=day, now=close, opening=opening,
                        source=source, last=last, parquet=parquet,
                        audit_path=folder/(day+'.quality.json'), telemetry_path=telemetry_path,
                        queue_db=root/'data/runner/queue.sqlite3', expected_rth_bytes=rth,
                        rth_ticks=390)
    refresh_fixture(f)
    return f


def refresh_fixture(f):
    """Rebind synthetic file hashes and ACK; retain its claimed 390-minute audit."""
    audit = dict(date=f.day, source_sha256=file_hash(f.source), integrity_passed=True,
                 derived_hashes={str(f.parquet):file_hash(f.parquet), str(f.last):file_hash(f.last)},
                 rth_minutes=390, rth_ticks=f.rth_ticks, missing_minutes=[], native_runs=0,
                 performance_evaluated=False, timezone='America/New_York', limitation='Synthetic fixture')
    atomic(f.audit_path, audit)
    run_id = 'bollinger-future-data-'+f.day
    telemetry = dict(id=run_id, strategy='Data quality only', symbol='NQ 12-26',
                     source='Native Historical Data NRD', worker='windows-candidate-research',
                     dataset=f.day, status='completed', progress=100, phase='data_quality',
                     metrics={}, equity=[], params=dict(quality=audit, performance_evaluated=False, native_runs=0))
    atomic(f.telemetry_path, telemetry)
    ack_hash = file_hash(f.telemetry_path)
    with closing(sqlite3.connect(f.queue_db)) as connection, connection:
        connection.execute('CREATE TABLE IF NOT EXISTS control(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        connection.execute('INSERT OR REPLACE INTO control VALUES(?,?)', ('ack:'+f.telemetry_path.name, ack_hash))
    state = f.intake.load()
    state['entries'][f.day].update(status='quality_passed', source_sha256=audit['source_sha256'],
        audit_path=str(f.audit_path), audit_sha256=file_hash(f.audit_path),
        quality_ack=dict(run_id=run_id, ack=True, telemetry_sha256=ack_hash))
    atomic(f.intake.path, state)


class FutureImportPacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = make_fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self, **kw):
        return stage_import(self.f.intake, kw.get('day', self.f.day), kw.get('now', self.f.now))

    def alter_entry(self, **kw):
        state = self.f.intake.load()
        state['entries'][self.f.day].update(kw)
        atomic(self.f.intake.path, state)

    def assert_no_market_read(self, callback):
        originals = {self.f.source.resolve(), self.f.parquet.resolve(), self.f.last.resolve()}
        path_open = Path.open
        reads = []
        def guarded(path, *args, **kwargs):
            if path.resolve() in originals:
                reads.append(str(path))
            return path_open(path, *args, **kwargs)
        def hashed(path):
            reads.append(str(path))
            return file_hash(path)
        with patch.object(Path, 'open', guarded), patch('runner.future_import_packet.file_hash', side_effect=hashed):
            with self.assertRaises(ValueError):
                callback()
        self.assertEqual(reads, [], 'Market bytes read before eligibility/ACK verification')

    def test_exact_close_stages_only_rth_and_preserves_original_bytes(self):
        packet = self.stage()
        self.assertEqual(Path(packet['path']).name, 'NQ DEC26.Last.txt')
        self.assertEqual(Path(packet['path']).read_bytes(), self.f.expected_rth_bytes)
        self.assertEqual(packet['rows'], 390)
        self.assertEqual(packet['sha256'], hashlib.sha256(self.f.expected_rth_bytes).hexdigest())
        self.assertEqual(packet['source_sha256'], file_hash(self.f.source))
        self.assertEqual(packet['source_last_sha256'], file_hash(self.f.last))
        self.assertEqual(packet['staging_manifest_sha256'], file_hash(packet['staging_manifest_path']))
        self.assertEqual(packet['rth_open_utc'], '2026-10-26T13:30:00+00:00')
        self.assertEqual(packet['session_close_utc'], '2026-10-26T20:00:00+00:00')

    def test_preclose_and_naive_or_unregistered_date_read_no_market_bytes(self):
        for kwargs in ({'now':self.f.now-timedelta(microseconds=1)},
                       {'now':self.f.now.replace(tzinfo=None)}, {'day':'2026-10-25'}):
            with self.subTest(kwargs=kwargs):
                self.assert_no_market_read(lambda: self.stage(**kwargs))
        self.assertFalse((self.f.root/'data/runner/nt-import').exists())

    def test_dst_close_is_computed_not_trusted_from_state(self):
        with tempfile.TemporaryDirectory() as folder:
            f = make_fixture(folder, '2026-11-02')
            with self.assertRaises(ValueError):
                stage_import(f.intake, f.day, datetime(2026,11,2,20,59,59,tzinfo=timezone.utc))
            packet = stage_import(f.intake, f.day, f.now)
            self.assertEqual(packet['rth_open_utc'], '2026-11-02T14:30:00+00:00')
            self.assertEqual(packet['session_close_utc'], '2026-11-02T21:00:00+00:00')
        self.alter_entry(session_close_utc='2026-10-26T19:00:00+00:00')
        self.assert_no_market_read(self.stage)

    def test_completed_staging_reentrant_and_intake_unchanged(self):
        before = self.f.intake.path.read_bytes()
        packet = self.stage()
        content = Path(packet['staging_manifest_path']).read_bytes()
        self.assertEqual(self.stage(), packet)
        self.assertEqual(Path(packet['staging_manifest_path']).read_bytes(), content)
        self.assertEqual(self.f.intake.path.read_bytes(), before)
        self.assertEqual(len(list((self.f.root/'data/runner/nt-import').rglob('NQ DEC26.Last.txt'))), 1)

    def test_reentry_revalidates_each_full_source_and_does_not_overwrite(self):
        packet = self.stage()
        staged_bytes = Path(packet['path']).read_bytes()
        for path in (self.f.source, self.f.parquet, self.f.last):
            original = path.read_bytes()
            path.write_bytes(original+b'changed')
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                self.stage()
            path.write_bytes(original)
        self.assertEqual(Path(packet['path']).read_bytes(), staged_bytes)

    def test_reentry_revalidates_ack_before_market_bytes(self):
        self.stage()
        with closing(sqlite3.connect(self.f.queue_db)) as connection, connection:
            connection.execute('UPDATE control SET value=?', ('0'*64,))
        self.assert_no_market_read(self.stage)

    def test_partial_stage_is_retained_without_overwrite(self):
        audit_hash = file_hash(self.f.audit_path)
        folder = self.f.root/'data/runner/nt-import'/PLAN_ID/self.f.day/audit_hash
        folder.mkdir(parents=True)
        path = folder/'NQ DEC26.Last.txt'
        path.write_bytes(b'partial sentinel')
        with self.assertRaisesRegex(ValueError, 'Partial staging'):
            self.stage()
        self.assertEqual(path.read_bytes(), b'partial sentinel')

    def test_source_audit_and_telemetry_corruption_fail(self):
        for path in (self.f.source, self.f.parquet, self.f.last, self.f.audit_path, self.f.telemetry_path):
            original = path.read_bytes()
            path.write_bytes(original+b'corruption')
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                self.stage()
            path.write_bytes(original)

    def test_ack_false_wrong_run_and_wrong_hash_fail_before_market_read(self):
        original = self.f.intake.load()['entries'][self.f.day]['quality_ack']
        for changed in (dict(ack=False), dict(run_id='wrong-date'), dict(telemetry_sha256='0'*64)):
            self.alter_entry(quality_ack={**original, **changed})
            self.assert_no_market_read(self.stage)
        self.alter_entry(quality_ack=original)

    def test_telemetry_audit_mismatch_even_with_matching_ack_hash_fails(self):
        telemetry = json.loads(self.f.telemetry_path.read_text())
        telemetry['params']['quality']['rth_ticks'] = 999
        atomic(self.f.telemetry_path, telemetry)
        digest = file_hash(self.f.telemetry_path)
        self.alter_entry(quality_ack=dict(ack=True, run_id='bollinger-future-data-'+self.f.day,
                                          telemetry_sha256=digest))
        with closing(sqlite3.connect(self.f.queue_db)) as connection, connection:
            connection.execute('UPDATE control SET value=?', (digest,))
        self.assert_no_market_read(self.stage)

    def test_missing_queue_does_not_create_production_queue(self):
        self.f.queue_db.unlink()
        self.assert_no_market_read(self.stage)
        self.assertFalse(self.f.queue_db.exists())

    def test_invalid_records_or_missing_minutes_fail_after_rebinding_hashes(self):
        original = self.f.last.read_bytes()
        variants = [original.replace(b';20000.25;1', b';20000.10;1', 1),
                    original.replace(b';20000.25;1', b';NaN;1', 1),
                    original.replace(b';20000.25;1', b';20000.25;0', 1),
                    original.replace(b';20000.25;1', b';20000.25;9223372036854775808', 1),
                    original.replace(self.f.expected_rth_bytes.splitlines(keepends=True)[100], b'', 1)]
        for number, raw in enumerate(variants):
            with self.subTest(variant=number), tempfile.TemporaryDirectory() as folder:
                f = make_fixture(folder)
                f.last.write_bytes(raw)
                refresh_fixture(f)
                with self.assertRaises(ValueError):
                    stage_import(f.intake, f.day, f.now)

    def test_equal_100ns_timestamps_preserved_but_reverse_order_rejected(self):
        original = self.f.last.read_bytes()
        first = self.f.expected_rth_bytes.splitlines(keepends=True)[0]
        self.f.last.write_bytes(original.replace(first, first+first, 1))
        self.f.rth_ticks = 391
        refresh_fixture(self.f)
        packet = self.stage()
        self.assertEqual(packet['rows'], 391)
        self.assertEqual(Path(packet['path']).read_bytes(), first+self.f.expected_rth_bytes)
        with tempfile.TemporaryDirectory() as folder:
            f = make_fixture(folder)
            rows = f.last.read_bytes().splitlines(keepends=True)
            rows[3], rows[4] = rows[4], rows[3]
            f.last.write_bytes(b''.join(rows))
            refresh_fixture(f)
            with self.assertRaisesRegex(ValueError, 'unordered'):
                stage_import(f.intake, f.day, f.now)

    def test_frozen_plan_or_outside_artifact_binding_fails_before_market_read(self):
        original = self.f.intake.planpath.read_bytes()
        self.f.intake.planpath.write_bytes(original+b' ')
        self.assert_no_market_read(self.stage)
        self.f.intake.planpath.write_bytes(original)
        self.alter_entry(audit_path=str(self.f.root/'outside-quality.json'))
        self.assert_no_market_read(self.stage)

    def test_staged_content_or_manifest_tampering_is_not_overwritten(self):
        packet = self.stage()
        staged = Path(packet['path'])
        staged.write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            self.stage()
        self.assertEqual(staged.read_bytes(), b'tampered')


if __name__ == '__main__':
    unittest.main()
