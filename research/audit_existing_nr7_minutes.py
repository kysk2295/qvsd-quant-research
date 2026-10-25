"""One native data-only snapshot of existing4minute sessions; no order methods."""
import json,time,hashlib
from pathlib import Path
from datetime import datetime,timedelta
from runner.core import ROOT,atomic,file_hash,dataset_hash,canonical,Queue,ProcessLock
from runner.adapter import Bridge
from runner.research_lifecycle import Lifecycle
from dashboard.reporter import post,emit
from dashboard.server import validate_run

def main():
    folder=ROOT/'data/runner/nr7-existing-minute-audit';folder.mkdir(exist_ok=True);statepath=folder/'state.json'
    with ProcessLock(folder/'audit.lock'):
        assert not statepath.exists(),'One diagnostic only;inspect previous result before resubmitting'
        source=ROOT/'native/CodexRthDataAudit.cs';assert file_hash(source)==file_hash(Path.home()/'Documents/NinjaTrader 8/bin/Custom/Strategies/CodexRthDataAudit.cs')
        dates=['2026-09-28','2026-09-29','2026-09-30','2026-10-01'];files=[Path.home()/f'Documents/NinjaTrader 8/db/minute/NQ 12-26/{d.replace("-", "")}.Last.ncd' for d in dates];assert all(p.exists() for p in files)
        dh=dataset_hash(files);req=dict(strategy='CodexRthDataAudit',instrument='NQ DEC26',barsPeriod=dict(type='Minute',value=1),inputs=dict(FirstDate=20260928,LastDate=20261001),tickReplay=False,includeCommission=False,includeTradeHistory=True,slippageTicks=0,fillResolution='Standard',breakAtEod=True,**{'from':'2026-09-27','to':'2026-10-02'})
        key=hashlib.sha256(canonical([req,dh,file_hash(source)]).encode()).hexdigest();state=dict(started=time.time(),request=req,source_hash=file_hash(source),data_hash=dh,key=key,state='submitting');atomic(statepath,state)
        bridge=Bridge();h=bridge.call('GET','/health');assert not h['anyLive'] and not h['anyNonSim'] and not h['standingModal'];assert not any(j['state'] in ('running','queued') for j in bridge.call('GET','/backtests'))
        Lifecycle().update('auditing','Native existing-minute data audit:4sessions,no order code,no performance trial',None)
        state['native_id']=bridge.call('POST','/backtest',req)['id'];atomic(statepath,state);deadline=time.time()+180
        while True:
            doc=bridge.call('GET','/backtest/'+state['native_id'])
            if doc['state'] not in ('running','queued'):break
            if time.time()>deadline:bridge.call('DELETE','/backtest/'+state['native_id']);raise RuntimeError('Data audit deadline')
            time.sleep(1)
        atomic(folder/'native.json',doc);assert doc['state']=='done' and not doc.get('error') and not doc['trades'] and dataset_hash(files)==dh
        sessions={d:[] for d in dates}
        for line in doc['output']:
            if not line.startswith('RTH_BAR|'):continue
            p=line.split('|');end=datetime.fromisoformat(p[1]);start=end-timedelta(minutes=1);day=start.date().isoformat();vals=list(map(float,p[2:6]));volume=int(p[6]);assert day in sessions and volume>0 and all(v>0 and v*4==round(v*4) for v in vals)
            o,hi,lo,close=vals;assert lo<=min(o,close)<=max(o,close)<=hi
            sessions[day].append(dict(minute=start.hour*60+start.minute,open=o,high=hi,low=lo,close=close,volume=volume))
        reports=[]
        for day,bars in sessions.items():
            assert [b['minute'] for b in bars]==list(range(570,960))
            reports.append(dict(date=day,rth_minutes=390,high=max(b['high'] for b in bars),low=min(b['low'] for b in bars),close=bars[-1]['close'],bars=bars,source='existing native Last minute store',independent_tick_crosscheck=False))
        evidence=dict(sessions=reports,source_files=[dict(path=str(p),sha256=file_hash(p)) for p in files],data_hash=dh,source_hash=state['source_hash'],native_id=state['native_id'],raw_response_sha256=file_hash(folder/'native.json'),limitation='Native historical minute-source completeness/structure checked;not independently reconciled to raw Last ticks. No orders or returns tested.')
        atomic(ROOT/'research/nr7-existing-minute-audit.json',evidence)
        q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());rid='nr7-data-audit-'+key[:24]
        run=dict(id=rid,strategy='CodexRthDataAudit',symbol='NQ',worker='windows-candidate-research',source='Existing native historical minute data',batch='nr7-context-data-audit',dataset='Sep28-Oct1 RTH minute data',data_hash=dh,status='completed',phase='data-audit',progress=100,reason='4complete sessions;data-only diagnostic,no performance observation',cost='not applicable:zero orders',params=dict(assessment=dict(diagnostic_only=True,unique_performance_observations_added=0,decision='deferred',reason='Data collection only;not a trading candidate',coverage_sessions=4),source_hash=state['source_hash'],native_trade_ledger=[]),metrics=dict(net=0,trades=0),equity=[],started_at=state['started'],completed_at=time.time(),evidence='research/nr7-existing-minute-audit.json')
        validate_run(run);emit(run,q.telemetry);assert post(config['url'],'/api/runs',run,config['token']).get('ok') is True;snap=q.telemetry/(hashlib.sha256(rid.encode()).hexdigest()+'.json');q.control('ack:'+snap.name,file_hash(snap));state.update(state='terminal',run_id=rid,ack=True,doc=doc);atomic(statepath,state)
        print(json.dumps(dict(sessions=4,bars=1560,data_only_native_runs=1,performance_runs=0,ack=True)))

if __name__=='__main__':main()
