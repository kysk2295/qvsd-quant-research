"""Audit new historical day, preserve raw simulation times, aggregate unique days."""
import csv,json,math
from datetime import datetime,time
from zoneinfo import ZoneInfo
import numpy as np
import pyarrow.parquet as pq
from runner.core import ROOT,atomic,Queue,file_hash
from research.finalize_gap_fade import publish
from runner.research_lifecycle import Lifecycle

def main():
    c=json.loads((ROOT/'research/ofi-oct2-coverage.json').read_text());assert file_hash(c['path'])==c['sha256']
    with open(c['path']) as f:features={int(x['end_utc_ns']):x for x in csv.DictReader(f,delimiter=';')}
    p=ROOT/'data/runner/ofi-oct2/state.json';state=json.loads(p.read_text());rows=sorted(state['experiments'].values(),key=lambda r:r['request']['slippageTicks']);assert len(rows)==2
    parts={0:[],1:[],2:[]}
    for b in pq.ParquetFile(ROOT/'data/incoming/replay/2026/NQ-2026_L1/20261002.parquet').iter_batches(batch_size=500000,columns=['Timestamp','MarketDataType','Price','Volume']):
        ts=b.column(0).cast('int64').to_numpy();kind=b.column(1).to_numpy();price=b.column(2).to_numpy();size=b.column(3).to_numpy()
        for side in parts:
            mask=kind==side;parts[side].append((ts[mask],price[mask],size[mask]))
    arrays={s:tuple(np.concatenate([x[i] for x in a]) for i in range(3)) for s,a in parts.items()}
    def event(line):
        x=line.split('|');ticks=int(x[2]);target=(ticks-621355968000000000)*100-9*3600*10**9;price=float(x[7]);assert ticks==int(x[4]) and x[9]=='Historical'
        ts,prices,_=arrays[2];lo=np.searchsorted(ts,target,'left');hi=np.searchsorted(ts,target,'right')
        book={}
        for side,label in ((0,'ask'),(1,'bid')):
            st,sp,sv=arrays[side];i=np.searchsorted(st,target,'left')-1;assert i>=0
            book[label]=dict(price=float(sp[i]),size=int(sv[i]),age_ns=target-int(st[i]),same_timestamp_events=int(np.searchsorted(st,target,'right')-np.searchsorted(st,target,'left')))
        return dict(raw=line,ticks=ticks,utc_ns=target,local=x[1],name=x[6],price=price,exact_last_price_match=bool(np.any(prices[lo:hi]==price)),prior_book=book,spread_ticks=(book['ask']['price']-book['bid']['price'])/.25)
    ledgers=[];fills=[]
    for r in rows:
        assert r['ack'] and r['assessment']['decision']!='execution_error';d=r['doc'];trades=d['trades'];signals=[s for s in d['output'] if s.startswith('SIGNAL ')];execs=[event(s) for s in d['output'] if s.startswith('CLOCK_EXEC|')];clock=[s.split('|') for s in d['output'] if s.startswith('CLOCK_TRADE|')]
        assert len(signals)==len(trades)==len(clock)==4 and len(execs)==8;matched=[];previous=None
        for i,(s,t) in enumerate(zip(signals,trades)):
            x=s.split();v=dict(z.split('=',1) for z in x[2:]);st=datetime.fromisoformat(x[1]).replace(tzinfo=ZoneInfo('America/New_York'));end=int(v['featureEnd']);f=features[end];last=int(v['lastSource']);score=float(f['ofi'])/float(f['mean_depth'])
            assert end==int(st.timestamp())*10**9-60*10**9 and 0<last<end and last==int(f['last_source_ns']) and f['eligible']=='1'
            assert math.isclose(score,float(v['score']),rel_tol=1e-12) and abs(score)>=10 and 0<float(v['spread'])<=4 and float(v['spread'])==float(f['spread_ticks'])
            assert v['side']==('L' if score>0 else 'S') and t['entryName']==v['side'] and t['side']==('Long' if score>0 else 'Short') and t['qty']==1
            en,ex=execs[2*i:2*i+2];assert en['ticks']==int(clock[i][2]) and ex['ticks']==int(clock[i][4])
            assert en['local'][:19]==t['entryTime'] and ex['local'][:19]==t['exitTime'] and en['price']==t['entryPrice'] and ex['price']==t['exitPrice']
            assert 0<=en['utc_ns']-int(st.timestamp())*10**9<=60*10**9 and en['utc_ns']<=ex['utc_ns'] and (previous is None or en['utc_ns']>=previous);previous=ex['utc_ns']
            assert time(9,40)<=st.time()<=time(15,25) and st.date().isoformat()=='2026-10-02'
            assert abs(t['pnl']-(t['exitPrice']-t['entryPrice'])*20*(1 if score>0 else -1))<1e-6
            matched.append(dict(signal=s,feature=f,trade=t,precise_entry=en,precise_exit=ex))
        fills.append([(t['entryTime'],t['exitTime'],t['entryPrice'],t['exitPrice'],t['side']) for t in trades])
        ledgers.append(dict(run_id=r['run_id'],native_id=r['native_id'],matched=matched,output=d['output'],settings=d['settings'],native_response_sha256=file_hash(p.parent/(r['key']+'.native.json'))))
    assert fills[0]==fills[1]
    aggregates=[]
    for slip in (2,4):
        fee=5 if slip==2 else 10;alltrades=[];dates=set();daily={}
        for folder in ('ofi-early','ofi-late','ofi-oct6','ofi-oct5','ofi-oct2'):
            s=json.loads((ROOT/f'data/runner/{folder}/state.json').read_text());r=next(r for r in s['experiments'].values() if r['request']['slippageTicks']==slip)
            groupdates=set()
            for t in r['doc']['trades']:
                day=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York')).date().isoformat();groupdates.add(day);daily[day]=daily.get(day,0)+t['pnl']-fee;alltrades.append(t)
            assert not dates&groupdates;dates|=groupdates
        alltrades.sort(key=lambda t:t['exitTime']);balance=peak=dd=0
        for t in alltrades:balance+=t['pnl']-fee;peak=max(peak,balance);dd=max(dd,peak-balance)
        assert len(alltrades)==60 and len(dates)==15
        aggregates.append(dict(slippage=slip,unique_trades=60,sessions=15,net=balance,daily=daily,closed_drawdown=dd,net_without_best_day=balance-max(daily.values()),additional2tick_net=balance-20*60,additional4tick_net=balance-40*60,additional_ticks_per_fill_break_even=balance/(10*60)))
    high=next(a for a in aggregates if a['slippage']==4)
    assert high['additional4tick_net']<=0 or high['net_without_best_day']<=0
    next_action='Current fixed OFI historical-extension campaign ends under preregistered cost/concentration gate. No more routine date additions or retuning on these15sessions. Preserve evidence; reopen only for distinct preregistered research question/regime. Execute separately preregistered MACD cross2run batch; preserve RSI/Bollinger backlog.'

    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    for r in rows:
        r['assessment'].update(adoption_gate='unmet_campaign_closed',causal_feature_match=True,exclusion_audit='research/ofi-oct2-exclusions.json',native_signal_fill_match=True,raw_simulated_timestamps_preserved=True,independent_oos=False,identical_native_fills_across_costs=True,
            native_fill_cost_limitation='Native2/4tick fills identical; difference is external fees. Additional ticks are arithmetic incremental adverse cost. No double subtraction of spread.',execution_limitations='Raw simulated times retained, not real routing latency; strict-prior quotes cannot establish same-timestamp execution order or queue fills.',combined_unique_sample=next(a for a in aggregates if a['slippage']==r['request']['slippageTicks']),next_action=next_action)
        publish(r,q,config)
    atomic(p,state);atomic(ROOT/'research/ofi-oct2-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows]);atomic(ROOT/'research/ofi-oct2-ledgers.json',ledgers)
    summary=dict(native_runs_this_batch=2,total_ofi_native_runs=10,parameter_configurations=1,result_acks=2,review_acks=2,new_unique_trades=4,unique_trades_total=60,sessions_total=15,independent_oos=False,eligible_minutes=383,excluded_minutes=7,results=[dict(slippage=r['request']['slippageTicks'],net=r['assessment']['net_after_assumed_fee'],trades=4) for r in rows],aggregate=aggregates,next_action=next_action)
    atomic(ROOT/'research/ofi-oct2-summary.json',summary)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text());c=next(c for c in b['candidates'] if c['id']=='ofi-lagged-v1');c.update(status='historical_campaign_closed_adoption_unmet',unique_trades=60,sessions=15,total_native_runs=10,latest_evidence='research/ofi-oct2-summary.json',next_action=next_action);b['next_action']=next_action;atomic(p,b)
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    for t in b['tasks']:
        if t['id']=='ofi-oct2-fixed-extension':t.update(status='completed',evidence='research/ofi-oct2-summary.json')
    atomic(p,b)
    Lifecycle().update('reviewing','OFI final extension complete;15sessions/60unique trades,10native cost runs. Campaign stopped under cost/concentration gate; MACD distinct batch in progress.',None)

    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
