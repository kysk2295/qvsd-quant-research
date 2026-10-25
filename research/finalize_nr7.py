"""Publish condition-absent functional validation, not zero-profit success."""
import json
from runner.core import ROOT,atomic,file_hash,Queue
from runner.nr7_cycle import Nr7Cycle
from runner.research_lifecycle import Lifecycle
from research.finalize_gap_fade import publish

def main():
    coverage=json.loads((ROOT/'research/nr7-rth-coverage.json').read_text());assert len(coverage['sessions'])==15 and len(coverage['setups'])==8 and not any(s['qualified'] for s in coverage['setups'])
    p=ROOT/'data/runner/nr7-rth/state.json';state=json.loads(p.read_text());assert len(state['experiments'])==1;r=next(iter(state['experiments'].values()));doc=r['doc']
    assert r['ack'] and r['assessment']['decision']!='execution_error';Nr7Cycle.validate_native(Nr7Cycle.__new__(Nr7Cycle),doc)
    assert not doc['trades'] and not any(s.startswith('SIGNAL ') for s in doc['output'])
    next_action='NR7 daily-session adaptation is deferred because8evaluationdays contain zero qualifying prior-day setups; not evidence of profitability or failure. Preserve7day lookback and strict tie rule. Next bounded data task: audit/acquire9adjacent preceding RTHsessions Sep21-Oct1 in chunks<=3downloads, no native experiments until coverage and new evaluation dates are preregistered. Do not substitute intraday7bars or unverified ETHdaily records. OFI campaign stays closed; MACD no-repeat; RSI/Bollinger preserved.'
    r['assessment'].update(decision='condition_mismatch',reason='Zero NR7 setup days in8eligible evaluation sessions; performance not evaluable',adoption_gate='not_evaluable_condition_absent',sample_role='functional_context_validation_only',qualified_sessions=0,evaluation_sessions=8,warmup_sessions=7,native_daily_context_match=True,independent_oos=False,
        source_scope='ChartSchool published previous-NR-day breakout interpretation; Crabel book not directly verified; NQ RTHdaily aggregation explicitly adapted.',
        execution_limitations='No entry/stop/exit was exercised by native trades.10pure-math assertions passed but do not establish execution behavior. HighTick1 settings read back; no fill-cost comparison possible with zero trades.',
        cost_evidence='Zero trades; fee and slippage sensitivities are not empirically evaluable. Second cost run skipped under pre-execution coverage condition.',next_action=next_action)
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());publish(r,q,config)
    atomic(p,state);atomic(ROOT/'research/nr7-rth-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')}])
    atomic(ROOT/'research/nr7-rth-ledgers.json',dict(run_id=r['run_id'],native_id=r['native_id'],trades=[],output=doc['output'],settings=doc['settings'],native_response_sha256=file_hash(p.parent/(r['key']+'.native.json')),source_context=coverage['setups']))
    summary=dict(native_runs=1,maximum_registered_runs=2,skipped_runs=1,skip_reason='No setups and native zero trades confirmed; no cost-variant information',result_acks=1,review_acks=1,completed_daily_sessions=15,warmup_sessions=7,evaluation_sessions=8,qualified_sessions=0,trades=0,performance_evaluable=False,native_prior7_context_match=True,csharp_boundary_assertions=10,independent_oos=False,next_action=next_action)
    atomic(ROOT/'research/nr7-rth-summary.json',summary)
    dates=['2026-09-21','2026-09-22','2026-09-23','2026-09-24','2026-09-25','2026-09-28','2026-09-29','2026-09-30','2026-10-01']
    plan=dict(role='historical_context_extension',dates=dates,maximum_download_submissions=9,maximum_downloads_per_chunk=3,native_runs=0,source_priority='Audit existing native minute data first; acquire real Last data only for missing/unverifiable sessions. Native daily file presence does not verify its session template or complete RTH.',quality='390one-minute RTH bars per full regular session; source hashes and chronological high-low aggregation; explicit holiday/session exceptions rather than filling missing bars.',resume='Require actual additional qualifying setup exposure and separately preregistered finite evaluation windows before native performance testing. No shorter lookback to manufacture trades.24sessions would still be exploratory, not statistical proof.')
    atomic(ROOT/'research/nr7-history-acquisition-plan.json',plan)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text());c=next(c for c in b['candidates'] if c['id']=='nr7-compression-feasibility');c.update(status='source_review_completed',evidence='research/nr7-source-review.json',next_action=next_action)
    if not any(c['id']=='nr7-rth-v1' for c in b['candidates']):b['candidates'].append(dict(id='nr7-rth-v1',status='deferred_condition_absent',manifest='research/nr7-rth-manifest.json',results='research/nr7-rth-summary.json',budget=dict(completed=1,maximum=2,skipped=1),next_action=next_action))
    b['next_action']=next_action;atomic(p,b)
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    for t in b['tasks']:
        if t['id']=='nr7-source-definition-review':t.update(status='completed',evidence='research/nr7-source-review.json')
    if not any(t['id']=='nr7-prior-rth-coverage' for t in b['tasks']):b['tasks'].append(dict(id='nr7-prior-rth-coverage',candidate='nr7-rth-v1',kind='data-extension',status='pending',depends_on=None,plan='research/nr7-history-acquisition-plan.json',next_action=next_action))
    atomic(p,b);Lifecycle().update('idle','NR7daily source/implementation validation1native run,1result+1review ACK;7warmup/8evaluation,0setups/0trades,performance not evaluable. Costduplicate skipped. Prior-RTH data task saved;OFIclosed.',None)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
