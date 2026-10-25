"""Publish audited native evidence; never submits or reruns a backtest."""
import json,hashlib
from collections import Counter
from runner.core import ROOT,atomic,file_hash,Queue
from runner.research_lifecycle import Lifecycle
from dashboard.reporter import post,emit
from dashboard.server import validate_run

def main():
    folder=ROOT/'data/runner/moving-momentum';path=folder/'state.json'
    state=json.loads(path.read_text());audits=json.loads((ROOT/'research/moving-momentum-trace-audit.json').read_text())
    byid={r['run_id']:r for r in audits};q=Queue()
    config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    next_action='Reject this fixed Moving Momentum setting on the observed sample; retain sparse-sample uncertainty, do not retune or rerun. Prioritize a distinct causal hypothesis. RSI remains deferred pending future fixed-rule data; Playback policy blocker unchanged.'
    rows=[];ledgers=[];summaries=[]
    for r in sorted(state['experiments'].values(),key=lambda x:x['request']['slippageTicks']):
        audit=byid[r['run_id']];assert audit['checks_passed'] and r['ack']
        a=r['assessment'];a['next_action']=next_action
        a['data_coverage']['note']='Scheduled ETH coverage and200preceding intervals passed; native RTH and warmup audits passed. Presence is not lossless tick coverage.'
        a['causal_trace_audit']=dict(passed=True,trace_rows=audit['trace_rows'],matched_signals=audit['signals'],evidence='research/moving-momentum-trace-audit.json')
        a['sample_limitation']='4trades on3of12observed sessions; all filled entries long. Short setup boundary tested synthetically, no native short execution observed. No OOS or Replay validation.'
        fee=10 if r['request']['slippageTicks']==4 else 5
        pnls=[t['pnl']-fee*t['qty'] for t in r['doc']['trades']]
        gains=sum(p for p in pnls if p>0);losses=-sum(p for p in pnls if p<0)
        balance=peak=dd=0
        for p in pnls:balance+=p;peak=max(peak,balance);dd=max(dd,peak-balance)
        a['after_fee_profit_factor']=gains/losses if losses else None;a['closed_trade_drawdown']=dd
        a['native_fill_cost_limitation']='Requested2/4tick settings yielded identical actual fill tuples; fee-only difference. Arithmetic additional fill-cost scenarios separate.'
        segments={}
        for name,lo,hi in [('Oct7-9','2026-10-07','2026-10-09'),('Oct12-16','2026-10-12','2026-10-16'),('Oct19-22','2026-10-19','2026-10-22')]:
            segments[name]=sum(v for d,v in a['ledger_evidence']['daily_net'].items() if lo<=d<=hi)
        a['descriptive_segments']=segments
        counts=Counter()
        for values in a['condition_counts'].values():counts.update(values)
        snap=q.telemetry/(hashlib.sha256(r['run_id'].encode()).hexdigest()+'.json')
        run=json.loads(snap.read_text());run['params']['assessment']=a
        validate_run(run);emit(run,q.telemetry)
        ack=post(config['url'],'/api/runs',run,config['token']);assert ack.get('ok') is True
        q.control('ack:'+snap.name,file_hash(snap))
        rows.append({k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')})
        ledgers.append(dict(run_id=r['run_id'],native_id=r['native_id'],settings=r['doc']['settings'],summary=r['doc']['summary'],trades=r['doc']['trades'],
            audit_output=[x for x in r['doc']['output'] if not x.startswith('TRACE ')],ack=True))
        summaries.append(dict(run_id=r['run_id'],trades=len(pnls),net=sum(pnls),profit_factor=a['after_fee_profit_factor'],closed_drawdown=dd,
            active_sessions=a['ledger_evidence']['active_days'],condition_counts=dict(counts),segments=segments,
            additional4tick_net=next(x['net'] for x in a['additional_fill_cost_sensitivity'] if x['additional_ticks_per_fill']==4)))
    atomic(path,state);atomic(ROOT/'research/moving-momentum-results.json',rows);atomic(ROOT/'research/moving-momentum-ledgers.json',ledgers)
    summary=dict(actual_native_runs=2,result_acks=2,metadata_acks=2,parameter_configurations=1,evaluation_sessions=12,independent_oos=False,
        tests=dict(csharp_state_boundary_assertions=13,python_protocol_tests=8,native_signal_fill_match=True),results=summaries,replay_runs=0,next_action=next_action)
    atomic(ROOT/'research/moving-momentum-summary.json',summary)
    backlog=json.loads((ROOT/'research/candidate-backlog.json').read_text());candidate=next(c for c in backlog['candidates'] if c['id']=='moving-momentum-v1')
    candidate.update(status='evaluated_performance_fail',priority=20,results='research/moving-momentum-results.json',next_action=next_action,budget=dict(completed=2,total=2),reason='After-fee -35/-55,4trades on3of12sessions; added4ticks/fill stress -215. No selection or retuning.')
    backlog['next_action']=next_action;atomic(ROOT/'research/candidate-backlog.json',backlog)
    Lifecycle().update('idle','Completed Moving Momentum2native runs/2ACKs:4trades,-35/-55net;trace audit passed. Fixed setting rejected; RSI deferred; Playback blocked. No background process.',None)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
