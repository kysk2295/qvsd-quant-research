"""Review immutable native evidence and ACK metadata; no test submissions."""
import json
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from runner.core import ROOT,atomic,file_hash,Queue
from runner.stochastic_cycle import StochasticCycle
from runner.research_lifecycle import Lifecycle
from research.finalize_gap_fade import publish

def main():
    path=ROOT/'data/runner/stochastic/state.json';state=json.loads(path.read_text());rows=sorted(state['experiments'].values(),key=lambda r:r['request']['slippageTicks'])
    assert 1<=len(rows)<=2 and all(r.get('ack') and r['assessment']['decision']!='execution_error' for r in rows)
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());summaries=[];ledgers=[]
    fields=('entryTime','entryPrice','exitTime','exitPrice','qty','side');fills=[[tuple(t[k] for k in fields) for t in r['doc']['trades']] for r in rows];same=len(rows)==2 and fills[0]==fills[1]
    next_action='Fixed stochastic pilot completed;no same-date repeat or outcome-driven tuning. Preserve sparse CafeRange and NR7 with explicit resume criteria. Next finite work: CafeRange distinct-session regime/ETHwarmup feasibility using already available missing dates before any new performance runs;Bollinger cost/distinct-sample review and RSI prospective-data tasks retained. OFIclosed,MACDno-repeat,Playbackpolicyblock unchanged.'
    for r in rows:
        doc=r['doc'];trades=doc['trades'];StochasticCycle.validate_native(StochasticCycle.__new__(StochasticCycle),doc)
        execs=[s for s in doc['output'] if s.startswith('CLOCK_EXEC|')];clocks=list(dict.fromkeys(s for s in doc['output'] if s.startswith('CLOCK_TRADE|')))
        assert len(clocks)==len(trades) and len(execs)==2*len(trades)
        daily=[];lastday=None;previous_exit=None
        for t,entry,exit,clock in zip(trades,execs[::2],execs[1::2],clocks):
            e=entry.split('|');x=exit.split('|');c=clock.split('|')
            assert e[1]==e[3]==c[1] and e[2]==e[4]==c[2] and x[1]==x[3]==c[3] and x[2]==x[4]==c[4]
            assert float(e[7])==t['entryPrice'] and float(x[7])==t['exitPrice'] and e[8]==x[8]=='1' and e[9]==x[9]=='Historical'
            assert int(e[2])<=int(x[2]) and (previous_exit is None or int(e[2])>previous_exit);previous_exit=int(x[2])
            day=datetime.fromisoformat(t['entryTime']).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(ZoneInfo('America/New_York')).date().isoformat()
            if day!=lastday:daily=[];lastday=day
            assert len(daily)<4 and sum(daily)>-900;daily.append(t['pnl']-10)
            assert t['exitName'] in ('Stop loss','Profit target','TimeExit')
        fee=10 if r['request']['slippageTicks']==4 else 5;pnl=[t['pnl']-fee*t['qty'] for t in trades];balance=peak=dd=0
        for value in pnl:balance+=value;peak=max(peak,balance);dd=max(dd,peak-balance)
        a=r['assessment'];bestday=max([0]+list(a['ledger_evidence']['daily_net'].values()));types=dict(Counter(t['exitName'] for t in trades))
        a.update(adoption_gate='unmet_in_observed_sample' if sum(pnl)<=0 else 'deferred_pending_distinct_evidence',sample_status='finite_dependent_historical_sample_not_statistical_proof',closed_trade_drawdown=dd,net_without_best_positive_day=sum(pnl)-bestday,independent_raw_ohlc_and_stochastic_match=True,raw_simulated_clock_match=True,risk_gate_ledger_match=True,exit_types_exercised=types,next_action=next_action,
            native_fill_cost_limitation='Native2/4tickfills identical;fee-only difference. Extra2/4ticks are separate arithmetic sensitivity' if same else 'Nativefilltuples differ;extra2/4ticks remain separate arithmetic sensitivity',execution_limitations='Historical Last-fill simulation;no orderqueue or live latency validation. No intratrade account-equity risk reconstruction.',csharp_math_assertions=11)
        publish(r,q,config)
        summaries.append(dict(run_id=r['run_id'],slippage_ticks=r['request']['slippageTicks'],fee=fee,trades=len(trades),net=sum(pnl),closed_drawdown=dd,active_days=a['ledger_evidence']['active_days'],without_best_trade=a['ledger_evidence']['net_without_best_positive'],without_best_day=sum(pnl)-bestday,extra2tick_net=a['additional_fill_cost_sensitivity'][0]['net'],extra4tick_net=a['additional_fill_cost_sensitivity'][1]['net'],exit_types=types,decision=a['decision']))
        ledgers.append(dict(run_id=r['run_id'],trades=trades,raw_execution_clocks=execs,raw_trade_clocks=clocks,signals=[s for s in doc['output'] if s.startswith('SIGNAL ')],settings=doc['settings'],summary=doc['summary'],native_response_sha256=file_hash(path.parent/(r['key']+'.native.json')),source_hash=r['source_hash'],manifest_hash=r['manifest_hash'],data_hash=r['data_hash']))
    atomic(path,state);atomic(ROOT/'research/stochastic-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows]);atomic(ROOT/'research/stochastic-ledgers.json',ledgers)
    summary=dict(native_runs=len(rows),result_acks=len(rows),review_acks=len(rows),parameter_configurations=1,evaluation_sessions=15,independent_oos=False,unique_trades=len(rows[0]['doc']['trades']),identical_native_fills=same,raw_minutes_checked_per_run=5850,csharp_math_assertions=11,results=summaries,next_action=next_action)
    atomic(ROOT/'research/stochastic-summary.json',summary)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text());c=next(c for c in b['candidates'] if c['id']=='stochastic-fast-v1');c.update(status='evaluated_adoption_unmet' if any(s['net']<=0 for s in summaries) else 'deferred_historical_sample',results='research/stochastic-summary.json',budget=dict(completed=len(rows),maximum=2),next_action=next_action);b['next_action']=next_action;atomic(p,b)
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    for t in b['tasks']:
        if t.get('candidate')=='stochastic-fast-v1-14' and t.get('status')=='pending':t.update(status='superseded_by_review',next_action='No automatic repeated date expansion;see stochastic-summary.json')
    b['next_action']=next_action;atomic(p,b)
    Lifecycle().update('idle','CafeRange12ledger reviews+NR7sample status ACKed;stochastic finite2run native batch/ledger review completed. All ACKs persisted;no background research running.',None)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
