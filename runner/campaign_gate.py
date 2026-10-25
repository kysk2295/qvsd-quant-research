"""Fixed prospective dispatch gate; generic native submissions remain refused.

This is a research-budget guard, not account/order authorization. The production
executor must obtain fresh source/data/native observations before calling it.
Only the fixed packet's canonical reservation store can consume one dispatch.
No native API is called here and the campaign policy file is never changed.
"""
import copy
from contextlib import closing
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3

from .core import ROOT
from .prospective_attempt import _exclusive, packet_fingerprint


FROZEN_PLAN_SHA256 = '25a1f2e7e137b797f36a3424779f6aa0bfeb2ccc16c9ae8d37f85fb38cd6cc00'
FROZEN_CONTROL_SHA256 = '58fd2a5c057d72fd8086cda75e62ca3d39ae2c4d503aaa9d9637cddb605ef777'
FROZEN_DATA_ROLE_SHA256 = '35f10c017dd6ee4985d262875f3af10b463aff31c59f45d7cb337750ae383299'
PLAN_PATH = Path('research/bollinger-prospective-plan.json')
CONTROL_PATH = Path('research/campaign-search-control.json')
ATTEMPT_PATH = Path('data/runner/prospective-execution')


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError('Finite JSON gate evidence required') from exc


def _hash(value):
    return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def _same(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_same(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_same(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _metadata(path, label, expected_sha=None):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result

    def invalid(value):
        raise ValueError('nonfinite JSON')

    try:
        if path.resolve() != path:
            raise RuntimeError(label + ' must use its canonical path')
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError(label + ' missing: ' + str(path)) from exc
    except OSError as exc:
        raise RuntimeError(label + ' unreadable') from exc
    digest = hashlib.sha256(raw).hexdigest()
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError(label + ' malformed') from exc
    if not isinstance(value, dict):
        raise RuntimeError(label + ' must be an object')
    if expected_sha is not None and digest != expected_sha:
        raise RuntimeError(label + ' frozen hash mismatch')
    return value, digest


def _now(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError('Timezone-aware current time required')
    return value.astimezone(timezone.utc)


def _stamp(value, label):
    try:
        if not isinstance(value, str):
            raise ValueError('string required')
        parsed = datetime.fromisoformat(value)
        return _now(parsed)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise RuntimeError(label + ' requires a timezone-aware ISO timestamp') from exc


def _fresh(value, now, label):
    stamp = _stamp(value, label)
    if not 0 <= (now - stamp).total_seconds() <= 60:
        raise RuntimeError(label + ' must be current: age 0..60 seconds')
    return stamp


def _verify_file(path, expected_sha, label):
    try:
        if path.resolve() != path:
            raise RuntimeError(label + ' requires its canonical path')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RuntimeError(label + ' unavailable') from exc
    if actual != expected_sha:
        raise RuntimeError(label + ' frozen hash mismatch')


def ensure_native_submission_allowed():
    """Always refuse the generic adapter POST; a label alone cannot release it."""
    policy, _ = _metadata(Path(ROOT).resolve() / CONTROL_PATH, 'Campaign control')
    if policy.get('native_submission_mode') != 'released_finite_packet':
        raise RuntimeError('Campaign native budget frozen: generic submissions are refused')
    raise RuntimeError('Prospective packet executor not released through generic POST; use the counted fixed-packet gate')


def read_policy(root, now):
    """Read immutable campaign policy and current Queue controls, without writes.

    Called before market-file/native access. A paused queue is reported as not
    running, rather than being labelled an explicit user stop. Nothing resumes
    it. The decision-time check precedes SQLite access.
    """
    root, now = Path(root).resolve(), _now(now)
    policy, _ = _metadata(root / CONTROL_PATH, 'Campaign control', FROZEN_CONTROL_SHA256)
    plan, _ = _metadata(root / PLAN_PATH, 'Prospective plan', FROZEN_PLAN_SHA256)
    if (policy.get('native_submission_mode') != 'frozen_pending_prospective_release'
            or policy.get('prospective_plan', '').replace('\\', '/') != PLAN_PATH.as_posix()
            or policy.get('prospective_plan_sha256') != FROZEN_PLAN_SHA256
            or type(policy.get('future_reserved_native_attempts')) is not int
            or policy['future_reserved_native_attempts'] != 1):
        raise RuntimeError('Frozen single prospective reservation policy required')
    if now < _stamp(plan.get('decision_at'), 'Frozen decision time'):
        raise RuntimeError('Prospective decision time has not arrived')
    # These are frozen metadata bindings, not price files or strategy outcomes.
    _verify_file(root / plan['source_manifest'], plan['source_manifest_sha256'], 'Source manifest')
    _verify_file(root / 'research/campaign-trial-registry.json', plan['campaign_registry_sha256'], 'Campaign registry')
    _verify_file(root / 'research/data-role-registry.json', FROZEN_DATA_ROLE_SHA256, 'Data-role registry')
    path = root / 'data/runner/queue.sqlite3'
    if not path.is_file() or path.resolve() != path:
        raise RuntimeError('Canonical Queue control database missing')
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
            connection.execute('BEGIN')
            rows = connection.execute("SELECT key,value FROM control WHERE key IN ('mode','uncertain')").fetchall()
            active = connection.execute("SELECT id FROM jobs WHERE status='running' ORDER BY id").fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError('Queue control database unreadable or malformed') from exc
    control = dict(rows)
    if len(rows) != 2 or set(control) != {'mode', 'uncertain'}:
        raise RuntimeError('Queue mode and uncertain controls required')
    if control['mode'] == 'stopped':
        raise RuntimeError('Explicit Queue stop is active')
    if control['mode'] != 'running':
        raise RuntimeError('Queue is not running: ' + str(control['mode']))
    if control['uncertain'] != '':
        raise RuntimeError('Queue has an unresolved submission')
    if active:
        raise RuntimeError('Queue has running jobs')
    return dict(plan=plan, policy=policy,
                queue=dict(mode='running', uncertain='', running_jobs=[]),
                checked_at_utc=now.isoformat())


def ensure_prospective_submission_allowed(root, packet, preflight, now):
    """Consume one fixed dispatch after validating the on-disk bound evidence.

    The returned marker is not permission for a later call or another request.
    Call immediately before the one POST. No automatic rollback/reset is provided,
    including when dispatch persistence or the subsequent POST has an unknown
    outcome. Source/data/native observation semantics belong to the real loader;
    this gate checks their durable snapshot and the precise execution binding.
    """
    root, now = Path(root).resolve(), _now(now)
    policy = read_policy(root, now)
    plan = policy['plan']
    fingerprint = packet_fingerprint(packet)
    if (packet['plan_id'] != plan['id'] or packet['plan_sha256'] != FROZEN_PLAN_SHA256
            or not _same(packet['request'], plan['request'])
            or packet['source_sha256'] != plan['source_code_sha256']):
        raise RuntimeError('Packet differs from the frozen plan/request/source')
    _verify_file(root / plan['source_code'], packet['source_sha256'], 'Frozen strategy source')
    store = root / ATTEMPT_PATH
    if not store.is_dir() or store.resolve() != store:
        raise RuntimeError('Canonical prospective attempt store required')
    fields = {'packet', 'checked_at_utc', 'dataset_sha256', 'engine', 'native_time_zone',
              'evidence_sha256', 'evidence'}
    if not isinstance(preflight, dict) or set(preflight) != fields:
        raise RuntimeError('Exact preflight snapshot schema required; no readiness flag')
    persisted, preflight_hash = _metadata(store / 'preflight.json', 'Preflight snapshot')
    if not _same(persisted, preflight) or not _same(preflight['packet'], packet):
        raise RuntimeError('Preflight file or packet snapshot binding mismatch')
    preflight_time = _fresh(preflight['checked_at_utc'], now, 'Preflight snapshot')
    engine = preflight['engine']
    engine_fields = {'pid', 'processStartUtc', 'startedAt', 'assemblyName', 'assemblyLocation'}
    if (not isinstance(engine, dict) or set(engine) != engine_fields
            or type(engine.get('pid')) is not int or engine['pid'] <= 0
            or any(not isinstance(engine[k], str) or not engine[k] for k in engine_fields - {'pid'})
            or _hash(engine) != packet['instance_id']):
        raise RuntimeError('Preflight engine instance binding mismatch')
    if (preflight['dataset_sha256'] != packet['dataset_sha256']
            or not isinstance(preflight['native_time_zone'], str) or not preflight['native_time_zone']
            or not isinstance(preflight['evidence'], dict) or not preflight['evidence']
            or preflight['evidence_sha256'] != _hash(preflight['evidence'])):
        raise RuntimeError('Preflight dataset/time-zone/evidence binding mismatch')
    prefix = packet['plan_id']
    reservation, _ = _metadata(store / (prefix + '.reservation.json'), 'Prospective reservation')
    state, _ = _metadata(store / (prefix + '.state.json'), 'Prospective state')
    token = reservation.get('token')
    reservation_hash = _hash(reservation)
    if (not isinstance(token, str) or re.fullmatch(r'[0-9a-f]{32}', token) is None
            or type(reservation.get('schema')) is not int or reservation['schema'] != 1
            or reservation.get('scope') != 'local_submission' or state.get('scope') != 'local_submission'
            or not _same(reservation.get('packet'), packet) or not _same(state.get('packet'), packet)
            or reservation.get('fingerprint') != fingerprint or state.get('fingerprint') != fingerprint
            or state.get('token') != token or state.get('reservation_sha256') != reservation_hash
            or state.get('native_instance') != packet['instance_id'] or state.get('native_id') is not None
            or type(reservation.get('local_submission_budget_consumed')) is not int
            or reservation['local_submission_budget_consumed'] != 1
            or state.get('status') != 'submitting' or type(state.get('transport_attempt_intents')) is not int
            or state['transport_attempt_intents'] != 1):
        raise RuntimeError('Durable submitting reservation/state binding required')
    proof = reservation.get('authorization')
    proof_fields = {'scope', 'approved', 'fingerprint', 'packet_sha256', 'checked_at_utc'}
    if (not isinstance(proof, dict) or set(proof) != proof_fields
            or proof['scope'] != 'local_submission' or proof['approved'] is not True
            or proof['fingerprint'] != fingerprint or proof['packet_sha256'] != _hash(packet)):
        raise RuntimeError('Reservation lacks the exact bound authorization proof')
    proof_time = _fresh(proof['checked_at_utc'], now, 'Reservation authorization')
    _fresh(reservation.get('reserved_at_utc'), now, 'Reservation timestamp')
    if (store / (prefix + '.handle.json')).exists():
        raise RuntimeError('Native handle already exists; dispatch cannot be repeated')
    dispatch = dict(schema=1, kind='prospective_native_dispatch', token=token,
                    fingerprint=fingerprint, packet_sha256=_hash(packet),
                    reservation_sha256=reservation_hash, preflight_sha256=preflight_hash,
                    evidence_sha256=preflight['evidence_sha256'], dataset_sha256=packet['dataset_sha256'],
                    engine_sha256=_hash(engine), checked_at_utc=now.isoformat(),
                    expires_at_utc=(min(preflight_time, proof_time) + timedelta(seconds=60)).isoformat(),
                    local_dispatch_budget_consumed=1)
    try:
        _exclusive(store / (prefix + '.dispatch.json'), dispatch)
    except FileExistsError as exc:
        raise RuntimeError('Prospective dispatch already consumed; no retry') from exc
    except OSError as exc:
        raise RuntimeError('Dispatch persistence uncertain; never reset or resubmit automatically') from exc
    return copy.deepcopy(dispatch)
