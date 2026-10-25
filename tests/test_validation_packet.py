"""Synthetic metadata and byte fixtures only; no market prices or native calls."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research.validation_packet import (OPERATIONAL, PLAN, INTAKE, inspect_evidence,
    load_metadata, read_json, session_bounds, write_exclusive_json)
from runner.core import file_hash

H = 'a' * 64
DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30',
         '2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06']
NOW = datetime(2026, 11, 7, 1, tzinfo=timezone.utc)


def fixture():
    plan = dict(evaluation_dates=DATES[:], decision_at='2026-11-07T10:00:00+09:00',
                source_code='native/Frozen.cs', source_code_sha256=H,
                source_manifest='research/manifest.json', source_manifest_sha256=H,
                campaign_registry_sha256=H,
                search_budget=dict(active_native_attempts=0, reserved_native_attempts=1))
    control = dict(prospective_plan_sha256=H, active_native_diagnostic_budget=0,
                   additional_observed_date_performance_runs=0, new_historical_candidate_budget=0,
                   future_reserved_native_attempts=1, native_submission_mode='frozen_pending_prospective_release')
    interval = dict(first='2026-08-14', last='2026-10-23')
    roles = dict(reserved_future_validation_dates=DATES[:], reservation_plan=PLAN,
                 known_observed_dates=['2026-08-14', '2026-10-23'],
                 conservative_development_interval=copy.deepcopy(interval))
    campaign = dict(observed_dates=['2026-08-14', '2026-10-23'],
                    conservative_no_oos_interval=copy.deepcopy(interval))
    entries, audits = {}, {}
    for day in DATES:
        entries[day] = dict(timezone='America/New_York', expected_rth_minutes=390,
                            session_close_utc=session_bounds(day)[1].isoformat(),
                            status='quality_passed', audit_sha256=H, source_sha256=H)
        derived = {day + '.parquet': H, day + '.Last.txt': H}
        audit = dict(date=day, timezone='America/New_York', rth_minutes=390,
                     missing_minutes=[], integrity_passed=True, source_sha256=H,
                     derived_hashes=derived, native_runs=0, performance_evaluated=False)
        audits[day] = dict(document=audit, actual_audit_sha256=H,
                           actual_source_sha256=H, actual_derived_hashes=derived.copy())
    proof = dict(status='passed', plan_sha256=H, dates=DATES[:], evidence_sha256=H, actual_sha256=H)
    return dict(plan=plan, plan_sha256=H, control=control, data_roles=roles,
                campaign_registry=campaign, campaign_registry_sha256=H,
                actual_rule_sha256=H, actual_manifest_sha256=H,
                protected_hashes={'frozen': dict(expected=H, actual=H)},
                intake=dict(plan_sha256=H, entries=entries), audits=audits,
                attempt_evidence=dict(authority_verified=True, plan_sha256=H, status='unreserved',
                                      attempts=0, evidence_sha256=H, actual_sha256=H),
                operational_evidence={k: copy.deepcopy(proof) for k in OPERATIONAL}, loader_errors=[])


class ValidationPacketTests(unittest.TestCase):
    def codes(self, bundle, now=NOW):
        result = inspect_evidence(bundle, now)
        self.assertFalse(result['ready_for_native'])
        self.assertEqual(result['reserved_native_attempts_consumed'], 0)
        return {r['code'] for r in result['unmet_reasons']}

    def test_all_synthetic_prerequisites_still_cannot_authorize_native(self):
        result = inspect_evidence(fixture(), NOW)
        self.assertEqual(result['unmet_reasons'], [])
        self.assertTrue(result['draft_prerequisites_met'])
        self.assertFalse(result['ready_for_native'])
        self.assertFalse(result['strategy_validated'])

    def test_input_unchanged(self):
        bundle = fixture(); original = copy.deepcopy(bundle)
        inspect_evidence(bundle, NOW)
        self.assertEqual(bundle, original)

    def test_decision_boundary_and_future_session_close(self):
        self.assertNotIn('decision_time', self.codes(fixture(), NOW))
        earlier = datetime(2026, 10, 26, 19, 59, tzinfo=timezone.utc)
        codes = self.codes(fixture(), earlier)
        self.assertIn('decision_time', codes)
        self.assertIn('2026-10-26:session_closed', codes)

    def test_dst_session_boundaries(self):
        self.assertEqual(session_bounds('2026-10-26')[0].hour, 13)
        self.assertEqual(session_bounds('2026-10-26')[1].hour, 20)
        self.assertEqual(session_bounds('2026-11-02')[0].hour, 14)
        self.assertEqual(session_bounds('2026-11-02')[1].hour, 21)
        b = fixture(); b['intake']['entries']['2026-11-02']['session_close_utc'] = '2026-11-02T20:00:00+00:00'
        self.assertIn('2026-11-02:session_close_dst', self.codes(b))

    def test_full_development_interval_even_if_date_not_enumerated(self):
        b = fixture(); b['data_roles']['conservative_development_interval']['last'] = '2026-10-27'
        self.assertIn('outside_data_role_development_interval', self.codes(b))
        b = fixture(); b['campaign_registry']['conservative_no_oos_interval']['last'] = '2026-10-27'
        self.assertIn('outside_campaign_development_interval', self.codes(b))

    def test_observed_date_and_exact_reservation(self):
        b = fixture(); b['data_roles']['known_observed_dates'].append('2026-10-26')
        b['data_roles']['reserved_future_validation_dates'].pop()
        codes = self.codes(b)
        self.assertIn('no_observed_date_overlap', codes)
        self.assertIn('exact_reserved_dates', codes)

    def test_rule_manifest_and_protected_hashes(self):
        for field, code in [('actual_rule_sha256', 'rule_hash'), ('actual_manifest_sha256', 'manifest_hash')]:
            b = fixture(); b[field] = 'b' * 64
            self.assertIn(code, self.codes(b))
        b = fixture(); b['protected_hashes']['frozen']['actual'] = None
        self.assertIn('protected_hash:frozen', self.codes(b))

    def test_existing_attempt_and_unknown_authority(self):
        b = fixture(); b['attempt_evidence'].update(status='reserved', attempts=1)
        self.assertIn('native_attempt_unreserved', self.codes(b))
        b['attempt_evidence'] = None
        self.assertIn('attempt_registry_authority', self.codes(b))

    def test_missing_operational_evidence_never_inferred_from_quality(self):
        b = fixture(); b['operational_evidence'] = {}
        self.assertTrue(set(OPERATIONAL) <= self.codes(b))

    def test_incomplete_session_and_changed_source_or_derived_hash(self):
        b = fixture(); day = DATES[0]
        b['audits'][day]['document']['rth_minutes'] = 389
        b['audits'][day]['actual_source_sha256'] = 'b' * 64
        b['audits'][day]['actual_derived_hashes'][day + '.Last.txt'] = 'c' * 64
        codes = self.codes(b)
        self.assertIn(day + ':rth_coverage', codes)
        self.assertIn(day + ':source_hash', codes)
        self.assertIn(day + ':derived_hash:' + day + '.Last.txt', codes)

    def test_missing_audit_and_outcome_inspection(self):
        b = fixture(); del b['audits'][DATES[0]]
        b['audits'][DATES[1]]['document']['performance_evaluated'] = True
        self.assertIn(DATES[0] + ':quality_audit', self.codes(b))
        self.assertIn(DATES[1] + ':no_performance_computation', self.codes(b))

    def test_malformed_fail_closed_and_boolean_not_integer(self):
        for mutate in (lambda b: b.update(plan=[]),
                       lambda b: b['plan'].update(evaluation_dates=DATES + [DATES[0]]),
                       lambda b: b['intake']['entries'][DATES[0]].update(expected_rth_minutes=True),
                       lambda b: b.update(plan_sha256='invalid')):
            b = fixture(); mutate(b)
            self.assertIn('malformed_metadata', self.codes(b))
        self.assertIn('malformed_metadata', self.codes(fixture(), datetime(2026, 11, 7)))

    def test_strict_json_and_exclusive_reservation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'record.json'
            write_exclusive_json(path, {'attempt': 1})
            with self.assertRaises(FileExistsError):
                write_exclusive_json(path, {'attempt': 2})
            self.assertEqual(read_json(path), {'attempt': 1})
            for content in ('{"x":1,"x":2}', '{"x":NaN}', '[]'):
                path.write_text(content, encoding='utf-8')
                with self.assertRaises(ValueError):
                    read_json(path)

    def test_loader_hashes_opaque_bytes_without_parsing_market_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); b = fixture(); plan = b['plan']
            def save(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding='utf-8')
            for relative, value in [(PLAN, plan), ('research/campaign-search-control.json', b['control']),
                    ('research/data-role-registry.json', b['data_roles']),
                    ('research/campaign-trial-registry.json', b['campaign_registry'])]:
                save(root / relative, value)
            for relative in (plan['source_code'], plan['source_manifest']):
                p = root / relative; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'opaque code fixture')
            download = root / 'downloads'; download.mkdir()
            quality = root / 'data/runner/future-data-intake/quality'; quality.mkdir(parents=True)
            day = DATES[0]; source = download / (day.replace('-', '') + '.nrd')
            source.write_bytes(b'\x00opaque source: no decoder can be called\xff')
            derived = {}
            for suffix in ('.parquet', '.Last.txt'):
                p = quality / (day + suffix); p.write_bytes(b'\x00not parseable market data\xff')
                derived[str(p)] = file_hash(p)
            audit_path = quality / (day + '.quality.json')
            audit = copy.deepcopy(b['audits'][day]['document'])
            audit.update(derived_hashes=derived, source_sha256=file_hash(source))
            save(audit_path, audit)
            entry = b['intake']['entries'][day]
            entry.update(audit_path=str(audit_path), audit_sha256=file_hash(audit_path),
                         expected_download_path=str(source), source_sha256=file_hash(source))
            save(root / INTAKE, b['intake'])
            readiness = dict(protected_hashes={PLAN: file_hash(root / PLAN)})
            loaded = load_metadata(root, readiness, download, now=NOW)
            self.assertEqual(loaded['audits'][day]['actual_source_sha256'], file_hash(source))
            self.assertEqual(loaded['audits'][day]['actual_derived_hashes'], derived)
            self.assertIsNone(loaded['attempt_evidence'])
            self.assertEqual(loaded['operational_evidence'], {})
            preclose = datetime(2026, 10, 26, 19, 59, tzinfo=timezone.utc)
            real_hash = file_hash
            def no_market_hash(path):
                self.assertFalse(Path(path).is_relative_to(download))
                self.assertFalse(Path(path).is_relative_to(quality))
                return real_hash(path)
            with patch('research.validation_packet.file_hash', side_effect=no_market_hash):
                early = load_metadata(root, readiness, download, now=preclose)
            self.assertEqual(early['audits'], {})
            # A metadata pointer cannot cause a read outside the dated quality folder.
            entry['audit_path'] = str(root / 'research/data-role-registry.json')
            save(root / INTAKE, b['intake'])
            rejected = load_metadata(root, readiness, download, now=NOW)
            self.assertNotIn(day, rejected['audits'])
            self.assertTrue(rejected['loader_errors'])
            del plan['source_code']
            save(root / PLAN, plan)
            malformed = load_metadata(root, readiness, download, now=NOW)
            self.assertIsNone(malformed['actual_rule_sha256'])
            self.assertTrue(any('plan source_code:' in item for item in malformed['loader_errors']))


if __name__ == '__main__':
    unittest.main()
