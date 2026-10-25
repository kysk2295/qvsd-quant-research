"""Publish saved quality evidence only; never decode or evaluate a strategy."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from runner.core import ROOT, Queue, atomic, file_hash
from dashboard.reporter import emit, post
from dashboard.server import validate_run
from runner.research_lifecycle import Lifecycle
from research.analyze_market_state import read, require
from research.diagnose_nrd_oct23 import PLAN, PLAN_HASH, verify

ID = 'nq-nrd-oct23-quality-20261025'
DIAGNOSTIC = 'research/nrd-oct23-wire-diagnostic.json'
CONCLUSION = 'research/nrd-oct23-quality-conclusion.json'
REPORT = 'docs/nrd-oct23-quality-diagnosis-2026-10-25.md'
PUBLICATION = 'research/nrd-oct23-publication.json'


def main():
    plan, diagnostic, tests = read(PLAN), read(DIAGNOSTIC), read('research/nrd-oct23-tests.json')
    verify(plan)
    decoder_tests = Path(plan['decoder']).parents[1]/'tests/test_nrd_offline.py'
    require(file_hash(decoder_tests) == plan['original_decoder_tests_sha256'], 'Original tests changed')
    require(not (ROOT/PUBLICATION).exists(), 'Already published; inspect saved ACK')
    require(diagnostic['plan_sha256'] == PLAN_HASH and not diagnostic['integrity_ok'], 'Unexpected diagnostic')
    require(diagnostic['source_sha256'] == plan['source_sha256'], 'Source mismatch')
    require(diagnostic['code_sha256'] == file_hash(ROOT/'research/diagnose_nrd_oct23.py'), 'Diagnostic code changed')
    require(tests['success'] and tests['tests_run'] == 17 and not tests['skips'], 'Tests not verified')
    require(tests['trace_sha256'] == file_hash(ROOT/'research/nrd_trace.py'), 'Trace code changed')
    require(tests['test_sha256'] == file_hash(ROOT/'tests/test_nrd_quality_trace.py'), 'Test code changed')
    ledger = read('research/campaign-data-analysis-ledger.json')
    entry = next(e for e in ledger['entries'] if e['id'] == ID)
    used = {k: entry['attempts'].get(k, {}).get('count', 0) for k in plan['limits']}
    require(all(n <= plan['limits'][k] for k, n in used.items()), 'Budget exceeded')
    require(used['baseline_full_decode'] == 1 and used['targeted_wire_inspection'] == 1, 'Attempt ledger mismatch')
    conclusion = dict(id=ID, quality_accepted=False, data_status='blocked_excluded',
        diagnosis_status='completed', root_cause='unresolved_header_body_or_decoder',
        parser_defect_proven=False, parser_changed=False, arbitrary_correction=False,
        source_sha256=plan['source_sha256'], diagnostic=DIAGNOSTIC,
        diagnostic_sha256=file_hash(ROOT/DIAGNOSTIC), report=REPORT,
        report_sha256=file_hash(ROOT/REPORT), rth_minutes=343, expected_rth_minutes=390,
        decoded_time_gap_et='2026-10-23 11:35 through 12:21 inclusive; not proven physical loss',
        timezone_explains_whole_file_discrepancy=False,
        duplicate_or_corruption_ruled_out=False, independent_format_oracle=False,
        attempts_used=used, limits=plan['limits'], conditional_unused_budget_closed=True,
        tests_passed=17, representative_real_date_regression_runs=0,
        source_and_immutable_hashes_preserved=True, production_decoder_tests_preserved=True,
        resume_conditions=[
            'Separately scoped independent event dump/format evidence for identical file and known offsets',
            'Or separately preserved provenance-verified raw source passing original quality gates',
            'Only proven parser defect permits minimal fix, independent synthetic regression and registered representative dates'],
        no_automatic_rerun=True, new_market_artifacts_written=False, strategy_adopted=False)
    atomic(ROOT/CONCLUSION, conclusion)
    run = dict(id=ID, strategy='NQ 10월23일 데이터 품질 진단', symbol='NQ DEC26',
        source='Offline NRD/header diagnostic; no strategy execution', worker='windows-candidate-research',
        dataset='NQ DEC26 2026-10-23', status='completed', progress=100, phase='data_quality',
        reason='진단 완료·자료 제외 유지. 가격/거래량 불일치, 디코딩 시각의 RTH47분 공백. 원인 미확정·파서 변경0·전략 실행0.',
        metrics={}, equity=[], params=dict(quality_report=conclusion), evidence=REPORT)
    validate_run(run)
    queue = Queue()
    config = json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text(encoding='utf-8'))
    emit(run, queue.telemetry)
    require(post(config['url'], '/api/runs', run, config['token']).get('ok') is True, 'Dashboard ACK missing')
    snap = queue.telemetry/(hashlib.sha256(ID.encode()).hexdigest()+'.json')
    queue.control('ack:'+snap.name, file_hash(snap))
    completed = datetime.now(timezone.utc).isoformat()
    publication = dict(id=ID, ack=True, completed_at_utc=completed,
        plan_sha256=PLAN_HASH, diagnostic_sha256=file_hash(ROOT/DIAGNOSTIC),
        conclusion_sha256=file_hash(ROOT/CONCLUSION), report_sha256=file_hash(ROOT/REPORT),
        telemetry_sha256=file_hash(snap), tests_sha256=file_hash(ROOT/'research/nrd-oct23-tests.json'),
        source_and_immutable_hashes_preserved=True, decoder_unchanged=True, decoder_tests_unchanged=True,
        quality_accepted=False, attempts_used=used, tests_passed=17,
        downloads=0, native_runs=0, strategy_performance_runs=0, optimization=0)
    atomic(ROOT/PUBLICATION, publication)
    entry['attempts']['targeted_wire_inspection'].update(status='completed', result_saved=True, result=DIAGNOSTIC)
    entry.update(status='completed', quality_status='blocked_excluded', root_cause='unresolved',
        parser_changed=False, completed_at_utc=completed, dashboard_ack=True, conclusion=CONCLUSION,
        report=REPORT, publication=PUBLICATION, conditional_unused_budget_closed=True)
    atomic(ROOT/'research/campaign-data-analysis-ledger.json', ledger)
    work = read('research/evidence-work-queue.json')
    next(t for t in work['tasks'] if t['id'] == ID).update(status='completed', quality_status='blocked_excluded',
        result=CONCLUSION, report=REPORT, publication=PUBLICATION, native_runs=0, downloads=0,
        next_action='Keep Oct23 excluded. Reopen only with independent source/format evidence under a separate finite plan.')
    atomic(ROOT/'research/evidence-work-queue.json', work)
    backlog = read('research/candidate-backlog.json')
    backlog['oct23_data_quality'].update(status='diagnosis_complete_data_blocked', quality_accepted=False,
        evidence=CONCLUSION, report=REPORT, publication=PUBLICATION, parser_changed=False,
        next_action='Independent source/format evidence required; no automatic decode or strategy rerun.')
    atomic(ROOT/'research/candidate-backlog.json', backlog)
    verify(plan)
    Lifecycle().update('idle', 'Oct23 offline quality diagnosis completed and ACKed; source remains excluded, cause unresolved, parser unchanged.17 synthetic tests passed. Downloads/native/performance0. This finite diagnostic is closed; the user requested a separate continuing NQ validation goal.', None)
    print(json.dumps(dict(report=REPORT, dashboard_ack=True, quality_accepted=False, tests=17, native_runs=0)))


if __name__ == '__main__':
    main()
