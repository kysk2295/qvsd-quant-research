"""Fixed metadata, fake Queue and temporary claims only; no network or real store."""
import copy
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from runner.campaign_gate import (ATTEMPT_PATH, ensure_native_submission_allowed,
    ensure_prospective_submission_allowed, read_policy)
from runner.prospective_attempt import packet_fingerprint


NOW = datetime(2026, 11, 7, 1, 1, tzinfo=timezone.utc)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


class CampaignProspectiveGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        repo = Path(__file__).resolve().parents[1]
        for name in ('research/campaign-search-control.json', 'research/bollinger-prospective-plan.json',
                     'research/bollinger-return-manifest.json', 'research/campaign-trial-registry.json',
                     'research/data-role-registry.json',
                     'native/CodexBollingerClock.cs'):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / name, target)
        self.plan = json.loads((self.root / 'research/bollinger-prospective-plan.json').read_text())
        self.store = self.root / ATTEMPT_PATH
        self.store.mkdir(parents=True)
        self.db = self.root / 'data/runner/queue.sqlite3'
        with closing(sqlite3.connect(self.db)) as connection:
            connection.executescript("CREATE TABLE control(key TEXT PRIMARY KEY,value TEXT);"
                "CREATE TABLE jobs(id TEXT,status TEXT);"
                "INSERT INTO control VALUES('mode','running');"
                "INSERT INTO control VALUES('uncertain','');")
            connection.commit()
        engine = dict(pid=123, processStartUtc='2026-11-07T00:00:00Z', startedAt='2026-11-07T09:00:00',
                      assemblyName='synthetic', assemblyLocation='C:/synthetic/strategy.dll')
        self.packet = dict(plan_id=self.plan['id'],
            plan_sha256=hashlib.sha256((self.root / 'research/bollinger-prospective-plan.json').read_bytes()).hexdigest(),
            request=self.plan['request'], source_sha256=self.plan['source_code_sha256'],
            dataset_sha256='a' * 64, instance_id=digest(engine))
        evidence = {'synthetic_observation': 'no native calls', 'source_sha256': self.packet['source_sha256']}
        self.preflight = dict(packet=copy.deepcopy(self.packet), checked_at_utc=NOW.isoformat(),
            dataset_sha256=self.packet['dataset_sha256'], engine=engine, native_time_zone='Korea Standard Time',
            evidence_sha256=digest(evidence), evidence=evidence)
        fp = packet_fingerprint(self.packet)
        proof = dict(scope='local_submission', approved=True, fingerprint=fp,
                     packet_sha256=digest(self.packet), checked_at_utc=NOW.isoformat())
        self.reservation = dict(schema=1, scope='local_submission', token='b' * 32,
            fingerprint=fp, packet=copy.deepcopy(self.packet), reserved_at_utc=NOW.isoformat(),
            authorization=proof, local_submission_budget_consumed=1)
        self.state = dict(scope='local_submission', token=self.reservation['token'], fingerprint=fp,
            packet=copy.deepcopy(self.packet), reservation_sha256=digest(self.reservation),
            status='submitting', transport_attempt_intents=1, native_id=None,
            native_instance=self.packet['instance_id'])
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, suffix):
        return self.store / (self.packet['plan_id'] + suffix)

    def save(self):
        (self.store / 'preflight.json').write_text(json.dumps(self.preflight), encoding='utf-8')
        self.path('.reservation.json').write_text(json.dumps(self.reservation), encoding='utf-8')
        self.path('.state.json').write_text(json.dumps(self.state), encoding='utf-8')

    def sql(self, statement, params=()):
        with closing(sqlite3.connect(self.db)) as connection:
            rows = connection.execute(statement, params).fetchall()
            connection.commit()
            return rows

    def claim(self, now=NOW):
        return ensure_prospective_submission_allowed(self.root, self.packet, self.preflight, now)

    def test_valid_fixed_packet_consumes_one_exclusive_dispatch(self):
        result = self.claim()
        self.assertEqual(result['local_dispatch_budget_consumed'], 1)
        self.assertEqual(json.loads(self.path('.dispatch.json').read_text()), result)
        self.assertEqual(result['expires_at_utc'], (NOW + timedelta(seconds=60)).isoformat())
        with self.assertRaisesRegex(RuntimeError, 'already consumed'):
            self.claim()

    def test_concurrent_gate_calls_can_create_only_one_dispatch(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.claim) for _ in range(2)]
            results, failures = [], []
            for future in futures:
                try:
                    results.append(future.result(timeout=10))
                except RuntimeError as exc:
                    failures.append(str(exc))
        self.assertEqual(len(results), 1)
        self.assertEqual(len(failures), 1)
        self.assertIn('already consumed', failures[0])

    def test_generic_missing_malformed_frozen_and_label_changed_always_refused(self):
        control = self.root / 'research/campaign-search-control.json'
        for contents, message in [(None, 'missing'), ('{bad', 'malformed'),
                                  ('{"native_submission_mode":"frozen_pending_prospective_release"}', 'budget frozen'),
                                  ('{"native_submission_mode":"released_finite_packet"}', 'not released')]:
            if contents is None:
                control.unlink()
            else:
                control.write_text(contents)
            with self.subTest(contents=contents), patch('runner.campaign_gate.ROOT', self.root):
                with self.assertRaisesRegex(RuntimeError, message):
                    ensure_native_submission_allowed()

    def test_policy_decision_gate_precedes_queue_and_other_evidence(self):
        with patch('runner.campaign_gate.sqlite3.connect') as database:
            with self.assertRaisesRegex(RuntimeError, 'decision time'):
                read_policy(self.root, datetime(2026, 10, 25, tzinfo=timezone.utc))
            database.assert_not_called()
        self.assertFalse(self.path('.dispatch.json').exists())

    def test_policy_and_plan_byte_hash_changes_are_refused(self):
        for relative in ('research/campaign-search-control.json', 'research/bollinger-prospective-plan.json',
                         'research/bollinger-return-manifest.json', 'research/campaign-trial-registry.json',
                         'research/data-role-registry.json'):
            target = self.root / relative
            original = target.read_bytes()
            target.write_bytes(original + b' ')
            with self.subTest(path=relative), self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
                self.claim()
            target.write_bytes(original)

    def test_paused_stopped_uncertain_and_active_jobs_refused_without_changes(self):
        for mode, uncertain in [('paused', ''), ('stopped', ''), ('running', 'unknown previous submission')]:
            self.sql("UPDATE control SET value=? WHERE key='mode'", (mode,))
            self.sql("UPDATE control SET value=? WHERE key='uncertain'", (uncertain,))
            with self.subTest(mode=mode, uncertain=uncertain), self.assertRaises(RuntimeError):
                self.claim()
            self.assertEqual(self.sql("SELECT value FROM control WHERE key='mode'")[0][0], mode)
        self.sql("UPDATE control SET value='running' WHERE key='mode'")
        self.sql("UPDATE control SET value='' WHERE key='uncertain'")
        self.sql("INSERT INTO jobs VALUES('synthetic','running')")
        with self.assertRaisesRegex(RuntimeError, 'running jobs'):
            self.claim()

    def test_request_types_source_and_dataset_bindings_cannot_change(self):
        for field, value in [('request', {**self.packet['request'], 'includeTradeHistory': 1}),
                             ('source_sha256', 'c' * 64), ('dataset_sha256', 'c' * 64)]:
            altered = {**self.packet, field: value}
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                ensure_prospective_submission_allowed(self.root, altered, self.preflight, NOW)
        source = self.root / 'native/CodexBollingerClock.cs'
        source.write_bytes(source.read_bytes() + b' ')
        with self.assertRaisesRegex(RuntimeError, 'source frozen hash mismatch'):
            self.claim()

    def test_preflight_must_equal_actual_file_and_have_exact_schema(self):
        original = copy.deepcopy(self.preflight)
        self.preflight['native_time_zone'] = 'UTC'
        with self.assertRaisesRegex(RuntimeError, 'file or packet'):
            self.claim()
        self.preflight = original
        self.preflight['ready'] = True
        self.save()
        with self.assertRaisesRegex(RuntimeError, 'schema'):
            self.claim()

    def test_preflight_future_stale_missing_evidence_and_engine_rejected(self):
        original = copy.deepcopy(self.preflight)
        for changed in [{'checked_at_utc': (NOW - timedelta(seconds=61)).isoformat()},
                        {'checked_at_utc': (NOW + timedelta(seconds=1)).isoformat()},
                        {'evidence_sha256': 'c' * 64}, {'evidence': {}},
                        {'engine': {**original['engine'], 'pid': 124}}]:
            self.preflight = {**copy.deepcopy(original), **changed}
            self.save()
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                self.claim()

    def test_reservation_token_hash_fingerprint_status_and_typed_budget_required(self):
        original = copy.deepcopy(self.state)
        for changed in [{'token': 'c' * 32}, {'fingerprint': 'c' * 64},
                        {'reservation_sha256': 'c' * 64}, {'status': 'running'},
                        {'transport_attempt_intents': True}, {'native_id': 'b1'}]:
            self.state = {**copy.deepcopy(original), **changed}
            self.save()
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                self.claim()
        self.state = original
        self.reservation['local_submission_budget_consumed'] = True
        self.state['reservation_sha256'] = digest(self.reservation)
        self.save()
        with self.assertRaises(RuntimeError):
            self.claim()

    def test_authorization_proof_expiry_blocks_dispatch(self):
        self.reservation['authorization']['checked_at_utc'] = (NOW - timedelta(seconds=61)).isoformat()
        self.state['reservation_sha256'] = digest(self.reservation)
        self.save()
        with self.assertRaisesRegex(RuntimeError, 'Reservation authorization'):
            self.claim()
        self.assertFalse(self.path('.dispatch.json').exists())

    def test_existing_handle_partial_dispatch_and_duplicate_json_fail_closed(self):
        self.path('.handle.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'handle already exists'):
            self.claim()
        self.path('.handle.json').unlink()
        self.path('.dispatch.json').write_text('{partial')
        with self.assertRaisesRegex(RuntimeError, 'already consumed'):
            self.claim()
        self.path('.dispatch.json').unlink()
        (self.store / 'preflight.json').write_text('{"packet":{},"packet":{}}')
        with self.assertRaisesRegex(RuntimeError, 'malformed'):
            self.claim()

    def test_custom_attempt_location_does_not_substitute_for_canonical_store(self):
        other = self.root / 'other-store'
        shutil.copytree(self.store, other)
        for path in self.store.iterdir():
            path.unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing'):
            self.claim()
        self.assertFalse((other / (self.packet['plan_id'] + '.dispatch.json')).exists())


if __name__ == '__main__':
    unittest.main()
