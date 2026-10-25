"""Publish existing audit only; preserve original results and frozen plan byte-for-byte."""
import copy
import hashlib
import json
from runner.core import ROOT, Queue, atomic, file_hash
from runner.research_lifecycle import Lifecycle
from dashboard.reporter import emit, post
from dashboard.server import validate_run

def main():
    frozen=json.loads((ROOT/'research/equity-audit-immutable-inputs.json').read_text())
    def unchanged():
        for path,digest in frozen.items():
            if file_hash(ROOT/path)!=digest:raise RuntimeError('Immutable input changed: '+path)
    unchanged()
    auditpath=ROOT/'research/bollinger-equity-path-audit.json'
    audit=json.loads(auditpath.read_text())
    readiness=json.loads((ROOT/'research/future-data-collector-readiness.json').read_text())
    tests=json.loads((ROOT/'research/equity-intake-tests.json').read_text())
    assert tests['passed'] and tests['tests_run']==30
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());acks=[]
    for aggregate in audit['aggregates']:
        snap=q.telemetry/(hashlib.sha256(aggregate['run_id'].encode()).hexdigest()+'.json')
        run=json.loads(snap.read_text());metrics=copy.deepcopy(run.get('metrics'));equity=copy.deepcopy(run.get('equity'))
        assessment=run['params']['assessment'];digest=file_hash(auditpath)
        if assessment.get('equity_path_audit',{}).get('audit_sha256')!=digest:
            run['params'].setdefault('assessment_history',[]).append(copy.deepcopy(assessment))
        details={k:aggregate[k] for k in ('fee','net','closed_trade_drawdown','holding_path_drawdown_lower','holding_path_drawdown_upper','worst_closed_day','worst_intraday_loss_from_day_start_lower','worst_intraday_loss_from_day_start_upper')}
        details.update(audit='research/bollinger-equity-path-audit.json',audit_sha256=digest,
            valuation=audit['valuation'],uncertainty=audit['uncertainty'],limits=audit['limits'],cost_scope=audit['cost_scope'],
            immutable_input_hashes=frozen,raw_sources=audit['raw_sources'],tests=tests,
            maximum_realized_overshoot_beyond900=max(x['realized_overshoot_beyond900'] for x in audit['realized_entry_gate']))
        assessment['equity_path_audit']=details
        assessment['future_data_collector']=readiness
        assert run.get('metrics')==metrics and run.get('equity')==equity
        validate_run(run);emit(run,q.telemetry)
        if post(config['url'],'/api/runs',run,config['token']).get('ok') is not True:raise RuntimeError('Metadata ACK missing')
        q.control('ack:'+snap.name,file_hash(snap));acks.append(dict(run_id=run['id'],ack=True,telemetry_sha256=file_hash(snap)))
    next_action='After a registered session closes, run finite data-only collector; inspect pending downloads without resubmission. No scheduler. No strategy outcomes before Nov7 10:00 KST. Native budget remains0; future executor not released. Research decision is separate from competition deadlines.'
    path=ROOT/'research/candidate-backlog.json';backlog=json.loads(path.read_text())
    candidate=next(x for x in backlog['candidates'] if x['id']=='bollinger-return-v1')
    candidate.update(equity_path_audit='research/bollinger-equity-path-audit.json',equity_path_metadata_acks=acks,
        data_collector='runner/future_data_collector.py',collector_readiness='research/future-data-collector-readiness.json',next_action=next_action)
    backlog['next_action']=next_action;atomic(path,backlog)
    path=ROOT/'research/evidence-work-queue.json';queue=json.loads(path.read_text())
    task=dict(id='bollinger-existing-equity-intake-audit',candidate='bollinger-return-v1',kind='existing-ledger-audit',status='completed',
        evidence='research/equity-intake-review-summary.json',native_runs=0,downloads=0,next_action=next_action)
    queue['tasks']=[x for x in queue['tasks'] if x['id']!=task['id']]+[task]
    future=next(x for x in queue['tasks'] if x['id']=='bollinger-prospective-20261026-1106')
    future.update(collector='runner/future_data_collector.py',automatic_collection_running=False,next_action=next_action)
    atomic(path,queue)
    unchanged()
    summary=dict(metadata_acks=acks,tests=tests,native_runs=0,downloads=0,performance_recomputed=False,
        immutable_hashes_preserved=True,immutable_input_hashes=frozen,collector_readiness=readiness,
        collector_live_download_verified=False,next_action=next_action)
    atomic(ROOT/'research/equity-intake-review-summary.json',summary)
    Lifecycle().update('idle','Existing52trade Last-equity audit published: highfee DD bounds3110-3140; closedDD2260 preserved. Finite data collector implemented/tested; no schedule/download/native execution. Await registered session close.',None)
    print(json.dumps(dict(metadata_acks=len(acks),tests=tests['tests_run'],native_runs=0,downloads=0,immutable_hashes_preserved=True)))

if __name__=='__main__':main()
