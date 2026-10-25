"""One frozen prospective backtest: prepare, submit once, observe once, assess.

No scheduler, retry, order/Playback operation, source installation or global gate
release. The real clock and fixed local store govern the production CLI. Native
metadata and import receipts are preflight evidence; BAR/clock/ledger parity is
checked after the bound run. No result from this module validates a strategy.
"""
import argparse
import copy
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .core import ROOT, file_hash, ProcessLock
from .future_data_intake import FutureIntake
from .future_data_importer import NoRedirect, instance
from .prospective_attempt import (AttemptTransport, ProspectiveAttempt, AttemptError,
    _hash, _read, _exclusive, _replace, packet_fingerprint)
from .prospective_dataset import load_imported_dataset
from .campaign_gate import read_policy, ensure_prospective_submission_allowed
from research.prospective_postrun import assess_postrun

REVIEWED_BACKENDS = {
    'NT8Bridge.Backtest.cs': '6e5d61984fa40b8a02d3abb9ae6364faa9ebddadd3b8c57ebfa5c81d687ccd2e',
    'NT8Bridge.ResearchControl.cs': '6c1436645a9bd19220a70501598ab3e73b8fd24f713db0f5747b587588ae5031',
}

def utcnow():
    return datetime.now(timezone.utc)


def system_time_zone():
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r'SYSTEM\CurrentControlSet\Control\TimeZoneInformation') as key:
        value = winreg.QueryValueEx(key, 'TimeZoneKeyName')[0]
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Windows timezone expectation unavailable')
    return value.strip('\x00 ')


def dispatch_bound(root, packet, preflight, clock, send):
    """Consume the canonical dispatch before a transport's sole POST callback."""
    marker = ensure_prospective_submission_allowed(root, packet, preflight, clock())
    now = clock()
    if (now.tzinfo is None or now.utcoffset() is None
            or not datetime.fromisoformat(marker['checked_at_utc']) <= now <= datetime.fromisoformat(marker['expires_at_utc'])):
        raise AttemptError('Dispatch expired after persistence; consumed without POST')
    return send(copy.deepcopy(packet['request']))


class NativeResearch:
    """Narrow HTTP transport. Redirects, retries and other endpoints are absent."""
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(self, method, path, body=None):
        reads = {'/health', '/ntstatus', '/strategies', '/backtests', '/research/import'}
        if not (method == 'GET' and (path in reads or re.fullmatch(r'/backtest/b[1-9][0-9]*', path))):
            raise ValueError('Endpoint outside fixed prospective research scope')
        if body is not None:
            raise ValueError('GET body refused')
        return self._http(method, path)

    def submit_bound(self, root, packet, preflight, clock):
        if Path(root).resolve() != ROOT.resolve():
            raise ValueError('Real submission requires the canonical production root')
        # Real HTTP never trusts an injected future clock. Synthetic transports
        # separately use dispatch_bound with their explicitly fake clock.
        return dispatch_bound(root, packet, preflight, utcnow,
                              lambda body: self._http('POST', '/backtest', body))

    def _http(self, method, path, body=None):
        req = urllib.request.Request('http://127.0.0.1:7891'+path,
            data=json.dumps(body, allow_nan=False).encode() if body is not None else None,
            headers={'Content-Type': 'application/json'}, method=method)
        try:
            with self.opener.open(req, timeout=10) as response:
                raw = response.read(32*1024*1024+1)
        except urllib.error.HTTPError as exc:
            # Keep the actual server refusal; never retry the mutation.
            detail = exc.read(1024*1024).decode('utf-8', errors='replace')
            raise AttemptError('HTTP '+str(exc.code)+': '+detail) from exc
        if len(raw) > 32*1024*1024:
            raise AttemptError('Native response exceeds finite output limit')
        def invalid(value):
            raise ValueError('Nonfinite native JSON')
        return json.loads(raw, parse_constant=invalid)


class BoundTransport(AttemptTransport):
    def __init__(self, executor):
        self.executor = executor

    def current_instance(self):
        health = self.executor.native.call('GET', '/health')
        self.executor.last_health = health
        return _hash(instance(health))

    def submit(self, request):
        owner = self.executor
        if request != owner.packet['request'] or _hash(request) != _hash(owner.plan['request']):
            raise AttemptError('Only the exact frozen request may be submitted')
        owner._verify_files(owner.preflight['evidence']['files'])
        health = owner.native.call('GET', '/health')
        owner._safe_health(health)
        if _hash(instance(health)) != owner.packet['instance_id']:
            raise AttemptError('Engine changed before dispatch')
        owner._refresh_activity(health)
        # Claims a separate durable dispatch marker. The generic Bridge remains
        # blocked and a second direct call of this transport cannot issue a POST.
        try:
            document = owner.native.submit_bound(owner.root, owner.packet, owner.preflight, owner.clock)
        except Exception as exc:
            # A repeated direct transport call must not overwrite the first
            # response or its uncertain-outcome evidence.
            path = owner.folder/'dispatch-response.json'
            if not path.exists():
                _exclusive(path, {'received': False, 'error': type(exc).__name__+': '+str(exc)})
            raise
        _exclusive(owner.folder/'dispatch-response.json', {'received': True, 'document': document})
        return document

    def poll(self, native_id):
        if not re.fullmatch(r'b[1-9][0-9]*', native_id):
            raise AttemptError('Exact reserved native job ID required')
        return self.executor.native.call('GET', '/backtest/'+native_id)


class ProspectiveExecutor:
    def __init__(self, root=ROOT, native=None, clock=utcnow, nt_dir=None, zone_reader=None):
        self.root = Path(root).resolve()
        if self.root == ROOT.resolve() and (clock is not utcnow or nt_dir is not None or zone_reader is not None):
            raise ValueError('Production requires the real clock and fixed installation paths')
        if self.root != ROOT.resolve() and native is None:
            raise ValueError('Synthetic root requires explicit inert native transport')
        self.native = native if native is not None else NativeResearch()
        self.clock = clock
        self.nt_dir = Path(nt_dir) if nt_dir is not None else Path.home()/'Documents/NinjaTrader 8'
        self.zone_reader = zone_reader or system_time_zone
        self.folder = self.root/'data/runner/prospective-execution'
        self.intake = FutureIntake(self.root, self.nt_dir/'db/replay/NQ 12-26')
        self.transport = BoundTransport(self)
        self.packet = self.preflight = self.plan = None
        self.last_health = None

    @staticmethod
    def _safe_health(health):
        instance(health)
        if (health.get('connections') != [] or health.get('anyLive') is not False
                or health.get('anyNonSim') is not False or health.get('standingModal') is not None):
            raise AttemptError('Disconnected native research state without modal required')

    @staticmethod
    def _verify_files(files):
        if not isinstance(files, dict) or not files:
            raise ValueError('Bound artifact files required')
        for path, expected in files.items():
            if file_hash(path) != expected:
                raise ValueError('Evidence file changed: '+Path(path).name)

    def _disk(self, plan):
        files = {}
        for source, installed in [
            (self.root/plan['source_code'], self.nt_dir/'bin/Custom/Strategies/CodexBollingerClock.cs'),
            (self.root/'native/NT8Bridge.Backtest.cs', self.nt_dir/'bin/Custom/AddOns/NT8Bridge.Backtest.cs'),
            (self.root/'native/NT8Bridge.ResearchControl.cs', self.nt_dir/'bin/Custom/AddOns/NT8Bridge.ResearchControl.cs')]:
            digest = file_hash(source)
            if source.name in REVIEWED_BACKENDS and digest != REVIEWED_BACKENDS[source.name]:
                raise ValueError('Backend differs from the reviewed source: '+source.name)
            if file_hash(installed) != digest:
                raise ValueError('Installed and reviewed source differ: '+installed.name)
            files[str(source)] = files[str(installed)] = digest
        if files[str(self.root/plan['source_code'])] != plan['source_code_sha256']:
            raise ValueError('Frozen strategy source changed')
        config = self.nt_dir/'Config.xml'
        config_hash = file_hash(config)
        tree = ET.parse(config)
        elements = [e for e in tree.iter() if e.tag.split('}')[-1] == 'TimeZoneInfoSerializable']
        if len(elements) != 1:
            raise ValueError('Unique configured timezone element required')
        element = elements[0]
        values = [e.text.strip() for e in element.iter() if e.text and e.text.strip()]
        if len(values) > 1:
            raise ValueError('Unknown serialized timezone structure')
        saved = values[0] if values else None
        system = self.zone_reader()
        expected_zone = saved or system
        if not isinstance(expected_zone, str) or not expected_zone:
            raise ValueError('Timezone expectation missing')
        if file_hash(config) != config_hash:
            raise ValueError('Configuration changed during snapshot')
        files[str(config)] = config_hash
        stores = []
        for day in plan['evaluation_dates']:
            name = day.replace('-', '')
            minute = self.nt_dir/'db/minute/NQ 12-26'/(name+'.Last.ncd')
            ticks = sorted((self.nt_dir/'db/tick/NQ 12-26').glob(name+'*.Last.ncd'))
            if not minute.is_file() or not ticks:
                raise ValueError('Native date stores missing: '+day)
            for path in [minute]+ticks:
                stat = path.stat()
                if stat.st_size <= 0:
                    raise ValueError('Empty native store: '+path.name)
                digest = file_hash(path)
                files[str(path)] = digest
                stores.append(dict(date=day, path=str(path), size=stat.st_size,
                                   mtime_ns=stat.st_mtime_ns, sha256=digest))
        return dict(files=files, stores=stores, expected_time_zone=expected_zone,
            saved_time_zone=saved, system_time_zone=system,
            timezone_basis='saved configuration' if saved else 'system expectation: empty saved setting does not prove runtime fallback',
            cache_content_parity=False, compiled_method_equivalence_proven=False)

    def prepare(self):
        with ProcessLock(self.folder/'executor.lock'):
            return self._prepare()

    def _prepare(self):
        policy = read_policy(self.root, self.clock())  # before any market/native access
        self.plan = policy['plan']
        self.folder.mkdir(parents=True, exist_ok=True)
        prefix = self.plan['id']
        if any((self.folder/(prefix+suffix)).exists() for suffix in
               ('.reservation.json', '.state.json', '.handle.json', '.dispatch.json')):
            raise AttemptError('Plan already consumed; use only existing observation/evaluation')
        loaded = load_imported_dataset(self.intake, self.clock())
        disk = self._disk(self.plan)
        health = self.native.call('GET', '/health')
        self._safe_health(health)
        engine = instance(health)
        status = self.native.call('GET', '/ntstatus')
        if (not isinstance(status, dict) or status.get('verdict') != 'current' or status.get('scanError')):
            raise AttemptError('Native source/assembly freshness not established')
        catalog = self.native.call('GET', '/strategies')
        selected = [r for r in catalog if isinstance(r, dict) and
                    r.get('fullName') == 'NinjaTrader.NinjaScript.Strategies.CodexBollingerClock'] if isinstance(catalog, list) else []
        if (len(selected) != 1 or selected[0].get('error')
                or selected[0].get('inputs', {}).get('BandLength') != {'type': 'Int32', 'default': 20}):
            raise AttemptError('Frozen backtest selector type/default unavailable')
        jobs = self.native.call('GET', '/backtests')
        if (not isinstance(jobs, list) or any(not isinstance(j, dict) or
                j.get('state') not in {'done', 'error', 'timeout', 'cancelled'} for j in jobs)):
            raise AttemptError('Queued/running/unknown native job state')
        import_status = self.native.call('GET', '/research/import')
        if not isinstance(import_status, dict) or import_status.get('state') not in {'idle', 'done'}:
            raise AttemptError('Native import still running or unresolved')
        dll = Path(health['assemblyLocation']).resolve(strict=True)
        if not dll.is_relative_to(self.nt_dir.resolve()) or dll.suffix.lower() != '.dll':
            raise AttemptError('Native assembly outside expected installation')
        newest_source = max((p.stat().st_mtime_ns for p in (self.nt_dir/'bin/Custom').rglob('*.cs')), default=None)
        if newest_source is None or dll.stat().st_mtime_ns < newest_source:
            raise AttemptError('Loaded DLL predates installed sources by disk metadata')
        files = {**loaded['dataset']['files'], **disk['files'], str(dll): file_hash(dll)}
        self._verify_files(files)
        final_health = self.native.call('GET', '/health')
        self._safe_health(final_health)
        if instance(final_health) != engine:
            raise AttemptError('Engine changed during preflight')
        self.packet = dict(plan_id=prefix, plan_sha256=self.intake.planhash,
            request=copy.deepcopy(self.plan['request']), source_sha256=self.plan['source_code_sha256'],
            dataset_sha256=loaded['dataset_sha256'], instance_id=_hash(engine))
        evidence = dict(files=files, dataset=loaded['dataset'], disk=disk, health_before=health,
            health_after=final_health, native_status=status, selected_strategy=selected[0],
            newest_installed_source_mtime_ns=newest_source,
            job_metadata=jobs, import_status=import_status,
            limitations=['Metadata/source mtime and catalog are not IL equivalence',
                        'Job list is an observation, not atomic full worker idle proof',
                        'Native file hashes and import receipts are not cache content parity',
                        'Saved/system timezone is an expectation, verified against bound result clocks'])
        self.preflight = dict(packet=self.packet, checked_at_utc=self.clock().isoformat(),
            dataset_sha256=loaded['dataset_sha256'], engine=engine,
            native_time_zone=disk['expected_time_zone'], evidence_sha256=_hash(evidence), evidence=evidence)
        _replace(self.folder/'preflight.json', self.preflight)
        return copy.deepcopy(self.preflight)

    def _refresh_activity(self, health):
        """Refresh the actual mutable observations, not just their timestamp."""
        jobs = self.native.call('GET', '/backtests')
        importing = self.native.call('GET', '/research/import')
        if (not isinstance(jobs, list) or any(not isinstance(j, dict) or
                j.get('state') not in {'done', 'error', 'timeout', 'cancelled'} for j in jobs)):
            raise AttemptError('Native job became busy before submission')
        if not isinstance(importing, dict) or importing.get('state') not in {'idle', 'done'}:
            raise AttemptError('Native import became busy before submission')
        after = self.native.call('GET', '/health')
        self._safe_health(after)
        if instance(after) != self.preflight['engine'] or instance(health) != instance(after):
            raise AttemptError('Engine changed during activity refresh')
        self.preflight['evidence']['latest_activity'] = dict(health_before=health, health_after=after,
            jobs=jobs, import_status=importing, checked_at_utc=self.clock().isoformat())
        self.preflight['evidence_sha256'] = _hash(self.preflight['evidence'])
        self.preflight['checked_at_utc'] = self.clock().isoformat()
        _replace(self.folder/'preflight.json', self.preflight)

    def _authorize(self, packet, fingerprint):
        read_policy(self.root, self.clock())
        if packet != self.packet or fingerprint != packet_fingerprint(packet):
            raise AttemptError('Fresh authorization packet mismatch')
        self._verify_files(self.preflight['evidence']['files'])
        health = self.native.call('GET', '/health')
        self._safe_health(health)
        if instance(health) != self.preflight['engine']:
            raise AttemptError('Engine changed before reservation')
        self._refresh_activity(health)
        return dict(scope='local_submission', approved=True, fingerprint=fingerprint,
                    packet_sha256=_hash(packet), checked_at_utc=self.clock().isoformat())

    def submit(self):
        # Serialize prepare as well as claim so concurrent callers cannot change
        # the recorded preflight during another caller's reservation.
        with ProcessLock(self.folder/'executor.lock'):
            self._prepare()
            attempt = ProspectiveAttempt(self.folder, self.packet, self.transport, self._authorize, self.clock)
            return attempt.submit()

    def _existing(self):
        policy = read_policy(self.root, self.clock())
        self.plan = policy['plan']
        self.preflight = _read(self.folder/'preflight.json')
        self.packet = self.preflight['packet']
        if (self.preflight.get('evidence_sha256') != _hash(self.preflight['evidence'])
                or self.packet.get('plan_sha256') != self.intake.planhash
                or self.packet.get('request') != self.plan['request']
                or self.packet.get('instance_id') != _hash(self.preflight['engine'])):
            raise AttemptError('Persisted preflight binding changed')
        attempt = ProspectiveAttempt(self.folder, self.packet, self.transport, self._authorize, self.clock)
        reservation = _read(attempt.reservation_path)
        state = attempt._load_bound(reservation['token'], attempt.fingerprint)
        return attempt, state

    def observe(self):
        with ProcessLock(self.folder/'executor.lock'):
            attempt, state = self._existing()
            return attempt.observe(state['token'], state['fingerprint'])

    def assess(self):
        with ProcessLock(self.folder/'executor.lock'):
            attempt, state = self._existing()
            if state['status'] != 'terminal':
                raise AttemptError('Bound native terminal evidence required')
            result_path = self.folder/'assessment.json'
            if result_path.exists():
                saved = _read(result_path)
                if (saved.get('terminal_sha256') != state['terminal_document_sha256']
                        or saved.get('packet_sha256') != _hash(self.packet)):
                    raise AttemptError('Saved assessment binding differs')
                return saved
            # Terminal original is durable in attempt state before any evaluation.
            self._verify_files(self.preflight['evidence']['files'])
            loaded = load_imported_dataset(self.intake, self.clock())
            if loaded['dataset_sha256'] != self.packet['dataset_sha256']:
                raise AttemptError('Dataset changed after run')
            if self.transport.current_instance() != self.packet['instance_id']:
                raise AttemptError('Engine changed after bound run; attribution unresolved')
            binding = dict(job_id=state['native_id'], expected_instance=self.packet['instance_id'],
                observed_instance=self.packet['instance_id'], native_time_zone=self.preflight['native_time_zone'])
            evaluation = assess_postrun(self.plan, state['terminal_document'], loaded['last_by_date'], binding)
            self._verify_files(self.preflight['evidence']['files'])
            result = dict(packet_sha256=_hash(self.packet), terminal_sha256=state['terminal_document_sha256'],
                recorded_at_utc=self.clock().isoformat(), evaluation=evaluation,
                strategy_validated=False, prospective_candidate_promoted=False,
                evidence_scope='Bound local attempt/input files and native response; external completeness/exit causality/longer validation remain pending')
            _exclusive(result_path, result)
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'submit', 'observe', 'assess'])
    args = parser.parse_args()
    executor = ProspectiveExecutor()
    try:
        value = getattr(executor, args.action)()
    except (ValueError, RuntimeError, OSError) as exc:
        print(json.dumps(dict(action=args.action, status='blocked', reason=str(exc), strategy_validated=False), ensure_ascii=False))
        raise SystemExit(2)
    # CLI prints identity/status only; potentially large raw outcomes are stored
    # locally and only the explicit assess action returns assessment details.
    print(json.dumps(value if args.action == 'assess' else
        {k:value[k] for k in ('status', 'native_id', 'fingerprint', 'checked_at_utc') if k in value}, ensure_ascii=False))


if __name__ == '__main__':
    main()
