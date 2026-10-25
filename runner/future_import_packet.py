"""Stage one closed, quality-acknowledged frozen session; never call NinjaTrader.

The manifest binds the full collected sources and the verbatim RTH subset. It is
evidence of local input integrity, not native cache parity or strategy validity.
Completed staging is reentrant, but every call rechecks its original inputs and
ACK. A partial directory is deliberately retained and must not be overwritten.
"""
import calendar
import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing as close_connection
from datetime import datetime, time, timezone
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

from .core import ProcessLock, canonical, file_hash


PLAN_ID = 'bollinger-prospective-20261026-1106'
FROZEN_PLAN_SHA256 = '25a1f2e7e137b797f36a3424779f6aa0bfeb2ccc16c9ae8d37f85fb38cd6cc00'
COHORT = ('2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29',
          '2026-10-30', '2026-11-02', '2026-11-03', '2026-11-04',
          '2026-11-05', '2026-11-06')
_HASH = re.compile(r'[0-9a-f]{64}')
_LINE = re.compile(rb'([0-9]{8} [0-9]{6}) ([0-9]{7});([0-9]+(?:\.[0-9]+)?);([1-9][0-9]*)(?:\r?\n)?')
_NS = 10**9
_MINUTE_NS = 60 * _NS


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _sha(value, label):
    _require(isinstance(value, str) and _HASH.fullmatch(value) is not None,
             'Invalid ' + label + ' SHA256')
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _read_json(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                       parse_constant=lambda token: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    _require(isinstance(value, dict), 'Expected JSON object')
    return value, hashlib.sha256(raw).hexdigest()


def _bound(path, expected, base):
    """Require the named file, and prevent symlink escapes from its allowed root."""
    actual, wanted, parent = Path(path).resolve(), Path(expected).resolve(), Path(base).resolve()
    _require(actual == wanted and actual.is_relative_to(parent), 'Artifact path outside its dated binding')
    return actual


def _session(day, now):
    _require(isinstance(day, str) and day in COHORT, 'Date outside frozen cohort')
    _require(isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None,
             'Timezone-aware current time required')
    date = datetime.strptime(day, '%Y-%m-%d').date()
    zone = ZoneInfo('America/New_York')
    opening = datetime.combine(date, time(9, 30), zone).astimezone(timezone.utc)
    closing = datetime.combine(date, time(16), zone).astimezone(timezone.utc)
    _require(now >= closing, 'Registered session has not closed')
    return opening, closing


def _metadata(intake, day, opening, closing):
    """Read only plan, state, audit and ACK metadata; no source market bytes."""
    root = Path(intake.root).resolve()
    plan_path = _bound(intake.planpath, root/'research/bollinger-prospective-plan.json', root)
    plan, plan_hash = _read_json(plan_path)
    _require(plan_hash == FROZEN_PLAN_SHA256 == intake.planhash,
             'Exact frozen plan hash required')
    _require(plan.get('id') == PLAN_ID and plan.get('evaluation_dates') == list(COHORT),
             'Frozen plan identity or cohort differs')
    state_path = _bound(intake.path, root/'data/runner/future-data-intake/state.json', root)
    state, _ = _read_json(state_path)
    _require(state.get('plan_sha256') == FROZEN_PLAN_SHA256, 'Intake plan binding differs')
    entries = state.get('entries')
    _require(isinstance(entries, dict) and set(entries) == set(COHORT), 'Intake cohort differs')
    entry = entries[day]
    _require(isinstance(entry, dict) and entry.get('status') == 'quality_passed', 'Quality not passed')
    _require(entry.get('timezone') == 'America/New_York' and entry.get('expected_rth_minutes') == 390,
             'Intake session specification differs')
    _require(entry.get('session_close_utc') == closing.isoformat(), 'Intake close differs from timezone calendar')
    quality = root/'data/runner/future-data-intake/quality'
    audit_path = _bound(entry.get('audit_path', ''), quality/(day+'.quality.json'), root)
    audit, audit_hash = _read_json(audit_path)
    _require(audit_hash == _sha(entry.get('audit_sha256'), 'audit'), 'Quality audit hash differs')
    source_hash = _sha(entry.get('source_sha256'), 'source')
    _require(audit.get('date') == day and audit.get('timezone') == 'America/New_York'
             and audit.get('source_sha256') == source_hash and audit.get('integrity_passed') is True,
             'Dated source integrity audit differs')
    _require(type(audit.get('rth_minutes')) is int and audit['rth_minutes'] == 390
             and audit.get('missing_minutes') == []
             and type(audit.get('rth_ticks')) is int and audit['rth_ticks'] >= 390,
             'Complete 390-minute audit required')
    _require(audit.get('performance_evaluated') is False and type(audit.get('native_runs')) is int
             and audit['native_runs'] == 0, 'Quality-only audit required')
    download_root = Path(intake.download_root).resolve()
    source = _bound(entry.get('expected_download_path', ''),
                    download_root/(day.replace('-', '')+'.nrd'), download_root)
    derived = audit.get('derived_hashes')
    _require(isinstance(derived, dict) and len(derived) == 2, 'Exactly Last and parquet hashes required')
    expected = { (quality/(day+'.Last.txt')).resolve(): 'last',
                 (quality/(day+'.parquet')).resolve(): 'parquet' }
    paths, hashes = {}, {}
    for name, digest in derived.items():
        path = Path(name).resolve()
        _require(path in expected and path.is_relative_to(root) and expected[path] not in paths,
                 'Unexpected derived artifact binding')
        label = expected[path]
        paths[label], hashes[label] = path, _sha(digest, label)
    _require(set(paths) == {'last', 'parquet'}, 'Missing derived source')
    ack = entry.get('quality_ack')
    run_id = 'bollinger-future-data-' + day
    _require(isinstance(ack, dict) and ack.get('ack') is True and ack.get('run_id') == run_id,
             'Expected quality dashboard ACK required')
    ack_hash = _sha(ack.get('telemetry_sha256'), 'quality ACK')
    telemetry_name = hashlib.sha256(run_id.encode('utf-8')).hexdigest()+'.json'
    telemetry_path = _bound(root/'data/runner/telemetry'/telemetry_name,
                            root/'data/runner/telemetry'/telemetry_name, root)
    telemetry, telemetry_hash = _read_json(telemetry_path)
    _require(telemetry_hash == ack_hash, 'Quality ACK telemetry hash differs')
    _require(telemetry.get('id') == run_id and telemetry.get('dataset') == day
             and telemetry.get('symbol') == 'NQ 12-26' and telemetry.get('status') == 'completed'
             and telemetry.get('phase') == 'data_quality' and telemetry.get('progress') == 100
             and telemetry.get('metrics') == {} and telemetry.get('equity') == [],
             'Quality telemetry identity differs')
    params = telemetry.get('params')
    _require(isinstance(params, dict) and params.get('quality') == audit
             and params.get('performance_evaluated') is False and type(params.get('native_runs')) is int
             and params['native_runs'] == 0, 'ACK does not bind this quality audit')
    queue_db = _bound(root/'data/runner/queue.sqlite3', root/'data/runner/queue.sqlite3', root)
    # Readonly direct SQLite access: Queue() would create/control production state.
    with close_connection(sqlite3.connect(queue_db.as_uri()+'?mode=ro', uri=True)) as connection:
        row = connection.execute('SELECT value FROM control WHERE key=?', ('ack:'+telemetry_name,)).fetchone()
    _require(row is not None and row[0] == ack_hash, 'Persisted dashboard ACK differs')
    return dict(root=root, source=source, last=paths['last'], parquet=paths['parquet'],
                source_hash=source_hash, last_hash=hashes['last'], parquet_hash=hashes['parquet'],
                audit_path=audit_path, audit_hash=audit_hash, telemetry_path=telemetry_path,
                ack_hash=ack_hash, ticks=audit['rth_ticks'], run_id=run_id)


def _check_file(path, expected):
    _require(file_hash(path) == expected, 'Source artifact changed: '+Path(path).name)


def _scan_last(path, opening, closing, expected_hash, expected_rows, output=None):
    start = calendar.timegm(opening.utctimetuple()) * _NS
    end = calendar.timegm(closing.utctimetuple()) * _NS
    full_hash, selected_hash = hashlib.sha256(), hashlib.sha256()
    minutes, rows, previous = set(), 0, None
    with Path(path).open('rb') as source:
        for line in source:
            full_hash.update(line)
            _require(len(line) <= 256, 'Oversized Last record')
            match = _LINE.fullmatch(line)
            _require(match is not None, 'Invalid ASCII Last record')
            stamp_text, fraction, price_text, size_text = match.groups()
            stamp = datetime.strptime(stamp_text.decode('ascii'), '%Y%m%d %H%M%S')
            ns = calendar.timegm(stamp.timetuple()) * _NS + int(fraction) * 100
            price = Fraction(price_text.decode('ascii'))
            _require(price > 0 and math.isfinite(float(price)) and (price*4).denominator == 1
                     and 0 < int(size_text) <= 2**63-1, 'Invalid Last price or size')
            _require(previous is None or ns >= previous, 'Last timestamps are unordered')
            previous = ns
            if start <= ns < end:
                minutes.add((ns-start)//_MINUTE_NS)
                rows += 1
                selected_hash.update(line)
                if output is not None:
                    output.write(line)
    _require(full_hash.hexdigest() == expected_hash, 'Full Last source hash differs')
    _require(minutes == set(range(390)), 'Last source does not cover every RTH minute')
    _require(rows == expected_rows, 'Staged RTH row count differs from quality audit')
    return selected_hash.hexdigest(), rows


def _stage(intake, day, now):
    # This happens before metadata inspection or any source file access.
    opening, closing = _session(day, now)
    meta = _metadata(intake, day, opening, closing)
    base = meta['root']/'data/runner/nt-import'
    directory = base/PLAN_ID/day/meta['audit_hash']
    _bound(directory, directory, meta['root'])
    with ProcessLock(base/PLAN_ID/day/'stage.lock'):
        _check_file(meta['source'], meta['source_hash'])
        _check_file(meta['parquet'], meta['parquet_hash'])
        staged = directory/'NQ DEC26.Last.txt'
        manifest_path = directory/'staging-manifest.json'
        existed = directory.exists()
        if existed:
            _require(staged.is_file() and manifest_path.is_file(), 'Partial staging exists; no overwrite')
            _bound(staged, staged, meta['root'])
            _bound(manifest_path, manifest_path, meta['root'])
            selected_hash, rows = _scan_last(meta['last'], opening, closing, meta['last_hash'], meta['ticks'])
            _check_file(staged, selected_hash)
        else:
            directory.mkdir(parents=True, exist_ok=False)
            with staged.open('xb') as output:
                selected_hash, rows = _scan_last(meta['last'], opening, closing, meta['last_hash'], meta['ticks'], output)
        # Detect source or ACK changes during staging as well as between invocations.
        _check_file(meta['source'], meta['source_hash'])
        _check_file(meta['parquet'], meta['parquet_hash'])
        _check_file(meta['last'], meta['last_hash'])
        _check_file(staged, selected_hash)
        _require(_metadata(intake, day, opening, closing) == meta, 'Metadata changed during staging')
        packet = dict(plan_id=PLAN_ID, plan_sha256=FROZEN_PLAN_SHA256, date=day,
                      path=str(staged), sha256=selected_hash, rows=rows,
                      source_sha256=meta['source_hash'], audit_sha256=meta['audit_hash'],
                      quality_ack_sha256=meta['ack_hash'], session_close_utc=closing.isoformat(),
                      source_last_sha256=meta['last_hash'], source_parquet_sha256=meta['parquet_hash'],
                      rth_open_utc=opening.isoformat(), rth_minutes=390,
                      staging_manifest_path=str(manifest_path))
        manifest = dict(version=1, packet=packet, provenance=dict(
            source_path=str(meta['source']), source_last_path=str(meta['last']),
            source_parquet_path=str(meta['parquet']), audit_path=str(meta['audit_path']),
            quality_telemetry_path=str(meta['telemetry_path']), quality_run_id=meta['run_id']),
            selection='UTC Last records in [09:30,16:00) America/New_York; original bytes and order retained',
            limitation='Local source and RTH staging integrity only; no native import/cache parity or strategy validation')
        if existed:
            old_manifest, manifest_hash = _read_json(manifest_path)
            _require(old_manifest == manifest, 'Existing staging manifest differs; no overwrite')
        else:
            raw = canonical(manifest).encode('utf-8')
            with manifest_path.open('xb') as output:
                output.write(raw)
            manifest_hash = hashlib.sha256(raw).hexdigest()
        return {**packet, 'staging_manifest_sha256': manifest_hash}


def stage_import(intake, day, now):
    """Return one immutable RTH import packet or raise ValueError.

    Requires a FutureIntake-compatible object and the exact frozen plan. The
    function stages local files only. It never initializes Queue, downloads,
    imports, schedules, evaluates performance, or changes the intake lifecycle.
    Reentry verifies original source hashes and persisted quality ACK anew.
    """
    try:
        return _stage(intake, day, now)
    except (OSError, sqlite3.Error, KeyError, TypeError, AttributeError,
            OverflowError, UnicodeError, AssertionError) as exc:
        raise ValueError('Invalid import staging evidence: '+str(exc)) from exc
