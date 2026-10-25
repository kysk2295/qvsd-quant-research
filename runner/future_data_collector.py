"""Finite, data-only intake. Default is offline dry-run; never executes a strategy."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .core import ROOT, ProcessLock, atomic, file_hash
from .future_data_intake import FutureIntake

SERVER = Path(r'C:\Users\User\Documents\Codex\2026-10-04\dlrj\work\nt8-mcp\server')

class NativeDownload:
    def __init__(self):
        sys.path.insert(0, str(SERVER))
        from nt8_mcp.tools_researchcontrol import nt_replay_download, nt_research_window
        self.download, self.window = nt_replay_download, nt_research_window

    def idle(self):
        # No Playback status, connection changes, account queries or arming.
        view = self.window()
        buttons = [c for c in view.get('controls', []) if c.get('name') == 'btnDownloadMarketReplay']
        return not view.get('error') and len(buttons) == 1 and buttons[0].get('enabled') is True

    def submit(self, day):
        return self.download('NQ 12-26', day)

def quality_arrays(day, ts, kinds, prices, volumes):
    import numpy as np
    if not len(ts) or not np.all(np.diff(ts) >= 0):
        raise ValueError('Empty or unordered source')
    opening = int(datetime.fromisoformat(day+'T09:30').replace(tzinfo=ZoneInfo('America/New_York')).timestamp())*10**9
    mask = (kinds == 2) & (ts >= opening) & (ts < opening+390*60*10**9)
    t, p, v = ts[mask], prices[mask], volumes[mask]
    if not len(t) or not np.all(np.isfinite(p)) or not np.all(p > 0) or not np.all(v > 0) or not np.all(p*4 == np.rint(p*4)):
        raise ValueError('Invalid RTH Last price/size')
    minutes = set(((t-opening)//(60*10**9)).tolist())
    missing = sorted(set(range(390))-minutes)
    if missing:
        raise ValueError('Missing RTH minutes: '+str(missing))
    return dict(rth_minutes=len(minutes), rth_ticks=len(t), missing_minutes=missing)

def audit_file(day, source, folder):
    import pyarrow.parquet as pq
    sys.path.insert(0, str(SERVER))
    from nt8_mcp.nrd_offline import convert_file, build_table
    from research.prepare_nt_ticks import prepare
    before = file_hash(source)
    folder.mkdir(parents=True, exist_ok=True)
    auditpath = folder/(day+'.quality.json')
    if auditpath.exists():
        old = json.loads(auditpath.read_text())
        if old['source_sha256'] != before:
            raise ValueError('Previously audited source changed')
        for path, digest in old['derived_hashes'].items():
            if file_hash(path) != digest:
                raise ValueError('Derived artifact changed')
        return auditpath
    decoded = convert_file(source, want_l1=True, want_l2=False, salvage=False)
    if decoded.get('integrity_ok') is not True or decoded.get('truncated'):
        raise ValueError('Strict NRD integrity failed')
    table = build_table(decoded['L1'], source)
    arrays = [table.column(k).cast('int64').to_numpy() if k == 'Timestamp' else table.column(k).to_numpy() for k in ('Timestamp','MarketDataType','Price','Volume')]
    coverage = quality_arrays(day, *arrays)
    if file_hash(source) != before:
        raise ValueError('Source still changing')
    parquet, last = folder/(day+'.parquet'), folder/(day+'.Last.txt')
    if parquet.exists() or last.exists():
        raise ValueError('Partial artifacts require inspection; no overwrite')
    pq.write_table(table, parquet, compression='zstd')
    prepare(parquet, last)
    if file_hash(source) != before:
        raise ValueError('Source changed during export')
    atomic(auditpath, dict(date=day, source_sha256=before, integrity_passed=True,
        derived_hashes={str(p):file_hash(p) for p in (parquet,last)}, **coverage,
        native_runs=0, performance_evaluated=False, timezone='America/New_York',
        limitation='Observed Last coverage; not proof of lossless exchange capture. No performance computation.'))
    return auditpath

def publish_quality(day, auditpath):
    from dashboard.reporter import emit, post
    from dashboard.server import validate_run
    from .core import Queue
    import hashlib
    q = Queue(); audit = json.loads(auditpath.read_text())
    run = dict(id='bollinger-future-data-'+day, strategy='Data quality only', symbol='NQ 12-26',
        source='Native Historical Data NRD', worker='windows-candidate-research', dataset=day,
        status='completed', progress=100, phase='data_quality', metrics={}, equity=[],
        params=dict(quality=audit, performance_evaluated=False, native_runs=0))
    validate_run(run); emit(run,q.telemetry)
    config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    if post(config['url'],'/api/runs',run,config['token']).get('ok') is not True:
        raise RuntimeError('Quality ACK missing')
    snap=q.telemetry/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json')
    q.control('ack:'+snap.name,file_hash(snap))
    return dict(run_id=run['id'],ack=True,telemetry_sha256=file_hash(snap))

class Collector:
    def __init__(self, intake, adapter=None, auditor=audit_file, publisher=publish_quality):
        self.intake,self.adapter,self.auditor,self.publisher=intake,adapter,auditor,publisher

    def run(self, now, execute=False):
        self.intake.initialize()
        with ProcessLock(self.intake.folder/'collector.lock'):
            state=self.intake.load(); ready=self.intake.available(now)
            report=dict(dry_run=not execute, eligible=ready, processed=[], downloads_submitted=0,
                automatic_collection_running=False, native_runs=0, performance_evaluated=False)
            if not execute:
                return report
            # Audit existing closed files before requesting anything else. Max three dates total.
            existing=[d for d in ready['existing_files_requiring_audit']
                if now >= datetime.fromisoformat(state['entries'][d]['session_close_utc'])
                and not state['entries'][d].get('quality_ack')]
            dates=(existing+ready['eligible_dates'])[:3]
            for day in dates:
                source=Path(state['entries'][day]['expected_download_path'])
                if self.adapter is None:
                    self.adapter=NativeDownload()
                if not self.adapter.idle():
                    report['blocked']='Historical Data download is not verified idle; no control changes';break
                if not source.exists():
                    token=self.intake.claim_batch([day],now)
                    self.intake.record_submission(day,token,now)
                    report['downloads_submitted']+=1
                    try:
                        response=self.adapter.submit(day)
                        if response.get('requested') is not True:
                            raise RuntimeError('Download not confirmed queued')
                    except Exception as exc:
                        self.intake.record_failure(day,type(exc).__name__+': submission uncertain; no retry')
                        report['blocked']='Submission failed or uncertain; inspect before resuming';break
                    # Async service: finish this finite invocation; later invocation only reads file.
                    report['processed'].append(dict(date=day,status='submitted_awaiting_file'));break
                auditpath=self.auditor(day,source,self.intake.folder/'quality')
                self.intake.record_quality(day,auditpath)
                ack=self.publisher(day,auditpath)
                with ProcessLock(self.intake.folder/'intake.lock'):
                    updated=self.intake.load();updated['entries'][day]['quality_ack']=ack;atomic(self.intake.path,updated)
                report['processed'].append(dict(date=day,status='quality_published',**ack))
            return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();intake=FutureIntake()
    report=Collector(intake).run(datetime.now(timezone.utc),args.execute)
    report.update(download_adapter_implemented=True, scheduled_worker_running=False,
        plan_sha256=intake.planhash, checked_at_utc=datetime.now(timezone.utc).isoformat(),
        actual_download_requests=intake.load()['actual_download_requests'])
    atomic(ROOT/'research/future-data-collector-readiness.json',report)
    print(json.dumps(report))

if __name__=='__main__':main()
