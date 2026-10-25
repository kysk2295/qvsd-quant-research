"""Audit completed native runs and publish evidence; never submit backtests."""
import json
from runner.core import ROOT,atomic,file_hash,Queue
from runner.nr7_extension_cycle import Nr7ExtensionCycle
from runner.research_lifecycle import Lifecycle
from research.finalize_gap_fade import publish

def main():
    path=ROOT/'data/runner/nr7-history-extension/state.json';state=json.loads(path.read_text())
    rows=sorted(state['experiments'].values(),key=lambda r:r['request']['slippageTicks'])
    coverage=json.loads((ROOT/'research/nr7-history-extension-coverage.json').read_text())
    qualified=[s['date'] for s in coverage['setups'] if s['qualified']]
    assert len(rows)==(2 if qualified else 1)
    next_action='Finite NR7 historical extension completed;retain fixed rules and sparse-sample limitation. No routine same-window rerun or outcome-driven tuning. Review preserved CafeRange broader-regime/constraint coverage plan and Bollinger cost/distinct-sample plan;RSI awaits post-Oct25 data. OFI extension campaign closed;MACD no-repeat;Playback policy block unchanged.'
    summaries=[];ledgers=[];q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    fields=('entryTime','entryPrice','exitTime','exitPrice','qty','side')
    tuples=[[tuple(t[k] for k in fields) for t in r['doc']['trades']] for r in rows]
    same=len(tuples)==2 and tuples[0]==tuples[1]
    for r in rows:
        assert r['ack'] and r['assessment']['decision']!='execution_error'
        Nr7ExtensionCycle.validate_native(Nr7ExtensionCycle.__new__(Nr7ExtensionCycle),r['doc'])
        doc=r['doc'];trades=doc['trades'];fee=10 if r['request']['slippageTicks']==4 else 5
        clock_exec=[x for x in doc['output'] if x.startswith('CLOCK_EXEC|')]
        clock_trade=list(dict.fromkeys(x for x in doc['output'] if x.startswith('CLOCK_TRADE|')))
        assert len(clock_trade)==len(trades) and len(clock_exec)==2*len(trades)
        for t,entry,exit,ct in zip(trades,clock_exec[::2],clock_exec[1::2],clock_trade):
            e=entry.split('|');x=exit.split('|');c=ct.split('|')
            assert e[1]==e[3]==c[1] and e[2]==e[4]==c[2]
            assert x[1]==x[3]==c[3] and x[2]==x[4]==c[4]
            assert float(e[7])==t['entryPrice'] and float(x[7])==t['exitPrice'] and e[8]==x[8]=='1'
            assert int(x[2])>=int(e[2]) and e[9]==x[9]=='Historical'
        pnl=[t['pnl']-fee*t['qty'] for t in trades];balance=peak=dd=0
        for value in pnl:balance+=value;peak=max(peak,balance);dd=max(dd,peak-balance)
        a=r['assessment'];a.update(adoption_gate='unmet_in_observed_sample' if trades else 'not_evaluable_condition_absent',sample_role='historical_extension_not_independent_oos',qualified_sessions=len(qualified),evaluation_sessions=7,warmup_sessions=7,native_daily_context_match=True,independent_minute_signal_match=True,raw_simulated_clock_match=True,closed_trade_drawdown=dd,next_action=next_action,
            hypothesis_inference='One finite historical window cannot establish or reject a strategy family;cost variants are not independent observations',
            native_fill_cost_limitation='2/4tick native fill tuples identical;difference is assumed fees only;additional friction is separate arithmetic sensitivity' if same else 'Compare actual native fills;additional friction is separate arithmetic sensitivity',
            execution_limitations='Historical simulated timestamps only;no live routing latency or queue validation. Only exit types observed in ledger were exercised;unrealized drawdown not reconstructed.',
            backlog_audit='research/preserved-candidate-audit.json')
        publish(r,q,config)
        daily=a['ledger_evidence']['daily_net'];best=max([0]+list(daily.values()))
        summaries.append(dict(run_id=r['run_id'],slippage_ticks=r['request']['slippageTicks'],roundtrip_fee=fee,trades=len(trades),net=sum(pnl),closed_drawdown=dd,net_without_best_positive_day=sum(pnl)-best,additional2tick_net=a['additional_fill_cost_sensitivity'][0]['net'],additional4tick_net=a['additional_fill_cost_sensitivity'][1]['net'],decision=a['decision']))
        ledgers.append(dict(run_id=r['run_id'],trades=trades,output=doc['output'],settings=doc['settings'],summary=doc['summary'],raw_execution_clocks=clock_exec,raw_trade_clocks=clock_trade,native_response_sha256=file_hash(path.parent/(r['key']+'.native.json')),source_hash=r['source_hash'],data_hash=r['data_hash'],manifest_hash=r['manifest_hash']))
    atomic(path,state)
    atomic(ROOT/'research/nr7-history-extension-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in rows])
    atomic(ROOT/'research/nr7-history-extension-ledgers.json',ledgers)
    summary=dict(native_runs=len(rows),maximum_registered_runs=2,result_acks=len(rows),review_acks=len(rows),evaluation_sessions=7,warmup_sessions=7,qualified_dates=qualified,unique_trades=len(rows[0]['doc']['trades']),identical_native_fills=same,independent_oos=False,all_context_and_signal_checks_passed=True,results=summaries,original_evaluation_sessions=8,combined_distinct_evaluation_sessions=15,original_runs_repeated=0,limitation='Only one NR7-qualified day in15distinct evaluated sessions;insufficient regime/sample evidence. Sep28-Oct1 native minute context not independently raw-tick reconciled.',next_action=next_action)
    atomic(ROOT/'research/nr7-history-extension-summary.json',summary)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text())
    candidate=dict(id='nr7-history-extension-v1',status='evaluated_adoption_gate_unmet' if any(s['net']<0 for s in summaries) else 'deferred_sparse_sample',manifest='research/nr7-history-extension-manifest.json',results='research/nr7-history-extension-summary.json',budget=dict(completed=len(rows),maximum=2),next_action=next_action)
    assert not any(x['id']==candidate['id'] for x in b['candidates'])
    b['candidates'].append(candidate);b['next_action']=next_action;atomic(p,b)
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    for t in b['tasks']:
        if t['id']=='nr7-prior-rth-coverage':t.update(status='completed',evidence='research/nr7-history-extension-coverage.json',next_action='Contiguous Sep23-Oct1 warmup completed;Sep21-22 unnecessary for this finite evaluation')
        if t.get('candidate')=='nr7-history-extension-v1-7' and t.get('status')=='pending':t.update(status='superseded_by_review',next_action=next_action)
    b['next_action']=next_action;atomic(p,b)
    Lifecycle().update('idle','NR7 extension complete:7new historical sessions,1qualified day;native results and review ACKs saved. No background loop. CafeRange/Bollinger reviews preserved;OFIclosed.',None)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
