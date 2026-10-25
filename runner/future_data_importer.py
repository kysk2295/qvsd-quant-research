"""Finite, dated Last import. No arming, connection changes, backtests or loop.

The native importer has no job ID or idempotency key. A durable local date
reservation allows at most one POST; an uncertain response is never retried.
Path and bracketed engine observations provide limited correlation, not atomic
server identity. Native 'done' still requires independent cache/bar parity.
"""
import argparse
import copy
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .core import ROOT, ProcessLock, file_hash
from .future_data_intake import FutureIntake
from .future_import_packet import stage_import
from .prospective_attempt import _exclusive, _replace, _read, _hash


def utcnow():
    return datetime.now(timezone.utc)


class NativeImportError(RuntimeError):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NativeImportError('Import transport refuses redirects', {'http_status': code})


class NativeImportTransport:
    """Only the existing local importer and its read-only preflight endpoints."""
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def _call(self, method, path, body=None):
        allowed = {('GET', '/health'), ('GET', '/research/status'),
                   ('GET', '/research/import'), ('POST', '/research/import')}
        if (method, path) not in allowed:
            raise NativeImportError('Endpoint outside import scope')
        if method == 'POST':
            if not isinstance(body, dict) or set(body) != {'path', 'sha256'}:
                raise NativeImportError('Exact importer request required')
            target = Path(body['path']).resolve(strict=True)
            root = (ROOT/'data/runner/nt-import').resolve()
            if (not target.is_relative_to(root) or target.name != 'NQ DEC26.Last.txt'
                    or file_hash(target) != body['sha256']):
                raise NativeImportError('Importer path/hash outside prepared scope')
        elif body is not None:
            raise NativeImportError('GET body refused')
        request = urllib.request.Request('http://127.0.0.1:7891'+path,
            data=json.dumps(body).encode('utf-8') if body is not None else None,
            headers={'Content-Type': 'application/json'}, method=method)
        try:
            with self.opener.open(request, timeout=5) as response:
                raw = response.read(1_048_577)
        except urllib.error.HTTPError as exc:
            raw = exc.read(1_048_577).decode('utf-8', errors='replace')
            raise NativeImportError('Native request refused; no retry',
                                    {'http_status': exc.code, 'body': raw}) from exc
        if len(raw) > 1_048_576:
            raise NativeImportError('Oversize native import response')
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise NativeImportError('Non-JSON native response',
                                    {'body': raw.decode('utf-8', errors='replace')}) from exc
        if not isinstance(value, dict):
            raise NativeImportError('Object native response required', value)
        return value

    def health(self):
        return self._call('GET', '/health')

    def permission(self):
        return self._call('GET', '/research/status')

    def poll(self):
        return self._call('GET', '/research/import')

    def submit(self, packet):
        return self._call('POST', '/research/import',
                          {'path': packet['path'], 'sha256': packet['sha256']})


def instance(health):
    if not isinstance(health, dict) or health.get('ok') is not True:
        raise NativeImportError('Healthy native engine required')
    keys = ('pid', 'processStartUtc', 'startedAt', 'assemblyName', 'assemblyLocation')
    if type(health.get('pid')) is not int or health['pid'] <= 0:
        raise NativeImportError('Native process identity missing')
    if any(not isinstance(health.get(k), str) or not health[k] for k in keys[1:]):
        raise NativeImportError('Native generation identity missing')
    return {k: health[k] for k in keys}


def same_path(value, expected):
    if not isinstance(value, str) or not value:
        return False
    return Path(value).resolve() == Path(expected).resolve()


class FutureImporter:
    def __init__(self, intake, transport=None, clock=utcnow):
        self.intake, self.clock = intake, clock
        if transport is None and intake.root.resolve() != ROOT.resolve():
            raise ValueError('Nonproduction root requires an explicit synthetic transport')
        self.transport = transport if transport is not None else NativeImportTransport()
        self.folder = intake.folder/'imports'
        self.folder.mkdir(parents=True, exist_ok=True)

    def _paths(self, day):
        if day not in self.intake.plan['evaluation_dates']:
            raise ValueError('Only fixed prospective dates')
        return self.folder/(day+'.reservation.json'), self.folder/(day+'.state.json')

    def _payload(self, packet):
        now = self.clock()
        if (now.tzinfo is None or now.utcoffset() is None
                or now < datetime.fromisoformat(packet['session_close_utc'])):
            raise ValueError('Closed session required')
        target = Path(packet['path']).resolve(strict=True)
        root = (self.intake.root/'data/runner/nt-import').resolve()
        if not target.is_relative_to(root) or target.name != 'NQ DEC26.Last.txt':
            raise ValueError('Staging outside approved root/name')
        manifest = Path(packet['staging_manifest_path']).resolve(strict=True)
        if (not manifest.is_relative_to(target.parent)
                or file_hash(target) != packet['sha256']
                or file_hash(manifest) != packet['staging_manifest_sha256']):
            raise ValueError('Immutable staged payload changed')

    def _load(self, day):
        reservation_path, state_path = self._paths(day)
        reservation, state = _read(reservation_path), _read(state_path)
        if (state.get('reservation_sha256') != _hash(reservation)
                or state.get('packet') != reservation.get('packet')
                or state.get('engine') != reservation.get('engine')
                or state.get('date') != day or reservation.get('date') != day
                or state.get('submission_budget_consumed') != 1
                or type(state.get('post_attempt_intents')) is not int
                or state['post_attempt_intents'] not in (0, 1)
                or state.get('status') not in {'reserved', 'submitting', 'submission_unknown',
                    'not_invoked_no_retry', 'queued', 'running', 'native_error_no_retry',
                    'ambiguous_no_retry', 'native_done_pending_cache_parity'}):
            raise ValueError('Import attempt binding damaged')
        if state['status'] in {'queued', 'running', 'native_done_pending_cache_parity'}:
            receipt = state.get('receipt', {})
            if (state['post_attempt_intents'] != 1 or receipt.get('state') != 'queued'
                    or not same_path(receipt.get('path'), state['packet']['path'])
                    or state.get('receipt_sha256') != _hash(receipt)):
                raise ValueError('No intact import receipt')
        if state['status'] == 'native_done_pending_cache_parity':
            document = state.get('last_raw_observation', {})
            if (document.get('state') != 'done'
                    or not same_path(document.get('path'), state['packet']['path'])
                    or type(document.get('points')) is not int
                    or document['points'] != state['packet']['rows']
                    or document.get('instruments') not in [['NQ DEC26'], ['NQ 12-26']]
                    or state.get('observation_sha256') != _hash(document)):
                raise ValueError('Native completion evidence damaged')
        return state

    def submit(self, day):
        """One date, no retries. Never changes the intake quality state."""
        reservation_path, state_path = self._paths(day)
        with ProcessLock(self.folder/'import.lock'):
            if reservation_path.exists() or state_path.exists():
                raise NativeImportError('Date already reserved; never resubmit')
            # Global importer status is shared. Do not overwrite unresolved work.
            for existing in self.folder.glob('*.reservation.json'):
                other = existing.name.removesuffix('.reservation.json')
                if self._load(other)['status'] != 'native_done_pending_cache_parity':
                    raise NativeImportError('Prior import unresolved; no new date submission')
            packet = stage_import(self.intake, day, self.clock())
            health = self.transport.health()
            generation = instance(health)
            if (health.get('connections') != [] or health.get('anyLive') is not False
                    or health.get('anyNonSim') is not False):
                raise NativeImportError('No connected feeds; no automatic disconnection')
            permission = self.transport.permission()
            if not isinstance(permission, dict) or permission.get('armed') is not True:
                raise NativeImportError('Existing research permission required; no arming')
            previous = self.transport.poll()
            if (not isinstance(previous, dict) or previous.get('state') not in {'idle', 'done', 'error'}
                    or same_path(previous.get('path'), packet['path'])):
                raise NativeImportError('Importer unavailable or path already observed')
            if instance(self.transport.health()) != generation:
                raise NativeImportError('Native generation changed during preflight')
            reservation = dict(date=day, packet=packet, engine=generation,
                reserved_at_utc=self.clock().isoformat(), submission_budget_consumed=1,
                preflight=dict(health=health, permission=permission, import_status=previous))
            _exclusive(reservation_path, reservation)
            state = dict(date=day, packet=packet, engine=generation,
                reservation_sha256=_hash(reservation), submission_budget_consumed=1,
                status='reserved', post_attempt_intents=0, observations=0,
                native_cache_parity=False, strategy_validated=False)
            _exclusive(state_path, state)
            try:
                self._payload(packet)
                latest = self.transport.health()
                if (instance(latest) != generation or latest.get('connections') != []
                        or latest.get('anyLive') is not False or latest.get('anyNonSim') is not False):
                    raise NativeImportError('Engine or connection changed before POST')
            except Exception as exc:
                state.update(status='not_invoked_no_retry', error=type(exc).__name__+': '+str(exc))
                _replace(state_path, state)
                return state
            state.update(status='submitting', post_attempt_intents=1)
            _replace(state_path, state)  # flushed before external side effect
            try:
                receipt = self.transport.submit(copy.deepcopy(packet))
                state['raw_receipt'] = receipt
                if (instance(self.transport.health()) != generation
                        or not isinstance(receipt, dict) or receipt.get('state') != 'queued'
                        or not same_path(receipt.get('path'), packet['path'])):
                    raise NativeImportError('Receipt/path/engine correlation uncertain', receipt)
                state.update(status='queued', receipt=receipt, receipt_sha256=_hash(receipt))
            except Exception as exc:
                state.update(status='submission_unknown', error=type(exc).__name__+': '+str(exc),
                             error_response=getattr(exc, 'response', None))
            _replace(state_path, state)
            return copy.deepcopy(state)

    def observe(self, day):
        """One status read for the same acknowledged path. Never searches/retries."""
        with ProcessLock(self.folder/'import.lock'):
            state = self._load(day)
            if state['status'] not in {'queued', 'running'}:
                return copy.deepcopy(state)
            _, state_path = self._paths(day)
            state['observations'] += 1
            try:
                self._payload(state['packet'])
                if instance(self.transport.health()) != state['engine']:
                    raise NativeImportError('Engine changed before observation')
                document = self.transport.poll()
                state['last_raw_observation'] = document
                state['observation_sha256'] = _hash(document)
                if instance(self.transport.health()) != state['engine']:
                    raise NativeImportError('Engine changed during observation', document)
                self._payload(state['packet'])
                if (not isinstance(document, dict)
                        or not same_path(document.get('path'), state['packet']['path'])):
                    raise NativeImportError('Global status does not identify this import', document)
                native_state = document.get('state')
                if native_state in {'queued', 'running'}:
                    state['status'] = native_state
                elif native_state == 'error':
                    state['status'] = 'native_error_no_retry'
                elif native_state == 'done':
                    if (type(document.get('points')) is not int or document['points'] != state['packet']['rows']
                            or document.get('instruments') not in [['NQ DEC26'], ['NQ 12-26']]):
                        raise NativeImportError('Imported rows/instrument mismatch', document)
                    state.update(status='native_done_pending_cache_parity',
                                 native_done_observed_at_utc=self.clock().isoformat())
                else:
                    raise NativeImportError('Unexpected importer state', document)
            except Exception as exc:
                # This is not retryable automatically, including an engine or
                # network ambiguity. Persist the response instead of guessing.
                state.update(status='ambiguous_no_retry', error=type(exc).__name__+': '+str(exc),
                             error_response=getattr(exc, 'response', None))
            _replace(state_path, state)
            return copy.deepcopy(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('date')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--stage', action='store_true')
    action.add_argument('--submit', action='store_true')
    action.add_argument('--observe', action='store_true')
    args = parser.parse_args()
    intake = FutureIntake()
    if args.stage:
        result = stage_import(intake, args.date, utcnow())
    else:
        importer = FutureImporter(intake)
        result = importer.submit(args.date) if args.submit else importer.observe(args.date)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
