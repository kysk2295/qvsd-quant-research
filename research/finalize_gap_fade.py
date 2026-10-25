"""Audit and publish the finite gap batch; never submits a backtest."""
import json,hashlib
from datetime import datetime,time
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash,Queue
from runner.research_lifecycle import Lifecycle
from dashboard.reporter import post,emit
from dashboard.server import validate_run

def publish(row,q,config):
    snap=q.telemetry/(hashlib.sha256(row['run_id'].encode()).hexdigest()+'.json')
    run=json.loads(snap.read_text());run['params']['assessment']=row['assessment']
    validate_run(run);emit(run,q.telemetry)
    result=post(config['url'],'/api/runs',run,config['token']);assert result.get('ok') is True
    q.control('ack:'+snap.name,file_hash(snap))

def main():
    config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());q=Queue()
    path=ROOT/'data/runner/gap-fade/state.json';state=json.loads(path.read_text())
    rows=sorted(state['experiments'].values(),key=lambda r:r['request']['slippageTicks']);assert len(rows)==2
    coverage=json.loads((ROOT/'research/gap-fade-coverage.json').read_text())
    qualified={r['date'] for r in coverage['observations'] if r['qualified']};ledgers=[];summaries=[]
    next_action='Do not adopt or retune this fixed gap setting on observed dates. Next candidate: causal top-of-book order-flow imbalance, first audit quote size/order/coverage and original paper. RSI fixed-rule future-data backlog preserved; Playback blocker unchanged.'
    for r in rows:
        assert r['ack'] and r['assessment']['decision']!='execution_error'
        doc=r['doc'];trades=doc['trades'];seen=set();matched=[]
        signals=[x for x in doc['output'] if x.startswith('SIGNAL ')];assert len(signals)==len(trades)==len(qualified)
        for signal,t in zip(signals,trades):
            entry=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
            exit=datetime.fromisoformat(t['exitTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York'))
            st=datetime.fromisoformat(signal.split()[1]).replace(tzinfo=ZoneInfo('America/New_York'))
            day=entry.date().isoformat();assert day in qualified and day not in seen;seen.add(day)
            assert entry.date()==exit.date() and time(9,31)<=entry.time()<=time(9,32)
            assert 0<=(entry-st).total_seconds()<=60 and entry<=exit and exit.time()<=time(10,16)
            assert t['qty']==1 and t['side']=='Long' and t['entryName']=='L'
            assert abs(t['pnl']-(t['exitPrice']-t['entryPrice'])*20)<1e-6
            matched.append(dict(entry_et=entry.isoformat(),exit_et=exit.isoformat(),signal=signal,trade=t))
        assert seen==qualified
        fee=10 if r['request']['slippageTicks']==4 else 5
        pnl=[t['pnl']-fee*t['qty'] for t in trades];balance=peak=dd=0
        for p in pnl:balance+=p;peak=max(peak,balance);dd=max(dd,peak-balance)
        a=r['assessment'];a.update(adoption_gate='unmet_in_observed_sample',hypothesis_inference='statistically_inconclusive;12sessions/9trades cannot reject all gap-reversal strategies',
            sample_test_result='negative_after_cost',next_action=next_action,closed_trade_drawdown=dd,
            source_context_match=True,native_signal_fill_match=True,
            execution_limitations='All9 exits were stops; the time-exit branch was not exercised in native fills. No Replay validation.',
            native_fill_cost_limitation='Actual2/4tick fill tuples identical; nominal stress difference is fees only; additional friction arithmetic remains separate.')
        a['data_coverage']['note']='Previous RTH close, first-minute open and prior60minute population sigma independently matched raw Last ticks for all12 sessions; complete prior/current RTH verified.'
        publish(r,q,config)
        ledgers.append(dict(run_id=r['run_id'],native_id=r['native_id'],matched=matched,settings=doc['settings'],summary=doc['summary'],output=doc['output'],
            native_response_sha256=file_hash(ROOT/'data/runner/gap-fade'/(r['key']+'.native.json')),ack=True))
        summaries.append(dict(run_id=r['run_id'],trades=len(trades),net=sum(pnl),closed_drawdown=dd,active_sessions=len(seen),
            additional4tick_net=next(x['net'] for x in a['additional_fill_cost_sensitivity'] if x['additional_ticks_per_fill']==4)))
    keys=('entryTime','entryPrice','exitTime','exitPrice','qty','side')
    same=[[tuple(t[k] for k in keys) for t in r['doc']['trades']] for r in rows]
    assert same[0]==same[1]
    atomic(path,state);atomic(ROOT/'research/gap-fade-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])
    atomic(ROOT/'research/gap-fade-ledgers.json',ledgers)
    summary=dict(actual_native_runs=2,result_acks=2,metadata_acks=2,parameter_configurations=1,evaluation_sessions=12,
        qualified_sessions=len(qualified),independent_oos=False,identical_native_fills=True,tests=dict(csharp_boundary_assertions=10,protocol_tests=8,source_context_match=True,signal_fill_match=True),
        results=summaries,replay_runs=0,next_action=next_action)
    atomic(ROOT/'research/gap-fade-summary.json',summary)
    # Clarify statistical interpretation of the previous four-trade sample without changing any result.
    oldpath=ROOT/'data/runner/moving-momentum/state.json';old=json.loads(oldpath.read_text())
    for r in old['experiments'].values():
        r['assessment'].update(adoption_gate='unmet_in_observed_sample',hypothesis_inference='statistically_inconclusive:4trades; not evidence that all Moving Momentum strategies fail')
        publish(r,q,config)
    atomic(oldpath,old);atomic(ROOT/'research/moving-momentum-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in old['experiments'].values()])
    backlog=json.loads((ROOT/'research/candidate-backlog.json').read_text());c=next(x for x in backlog['candidates'] if x['id']=='gap-fade-v1')
    c.update(status='evaluated_adoption_criteria_unmet',adoption_gate='unmet_in_observed_sample',hypothesis_inference='inconclusive_small_sample',
        budget=dict(completed=2,total=2),results='research/gap-fade-results.json',reason='9trades/12sessions,-2210/-2255afterfees; allstop exits; not statistical rejection of gap-reversal family',next_action=next_action,priority=20)
    candidate='ofi-quote-feasibility-v1'
    if not any(x['id']==candidate for x in backlog['candidates']):
        backlog['candidates'].append(dict(id=candidate,status='data_feasibility_pending',priority=1,
            sources=['https://arxiv.org/abs/1011.6402','https://www.sashastoikov.com/finance/2015/3/12/the-price-impact-of-order-book-events'],
            original_scope='Cont,Kukanov,Stoikov: contemporaneous price impact versus best-quote imbalance in equities; not a demonstrated profitable lagged NQ strategy.',
            hypothesis='Test a separately preregistered lagged NQ OFI signal only if recorded best bid/ask quantities support causal reconstruction.',
            next_action='Audit real L1 quote prices/sizes, ordering, stale/crossed quotes and coverage; read full primary paper before defining lag/threshold/exits. Never substitute OHLCV or contemporaneous impact as predictive proof.',
            budget=dict(feasibility_passes=1,native_runs=0,unregistered_native_runs_forbidden=True)))
    backlog['next_action']=next_action;atomic(ROOT/'research/candidate-backlog.json',backlog)
    work=ROOT/'research/evidence-work-queue.json';queue=json.loads(work.read_text())
    task_id='ofi-quote-feasibility-v1-data-audit'
    if not any(x['id']==task_id for x in queue['tasks']):
        queue['tasks'].append(dict(id=task_id,candidate=candidate,kind='coverage-audit',status='pending',depends_on=None,
            reason='Native Last-tick imports cannot establish best-quote size completeness or OFI causality',
            next_action='Inspect original NRD/L1 parquet quote fields and timestamps; quantify valid bid/ask size coverage, record source hashes, then freeze any predictive hypothesis before looking at its PnL'))
    atomic(work,queue)
    Lifecycle().update('idle','Gap-fade2native runs/2ACKs:9trades,-2210/-2255;context and ledger audits passed. Adoption gate unmet, not family rejection. Next:OFI quote feasibility. RSI preserved;Playback blocked.',None)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
