"""Publish synthetic preparation evidence; never touch the native importer."""
import hashlib
import json
from datetime import datetime, timezone
from runner.core import ROOT, Queue, atomic, file_hash
from runner.research_lifecycle import Lifecycle
from dashboard.reporter import emit, post
from dashboard.server import validate_run
from research.validation_packet import read_json, verify_protected
from research.run_future_import_preparation_tests import PLAN, PLAN_HASH, CODE

REPORT = 'docs/nq-future-import-preparation-2026-10-25.md'
RESULT = 'research/future-import-preparation-result.json'
PUBLICATION = 'research/future-import-preparation-publication.json'


def main():
    if (ROOT/PUBLICATION).exists() or (ROOT/RESULT).exists():
        raise FileExistsError('Publication already attempted; inspect existing evidence')
    plan = read_json(ROOT/PLAN)
    if file_hash(ROOT/PLAN) != PLAN_HASH:
        raise ValueError('Plan changed')
    verify_protected(ROOT, plan)
    tests = read_json(ROOT/'research/future-import-preparation-tests.json')
    if tests['success'] is not True or tests['code_hashes'] != {p:file_hash(ROOT/p) for p in CODE}:
        raise ValueError('Current code lacks passing counted checks')
    attempts = read_json(ROOT/'research/future-import-preparation-test-attempts.json')
    intake = read_json(ROOT/'data/runner/future-data-intake/state.json')
    future = read_json(ROOT/'research/bollinger-prospective-plan.json')
    now = datetime.now(timezone.utc)
    next_action = ('Finish one narrowly scoped production prospective executor with real preflight and '
        'durable single-attempt transport, using synthetic fixtures only now. Then await fixed closed '
        'sessions and Nov7 decision; no repeated preparation or candidate outcome search.')
    result = dict(id=plan['id'], recorded_at_utc=now.isoformat(), plan_sha256=PLAN_HASH,
        previous_goal_turn='progress: e8c8dbb installed/native metadata and importer gap',
        current_goal_turn='progress: scoped RTH staging plus bounded native import lifecycle, synthetic verified',
        tests=tests, suite_attempts=len(attempts['attempts']), native_calls=0, native_imports=0,
        repair_note='First suite retained: SQLite fixture connections stayed open on Windows; explicitly closed. Crash evidence raises AttemptError, so the test expectation was corrected. Second suite passed. Independent review then required native Int64 volume range; added limit/overflow fixture and reran focused suite.',
        native_backtests=0, downloads=0, real_market_file_reads=0, strategy_validated=False,
        production_import_executed=False, native_cache_parity=False,
        implementation=dict(staging='Only registered closed RTH lines, verbatim bytes and 100ns; source/quality/ACK/hash bound',
            submission='One durable date reservation; narrow HTTP; no flags, connection changes, orders or retries',
            correlation='Unique staged path and observed process/assembly before and after; no atomic server job identity',
            completion='Done path, strict integer row count and NQ contract; cache/bar parity still required'),
        scope_note='Native importer and tests are preparation; quality_passed/import done do not imply strategy validation',
        future_sessions=[dict(date=d, status=intake['entries'][d]['status'],
                             session_close_utc=intake['entries'][d]['session_close_utc']) for d in future['evaluation_dates']],
        actual_download_requests=intake['actual_download_requests'], goal_status='active',
        remaining=['Unclosed fixed dates and decision time', 'Actual download/quality/import/cache/bar evidence',
                   'Final bounded production executor wiring',
                   'Actual native postrun evidence, longer independent validation and permitted forward execution'],
        next_action=next_action)
    atomic(ROOT/RESULT, result)
    lines = ['# NQ 미래 자료 가져오기 준비', '',
        '**품질 확인 자료를 NinjaTrader에 넘기는 코드를 연결했다. 실제 가져오기와 전략 검증은 아직 실행하지 않았다.**', '',
        f"합성 검사 {tests['tests_run']}개가 통과했다. 등록된 최대 4회 중 전체 검사 {len(attempts['attempts'])}회를 사용했다. 테스트는 임시 합성 파일과 가짜 전송만 사용했으며, 실제 시장 파일 열람·다운로드·NT 호출·import·백테스트는 모두 0회다.", '',
        '첫 검사 실패 기록도 보존했다. Windows에서 테스트용 SQLite 연결이 닫히지 않아 파일 잠금 오류가 발생했고, 중단된 예약의 예외 형식을 테스트가 잘못 기대한 부분이 있었다. 이를 수정한 두 번째 검사는 통과했다. 이후 독립 리뷰에서 실제 importer의 Int64 거래량 상한을 확인해 입력 검사와 초과값 fixture를 추가했고, 마지막 검사가 통과했다.', '',
        '## 연결한 동작', '',
        '1. 고정 계획·대상 날짜·실제 세션 종료 시각을 먼저 확인한다. 종료 전에는 시장 파일을 열지 않는다.',
        '2. quality_passed 기록, NRD 원본·Parquet·Last 해시, 날짜별 품질 보고서, 대시보드 telemetry와 ACK 기록을 대조한다.',
        '3. 원본 Last에는 정규장 밖 자료도 들어 있으므로 해당 날짜 뉴욕 09:30 이상 16:00 미만 행만 추린다. 선택한 행의 바이트와 순서, 100ns 시각을 보존하고 390분·양의 거래량·가격 틱을 검사한다. 따라서 전체 Last 파일의 단순 복제는 아니며 원본·추출본 해시를 각각 기록한다.',
        '4. nt-import 아래 날짜·품질 해시별 고유 폴더에 NQ DEC26.Last.txt를 만든다. 기존 완성 파일은 다시 검증하며, 손상·부분 작성 파일은 덮어쓰지 않는다.',
        '5. 실제 제출 시 기존 연구 권한과 연결 상태를 읽고, 날짜별 예약·제출 의도를 디스크에 먼저 저장한 뒤 기존 /research/import에 한 번만 POST한다. 권한 활성화·연결 변경·주문 호출은 없다.',
        '6. 같은 경로와 엔진 관측을 묶어 한 번씩 상태를 읽는다. 잘못된 경로·파일 변경·엔진 변경·불명확한 응답은 보존하고 자동 재제출을 막는다. done의 행수·종목·원응답 해시도 저장 후 다시 확인한다.', '',
        '## 완료의 범위와 한계', '',
        'NinjaTrader importer는 고유 job ID나 서버 idempotency key가 없으며 전역 상태 하나만 제공한다. 로컬 예약은 날짜당 POST를 최대 한 번으로 제한하지만, 예약 직후 중단되면 실제 POST 없이 그 기회를 소진할 수 있다. 경로와 전후 엔진 관측은 제한된 연결 증거이며 원자적인 서버 식별 증명은 아니다.', '',
        'done은 importer가 반환한 상태다. 실제 tick/minute cache 내용과 390분 봉, 이후 체결·손익 원장의 일치는 별도로 확인해야 한다. quality_passed 상태는 그대로 두고 import 상태를 별도 저장한다. 이번 작업은 기존 도구에 노출되지 않은 import endpoint만 좁은 로컬 전송으로 연결했으며, 실제 호출이나 차단 경로의 재시도는 하지 않았다.', '',
        '## 이후 실행 순서', '',
        '세션 종료 후 기존 collector의 품질 검사와 ACK가 끝난 날짜에만 다음 명령을 사용한다. 현재는 미래 자료가 없으므로 실행하지 않았다.', '',
        '```powershell',
        'python -m runner.future_data_importer 2026-10-26 --stage',
        'python -m runner.future_data_importer 2026-10-26 --submit',
        'python -m runner.future_data_importer 2026-10-26 --observe',
        '```', '',
        '각 명령은 유한하며 예약 실행이나 반복 루프가 아니다. unknown·error·중간 파일을 삭제해 재시도하지 않는다. 기존 서버의 연구 권한·연결·포지션/작업 주문 검사는 계속 적용된다.', '',
        '첫 대상 세션 종료는 10월 27일 05:00 KST, 성과 판정은 11월 7일 10:00 KST 이후다. 지금 남은 구현은 고정된 한 번의 실제 백테스트 제출·조회·결과 판독 경로를 연결하는 작업이다. 이 연결까지 마치면 미발생 세션을 기다리며 추가 준비나 같은 자료 최적화를 반복하지 않는다. 10일 검증 통과도 더 긴 독립 검증 후보를 뜻한다.', '',
        '## 증거', '',
        '- [사전 계획](../research/nq-future-import-preparation-plan.json)',
        '- [합성 검사와 코드 해시](../research/future-import-preparation-tests.json)',
        '- [모든 검사 시도](../research/future-import-preparation-test-attempts.json)',
        '- [상태·남은 단계](../research/future-import-preparation-result.json)',
        '- [대시보드 수신](../research/future-import-preparation-publication.json)', '']
    (ROOT/REPORT).write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    run = dict(id=plan['id'], strategy='NQ 미래 Last 가져오기 준비', symbol='NQ DEC26',
        source='Synthetic import preparation only', worker='windows-candidate-research',
        dataset='Temporary synthetic fixtures; no real market reads', status='completed', progress=100,
        phase='research_preparation', metrics={}, equity=[],
        reason='날짜별 정규장 추출·해시·ACK·단일 import 제출/상태 연결 합성 검사. 실제 가져오기·전략 검증은 미실행.',
        params=dict(goal_status='active', strategy_validated=False, native_backtests=0, result=result), evidence=REPORT)
    validate_run(run)
    q = Queue()
    config = read_json(ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json')
    emit(run, q.telemetry)
    if post(config['url'], '/api/runs', run, config['token']).get('ok') is not True:
        raise RuntimeError('Dashboard ACK missing')
    snap = q.telemetry/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json')
    q.control('ack:'+snap.name, file_hash(snap))
    atomic(ROOT/PUBLICATION, dict(id=plan['id'], ack=True, completed_at_utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=PLAN_HASH, result_sha256=file_hash(ROOT/RESULT), report_sha256=file_hash(ROOT/REPORT),
        telemetry_sha256=file_hash(snap), native_calls=0, native_imports=0, native_backtests=0,
        strategy_validated=False, goal_status='active'))
    ledger = read_json(ROOT/'research/campaign-data-analysis-ledger.json')
    ledger['entries'].append(dict(id=plan['id'], kind='import_preparation_only', status='completed', plan=PLAN,
        report=REPORT, result=RESULT, publication=PUBLICATION, native_runs=0, native_imports=0,
        downloads=0, dashboard_ack=True))
    atomic(ROOT/'research/campaign-data-analysis-ledger.json', ledger)
    work = read_json(ROOT/'research/evidence-work-queue.json')
    work['tasks'].append(dict(id=plan['id'], kind='import_preparation_only', status='completed', report=REPORT,
        publication=PUBLICATION, native_runs=0, next_action=next_action))
    atomic(ROOT/'research/evidence-work-queue.json', work)
    backlog = read_json(ROOT/'research/candidate-backlog.json')
    backlog['validation_goal'].update(status='active', readiness_report=REPORT,
        readiness_publication=PUBLICATION, next_action=next_action, strategy_validated=False)
    atomic(ROOT/'research/candidate-backlog.json', backlog)
    verify_protected(ROOT, plan)
    Lifecycle().update('idle', 'Finite synthetic import preparation complete and ACKed. No actual market reads, imports or backtests. One production executor integration remains before awaiting future dates/decision. No validated strategy.', None)
    print(json.dumps(dict(report=REPORT, ack=True, tests=tests['tests_run'], suite_attempts=len(attempts['attempts']), native_imports=0, native_backtests=0)))


if __name__ == '__main__':
    main()
