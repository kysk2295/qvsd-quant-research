"""Publish existing preparation evidence; never runs its checker or a strategy."""
import hashlib
import json
from datetime import datetime, timezone

from runner.core import ROOT, Queue, atomic, file_hash
from dashboard.reporter import emit, post
from dashboard.server import validate_run
from runner.research_lifecycle import Lifecycle
from research.analyze_market_state import read, require
from research.validation_packet import READINESS_PLAN, READINESS_HASH, DRAFT, verify_protected

REPORT = 'docs/nq-goal-validation-readiness-2026-10-25.md'
PUBLICATION = 'research/validation-readiness-publication.json'


def main():
    plan, draft, tests = read(READINESS_PLAN), read(DRAFT), read('research/validation-packet-tests.json')
    require(file_hash(ROOT/READINESS_PLAN) == READINESS_HASH, 'Readiness plan changed')
    verify_protected(ROOT, plan)
    require(draft['readiness_plan_sha256'] == READINESS_HASH, 'Unbound draft')
    require(tests['success'] and not tests['skips'], 'Focused tests not verified')
    code_hash = file_hash(ROOT/'research/validation_packet.py')
    require(tests['code_sha256'] == code_hash == draft['code_sha256'], 'Code changed after evidence')
    require(tests['test_sha256'] == file_hash(ROOT/'tests/test_validation_packet.py'), 'Tests changed after evidence')
    require(not draft['ready_for_native'] and draft['native_submissions'] == 0, 'Unexpected submission state')
    require(not (ROOT/PUBLICATION).exists(), 'Publication already exists; inspect ACK')
    lines = ['# NQ Goal: 독립 검증 준비 도구', '',
        '**준비 도구를 구현하고 검사했다. 전략이 검증됐다는 결과는 아니다.** Goal은 활성 상태다. 기존 고정 후보·미사용 기간·실행 제한은 보존했다.', '',
        f"합성 검사 {tests['tests_run']}개 통과, 실제 메타데이터 초안 1회 작성. 신규 다운로드·native 호출·성과 계산·예약된 native 시도 사용은 모두 0회다.", '',
        '## 도구가 확인하는 것', '',
        '- 계획·전략 코드·매니페스트·캠페인 원장·자료 역할의 고정 해시와 날짜.',
        '- 날짜별 기존 품질 기록과 원본/파생 파일의 실제 해시. 종료 전 세션은 감사 파일과 가격 파일을 읽기 전에 건너뛴다.',
        '- ET 정규장·DST·390분 기록, 품질 실패·누락·기존 관측 날짜와의 중복.',
        '- 판정 시각, 기존 시도 증거, 신호·시각·거래 원장·체결 경로의 증거 부족.',
        '- JSON 오류·날짜 오류·해시 변경은 통과시키지 않는다. 실제 draft의 중복 작성도 거절한다.', '',
        '순수 검사기에 완전한 합성 증거를 넣어도 ready_for_native는 false다. 이 도구에는 제출 기능이나 캠페인 해제 기능이 없다. 해시 일치는 파일 동일성의 증거이며 그 내용의 정확성을 보증하지 않는다.', '',
        '기존 캠페인 원장 JSON 전체를 읽으므로 과거 성과 필드가 메모리에 로드되지만, 이번 판정·출력·재계산에는 사용하지 않는다. 미래 성과를 읽지 않았다. 합성 검사 첫 14개 통과 후 이 설명을 바로잡고 최종 코드 해시로 예약된 두 번째 검사 묶음을 실행했다.', '',
        '## 현재 실제 메타데이터의 결과', '',
        f"- 초안 전제 충족: `{draft['draft_prerequisites_met']}`.",
        f"- 확보된 검사 항목: {len(draft['available_evidence'])}개. 미충족 항목: {len(draft['unmet_reasons'])}개. 이 수치는 수익성 지표나 독립 표본 수가 아니다.",
        '- 10월 26일~11월 6일의 예약된 10세션은 아직 종료·품질 확보 전이다.',
        '- 판정 시각 11월 7일 10:00 KST에 도달하지 않았다.',
        '- 권위 있는 단일 실행 시도 원장과 signal/clock/ledger/native path 증거는 아직 갖춰지지 않았다. 파일이 없다는 이유로 시도 0회를 입증했다고 하지 않는다.', '',
        '| 날짜 | 정규장 시작 UTC | 종료 UTC | 필요한 자료 증거 충족 |',
        '|---|---|---|---|']
    for row in draft['dates']:
        lines.append(f"| {row['date']} | {row['rth_open_utc']} | {row['rth_close_utc']} | {row['evidence_complete']} |")
    lines += ['', '## 남은 작업', '',
        '지금 완료한 것은 실행 전 증거를 검사하는 도구다. 실제 전략의 독립 검증, 주문/체결 검증, 대회 제출 적합성은 미완료다. 단일 실행을 안전하게 기록할 후속 실행기와 필요한 증거 수집을 별도 범위로 준비할 수 있으며, 미래 결과 계산은 기존 판정 시각과 품질 조건을 충족해야 한다.', '',
        '예약된 짧은 검증에서 통과하더라도 더 긴 사전 등록 검증 후보까지다. Goal의 완료 기준과 대회 마감의 차이는 [Goal 기록](nq-validation-goal-2026-10-25.md)에 명시했다. 합격 전략이 없는 상태를 변경하지 않았다.', '',
        '## 증거', '',
        '- [사전 등록 계획](../research/nq-goal-validation-readiness-plan.json)',
        '- [실제 메타데이터 초안](../research/validation-packet-draft.json)',
        '- [실행 횟수](../research/validation-packet-execution.json) / [합성 검사](../research/validation-packet-tests.json)',
        '- [검사기](../research/validation_packet.py) / [테스트](../tests/test_validation_packet.py)',
        '- [대시보드 수신 기록](../research/validation-readiness-publication.json)', '']
    (ROOT/REPORT).write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    run = dict(id=plan['id'], strategy='NQ 독립 검증 준비 도구', symbol='NQ DEC26',
        source='Metadata-only evidence draft and synthetic tests; no strategy execution',
        worker='windows-candidate-research', dataset='Frozen prospective reservation metadata only',
        status='completed', progress=100, phase='research_preparation', metrics={}, equity=[],
        reason='준비 도구 검사 완료. 미래10세션·판정일·실행 증거 대기. Goal 활성·채택전략 없음.',
        params=dict(goal_status='active', strategy_validated=False, tests_passed=tests['tests_run'],
            readiness_plan=READINESS_PLAN, readiness_plan_sha256=READINESS_HASH,
            draft=DRAFT, draft_sha256=file_hash(ROOT/DRAFT),
            draft_prerequisites_met=draft['draft_prerequisites_met'],
            unmet_reasons=draft['unmet_reasons'], ready_for_native=False,
            native_runs=0, downloads=0, performance_calculations=0), evidence=REPORT)
    validate_run(run)
    queue = Queue()
    config = json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text(encoding='utf-8'))
    emit(run, queue.telemetry)
    require(post(config['url'], '/api/runs', run, config['token']).get('ok') is True, 'Dashboard ACK missing')
    snap = queue.telemetry/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json')
    queue.control('ack:'+snap.name, file_hash(snap))
    publication = dict(id=plan['id'], ack=True, completed_at_utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=READINESS_HASH, draft_sha256=file_hash(ROOT/DRAFT), report_sha256=file_hash(ROOT/REPORT),
        telemetry_sha256=file_hash(snap), tests_sha256=file_hash(ROOT/'research/validation-packet-tests.json'),
        tests_passed=tests['tests_run'], goal_status='active', strategy_validated=False,
        protected_hashes_preserved=True, native_runs=0, downloads=0, performance_calculations=0)
    atomic(ROOT/PUBLICATION, publication)
    ledger = read('research/campaign-data-analysis-ledger.json')
    require(not any(e['id'] == plan['id'] for e in ledger['entries']), 'Preparation ledger already recorded')
    ledger['entries'].append(dict(id=plan['id'], kind='validation_infrastructure_only', status='completed',
        plan=READINESS_PLAN, plan_sha256=READINESS_HASH, publication=PUBLICATION, report=REPORT,
        packet_draft_runs=1, synthetic_suite_runs=tests['suite_attempt'], tests_passed=tests['tests_run'],
        native_runs=0, downloads=0, performance_calculations=0, strategy_validated=False, dashboard_ack=True))
    atomic(ROOT/'research/campaign-data-analysis-ledger.json', ledger)
    work = read('research/evidence-work-queue.json')
    require(not any(t['id'] == plan['id'] for t in work['tasks']), 'Preparation task already recorded')
    work['tasks'].append(dict(id=plan['id'], kind='validation_infrastructure_only', status='completed',
        plan=READINESS_PLAN, report=REPORT, publication=PUBLICATION, native_runs=0,
        next_action='Prepare a separately scoped counted executor with synthetic/dry-run checks; do not release or submit before fixed future data, decision time and required parity evidence.'))
    atomic(ROOT/'research/evidence-work-queue.json', work)
    backlog = read('research/candidate-backlog.json')
    backlog['validation_goal'] = dict(status='active', protocol='docs/nq-validation-goal-2026-10-25.md',
        strategy_validated=False, readiness_report=REPORT, readiness_publication=PUBLICATION,
        next_action='Separately scoped counted prospective execution preparation; frozen dates/rules and zero active native budget remain. Research completion requires independent validation and execution evidence.')
    atomic(ROOT/'research/candidate-backlog.json', backlog)
    verify_protected(ROOT, plan)
    Lifecycle().update('idle', 'Finite validation-readiness draft and synthetic checks completed and ACKed. NQ Goal remains active; no strategy validated. Future sessions/decision and actual execution evidence remain missing. No native calls, downloads or future outcomes; no scheduler.', None)
    print(json.dumps(dict(report=REPORT, dashboard_ack=True, tests=tests['tests_run'], strategy_validated=False)))


if __name__ == '__main__':
    main()
