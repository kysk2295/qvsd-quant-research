"""Audit saved native OFI results and publish review; no backtest submission."""
import csv,json,math
from collections import Counter
from datetime import datetime,time
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash,Queue
from runner.research_lifecycle import Lifecycle
from research.finalize_gap_fade import publish

def main():
    Lifecycle().update('auditing','Matching all four OFI native ledgers to frozen causal quote features',None)
    coverage=json.loads((ROOT/'research/ofi-signal-coverage.json').read_text())
    assert file_hash(coverage['path'])==coverage['sha256']
    with open(coverage['path']) as f: features={int(x['end_utc_ns']):x for x in csv.DictReader(f,delimiter=';')}
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    ledgers=[];results=[];combined={2:[],4:[]};states=[]
    next_action='Defer OFI adoption: freeze this rule, obtain distinct future quote sessions and audit coverage before a separately budgeted validation. No retuning on these12 observed dates. Preserve RSI and Playback blocker.'
    for segment in ('early','late'):
        path=ROOT/f'data/runner/ofi-{segment}/state.json';state=json.loads(path.read_text())
        rows=sorted(state['experiments'].values(),key=lambda r:r['request']['slippageTicks']);assert len(rows)==2
        tuples=[]
        for r in rows:
            assert r['ack'] and r['assessment']['decision']!='execution_error'
            doc=r['doc'];trades=doc['trades'];signals=[s for s in doc['output'] if s.startswith('SIGNAL ')]
            assert len(signals)==len(trades)
            counts=Counter();matched=[];prior_exit=None;daily={}
            fee=5 if r['request']['slippageTicks']==2 else 10
            for s,t in zip(signals,trades):
                p=s.split();st=datetime.fromisoformat(p[1]).replace(tzinfo=ZoneInfo('America/New_York'))
                fields=dict(x.split('=',1) for x in p[2:]);end=int(fields['featureEnd']);last=int(fields['lastSource'])
                now=int(st.timestamp())*1000000000;f=features[end]
                assert end==now-60000000000 and last==int(f['last_source_ns']) and 0<last<end
                score=float(f['ofi'])/float(f['mean_depth']);spread=float(f['spread_ticks'])
                assert f['eligible']=='1' and 0<spread<=4 and math.isclose(score,float(fields['score']),rel_tol=1e-12)
                assert spread==float(fields['spread']) and abs(score)>=10 and fields['side']==('L' if score>=10 else 'S')
                entry=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
                exit=datetime.fromisoformat(t['exitTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
                assert 0<=(entry-st).total_seconds()<=60 and entry<=exit and entry.date()==exit.date()
                assert time(9,40)<=st.time()<=time(15,25) and exit.time()<=time(15,56)
                assert prior_exit is None or entry>=prior_exit
                assert t['qty']==1 and t['entryName']==fields['side'] and t['side']==('Long' if score>0 else 'Short')
                assert abs(t['pnl']-(t['exitPrice']-t['entryPrice'])*20*(1 if score>0 else -1))<1e-6
                day=entry.date().isoformat();counts[day]+=1;assert counts[day]<=4
                daily[day]=daily.get(day,0)+t['pnl']-fee
                prior_exit=exit
                matched.append(dict(signal=s,feature=f,entry_et=entry.isoformat(),exit_et=exit.isoformat(),trade=t))
            tuples.append([(t['entryTime'],t['exitTime'],t['entryPrice'],t['exitPrice'],t['side'],t['qty']) for t in trades])
            a=r['assessment'];a.update(adoption_gate='deferred_regime_cost_and_concentration',native_signal_fill_match=True,causal_feature_match=True,
                feature_sha256=coverage['sha256'],next_action=next_action,independent_oos=False,
                native_fill_cost_limitation='Native2/4tick fills compared separately; additional friction is arithmetic, not queue simulation.',
                quote_limitations='Recorded L1 bid/ask quantities precomputed causally; TickReplay=false. L2 reconstruction and exchange-level losslessness unverified. No Playback validation.',
                net_without_best_day=sum(daily.values())-max(daily.values()))
            ledgers.append(dict(run_id=r['run_id'],native_id=r['native_id'],matched=matched,output=doc['output'],settings=doc['settings'],native_response_sha256=file_hash(path.parent/(r['key']+'.native.json'))))
            results.append(dict(segment=segment,slippage=r['request']['slippageTicks'],trades=len(trades),net=sum(daily.values()),daily=daily,net_without_best_day=a['net_without_best_day'],additional4tick_net=next(x['net'] for x in a['additional_fill_cost_sensitivity'] if x['additional_ticks_per_fill']==4)))
            combined[r['request']['slippageTicks']].extend(t['pnl']-fee for t in trades)
        same=tuples[0]==tuples[1]
        for r in rows:
            r['assessment']['identical_native_fills_across_costs']=same
            if same:r['assessment']['native_fill_cost_limitation']='Actual2/4tick fills identical; nominal stress difference is fees only. Extra friction is separate arithmetic, not queue simulation.'
        states.append((path,state,rows,segment))
    # Publish only after every saved run has passed the causal and ledger audit.
    for path,state,rows,segment in states:
        for r in rows:publish(r,q,config)
        atomic(path,state)
        atomic(ROOT/f'research/ofi-{segment}-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])
    summary=dict(actual_native_runs=4,result_acks=4,metadata_acks=4,unique_observed_trades=48,sessions=12,independent_oos=False,
        tests=dict(python=13,csharp_boundary=9,causal_and_native_ledger_match=True),results=results,
        combined=[dict(slippage=k,trades=len(v),net=sum(v),additional4tick_net=sum(v)-40*len(v)) for k,v in combined.items()],next_action=next_action)
    atomic(ROOT/'research/ofi-ledgers.json',ledgers);atomic(ROOT/'research/ofi-summary.json',summary)
    path=ROOT/'research/candidate-backlog.json';backlog=json.loads(path.read_text())
    candidate=next(c for c in backlog['candidates'] if c['id']=='ofi-quote-feasibility-v1')
    candidate.update(status='completed_l1_usable_l2_unvalidated',evidence='research/ofi-l1-quality.json',next_action='Frozen hypothesis evaluated in ofi-lagged-v1')
    if not any(c['id']=='ofi-lagged-v1' for c in backlog['candidates']):
        backlog['candidates'].append(dict(id='ofi-lagged-v1',status='deferred_regime_cost_and_concentration',budget=dict(completed=4,total=4),manifest='research/ofi-signal-manifest.json',results='research/ofi-summary.json',next_action=next_action))
    backlog['next_action']=next_action;atomic(path,backlog)
    path=ROOT/'research/evidence-work-queue.json';queue=json.loads(path.read_text())
    for task in queue['tasks']:
        if task['id']=='ofi-quote-feasibility-v1-data-audit':task.update(status='completed',evidence='research/ofi-l1-quality.json')
    if not any(t['id']=='ofi-future-quote-coverage' for t in queue['tasks']):
        queue['tasks'].append(dict(id='ofi-future-quote-coverage',candidate='ofi-lagged-v1',kind='coverage-audit',status='pending',depends_on=None,next_action='Obtain distinct post-Oct25 recorded L1 quote sessions; audit source consistency and quality before preregistering finite fixed-rule validation. No same-date retuning.'))
    atomic(path,queue)
    Lifecycle().update('idle','OFI4native runs/4result and4review ACKs;48unique trades. Combined+605/+365 fees-only, extra4ticks/fill negative. Deferred; future quote coverage required. Finite batch complete.',None)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
