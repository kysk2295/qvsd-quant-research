"""Frozen Cafe configurations on newly acquired historical data; never pristine OOS."""
import argparse,hashlib,json,time
from datetime import datetime,timedelta
from pathlib import Path
from .core import ROOT,Queue,ProcessLock,atomic,canonical,file_hash,dataset_hash
from .adapter import Bridge
from .assessment import assess,ledger_evidence
from .research_protocol import validate_manifest,enqueue_extension
from dashboard.reporter import post,emit
from dashboard.server import validate_run
from .research_lifecycle import Lifecycle

def reject_previous_request(folder,request):
    for oldpath in folder.glob('*.json'):
        old=json.loads(oldpath.read_text())
        if old.get('request')==request:
            raise RuntimeError('Same date/configuration already attempted under a different fingerprint; inspect evidence, do not resubmit')

def execute(manifest_path,lifecycle):
    folder=ROOT/'data/runner/cafe-extension';folder.mkdir(exist_ok=True)
    q=Queue();bridge=Bridge()
    config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text(encoding='utf-8'))
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    mh=validate_manifest(manifest)
    configurations=manifest.get('frozen_configurations')
    expected=[{'Variant':2,'RangeMinutes':15},{'Variant':2,'RangeMinutes':30},{'Variant':3,'RangeMinutes':15}]
    if configurations!=expected:raise ValueError('Explicit frozen Cafe configuration list required')
    if manifest['search_budget']['extension_runs']!=6 or manifest['search_budget']['new_parameters']!=0:
        raise ValueError('Exactly six frozen-cost experiments required')
    costs=manifest['costs']
    if [costs[k] for k in ('base_slippage_ticks','base_round_trip_fee','stress_slippage_ticks','stress_round_trip_fee')]!=[2,5,4,10]:
        raise ValueError('Cost manifest differs from frozen experiment')
    dates=manifest['chronological_split']['dates']
    if len(dates)!=1:raise ValueError('This finite runner accepts exactly one frozen extension session')
    day=datetime.strptime(dates[0],'%Y-%m-%d');date=day.strftime('%Y%m%d');iso=day.strftime('%Y-%m-%d')
    report_path=ROOT/'research'/('cafe-extension-results-'+date+'.json')
    audit=json.loads((ROOT/'research/recent-tick-audit-20261025.json').read_text(encoding='utf-8'))
    coverage=[s for r in audit if '/'+date+'/' in r['file'].replace('\\','/') for s in r['sessions'] if s['date']==iso]
    assert len(coverage)==1 and coverage[0]['minutes']==390 and not coverage[0]['missingMinutes']
    source=ROOT/'native/CodexCafeRange.cs';source_hash=file_hash(source)
    assert source_hash==file_hash(Path.home()/'Documents/NinjaTrader 8/bin/Custom/Strategies/CodexCafeRange.cs')
    db=Path.home()/'Documents/NinjaTrader 8/db'
    prefixes=tuple((day+timedelta(days=offset)).strftime('%Y%m%d') for offset in (-1,0,1))
    files=sorted(p for kind in ('minute','tick') for p in (db/kind/'NQ 12-26').glob('*.ncd') if p.name.startswith(prefixes))
    assert files
    dh=dataset_hash(files);results=[]
    with ProcessLock(folder/'cycle.lock'):
        for configuration in configurations:
            variant,minutes=configuration['Variant'],configuration['RangeMinutes']
            for slip,fee in ((2,5),(4,10)):
                request=dict(strategy='CodexCafeRange',instrument='NQ DEC26',barsPeriod={'type':'Minute','value':5},
                    inputs={'Variant':variant,'RangeMinutes':minutes,'FirstDate':int(date),'LastDate':int(date)},
                    tickReplay=False,includeCommission=False,includeTradeHistory=True,slippageTicks=slip,
                    fillResolution='High',fillResolutionType='Tick',fillResolutionValue=1,breakAtEod=True,
                    **{'from':(day-timedelta(days=1)).strftime('%Y-%m-%d'),'to':(day+timedelta(days=1)).strftime('%Y-%m-%d')})
                key=hashlib.sha256(canonical([request,dh,source_hash,mh]).encode()).hexdigest()
                path=folder/(key+'.json')
                if path.exists():
                    record=json.loads(path.read_text())
                    if not record.get('ack'):raise RuntimeError('Existing unacknowledged run: inspect before resuming')
                    results.append(record);continue
                reject_previous_request(folder,request)
                health=bridge.call('GET','/health')
                assert not health.get('anyLive') and not health.get('anyNonSim') and not health.get('standingModal')
                assert not any(j['state'] in ('running','queued') for j in bridge.call('GET','/backtests'))
                if q.control('mode')=='stopped':raise RuntimeError('User stop')
                record=dict(key=key,request=request,manifest_hash=mh,data_hash=dh,source_hash=source_hash,state='submitting',started=time.time())
                atomic(path,record)
                lifecycle.update('running','Native Cafe extension '+date,current_run='cafe-extension-'+key[:24])
                record['native_id']=bridge.call('POST','/backtest',request)['id'];atomic(path,record)
                deadline=time.time()+180
                while True:
                    doc=bridge.call('GET','/backtest/'+record['native_id'])
                    if doc['state'] not in ('queued','running'):break
                    if time.time()>deadline or q.control('mode')=='stopped':
                        bridge.call('DELETE','/backtest/'+record['native_id']);raise RuntimeError('Stopped/deadline')
                    time.sleep(1)
                record['doc']=doc;atomic(path,record)
                assert doc['state']=='done' and not doc.get('error')
                settings=doc['settings']
                assert settings['fillResolution']=='High' and settings['fillResolutionType']=='Tick' and settings['fillResolutionValue']==1
                assert settings['slippageTicks']==slip and settings['includeCommission'] is False
                assert any(x.startswith('AUDIT '+date+' ') and 'bars=77 gap=False' in x for x in doc['output'])
                assert len(doc['trades'])==doc['summary']['trades']
                from zoneinfo import ZoneInfo
                for trade in doc['trades']:
                    entry=datetime.fromisoformat(trade['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
                    assert entry.strftime('%Y%m%d')==date and trade['qty']==1
                assert not any('ORDER_ERROR' in x for x in doc['output'])
                assert dataset_hash(files)==dh and file_hash(source)==source_hash
                rejected=sum(x.startswith('SIZE_REJECT ') for x in doc['output'])
                review=assess(doc['trades'],fee,0,signals=rejected,condition_rejected=rejected)
                review['decision']='deferred' if review['decision']=='further_validation' else review['decision']
                review['reason']='One additional historical session; diagnostic only; session coverage remains insufficient' if doc['trades'] and review['net_after_assumed_fee']>0 else review['reason']
                review.pop('minimum_trades',None)
                review.update(coverage_policy=manifest['coverage_policy'],ledger_evidence=ledger_evidence(doc['trades'],fee),next_action='Acquire distinct sessions and evaluate frozen parameters; no promotion from this one-day extension')
                review['ledger_evidence']['daily_net'].setdefault(iso,0)
                enqueue_extension(ROOT/'research/evidence-work-queue.json',str(variant)+'-'+str(minutes),review,mh)
                run=dict(id='cafe-extension-'+key[:24],strategy='CodexCafeRange',symbol='NQ',worker='windows-candidate-research',
                    source='Frozen historical extension',batch='cafe-extension-'+date,dataset='NQ DEC26 '+date+' High Tick1',data_hash=dh,
                    status='completed',phase='historical_extension',progress=100,reason=review['reason'],
                    cost=f'{slip} ticks + ${fee} assumed round trip',params=dict(inputs=request['inputs'],assessment=review,source_hash=source_hash,manifest_hash=mh),
                    metrics=dict(net=review['net_after_assumed_fee'],trades=len(doc['trades'])),equity=[],
                    started_at=record['started'],completed_at=time.time(),evidence=str(report_path.relative_to(ROOT))+'; local complete native ledger')
                validate_run(run);emit(run,q.telemetry)
                ack=post(config['url'],'/api/runs',run,config['token']);assert ack.get('ok') is True
                snap=q.telemetry/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json');q.control('ack:'+snap.name,file_hash(snap))
                record.update(state='terminal',assessment=review,ack=True,run_id=run['id']);atomic(path,record);results.append(record)
                print(canonical(dict(inputs=request['inputs'],slip=slip,assessment=review,ack=True)),flush=True)
    atomic(report_path,[{k:r[k] for k in ('run_id','request','manifest_hash','data_hash','source_hash','assessment','ack')} for r in results])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);args=parser.parse_args()
    lifecycle=Lifecycle()
    try:
        execute(Path(args.manifest),lifecycle)
    except Exception as exc:
        lifecycle.update('failed',str(exc),current_run=None)
        raise
    else:lifecycle.update('idle','Finite extension batch complete; ACKs persisted. No background research running.',current_run=None)

if __name__=='__main__':main()
