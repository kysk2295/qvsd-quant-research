"""Publish bounded next-date acquisition without running strategy outcomes."""
import json
from runner.core import ROOT,atomic,Queue
from runner.research_lifecycle import Lifecycle
from research.finalize_gap_fade import publish

def main():
    quality=json.loads((ROOT/'research/ofi-oct2-quality.json').read_text())
    assert quality['integrity_passed'] and quality['rth_minutes_with_quotes']==390
    next_action='Oct2 original quotes acquired and quality-audited. Next finite batch: inspect causal exclusions and Last tick coverage/import, freeze a distinct feature hash, preregister at most2fixed OFI cost runs. Historical extension only; no repeat of14evaluateddates and no retuning. OFI cost/concentration gate unmet; RSI/Bollinger preserved.'
    p=ROOT/'data/runner/ofi-oct5/state.json';state=json.loads(p.read_text());q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    for r in state['experiments'].values():
        r['assessment'].update(next_action=next_action,next_data_acquisition=dict(date='2026-10-02',role='historical_extension',integrity_passed=True,rth_minutes=390,eligible_minutes=quality['eligible_minutes'],native_runs=0,evidence='research/ofi-oct2-quality.json'));publish(r,q,config)
    atomic(p,state);atomic(ROOT/'research/ofi-oct5-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','ack')} for r in state['experiments'].values()])
    p=ROOT/'research/ofi-oct5-summary.json';s=json.loads(p.read_text());s.update(next_action=next_action,acquisition_review_acks=2,next_data_date='2026-10-02',next_data_eligible_minutes=quality['eligible_minutes']);atomic(p,s)
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    for t in b['tasks']:
        if t['id']=='ofi-oct2-acquisition':t.update(status='completed',evidence='research/ofi-oct2-quality.json',next_action=next_action)
    if not any(t['id']=='ofi-oct2-fixed-extension' for t in b['tasks']):b['tasks'].append(dict(id='ofi-oct2-fixed-extension',candidate='ofi-lagged-v1',kind='historical-extension',status='pending',depends_on='ofi-oct2-acquisition',role='historical_extension',next_action=next_action))
    atomic(p,b)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text());c=next(c for c in b['candidates'] if c['id']=='ofi-lagged-v1');c.update(next_action=next_action,next_data_evidence='research/ofi-oct2-quality.json');b['next_action']=next_action;atomic(p,b)
    Lifecycle().update('idle',f'Oct5OFI2runs complete,56unique total,+315/+35;Oct2one download/audit complete,{quality["eligible_minutes"]}/390eligible,0Oct2native runs. Next fixed extension saved; all ACKs confirmed.',None)
    print(json.dumps(dict(eligible_minutes=quality['eligible_minutes'],acquisition_metadata_acks=2,native_runs_for_oct2=0,next_action=next_action)))

if __name__=='__main__':main()
