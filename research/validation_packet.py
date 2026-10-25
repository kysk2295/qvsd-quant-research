"""Submission-free prospective evidence draft. Never imports a native adapter.

Raw source and derived files are read only as byte streams for SHA256. Their
prices, signals, executions and returns are neither parsed nor calculated.
"""
import json
import os
import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from runner.core import ROOT, atomic, file_hash

READINESS_PLAN = 'research/nq-goal-validation-readiness-plan.json'
READINESS_HASH = '031380bef9c255ce1cb887da96e53263245fd496f924c762a0c27db6133b85f7'
DRAFT = 'research/validation-packet-draft.json'
EXECUTION = 'research/validation-packet-execution.json'
PLAN = 'research/bollinger-prospective-plan.json'
INTAKE = 'data/runner/future-data-intake/state.json'
OPERATIONAL = ('no_outcome_inspection', 'signal_parity', 'clock_parity',
               'ledger_parity', 'native_execution_path')
ET = ZoneInfo('America/New_York')


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError(name + ': object required')
    return value


def _dates(value, name):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(name + ': date list required')
    if len(value) != len(set(value)) or value != sorted(value):
        raise ValueError(name + ': distinct ordered dates required')
    for v in value:
        if date.fromisoformat(v).isoformat() != v:
            raise ValueError(name + ': ISO calendar date required')
    return value


def _instant(value):
    if not isinstance(value, str):
        raise ValueError('Timezone-aware ISO timestamp required')
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Timezone-aware ISO timestamp required')
    return result


def _digest(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('SHA256 hex digest required')
    return value


def _integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + ': nonnegative integer required')
    return value


def session_bounds(day):
    """Calendar conversion only; no price data or exchange-calendar inference."""
    d = date.fromisoformat(day)
    return (datetime.combine(d, time(9, 30), ET).astimezone(timezone.utc),
            datetime.combine(d, time(16), ET).astimezone(timezone.utc))


def inspect_evidence(bundle, now):
    """Pure checker. A supplied evidence assertion is not native authorization.

    ``actual_*`` hashes must come from load_metadata, or explicit synthetic
    fixtures. This function itself performs no I/O and accepts no price arrays.
    """
    available, unmet, per_date = [], [], []

    def check(code, passed, detail=None):
        item = dict(code=code)
        if detail is not None:
            item['detail'] = detail
        (available if passed else unmet).append(item)

    try:
        _object(bundle, 'bundle')
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('Timezone-aware current time required')
        errors = bundle.get('loader_errors', [])
        if not isinstance(errors, list) or not all(isinstance(x, str) for x in errors):
            raise ValueError('loader_errors must be strings')
        for error in errors:
            check('metadata_load', False, error)
        plan = _object(bundle['plan'], 'plan')
        digest = _digest(bundle['plan_sha256'])
        control = _object(bundle['control'], 'control')
        roles = _object(bundle['data_roles'], 'data_roles')
        campaign = _object(bundle['campaign_registry'], 'campaign_registry')
        dates = _dates(plan['evaluation_dates'], 'evaluation_dates')
        if len(dates) != 10:
            raise ValueError('Exactly ten frozen evaluation dates required')
        check('plan_binding', _digest(control['prospective_plan_sha256']) == digest)
        check('campaign_registry_binding',
              _digest(bundle['campaign_registry_sha256']) == _digest(plan['campaign_registry_sha256']))
        check('rule_hash', _digest(bundle['actual_rule_sha256']) == _digest(plan['source_code_sha256']))
        check('manifest_hash', _digest(bundle['actual_manifest_sha256']) == _digest(plan['source_manifest_sha256']))
        check('decision_time', now >= _instant(plan['decision_at']), plan['decision_at'])
        budgets = _object(plan['search_budget'], 'search_budget')
        check('frozen_budget_preserved',
              _integer(control['active_native_diagnostic_budget'], 'native diagnostic budget') == 0
              and _integer(control['additional_observed_date_performance_runs'], 'old-date runs') == 0
              and _integer(control['new_historical_candidate_budget'], 'new candidate budget') == 0
              and _integer(control['future_reserved_native_attempts'], 'future attempts') == 1
              and _integer(budgets['active_native_attempts'], 'active attempts') == 0
              and _integer(budgets['reserved_native_attempts'], 'reserved attempts') == 1
              and control['native_submission_mode'] == 'frozen_pending_prospective_release')
        protected = _object(bundle['protected_hashes'], 'protected_hashes')
        if not protected:
            raise ValueError('Protected hash evidence required')
        for path, evidence in protected.items():
            _object(evidence, 'protected hash evidence')
            check('protected_hash:' + path,
                  evidence.get('actual') == _digest(evidence['expected']))
        reserved = _dates(roles['reserved_future_validation_dates'], 'reserved dates')
        observed = set(_dates(roles['known_observed_dates'], 'known observed dates'))
        observed.update(_dates(campaign['observed_dates'], 'campaign observed dates'))
        check('exact_reserved_dates', reserved == dates and roles['reservation_plan'] == PLAN)
        check('no_observed_date_overlap', not (set(dates) & observed), sorted(set(dates) & observed))
        for label, interval in (
                ('data_role', roles['conservative_development_interval']),
                ('campaign', campaign['conservative_no_oos_interval'])):
            _object(interval, label + ' development interval')
            first, last = interval['first'], interval['last']
            _dates([first] if first == last else [first, last], label + ' interval')
            overlap = [d for d in dates if first <= d <= last]
            check('outside_' + label + '_development_interval', not overlap, overlap)
        intake = bundle.get('intake')
        if intake is None:
            check('intake_metadata', False, 'No intake state evidence')
        else:
            _object(intake, 'intake')
            check('intake_plan_binding', _digest(intake['plan_sha256']) == digest)
            entries = _object(intake['entries'], 'intake entries')
            check('intake_exact_dates', sorted(entries) == dates)
            audits = _object(bundle['audits'], 'audits')
            for day in dates:
                start, close = session_bounds(day)
                before = len(unmet)
                entry = entries.get(day)
                row = dict(date=day, rth_open_utc=start.isoformat(),
                           rth_close_utc=close.isoformat(), expected_rth_minutes=390)
                if entry is None:
                    check(day + ':intake_entry', False)
                    row['evidence_complete'] = False
                    per_date.append(row)
                    continue
                _object(entry, day + ' intake entry')
                check(day + ':session_closed', now >= close)
                check(day + ':session_timezone', entry['timezone'] == 'America/New_York')
                check(day + ':session_close_dst', _instant(entry['session_close_utc']) == close)
                check(day + ':expected_minutes',
                      _integer(entry['expected_rth_minutes'], 'expected minutes') == 390)
                if now < close:
                    row.update(status='awaiting_session_close', evidence_complete=False,
                               market_artifact_bytes_accessed=False)
                    per_date.append(row)
                    continue
                check(day + ':quality_status', entry['status'] == 'quality_passed')
                record = audits.get(day)
                if record is None:
                    check(day + ':quality_audit', False, 'No hashed quality audit available')
                    row['evidence_complete'] = False
                    per_date.append(row)
                    continue
                _object(record, day + ' audit record')
                audit = _object(record['document'], day + ' quality document')
                check(day + ':audit_hash', record.get('actual_audit_sha256') == _digest(entry['audit_sha256']))
                check(day + ':audit_date', audit['date'] == day)
                check(day + ':integrity', audit.get('integrity_passed') is True)
                check(day + ':audit_timezone', audit.get('timezone') == 'America/New_York')
                check(day + ':rth_coverage',
                      _integer(audit['rth_minutes'], 'RTH minutes') == 390
                      and audit.get('missing_minutes') == [])
                check(day + ':no_performance_computation',
                      audit.get('performance_evaluated') is False
                      and _integer(audit['native_runs'], 'audit native runs') == 0)
                source_digest = _digest(audit['source_sha256'])
                check(day + ':source_hash', record.get('actual_source_sha256') == source_digest
                      and _digest(entry['source_sha256']) == source_digest)
                derived = _object(audit['derived_hashes'], 'derived hashes')
                actual = _object(record['actual_derived_hashes'], 'actual derived hashes')
                check(day + ':derived_pair', len(derived) == 2
                      and sorted(Path(p).name for p in derived) == [day + '.Last.txt', day + '.parquet'])
                for path, expected in derived.items():
                    check(day + ':derived_hash:' + Path(path).name,
                          actual.get(path) == _digest(expected))
                row['evidence_complete'] = len(unmet) == before
                row['source_sha256'] = source_digest
                per_date.append(row)
        # Absence of a file in a guessed location cannot establish that a native
        # attempt has not already been reserved. Real loader leaves this unknown.
        attempt = bundle.get('attempt_evidence')
        if attempt is None:
            check('attempt_registry_authority', False,
                  'No authoritative counted native-attempt registry implemented; absence is not proof')
        else:
            _object(attempt, 'attempt evidence')
            check('attempt_registry_authority', attempt.get('authority_verified') is True)
            check('attempt_plan_binding', _digest(attempt['plan_sha256']) == digest)
            check('attempt_evidence_hash',
                  attempt.get('actual_sha256') == _digest(attempt['evidence_sha256']))
            check('native_attempt_unreserved', attempt['status'] == 'unreserved'
                  and _integer(attempt['attempts'], 'attempts') == 0)
        candidate_paths = bundle.get('attempt_candidate_paths', [])
        if not isinstance(candidate_paths, list) or not all(isinstance(p, str) for p in candidate_paths):
            raise ValueError('Attempt candidate paths must be strings')
        check('no_unreviewed_attempt_artifacts', not candidate_paths, candidate_paths)
        operational = _object(bundle.get('operational_evidence', {}), 'operational evidence')
        for name in OPERATIONAL:
            item = operational.get(name)
            if item is None:
                check(name, False, 'No verified evidence; not inferred from file presence or data quality')
                continue
            _object(item, name + ' evidence')
            check(name, item.get('status') == 'passed'
                  and _digest(item['plan_sha256']) == digest
                  and _dates(item['dates'], name + ' dates') == dates
                  and item.get('actual_sha256') == _digest(item['evidence_sha256']))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        check('malformed_metadata', False, str(exc))
    return dict(kind='submission_free_evidence_draft', ready_for_native=False,
                draft_prerequisites_met=not unmet, available_evidence=available,
                unmet_reasons=unmet, dates=per_date, native_submissions=0,
                reserved_native_attempts_consumed=0, downloads=0,
                performance_calculations=0, strategy_validated=False,
                limits=['Hash agreement proves artifact identity, not market-data truth or execution parity.',
                        'This draft cannot release the frozen campaign gate or authorize a native run.',
                        'No authoritative attempt registry or signal/clock/ledger/native-path proof is inferred.',
                        'Real loader reads JSON metadata and hashes bytes; it never parses market prices.'])


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result

    def reject(value):
        raise ValueError('Nonfinite JSON constant: ' + value)

    value = json.loads(Path(path).read_text(encoding='utf-8'),
                       object_pairs_hook=unique, parse_constant=reject)
    return _object(value, str(path))


def _under(path, folder):
    path, folder = Path(path).resolve(), Path(folder).resolve()
    if not path.is_relative_to(folder):
        raise ValueError('Evidence path outside expected folder')
    return path


def load_metadata(root, readiness, download_root=None, now=None):
    """Use intake metadata without native APIs, decoding or queue writes.

    Existing registry JSON includes old performance fields; they are loaded but
    never used, output or recalculated by this checker. Future outcomes are not read.
    """
    root = Path(root).resolve()
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Timezone-aware current time required')
    download_root = (Path(download_root) if download_root else
                     Path.home() / 'Documents/NinjaTrader 8/db/replay/NQ 12-26').resolve()
    quality_folder = root / 'data/runner/future-data-intake/quality'
    errors, audits = [], {}

    def read(relative):
        try:
            return read_json(root / relative)
        except (OSError, ValueError) as exc:
            errors.append(str(relative) + ': ' + str(exc))
            return None

    def hashed(path):
        try:
            return file_hash(path)
        except OSError as exc:
            errors.append(str(path) + ': ' + type(exc).__name__)
            return None

    plan = read(PLAN)
    control = read('research/campaign-search-control.json')
    roles = read('research/data-role-registry.json')
    campaign = read('research/campaign-trial-registry.json')
    intake = read(INTAKE)
    if plan is not None and intake is not None:
        try:
            entries = _object(intake['entries'], 'intake entries')
            for day in _dates(plan['evaluation_dates'], 'evaluation dates'):
                # Do not read an audit or hash any market bytes before the fixed
                # RTH session closes, even if a file is already present.
                if now < session_bounds(day)[1]:
                    continue
                entry = entries.get(day)
                if not isinstance(entry, dict) or 'audit_path' not in entry:
                    continue
                try:
                    audit_path = _under(entry['audit_path'], quality_folder)
                    if audit_path != (quality_folder / (day + '.quality.json')).resolve():
                        raise ValueError('Unexpected dated audit path')
                    source_path = _under(entry['expected_download_path'], download_root)
                    if source_path != download_root / (day.replace('-', '') + '.nrd'):
                        raise ValueError('Unexpected dated source path')
                    audit = read_json(audit_path)
                    derived = _object(audit['derived_hashes'], 'derived hashes')
                    expected_paths = {(quality_folder / (day + suffix)).resolve()
                                      for suffix in ('.parquet', '.Last.txt')}
                    resolved = {_under(p, quality_folder) for p in derived}
                    if resolved != expected_paths:
                        raise ValueError('Expected exact dated Parquet and Last artifacts')
                    audits[day] = dict(document=audit, actual_audit_sha256=hashed(audit_path),
                                       actual_source_sha256=hashed(source_path),
                                       actual_derived_hashes={p: hashed(Path(p)) for p in derived})
                except (OSError, KeyError, TypeError, ValueError) as exc:
                    errors.append(day + ': ' + str(exc))
        except (KeyError, TypeError, ValueError) as exc:
            errors.append('intake structure: ' + str(exc))
    protected = {p: dict(expected=h, actual=hashed(root / p))
                 for p, h in readiness['protected_hashes'].items()}

    def plan_file_hash(key):
        if plan is None:
            return None
        try:
            relative = plan[key]
            if not isinstance(relative, str) or not relative:
                raise ValueError('Nonempty plan file path required')
            return hashed(_under(root / relative, root))
        except (KeyError, TypeError, ValueError) as exc:
            errors.append('plan ' + key + ': ' + str(exc))
            return None

    # Candidate inventory is deliberately not represented as a complete attempt
    # authority. No executor/registry exists yet in the frozen implementation.
    candidates = sorted(str(p.relative_to(root)) for p in
                        (root / 'research').glob('bollinger-prospective-attempt*.json'))
    attempt_folder = root / 'data/runner/bollinger-prospective'
    if attempt_folder.exists():
        candidates.extend(sorted(str(p.relative_to(root)) for p in attempt_folder.glob('*.json')))
    return dict(plan=plan, plan_sha256=hashed(root / PLAN), control=control,
                campaign_registry=campaign,
                campaign_registry_sha256=hashed(root / 'research/campaign-trial-registry.json'),
                data_roles=roles, intake=intake, audits=audits, protected_hashes=protected,
                actual_rule_sha256=plan_file_hash('source_code'),
                actual_manifest_sha256=plan_file_hash('source_manifest'),
                attempt_evidence=None, attempt_candidate_paths=candidates,
                operational_evidence={}, loader_errors=errors)


def verify_protected(root, readiness):
    for path, expected in readiness['protected_hashes'].items():
        if file_hash(Path(root) / path) != _digest(expected):
            raise ValueError('Protected artifact changed: ' + path)


def write_exclusive_json(path, value):
    """Never overwrite a draft or a reservation, including after an uncertain run."""
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, separators=(',', ':'), allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    # No --now, --release, --submit or --execute options. Real time only.
    if file_hash(ROOT / READINESS_PLAN) != READINESS_HASH:
        raise ValueError('Registered readiness plan changed')
    readiness = read_json(ROOT / READINESS_PLAN)
    verify_protected(ROOT, readiness)
    if readiness['limits']['packet_draft_runs'] != 1:
        raise ValueError('Exactly one registered draft run required')
    if (ROOT / DRAFT).exists():
        raise FileExistsError('Draft already exists; no repeat run')
    now = datetime.now(timezone.utc)
    execution = dict(id=readiness['id'], readiness_plan_sha256=READINESS_HASH,
                     packet_draft_runs=1, status='reserved_before_metadata_inspection',
                     reserved_at_utc=now.isoformat(), native_submissions=0,
                     reserved_native_attempts_consumed=0)
    write_exclusive_json(ROOT / EXECUTION, execution)
    try:
        draft = inspect_evidence(load_metadata(ROOT, readiness, now=now), now)
        verify_protected(ROOT, readiness)
        draft.update(id=readiness['id'], checked_at_utc=now.isoformat(),
                     readiness_plan=READINESS_PLAN, readiness_plan_sha256=READINESS_HASH,
                     execution_record=EXECUTION,
                     code_sha256=file_hash(ROOT / 'research/validation_packet.py'))
        write_exclusive_json(ROOT / DRAFT, draft)
        execution.update(status='completed', draft=DRAFT, draft_sha256=file_hash(ROOT / DRAFT))
        atomic(ROOT / EXECUTION, execution)
        print(json.dumps(dict(draft=DRAFT, ready_for_native=False,
                              draft_prerequisites_met=draft['draft_prerequisites_met'],
                              unmet_reasons=len(draft['unmet_reasons']), native_submissions=0)))
    except Exception as exc:
        execution.update(status='failed_no_automatic_retry', error=type(exc).__name__ + ': ' + str(exc))
        atomic(ROOT / EXECUTION, execution)
        raise


if __name__ == '__main__':
    main()
