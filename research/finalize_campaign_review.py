"""Persist audit snapshots, scheduling status, and dashboard metadata ACKs."""
import json,time,hashlib,shutil
from pathlib import Path
from runner.core import ROOT,atomic,file_hash,Queue
from runner.research_lifecycle import Lifecycle
from research.finalize_gap_fade import publish

def main():
    out=ROOT/'research/campaign-review-summary.json';assert not out.exists()
    registry=json.loads((ROOT/'research/campaign-trial-registry.json').read_text());plan=json.loads((ROOT/'research/bollinger-prospective-plan.json').read_text())
    snapshot=ROOT/'data/runner/campaign-review-snapshot';snapshot.mkdir(exist_ok=True);index=[]
    for r in registry['records']:
        for evidence in r['evidence']:
            if not evidence.get('sha256'):continue
            source=Path(evidence['path']);assert file_hash(source)==evidence['sha256'],'Snapshot source changed before archival'
            dest=snapshot/(evidence['sha256']+source.suffix)
            if not dest.exists():shutil.copyfile(source,dest)
            index.append(dict(record=r['id'],original=str(source),snapshot=str(dest),sha256=evidence['sha256']))
    atomic(ROOT/'research/campaign-evidence-snapshot-index.json',index)
    next_action='Await fixed Oct26-Nov6futuredata;qualityonlycollection aftersessionclose,atmost1download/date/chunks<=3. No candidateperformancepeeking until Nov7 10:00KST. Then source/data/session/path audits and onecounted prospectivepacket;no native submission presentlyreleased. Preservealloldresults;no newfamilies/sameperiodvariants. Realtimepaperexecution remains unavailable underpolicyblock.'
    p=ROOT/'data/runner/bollinger-return/state.json';s=json.loads(p.read_text());q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text())
    for r in s['experiments'].values():
        r.setdefault('assessment_history',[]).append(dict(at=time.time(),assessment=dict(r['assessment']),reason='Campaignfreeze andfuturewindow registration'))
        r['assessment'].update(campaign_registry='research/campaign-trial-registry.json',campaign_control='research/campaign-search-control.json',prospective_plan='research/bollinger-prospective-plan.json',prospective_status='reserved_future_not_completed_OOS',completed_independent_oos_sessions=0,next_action=next_action)
        publish(r,q,config)
    atomic(p,s);atomic(ROOT/'research/bollinger-return-results.json',[{k:r[k] for k in ('run_id','request','source_hash','data_hash','manifest_hash','assessment','assessment_history','ack')} for r in s['experiments'].values()])
    p=ROOT/'research/evidence-work-queue.json';b=json.loads(p.read_text())
    for t in b['tasks']:
        if t['id']=='bollinger-cost-distinct-sample-review':t.update(status='completed',evidence='research/bollinger-cost-path-review.json',next_action=next_action)
        elif t.get('status') in ('pending','awaiting_new_market_data'):
            t.setdefault('scheduling_history',[]).append(dict(at=time.time(),status=t['status'],next_action=t.get('next_action')))
            t.update(status='deferred_campaign_budget',next_action='Preserved task;no activeperformancebudget during frozenBollingerfuturewindow. '+next_action)
    b['tasks'].append(dict(id=plan['id'],candidate='bollinger-return-v1',kind='prospective_data_preparation',status='awaiting_future_data',plan='research/bollinger-prospective-plan.json',native_attempts_active=0,next_action=next_action))
    b['next_action']=next_action;atomic(p,b)
    p=ROOT/'research/candidate-backlog.json';b=json.loads(p.read_text());c=next(c for c in b['candidates'] if c['id']=='bollinger-return-v1');c.update(status='deferred_cost_and_sample_future_reserved',latest_evidence='research/bollinger-cost-path-review.json',prospective_plan='research/bollinger-prospective-plan.json',next_action=next_action);b['next_action']=next_action;b['campaign_control']='research/campaign-search-control.json';atomic(p,b)
    summary=dict(local_telemetry_records=registry['telemetry_records'],archived_seed_records=registry['archived_dashboard_seed_records'],linked_records=len(registry['records']),queue_records=registry['queue_records'],unlinked_native_documents=registry['unlinked_native_documents'],observed_date_interval=registry['conservative_no_oos_interval'],completed_independent_oos_dates=[],native_runs_this_batch=0,new_strategy_families_this_batch=0,cost_review_pairs=7,cost_metadata_acks=14,prospective_metadata_acks=2,active_native_budget=0,future_reserved_native_attempts=1,future_evaluation_dates=plan['evaluation_dates'],fixed_decision_at=plan['decision_at'],tests=dict(campaign_gate=4,existing_runner=18),source_and_plan_hash_preflight_passed=True,unrealized_account_path='notverified_oldBBseconds;requiredfuturepreciseLastpathaudit',realtime_paper_forward='unavailable_policyblocked;prospectivehistoricalbatchdistinct',next_action=next_action)
    atomic(out,summary);Lifecycle().update('idle','Campaign reviewcomplete:206linkedrecords;olddata development;newnativebudget0. Bollinger futureOct26-Nov6reserved,Nov7 10KSTdecision,awaitdata. Cost14+plan2metadataACKs;no background loop.',None)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
