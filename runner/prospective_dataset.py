"""Load the ten existing prospective imports after the fixed decision time.

This adapter reads local evidence only. It does not submit/observe native jobs,
create a release flag, or infer cache parity from an importer's completion. Full
Last event order is retained, including ETH context needed around trade exits.
"""
import calendar
import hashlib
import math
from array import array
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import numpy as np

from .core import canonical, file_hash
from .future_data_importer import FutureImporter
from .future_import_packet import (COHORT, FROZEN_PLAN_SHA256, PLAN_ID, _LINE,
                                   _bound, _metadata, _read_json, _session, stage_import)
from .prospective_attempt import AttemptError


DECISION_AT = '2026-11-07T10:00:00+09:00'
_DECISION_UTC = datetime(2026, 11, 7, 1, tzinfo=timezone.utc)
_INT64_MAX = 2**63-1


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _decision(now):
    # Reject before touching even the intake object; the actual-clock dry run
    # cannot accidentally read a source or initialize a native transport.
    _require(isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None,
             'Timezone-aware decision clock required')
    _require(now >= _DECISION_UTC, 'Fixed prospective decision time has not arrived')


def _plan(intake):
    root = Path(intake.root).resolve()
    path = _bound(intake.planpath, root/'research/bollinger-prospective-plan.json', root)
    plan, digest = _read_json(path)
    _require(digest == FROZEN_PLAN_SHA256 == intake.planhash, 'Exact frozen plan hash required')
    _require(plan == intake.plan and plan.get('id') == PLAN_ID
             and plan.get('evaluation_dates') == list(COHORT) and plan.get('decision_at') == DECISION_AT,
             'Frozen plan, cohort or decision binding differs')
    _bound(intake.folder, root/'data/runner/future-data-intake', root)
    return root, plan


def _import_records(importer, root):
    """Use the existing receipt validator and bind its exact on-disk snapshots."""
    result = {}
    for day in COHORT:
        reservation_path, state_path = importer._paths(day)
        base = root/'data/runner/future-data-intake/imports'
        reservation_path = _bound(reservation_path, base/(day+'.reservation.json'), root)
        state_path = _bound(state_path, base/(day+'.state.json'), root)
        reservation, reservation_hash = _read_json(reservation_path)
        recorded_state, state_hash = _read_json(state_path)
        state = importer._load(day)
        _require(state == recorded_state, 'Import state changed while loading')
        _require(file_hash(reservation_path) == reservation_hash and file_hash(state_path) == state_hash,
                 'Import record changed while loading')
        _require(state.get('status') == 'native_done_pending_cache_parity',
                 'All ten dated imports must have bound native completion')
        packet = state.get('packet')
        _require(isinstance(packet, dict) and packet.get('date') == day
                 and packet.get('plan_id') == PLAN_ID and packet.get('plan_sha256') == FROZEN_PLAN_SHA256,
                 'Import packet is not bound to this frozen date')
        result[day] = dict(state=state, reservation=reservation,
            reservation_path=str(reservation_path), reservation_file_sha256=reservation_hash,
            state_path=str(state_path), state_file_sha256=state_hash)
    return result


def _load_last(path, expected_hash):
    """Read exact integer 100ns clocks without sorting, merging or RTH clipping."""
    stamps, prices, volumes = array('q'), array('d'), array('q')
    digest, previous = hashlib.sha256(), None
    _require(file_hash(path) == expected_hash, 'Original Last source changed before array loading')
    with Path(path).open('rb') as stream:
        for line in stream:
            digest.update(line)
            _require(len(line) <= 256, 'Oversized Last record')
            match = _LINE.fullmatch(line)
            _require(match is not None, 'Invalid ASCII Last record')
            stamp_text, fraction, price_text, volume_text = match.groups()
            stamp = datetime.strptime(stamp_text.decode('ascii'), '%Y%m%d %H%M%S')
            ns = calendar.timegm(stamp.timetuple())*10**9 + int(fraction)*100
            exact_price, size = Fraction(price_text.decode('ascii')), int(volume_text)
            price = float(exact_price)
            _require(0 <= ns <= _INT64_MAX and (previous is None or ns >= previous),
                     'Ordered nonnegative int64 Last clocks required')
            _require(exact_price > 0 and math.isfinite(price) and (exact_price*4).denominator == 1
                     and 0 < size <= _INT64_MAX, 'Finite NQ price and positive int64 volume required')
            stamps.append(ns)
            prices.append(price)
            volumes.append(size)
            previous = ns
    _require(len(stamps) > 0 and digest.hexdigest() == expected_hash,
             'Empty or changed original Last source')
    _require(file_hash(path) == expected_hash, 'Original Last source changed after array loading')
    arrays = dict(timestamps_ns=np.frombuffer(stamps, dtype=np.int64),
                  prices=np.frombuffer(prices, dtype=np.float64),
                  volumes=np.frombuffer(volumes, dtype=np.int64))
    for value in arrays.values():
        value.setflags(write=False)
    return arrays


def _load_dataset(intake, now):
    _decision(now)
    root, plan = _plan(intake)
    imports = _bound(Path(intake.folder)/'imports',
                     root/'data/runner/future-data-intake/imports', root)
    _require(imports.is_dir(), 'Existing import evidence directory required')
    # The existing validator needs no transport. An inert explicit object avoids
    # constructing NativeImportTransport; _load is the only importer method used.
    importer = FutureImporter(intake, transport=object(), clock=lambda: now)
    records = _import_records(importer, root)
    metadata = {}
    files = {str(Path(intake.planpath).resolve()):FROZEN_PLAN_SHA256,
             str(Path(intake.path).resolve()):file_hash(intake.path)}
    def bind(path, digest):
        name = str(Path(path).resolve())
        _require(name not in files or files[name] == digest, 'Conflicting dataset file binding')
        files[name] = digest
    for day in COHORT:
        opening, closing = _session(day, now)
        meta = _metadata(intake, day, opening, closing)
        packet = records[day]['state']['packet']
        expected_directory = root/'data/runner/nt-import'/PLAN_ID/day/meta['audit_hash']
        staged = _bound(packet.get('path', ''), expected_directory/'NQ DEC26.Last.txt', root)
        manifest = _bound(packet.get('staging_manifest_path', ''), expected_directory/'staging-manifest.json', root)
        _require(staged.is_file() and manifest.is_file(), 'Existing completed staging required; loader will not rebuild it')
        metadata[day] = meta
        record = records[day]
        for path, digest in ((meta['source'], meta['source_hash']),
                             (meta['parquet'], meta['parquet_hash']),
                             (meta['last'], meta['last_hash']),
                             (meta['audit_path'], meta['audit_hash']),
                             (meta['telemetry_path'], meta['ack_hash']),
                             (staged, packet['sha256']),
                             (manifest, packet['staging_manifest_sha256']),
                             (record['reservation_path'], record['reservation_file_sha256']),
                             (record['state_path'], record['state_file_sha256'])):
            bind(path, digest)
    # All ten completion records and quality ACKs are checked before any source
    # bytes. Reentrant stage_import verifies the already-existing artifacts.
    last_by_date, provenance = {}, []
    for day in COHORT:
        record, meta = records[day], metadata[day]
        packet = stage_import(intake, day, now)
        _require(packet == record['state']['packet'], 'Current staging differs from imported packet')
        last_by_date[day] = _load_last(meta['last'], packet['source_last_sha256'])
        provenance.append(dict(date=day, packet=packet,
            reservation_path=record['reservation_path'],
            reservation_file_sha256=record['reservation_file_sha256'],
            state_path=record['state_path'], state_file_sha256=record['state_file_sha256'],
            receipt_sha256=record['state']['receipt_sha256'],
            observation_sha256=record['state']['observation_sha256'],
            engine=record['state']['engine'],
            import_status=record['state']['status'], full_last_rows=len(last_by_date[day]['prices'])))
    # Recheck all dates together after loading; a changed early date cannot be
    # hidden by the later dates' successful checks. This is not an atomic FS snapshot.
    for path, expected in files.items():
        _require(file_hash(path) == expected, 'Dataset source or evidence changed during load')
    for day in COHORT:
        meta = metadata[day]
        opening, closing = _session(day, now)
        _require(_metadata(intake, day, opening, closing) == meta, 'Dataset quality evidence changed during load')
    _require(_import_records(importer, root) == records, 'Import completion evidence changed during load')
    _require(_plan(intake) == (root, plan), 'Frozen plan changed during dataset loading')
    dataset = dict(version=1, plan_id=PLAN_ID, plan_sha256=FROZEN_PLAN_SHA256,
        decision_at=DECISION_AT, evaluation_dates=list(COHORT), imports=provenance, files=files,
        array_source='Full original hash-bound Last text; integer 100ns timestamps and equal-time input order retained',
        native_cache_parity=False, strategy_validated=False,
        limitation='Completed native imports and local source integrity only. BAR, clock, ledger and marked-path reconciliation remain post-run requirements; no atomic filesystem snapshot or complete exchange-tape claim.')
    return dict(dataset=dataset,
        dataset_sha256=hashlib.sha256(canonical(dataset).encode('utf-8')).hexdigest(),
        last_by_date=last_by_date)


def load_imported_dataset(intake, now):
    """Return JSON provenance/digest plus full Last numpy arrays, or ValueError.

    Requires the exact frozen plan, its fixed decision time, all ten completed
    existing imports, unchanged sources and their actual persisted quality ACKs.
    There is no transport or new readiness flag, and no performance calculation.
    """
    try:
        return _load_dataset(intake, now)
    except (AttemptError, OSError, KeyError, TypeError, AttributeError, OverflowError,
            UnicodeError, AssertionError) as exc:
        raise ValueError('Invalid prospective dataset evidence: '+str(exc)) from exc
