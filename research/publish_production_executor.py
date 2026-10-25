"""Persist preparation evidence after the actual goal is externally blocked."""
import hashlib
import json
from datetime import datetime, timezone
from runner.core import ROOT, Queue, atomic, file_hash
from runner.research_lifecycle import Lifecycle
from dashboard.reporter import emit, post
from dashboard.server import validate_run
from research.validation_packet import read_json, verify_protected
from research.run_production_executor_tests import PLAN, PLAN_HASH, CODE

REPORT = 'docs/nq-production-executor-2026-10-25.md'
RESULT = 'research/production-executor-result.json'
PUBLICATION = 'research/production-executor-publication.json'
GOAL = 'research/production-executor-goal-status.json'
DRY = 'research/production-executor-dry-run.json'


def main():
    if (ROOT/RESULT).exists() or (ROOT/PUBLICATION).exists():
        raise FileExistsError('Publication already attempted; inspect stored evidence')
    if file_hash(ROOT/PLAN) != PLAN_HASH:
        raise ValueError('Registered plan changed')
    plan = read_json(ROOT/PLAN)
    verify_protected(ROOT, plan)
    tests = read_json(ROOT/'research/production-executor-tests.json')
    if tests['success'] is not True or tests['code_hashes'] != {p:file_hash(ROOT/p) for p in CODE}:
        raise ValueError('Current code lacks passing counted checks')
    attempts = read_json(ROOT/'research/production-executor-test-attempts.json')
    dry = read_json(ROOT/DRY)
    goal = read_json(ROOT/GOAL)
    if goal.get('goal', {}).get('status') != 'blocked':
        raise ValueError('Actual goal status must be blocked before publication')
    if dry['status'] != 'blocked_before_data_and_native' or any(dry[k] != 0 for k in
            ('native_calls', 'market_loader_calls', 'attempt_reservations', 'actual_download_requests')):
        raise ValueError('Dry-run scope mismatch')
    prior_paths = ['research/deployment-readiness-result.json',
                   'research/future-import-preparation-result.json', DRY]
    for p in prior_paths:
        sessions = read_json(ROOT/p)['future_sessions']
        if len(sessions) != 10 or any(s['status'] != 'awaiting_session_close' for s in sessions):
            raise ValueError('Consecutive future-session blocker evidence mismatch')
    next_action = ('Await registered sessions: first close Oct27 05:00 KST; run the existing finite '
        'data-quality/ACK/import process only after closure. After all ten sessions and Nov7 10:00 KST, '
        'the single frozen prospective executor requires actual preflight, same-handle results and '
        'postrun parity. No scheduler, repeated preparation, substitute candidates or outcome retuning. '
        'A ten-session pass is only eligibility for longer independent and permitted execution validation.')
    result = dict(id=plan['id'], recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=PLAN_HASH, previous_goal_turn='progress: 206f18b bounded future import preparation',
        current_goal_turn='progress: final fixed production executor integration; then external impasse',
        goal_status='blocked', strategy_validated=False, tests=tests,
        suite_attempts=len(attempts['attempts']),
        first_suite_note='76 checks, one WinError5 at synthetic temporary state-file os.replace in unchanged lifecycle test. Cause unconfirmed; retained. Final suite after separate code-review hardening:81 passed.',
        native_calls=0, native_backtests=0, native_imports=0, downloads=0,
        real_market_file_reads=0, real_performance_evaluations=0,
        production_executor_implemented=True, production_executor_executed=False,
        native_cache_parity=False, active_native_job_handle=None, metadata_dry_run=dry,
        evidence_sha256={p:file_hash(ROOT/p) for p in prior_paths+[GOAL,REPORT]},
        consecutive_same_blocker_turns=3,
        blocker='All fixed prospective sessions are unclosed and the fixed decision time has not arrived',
        immediately_actionable_implementation_remaining=False, scheduler_created=False,
        preserved='Frozen source, candidate, request, dates, costs, registry and budgets unchanged',
        limitations=['Synthetic passing tests are not an actual native run or strategy validation',
            'Source/catalog/assembly observations do not prove method-body equivalence',
            'Saved timezone is empty; system timezone expectation must match actual result and clocks',
            'Import done and cache hashes do not prove native bar/cache content parity',
            'Native activity snapshots are not an atomic all-process idle guarantee',
            'Submission intent is durable before POST; ambiguous results cannot be resubmitted',
            'Exit-order causality, longer independent sample and permitted execution evidence remain'],
        next_action=next_action)
    atomic(ROOT/RESULT, result)
    run = dict(id=plan['id'], strategy='NQ 고정 미래 검증 실행 경로 준비', symbol='NQ DEC26',
        source='Synthetic production-executor integration', worker='windows-candidate-research',
        dataset='Synthetic fixtures and actual-clock metadata only', status='completed', progress=100,
        phase='research_preparation', metrics={}, equity=[],
        reason='코드 검사81개 통과. 실제 미래 세션 미발생으로 Goal blocked; 전략 검증 미완료.',
        params=dict(goal_status='blocked', strategy_validated=False, native_backtests=0, result=result),
        evidence=REPORT)
    validate_run(run)
    q = Queue()
    config = read_json(ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json')
    emit(run, q.telemetry)
    if post(config['url'], '/api/runs', run, config['token']).get('ok') is not True:
        raise RuntimeError('Dashboard ACK missing')
    snap = q.telemetry/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json')
    q.control('ack:'+snap.name, file_hash(snap))
    atomic(ROOT/PUBLICATION, dict(id=plan['id'], ack=True,
        completed_at_utc=datetime.now(timezone.utc).isoformat(), plan_sha256=PLAN_HASH,
        result_sha256=file_hash(ROOT/RESULT), report_sha256=file_hash(ROOT/REPORT),
        telemetry_sha256=file_hash(snap), native_calls=0, native_backtests=0,
        strategy_validated=False, goal_status='blocked'))
    ledger = read_json(ROOT/'research/campaign-data-analysis-ledger.json')
    ledger['entries'].append(dict(id=plan['id'], kind='production_executor_preparation_only',
        status='completed', plan=PLAN, report=REPORT, result=RESULT, publication=PUBLICATION,
        native_runs=0, native_imports=0, downloads=0, dashboard_ack=True, goal_status='blocked'))
    atomic(ROOT/'research/campaign-data-analysis-ledger.json', ledger)
    work = read_json(ROOT/'research/evidence-work-queue.json')
    work['tasks'].append(dict(id=plan['id'], kind='production_executor_preparation_only',
        status='completed', report=REPORT, publication=PUBLICATION, native_runs=0,
        goal_status='blocked', next_action=next_action))
    atomic(ROOT/'research/evidence-work-queue.json', work)
    backlog = read_json(ROOT/'research/candidate-backlog.json')
    backlog['validation_goal'].update(status='blocked', readiness_report=REPORT,
        readiness_publication=PUBLICATION, next_action=next_action, strategy_validated=False,
        blocker=result['blocker'], consecutive_same_blocker_turns=3)
    backlog['next_action'] = next_action
    atomic(ROOT/'research/candidate-backlog.json', backlog)
    verify_protected(ROOT, plan)
    Lifecycle().update('blocked', 'Goal blocked by unclosed fixed prospective sessions and decision time. '
        'Production executor synthetic checks81 passed; no actual native run or validated strategy. '
        'No scheduler or active native job; preparation is complete.', None)
    print(json.dumps(dict(report=REPORT, ack=True, tests=tests['tests_run'],
        suite_attempts=len(attempts['attempts']), native_backtests=0, goal_status='blocked')))


if __name__ == '__main__':
    main()
