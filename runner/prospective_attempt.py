"""Durable local lifecycle with an explicitly injected store and transport.

The immutable reservation allows at most one local submission attempt per plan
id in the supplied store, preserving ambiguous outcomes. A crash before transport
may consume that attempt without executing a job. Without server idempotency this
does not guarantee exactly-once native execution.

There is no default store, transport, CLI, Bridge integration or campaign-gate
release. The caller supplies a fresh bound authorization callback implementing
its actual policy. This module verifies that evidence's binding and freshness;
it cannot infer native permission or validate a strategy from readiness flags.
Production wiring and post-run validation are separate, unimplemented concerns.
Instance checks bracket each transport call. They detect observed restarts but
are not atomic server-side proof that an id belongs to a particular instance;
production transport must separately establish the strength of that binding.
"""
import copy
import hashlib
import json
import os
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from .core import ProcessLock


class AttemptError(RuntimeError):
    pass


class DuplicateAttempt(AttemptError):
    pass


class AttemptTransport(ABC):
    """Explicit transport contract. No implementation is provided here."""

    @abstractmethod
    def current_instance(self):
        """Return a nonempty native instance identity string, or fail."""

    @abstractmethod
    def submit(self, request):
        """Return a submission receipt: {'id': 'b1', 'state': 'queued'}."""

    @abstractmethod
    def poll(self, native_id):
        """Return a document containing the same id and an explicit state."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def _digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _timestamp(value):
    if not isinstance(value, str):
        raise AttemptError('Timezone-aware timestamp required')
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise AttemptError('Timezone-aware timestamp required')
    return result


def _now(clock):
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AttemptError('Clock must return timezone-aware datetime')
    return value.astimezone(timezone.utc)


def _validate_packet(packet):
    required = {'plan_id', 'plan_sha256', 'request', 'source_sha256', 'dataset_sha256', 'instance_id'}
    if not isinstance(packet, dict) or set(packet) != required:
        raise AttemptError('Exact bound packet schema required')
    if not isinstance(packet['plan_id'], str) or re.fullmatch('[a-z0-9][a-z0-9_-]{0,127}', packet['plan_id']) is None:
        raise AttemptError('Invalid plan id')
    for name in ('plan_sha256', 'source_sha256', 'dataset_sha256'):
        if not _digest(packet[name]):
            raise AttemptError('Invalid ' + name)
    if not isinstance(packet['request'], dict) or not packet['request']:
        raise AttemptError('Nonempty fixed request required')
    if not isinstance(packet['instance_id'], str) or not packet['instance_id'].strip():
        raise AttemptError('Bound native instance identity required')
    try:
        _canonical(packet)
    except (TypeError, ValueError) as exc:
        raise AttemptError('Finite JSON packet required') from exc
    return copy.deepcopy(packet)


def packet_fingerprint(packet):
    packet = _validate_packet(packet)
    # A new instance may not create a second attempt for the same plan/request.
    return _hash({k: packet[k] for k in ('plan_id', 'plan_sha256', 'request',
                                       'source_sha256', 'dataset_sha256')})


def _fsync_directory(folder):
    # Windows has no portable directory fsync through Python. The files themselves
    # are always flushed and fsynced before transport invocation.
    if os.name != 'nt':
        descriptor = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _exclusive(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(_canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(path.parent)


def _replace(path, value):
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        _exclusive(temp, value)
        os.replace(temp, path)
        _fsync_directory(path.parent)
    finally:
        if temp.exists():
            temp.unlink()


def _read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise AttemptError('Duplicate record key')
            result[key] = value
        return result

    def invalid(value):
        raise AttemptError('Nonfinite record value')

    try:
        value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    except (OSError, TypeError, ValueError) as exc:
        raise AttemptError('Unreadable attempt evidence; no resubmission permitted') from exc
    if not isinstance(value, dict):
        raise AttemptError('Attempt record must be an object')
    return value


def _untrusted_observation(phase, document):
    """Retain ambiguous finite JSON as evidence without making it authoritative."""
    try:
        digest = _hash(document)
    except (TypeError, ValueError):
        return dict(phase=phase, document_preserved=False, reason='Non-JSON observation')
    return dict(phase=phase, document_preserved=True, document=copy.deepcopy(document),
                document_sha256=digest)


def _require_current_authorization(proof, now):
    try:
        age = (now - _timestamp(proof['checked_at_utc'])).total_seconds()
    except (TypeError, ValueError) as exc:
        raise AttemptError('Malformed authorization time') from exc
    if not 0 <= age <= 60:
        raise AttemptError('Authorization must be current, not future or stale')


class ProspectiveAttempt:
    """One immutable claim per plan id, and explicit single-observation follow-up.

    ``authorize(packet, fingerprint)`` must freshly return a bound authorization
    attestation. Its policy implementation is the caller's responsibility; merely
    constructing a proof or setting flags does not release any production gate.
    Every invocation of submit after the claim exists is rejected, including after
    a crash, malformed receipt, known native failure or transport uncertainty.
    """

    def __init__(self, folder, packet, transport, authorize, clock=None):
        self.folder = Path(folder).resolve()
        if not isinstance(transport, AttemptTransport):
            raise AttemptError('Explicit AttemptTransport implementation required')
        if not callable(authorize):
            raise AttemptError('Fresh bound authorization callback required')
        self.packet = _validate_packet(packet)
        self.fingerprint = packet_fingerprint(self.packet)
        self.transport, self.authorize = transport, authorize
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.folder.mkdir(parents=True, exist_ok=True)
        prefix = self.packet['plan_id']
        self.reservation_path = self.folder / (prefix + '.reservation.json')
        self.state_path = self.folder / (prefix + '.state.json')
        self.handle_path = self.folder / (prefix + '.handle.json')
        self.lock_path = self.folder / (prefix + '.lock')

    def _authorization(self):
        proof = self.authorize(copy.deepcopy(self.packet), self.fingerprint)
        fields = {'scope', 'approved', 'fingerprint', 'packet_sha256', 'checked_at_utc'}
        if not isinstance(proof, dict) or set(proof) != fields:
            raise AttemptError('Bound authorization evidence required')
        if (proof['scope'] != 'local_submission' or proof['approved'] is not True
                or proof['fingerprint'] != self.fingerprint or proof['packet_sha256'] != _hash(self.packet)):
            raise AttemptError('Authorization scope or packet binding mismatch')
        # Sample after the callback: it may itself perform slow policy checks
        # and legitimately timestamp evidence later than this method's entry.
        _require_current_authorization(proof, _now(self.clock))
        return copy.deepcopy(proof)

    def submit(self):
        with ProcessLock(self.lock_path):
            if self.reservation_path.exists() or self.state_path.exists() or self.handle_path.exists():
                raise DuplicateAttempt('Plan already claimed; never invoke submit again')
            if packet_fingerprint(self.packet) != self.fingerprint:
                raise AttemptError('Packet changed after construction')
            proof = self._authorization()
            if self.transport.current_instance() != self.packet['instance_id']:
                raise AttemptError('Pre-submission instance mismatch; no reservation created')
            now = _now(self.clock)
            reservation = dict(schema=1, scope='local_submission', token=uuid.uuid4().hex,
                               fingerprint=self.fingerprint, packet=copy.deepcopy(self.packet),
                               reserved_at_utc=now.isoformat(), authorization=proof,
                               local_submission_budget_consumed=1)
            # Exclusive immutable marker is authoritative even if the next state
            # write fails or the process dies before or during transport.
            _exclusive(self.reservation_path, reservation)
            state = dict(token=reservation['token'], fingerprint=self.fingerprint,
                         reservation_sha256=_hash(reservation), packet=copy.deepcopy(self.packet),
                         status='reserved', observer_status='not_started', native_id=None,
                         native_instance=self.packet['instance_id'], transport_attempt_intents=0,
                         observations=0, scope='local_submission')
            _replace(self.state_path, state)
            # Persist intent before entering the injected call. A crash here also
            # consumes the local budget: it can never be reset on absent receipt.
            state.update(status='submitting', transport_attempt_intents=1)
            _replace(self.state_path, state)
            request = copy.deepcopy(self.packet['request'])
            # Instance checks or durable writes may consume the proof's entire
            # lifetime. Recheck after those operations, immediately before the
            # call, while keeping an already-created reservation consumed.
            try:
                _require_current_authorization(proof, _now(self.clock))
            except AttemptError as exc:
                state.update(status='submission_not_invoked',
                             observer_status='authorization_not_current',
                             transport_not_invoked_reason='authorization_not_current_before_call',
                             error=str(exc))
                _replace(self.state_path, state)
                return copy.deepcopy(state)
            try:
                receipt = self.transport.submit(request)
            except Exception as exc:
                state.update(status='submission_unknown', observer_status='unresolved_handle',
                             error=type(exc).__name__)
                _replace(self.state_path, state)
                return copy.deepcopy(state)
            # A receipt alone is not enough: a server restart could have reused
            # its id between the preflight check and this response.
            try:
                receipt_instance = self.transport.current_instance()
            except Exception as exc:
                receipt_instance = None
                instance_error = 'Post-submission instance unavailable: ' + type(exc).__name__
            else:
                instance_error = 'Native instance changed or missing after submission'
            if receipt_instance != self.packet['instance_id']:
                state.update(status='submission_unknown', observer_status='unresolved_handle',
                             error=instance_error,
                             untrusted_observation=_untrusted_observation('submission_receipt', receipt))
                _replace(self.state_path, state)
                return copy.deepcopy(state)
            if (not isinstance(receipt, dict) or not isinstance(receipt.get('id'), str)
                    or re.fullmatch('b[1-9][0-9]*', receipt['id']) is None
                    or receipt.get('state') != 'queued'
                    or ('instance_id' in receipt and receipt['instance_id'] != self.packet['instance_id'])):
                state.update(status='submission_unknown', observer_status='unresolved_handle',
                             error='Invalid or missing native receipt identity')
            else:
                handle = dict(native_id=receipt['id'], native_instance=self.packet['instance_id'],
                              token=reservation['token'], fingerprint=self.fingerprint,
                              reservation_sha256=state['reservation_sha256'])
                _exclusive(self.handle_path, handle)
                state.update(status='running', observer_status='receipt_bound', native_id=receipt['id'],
                             handle_sha256=_hash(handle))
            _replace(self.state_path, state)
            return copy.deepcopy(state)

    def _load_bound(self, token, fingerprint):
        if packet_fingerprint(self.packet) != self.fingerprint:
            raise AttemptError('Packet changed after construction')
        reservation, state = _read(self.reservation_path), _read(self.state_path)
        if (not isinstance(token, str) or not token or fingerprint != self.fingerprint
                or reservation.get('fingerprint') != self.fingerprint
                or state.get('fingerprint') != self.fingerprint
                or reservation.get('packet') != self.packet or state.get('packet') != self.packet
                or reservation.get('token') != token or state.get('token') != token
                or state.get('reservation_sha256') != _hash(reservation)
                or reservation.get('scope') != 'local_submission' or state.get('scope') != 'local_submission'
                or state.get('native_instance') != self.packet['instance_id']):
            raise AttemptError('Token, fingerprint or immutable packet mismatch')
        if state.get('status') not in ('reserved', 'submitting', 'submission_not_invoked',
                                       'submission_unknown', 'running', 'terminal'):
            raise AttemptError('Unknown persisted state')
        if state['status'] == 'submission_not_invoked' and (
                state.get('native_id') is not None
                or state.get('transport_not_invoked_reason') != 'authorization_not_current_before_call'):
            raise AttemptError('No-invocation evidence is inconsistent')
        for key in ('observations', 'transport_attempt_intents'):
            if type(state.get(key)) is not int or state[key] < 0:
                raise AttemptError('Malformed persisted counter')
        if state['transport_attempt_intents'] > 1:
            raise AttemptError('Local submission budget exceeded')
        if state.get('native_id') is not None:
            handle = _read(self.handle_path)
            if (handle != dict(native_id=state['native_id'], native_instance=state['native_instance'],
                               token=token, fingerprint=self.fingerprint,
                               reservation_sha256=state['reservation_sha256'])
                    or state.get('handle_sha256') != _hash(handle)):
                raise AttemptError('Persisted native handle differs from immutable receipt binding')
        elif state['status'] in ('running', 'terminal'):
            raise AttemptError('Running or terminal state requires a verified native handle')
        if state['status'] == 'terminal':
            doc = state.get('terminal_document')
            if (not isinstance(doc, dict) or doc.get('id') != state['native_id']
                    or doc.get('state') not in ('done', 'error', 'timeout', 'cancelled')
                    or state.get('terminal_document_sha256') != _hash(doc)):
                raise AttemptError('Terminal state lacks intact explicit native terminal evidence')
        return state

    def observe(self, token, fingerprint):
        """One same-handle observation. Never submit, cancel, search or sleep."""
        with ProcessLock(self.lock_path):
            state = self._load_bound(token, fingerprint)
            if state['status'] in ('terminal', 'submission_not_invoked'):
                return copy.deepcopy(state)
            native_id = state.get('native_id')
            if not isinstance(native_id, str) or re.fullmatch('b[1-9][0-9]*', native_id) is None:
                state.update(observer_status='unresolved_handle', error='No verified native handle')
                _replace(self.state_path, state)
                return copy.deepcopy(state)
            state['observations'] += 1
            try:
                instance = self.transport.current_instance()
            except Exception as exc:
                state.update(observer_status='unavailable', error=type(exc).__name__)
                _replace(self.state_path, state)
                return copy.deepcopy(state)
            if instance != state['native_instance']:
                state.update(observer_status='unresolved_handle', error='Native instance changed or missing')
                _replace(self.state_path, state)
                return copy.deepcopy(state)
            try:
                document = self.transport.poll(native_id)
            except Exception as exc:
                state.update(observer_status='unavailable', error=type(exc).__name__)
                _replace(self.state_path, state)
                return copy.deepcopy(state)
            try:
                result_instance = self.transport.current_instance()
            except Exception as exc:
                state.update(observer_status='unavailable',
                             error='Post-observation instance unavailable: ' + type(exc).__name__,
                             untrusted_observation=_untrusted_observation('poll_document', document))
                _replace(self.state_path, state)
                return copy.deepcopy(state)
            if result_instance != state['native_instance']:
                state.update(observer_status='unresolved_handle',
                             error='Native instance changed or missing during observation',
                             untrusted_observation=_untrusted_observation('poll_document', document))
                _replace(self.state_path, state)
                return copy.deepcopy(state)
            if (not isinstance(document, dict) or document.get('id') != native_id
                    or document.get('state') not in ('queued', 'running', 'done', 'error', 'timeout', 'cancelled')
                    or ('instance_id' in document and document['instance_id'] != state['native_instance'])):
                state.update(observer_status='unresolved_handle', error='Unexpected result identity or state')
            else:
                state.pop('error', None)
                state.update(observer_status='observed', last_native_state=document['state'])
                if document['state'] in ('done', 'error', 'timeout', 'cancelled'):
                    # Terminal transport evidence is not a passing validation.
                    # The separate post-run contract must inspect this document.
                    try:
                        document_hash = _hash(document)
                    except (TypeError, ValueError):
                        state.update(observer_status='unresolved_handle', error='Malformed terminal document')
                    else:
                        state.update(status='terminal', terminal_document=copy.deepcopy(document),
                                     terminal_document_sha256=document_hash,
                                     validation_status='pending_post_run_contract')
            _replace(self.state_path, state)
            return copy.deepcopy(state)


# No CLI, default folder, transport implementation or automatic authorization.
