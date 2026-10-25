"""Annotate retained result telemetry; never rewrites native results or frozen plans."""
import copy
import json
from runner.core import ROOT,Queue,atomic,file_hash
from runner.research_lifecycle import Lifecycle
from dashboard.reporter import emit,post
from dashboard.server import validate_run

def main():
    path=ROOT/'research/strategy-rule-provenance-review.json';review=json.loads(path.read_text());digest=file_hash(path)
    immutable=review['immutable_input_hashes'];codehashes=review['source_code_hashes']
    def verify():
        for p,h in {**immutable,**codehashes}.items():
            if file_hash(ROOT/p)!=h:raise RuntimeError('Protected source changed: '+p)
    verify()
    bystrategy={name:row for row in review['candidates'] for name in row['strategies']}
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());acks=[]
    prefix='[적용 범위: 추가 제약을 포함한 NQ 변형이며 원전 전체의 성공/실패 판정이 아님] '
    for snap in sorted(q.telemetry.glob('*.json')):
        run=json.loads(snap.read_text());row=bystrategy.get(run.get('strategy'))
        if row is None:continue
        before={k:copy.deepcopy(run.get(k)) for k in ('metrics','equity','status','dataset','cost')}
        params=run.setdefault('params',{});assessment=params.setdefault('assessment',{})
        if assessment.get('rule_provenance_review',{}).get('sha256')!=digest or assessment.get('rule_provenance_review',{}).get('annotation_version')!=2:
            params.setdefault('assessment_history',[]).append(copy.deepcopy(assessment))
        params.setdefault('reason_before_provenance_review',run.get('reason',''))
        source_match=params.get('source_hash') in [row['files_sha256'][p] for p in row['code']]
        assessment['rule_provenance_review']=dict(report='research/strategy-rule-provenance-review.json',sha256=digest,annotation_version=2,
            candidate=row['id'],validity=row['validity'],original=row['original'],current_reviewed_implementation=row['implemented'],
            run_source_matches_reviewed_code=source_match,run_source_sha256=params.get('source_hash'),
            historical_version_limit='Current reviewed code is a reference, not a claim that older run rules match. Retain original run inputs/source hash and prior assessments; mismatch or absent hash means exact run-version parity unverified.',
            source=row['source'],source_status=row['source_status'],files_sha256=row['files_sha256'],
            common_constraints_validated=False,source_replication=False,new_native_budget=0)
        run['reason']=prefix+params['reason_before_provenance_review']
        assert all(run.get(k)==v for k,v in before.items())
        validate_run(run);emit(run,q.telemetry)
        if post(config['url'],'/api/runs',run,config['token']).get('ok') is not True:raise RuntimeError('Missing metadata ACK')
        q.control('ack:'+snap.name,file_hash(snap));acks.append(dict(run_id=run['id'],strategy=run['strategy'],ack=True,telemetry_sha256=file_hash(snap)))
        if len(acks)%15==0:print(json.dumps(dict(metadata_acks=len(acks))),flush=True)
    backlogpath=ROOT/'research/candidate-backlog.json';backlog=json.loads(backlogpath.read_text())
    for candidate in backlog['candidates']:
        row=next((r for r in review['candidates'] if r['id']==candidate['id']),None)
        if row:candidate.update(rule_provenance_review='research/strategy-rule-provenance-review.json',performance_inference_scope=row['validity'],common_constraints_validated=False)
    # Unexecuted questions are not candidate selection, executable manifests or reserved trials.
    questions=[
        ('source-specification','Obtain complete cafe source and resolve entry/exit/session/reentry omissions; verify current competition counted-entry rules.','One source completeness matrix; if unavailable retain unknowns. No inferred numeric strategy.'),
        ('risk-feasibility','Does each source-specific stop fit1NQ under the unchanged risk policy?','One static sizing review per candidate; overbudget=not feasible; never shrink stop or raise risk to force eligibility.'),
        ('entry-cap','What changes when max4 truncation is removed for one independently specified feasible candidate?','If separately authorized later: one two-policy comparison, identical other rules and distinct preregistered dates; no sweep or best-PnL selection.'),
        ('order-semantics','How do native source entry/cancel/reversal rules differ from flat-only translation?','First use deterministic order-state fixtures, no performance run; any later paired experiment requires separate release.'),
        ('bar-session-exit','Which observed strategy changes follow from timeframe, session reset and time-exit choices?','One named change at a time for one source-complete candidate; define before any new data outcomes, no combinatorial optimization.')]
    backlog['unexecuted_rule_research_questions']=[dict(id='rule-review-'+key,question=question,bounded_scope=scope,status='deferred_campaign_budget',native_budget=0,executed=False,changes_frozen_plan=False) for key,question,scope in questions]
    atomic(backlogpath,backlog)
    qp=ROOT/'research/evidence-work-queue.json';work=json.loads(qp.read_text());tid='source-rule-provenance-review'
    work['tasks']=[t for t in work['tasks'] if t['id']!=tid]+[dict(id=tid,kind='source-code-audit',status='completed',evidence='research/strategy-rule-provenance-review.json',native_runs=0,next_action='Finite data-only collector after registered session close; unexecuted specification questions stay deferred. Frozen plan unchanged.')]
    atomic(qp,work);verify()
    summary=dict(candidates_reviewed=len(review['candidates']),metadata_acks=acks,report_sha256=digest,
        native_runs=0,downloads=0,pnl_recomputed=False,original_metrics_preserved=True,immutable_hashes_preserved=True,
        source_hashes_preserved=True,future_plan_unchanged=True,new_native_budget=0,
        deferred_questions=len(questions),collector_runbook='docs/strategy-rule-provenance-2026-10-25.md')
    atomic(ROOT/'research/strategy-rule-provenance-publication.json',summary)
    Lifecycle().update('idle','Source/code review6families published; results apply only to constrained NQ variants. Max4/48tick appropriateness unvalidated. Frozen plan and budget0 preserved. Data-only collector awaits closed session; no background task.',None)
    print(json.dumps(dict(candidates=6,metadata_acks=len(acks),deferred_questions=5,native_runs=0,downloads=0,protected_hashes_preserved=True)),flush=True)

if __name__=='__main__':main()
