"""Publish precision/cost evidence, preserving original performance observations."""
import json
from runner.core import ROOT,atomic,Queue,file_hash
from runner.research_lifecycle import Lifecycle
from research.finalize_gap_fade import publish

def main():
    report=json.loads((ROOT/'research/execution-clock-audit.json').read_text())
    quality=json.loads((ROOT/'research/ofi-oct5-quality.json').read_text())
    assert report['baseline_trade_match'] and report['fractional_execution_count']==8
    next_action='Oct5 original quote file acquired and audited; next separately preregister fixed OFI historical extension after native Last-tick coverage/import audit. Preserve threshold10,lag60s,hold5bars. Future diagnostic runs should log raw simulated timestamps, but never relabel old JSON or simulation as live execution. RSI and Bollinger remain deferred; no same-date performance reruns.'
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());acks=0
    folders=[('execution-clock','execution-clock-results.json'),('ofi-early','ofi-early-results.json'),('ofi-late','ofi-late-results.json'),('ofi-oct6','ofi-oct6-results.json'),('bollinger-return','bollinger-return-results.json')]
    for folder,result in folders:
        p=ROOT/f'data/runner/{folder}/state.json';state=json.loads(p.read_text())
        for r in state['experiments'].values():
            a=r['assessment'];a.update(execution_clock_evidence='research/execution-clock-audit.json',next_action=next_action,
                timestamp_precision_finding='Installed serializer drops fractions. One distinct diagnostic demonstrates fractional HighTick1 simulated execution times; old saved result precision remains seconds.',
                exact_execution_validated=False,spread_cost_policy='When repricing to ask/bid, replace native price; do not additionally charge the same full spread. Incremental tick sensitivity is separate total adverse cost, not an extra proven execution cost.')
            if folder=='execution-clock':
                a.update(decision='deferred',reason='Diagnostic reproduction only; no new performance observation',diagnostic_only=True,unique_observations_added=0,baseline_trade_match=True,raw_simulation_precision_validated=True,adoption_gate='not_applicable_diagnostic')
            else:
                key='Bollinger_all13days' if folder=='bollinger-return' else 'OFI_all13days'
                a['combined_candidate_cost_break_even']=next(c for c in report['cost_break_even'] if c['candidate']==key)
                a['acquisition_followup']=dict(evidence='research/ofi-oct5-acquisition-recovered.json',new_historical_date='2026-10-05',integrity_passed=quality['integrity_passed'],rth_minutes=quality['rth_minutes_with_quotes'],eligible_minutes=quality['eligible_minutes'],new_native_runs=0)
            publish(r,q,config);acks+=1
        atomic(p,state);atomic(ROOT/'research'/result,[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in state['experiments'].values()])
    summary=dict(diagnostic_native_runs=1,new_performance_native_runs=0,unique_observations_added=0,result_acks=1,review_acks=acks,raw_fractional_executions=8,baseline_trade_match=True,
        data_acquisition=dict(date='2026-10-05',role='historical_extension',download_submissions=1,integrity_passed=quality['integrity_passed'],rth_minutes=quality['rth_minutes_with_quotes'],eligible_minutes=quality['eligible_minutes'],native_tests=0),cost_break_even=report['cost_break_even'],next_action=next_action)
    atomic(ROOT/'research/execution-evidence-summary.json',summary)
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    for t in b['tasks']:
        if t['id']=='native-execution-timestamp-audit':t.update(status='completed',evidence='research/execution-clock-audit.json',next_action=next_action)
    if not any(t['id']=='ofi-oct5-fixed-extension' for t in b['tasks']):b['tasks'].append(dict(id='ofi-oct5-fixed-extension',candidate='ofi-lagged-v1',kind='historical-extension',status='pending',depends_on=None,next_action=next_action,prerequisites=['Audit/import Last ticks for native fill coverage','Freeze feature CSV and source hash','Register maximum2cost runs before any new outcomes'],role='historical_extension'))
    atomic(p,b)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text())
    for c in b['candidates']:
        if c['id'] in ('ofi-lagged-v1','bollinger-return-v1'):c.update(execution_evidence='research/execution-evidence-summary.json',next_action=next_action)
    b['next_action']=next_action;atomic(p,b)
    Lifecycle().update('idle','1clock diagnostic ACKed,0new performance observations;8raw fractional simulation times verified.9review ACKs. Oct5download recovered:390RTH quote minutes; next fixed-rule historical extension after native coverage preregistration.',None)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
