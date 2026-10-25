"""Read-only preflight; never acquire data, place orders, or submit backtests."""
import json
from datetime import datetime,timezone
from runner.core import ROOT,file_hash,atomic

def inspect(now=None):
    now=now or datetime.now(timezone.utc)
    p=ROOT/'research/bollinger-prospective-plan.json';m=json.loads(p.read_text());gate=json.loads((ROOT/'research/campaign-search-control.json').read_text())
    source_ok=file_hash(ROOT/m['source_code'])==m['source_code_sha256'];manifest_ok=file_hash(ROOT/m['source_manifest'])==m['source_manifest_sha256'];plan_ok=file_hash(p)==gate['prospective_plan_sha256']
    registry=json.loads((ROOT/'research/data-role-registry.json').read_text());overlap=sorted(set(m['evaluation_dates'])&set(registry['known_observed_dates']))
    missing=[]
    for day in m['evaluation_dates']:
        prepared=ROOT/f'data/runner/nt-import/{day.replace("-", "")}/NQ DEC26.Last.txt'
        if not prepared.exists():missing.append(day)
    time_ready=now>=datetime.fromisoformat(m['decision_at'])
    registry_ok=file_hash(ROOT/'research/campaign-trial-registry.json')==m['campaign_registry_sha256']
    return dict(checked_at_utc=now.isoformat(),source_unchanged=source_ok,manifest_unchanged=manifest_ok,plan_unchanged=plan_ok,campaign_registry_unchanged=registry_ok,observed_date_overlap=overlap,decision_time_reached=time_ready,missing_prepared_dates=missing,
        ready_for_native=False,native_submissions=0,policy_mode=gate['native_submission_mode'],
        resume='Afterdecisiontime,check all10date integrity/session/DST andhashes,then explicitly prepare a counted1attempt packet. Filepresence alone isnotqualitypass;no automaticexecution orpeeking.',
        reason='await_future_data_and_fixed_decision_time' if not time_ready else 'requires_full_data_quality_and_counted_execution_packet',
        realtime_paper_forward_ready=False,realtime_paper_forward_blocker='Policyblocked simulation-control path;no retry/alternate route')

if __name__=='__main__':
    r=inspect();atomic(ROOT/'research/bollinger-prospective-preflight.json',r);print(json.dumps(r,indent=2))
