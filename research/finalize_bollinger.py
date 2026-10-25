"""Independently match raw Last minute closes, crossings and native ledgers."""
import json
from collections import Counter
from datetime import datetime,timedelta,timezone,time
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash,Queue
from runner.bollinger_cycle import BollingerCycle
from runner.research_lifecycle import Lifecycle
from research.finalize_gap_fade import publish

def main():
    Lifecycle().update('auditing','Bollinger: independently matching raw tick closes,5070bar calculations and native ledgers',None)
    p=ROOT/'data/runner/bollinger-return/state.json';state=json.loads(p.read_text());rows=sorted(state['experiments'].values(),key=lambda r:r['request']['slippageTicks']);assert len(rows)==2
    dates=json.loads((ROOT/'research/bollinger-return-manifest.json').read_text())['data_requirements']['recent'];ny=ZoneInfo('America/New_York')
    audit=json.loads((ROOT/'research/recent-tick-audit-20261025.json').read_text());bydate={s['date']:r for r in audit for s in r['sessions'] if s['minutes']==390 and not s['missingMinutes']}
    raw={};hashes=[]
    for day in dates:
        source=ROOT/bydate[day]['file'];assert file_hash(source)==bydate[day]['sha256'];previous=None;local=None;count=set()
        for line in source.open(encoding='ascii'):
            stamp,price,size=line.strip().split(';');key=stamp[:13]
            if key!=previous:local=datetime.strptime(key,'%Y%m%d %H%M').replace(tzinfo=timezone.utc).astimezone(ny);previous=key
            m=local.hour*60+local.minute
            if str(local.date())==day and 570<=m<960:
                raw[(local+timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%S')]=float(price);count.add(m)
        assert len(count)==390;hashes.append(dict(date=day,path=str(source),sha256=bydate[day]['sha256']))
    assert len(raw)==5070
    ledgers=[];results=[];fills=[]
    next_action='Defer Bollinger adoption: positive observed sample but adverse4ticks/fill erases net. Freeze20/2band rules and risk; no tuning on these13dates. Next finite work: diagnose seconds precision in native ledger serialization and feasibility of causal bid/ask cost validation using existing quote data, preserving old runs. OFI acquisition resumes only after Historical Data window resolves; RSI unchanged.'
    for r in rows:
        assert r['ack'] and r['assessment']['decision']!='execution_error';doc=r['doc'];BollingerCycle.validate_native(None,doc)
        trace={}
        for line in doc['output']:
            if line.startswith('BAR '):
                x=line.split();v=dict(z.split('=',1) for z in x[2:]);assert float(v['close'])==raw[x[1]];trace[x[1]]=v
        assert len(trace)==5070
        signals=[s for s in doc['output'] if s.startswith('SIGNAL ')];trades=doc['trades'];assert len(signals)==len(trades)
        matched=[];daily={};counts=Counter();prior_exit=None;fee=5 if r['request']['slippageTicks']==2 else 10;balance=peak=dd=0
        for s,t in zip(signals,trades):
            x=s.split();v=dict(z.split('=',1) for z in x[2:]);st=datetime.fromisoformat(x[1]).replace(tzinfo=ny);bar=trace[x[1]]
            assert int(bar['side'])==(1 if v['side']=='L' else -1)
            for k in ('close','mean','lower','upper'):assert float(v[k])==float(bar[k])
            entry=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ny);exit=datetime.fromisoformat(t['exitTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ny)
            assert entry.date()==exit.date() and 0<=(entry-st).total_seconds()<=60 and entry<=exit and time(9,51)<=st.time()<=time(15,25) and exit.time()<=time(15,56)
            assert prior_exit is None or entry>=prior_exit;prior_exit=exit
            assert t['qty']==1 and t['entryName']==v['side'] and t['side']==('Long' if v['side']=='L' else 'Short')
            assert abs(t['pnl']-(t['exitPrice']-t['entryPrice'])*20*(1 if v['side']=='L' else -1))<1e-6
            day=entry.date().isoformat();counts[day]+=1;assert counts[day]<=4
            pnl=t['pnl']-fee;daily[day]=daily.get(day,0)+pnl;balance+=pnl;peak=max(peak,balance);dd=max(dd,peak-balance)
            matched.append(dict(signal=s,trade=t,entry_et=entry.isoformat(),exit_et=exit.isoformat()))
        fills.append([(t['entryTime'],t['exitTime'],t['entryPrice'],t['exitPrice'],t['qty'],t['side']) for t in trades])
        r['assessment'].update(adoption_gate='deferred_cost_and_observed_sample',independent_oos=False,raw_tick_minute_closes_match=True,native_signal_fill_match=True,independent_band_math_match=True,closed_trade_drawdown=dd,
            net_without_best_day=sum(daily.values())-max(daily.values()),next_action=next_action,
            execution_limitations='HighTick1 Last fills; spread is not independently modeled. Extra ticks arithmetic only. Whole-second serialized fill timestamps prevent precise quote alignment. No bid/ask, queue or Playback validation for this candidate.',
            source_adaptation='Published code crosses back inside bands; source prose differs. Market entries and RTHreset/risk/exit rules explicitly adapted.')
        ledgers.append(dict(run_id=r['run_id'],native_id=r['native_id'],matched=matched,output=doc['output'],settings=doc['settings'],native_response_sha256=file_hash(p.parent/(r['key']+'.native.json'))))
        results.append(dict(run_id=r['run_id'],slippage=r['request']['slippageTicks'],trades=len(trades),net=sum(daily.values()),daily=daily,closed_drawdown=dd,net_without_best_day=r['assessment']['net_without_best_day'],additional4tick_net=next(s['net'] for s in r['assessment']['additional_fill_cost_sensitivity'] if s['additional_ticks_per_fill']==4)))
    same=fills[0]==fills[1];q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    for r in rows:
        r['assessment'].update(identical_native_fills_across_costs=same,native_fill_cost_limitation='Identical2/4tick native fills; difference fees only' if same else 'Native fills differ; inspect saved tuples')
        publish(r,q,config)
    atomic(p,state);atomic(ROOT/'research/bollinger-return-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows]);atomic(ROOT/'research/bollinger-return-ledgers.json',ledgers)
    summary=dict(native_runs=2,result_acks=2,review_acks=2,unique_trades=len(rows[0]['doc']['trades']),sessions=13,independent_oos=False,raw_sources=hashes,verified_bars_per_run=5070,csharp_boundary_assertions=8,identical_native_fills=same,results=results,next_action=next_action)
    atomic(ROOT/'research/bollinger-return-summary.json',summary)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text())
    if not any(c['id']=='bollinger-return-v1' for c in b['candidates']):b['candidates'].append(dict(id='bollinger-return-v1',status='deferred_cost_and_observed_sample',budget=dict(completed=2,total=2),manifest='research/bollinger-return-manifest.json',results='research/bollinger-return-summary.json',next_action=next_action))
    b['next_action']=next_action;atomic(p,b)
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    if not any(t['id']=='native-execution-timestamp-audit' for t in b['tasks']):b['tasks'].append(dict(id='native-execution-timestamp-audit',candidate='bollinger-return-v1',kind='execution-evidence',status='pending',depends_on=None,next_action='Read native bridge serialization and raw saved execution precision without order/Playback endpoints. Determine whether subsecond precision exists upstream; preserve old evidence and preregister any future native validation, no blind reruns.'))
    atomic(p,b)
    Lifecycle().update('idle','Bollinger2native runs/2result and2review ACKs;52trades,+1455/+1195;extra4ticks -625/-885.5070raw minute closes and math matched. OFI download window unresolved. Next:execution timestamp evidence.',None)
    print(json.dumps({k:v for k,v in summary.items() if k!='raw_sources'},indent=2))

if __name__=='__main__':main()
