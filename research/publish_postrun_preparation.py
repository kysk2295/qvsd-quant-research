"""Publish one metadata report of synthetic preparation, never market results."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from runner.core import ROOT, Queue, atomic, file_hash
from runner.research_lifecycle import Lifecycle
from dashboard.reporter import emit, post
from dashboard.server import validate_run
from research.validation_packet import read_json, verify_protected, write_exclusive_json
from research.run_postrun_preparation_tests import PLAN, PLAN_HASH, CODE

RESULT = 'research/postrun-preparation-result.json'
REPORT = 'docs/nq-postrun-evaluator-preparation-2026-10-25.md'
PUBLICATION = 'research/postrun-preparation-publication.json'


def main():
    plan = read_json(ROOT/PLAN)
    if file_hash(ROOT/PLAN) != PLAN_HASH:
        raise ValueError('Preparation plan changed')
    verify_protected(ROOT, plan)
    tests = read_json(ROOT/'research/postrun-preparation-tests.json')
    if not tests['success'] or tests['skips'] or any(file_hash(ROOT/p) != h for p,h in tests['code_hashes'].items()):
        raise ValueError('Current code lacks passing synthetic evidence')
    if (ROOT/RESULT).exists() or (ROOT/PUBLICATION).exists():
        raise FileExistsError('Metadata report already attempted; inspect evidence instead of rerun')
    write_exclusive_json(ROOT/'research/postrun-preparation-report-attempt.json',
        dict(id=plan['id'], metadata_reports=1, reserved_at_utc=datetime.now(timezone.utc).isoformat()))
    context = []
    for path, expected, lines in [
        ('C:/Users/User/Documents/NinjaTrader 8/bin/Custom/ImportTypes/@TextImportType.cs',
         'cd421b1835319f0e1b8366f702c6c662b1c1dafcddb8078101d19d048bb9a339', '117-121,152-153,162-168'),
        ('C:/Users/User/Documents/NinjaTrader 8/bin/Custom/BarsTypes/@MinuteBarsType.cs',
         '64f0d2960217dc9ae23bd29f7d0a1c62e3bb22fb5909e0608e1ef53e83461bd4', '49-51,89-96')]:
        actual = file_hash(Path(path))
        if actual != expected:
            raise ValueError('Reviewed installed timestamp/aggregation source changed')
        context.append(dict(path=path, sha256=actual, inspected_lines=lines))
    result = dict(id=plan['id'], plan_sha256=PLAN_HASH, generated_at_utc=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn_classification='progress: de37f6c', current_goal_turn_classification='progress: pure postrun evaluators and focused synthetic evidence',
        code_hashes={p:file_hash(ROOT/p) for p in CODE}, installed_source_context=context,
        tests_passed=tests['tests_run'], synthetic_suite_runs=tests['suite_attempt'],
        native_calls=0, downloads=0, real_market_performance_calculations=0, production_attempt_reservations=0,
        actual_future_market_bytes_accessed=False, strategy_validated=False, goal_status='active',
        production_executor_integrated=False, postrun_parity_complete=False,
        implemented=['100ns clock/ISO/DST and cumulative daily snapshot reconciliation',
                     'Native ledger/submission/execution correspondence with output event indexes',
                     'Raw Last 390-minute closes, SMA20 population bands/crossings and entry eligibility',
                     'Frozen fee5/10, incremental ticks2/4 per fill, best positive day removal and zero-trade dates',
                     'Last marked equity bounds reconciled to price ledger, daily loss and trade statistics'],
        remaining=['Future complete source data and frozen Nov7 decision gate',
                   'Authoritative source/deployment/import hashes, no-peek/attempt and released native execution evidence',
                   'Unlogged individual exit order submission/cancellation and stop trigger/fill causality',
                   'Longer independent validation and permitted execution evidence'],
        decision='synthetic_preparation_complete_not_strategy_validation')
    write_exclusive_json(ROOT/RESULT, result)
    lines = ['# NQ 미래 검증 결과 판독기 준비', '',
        '**새 전략 검증 결과는 없다. 고정된 미래 검증을 평가할 순수 함수와 합성 검사를 구현했다.**', '',
        f"합성 검사 {tests['tests_run']}개가 통과했다. 실제 시장 성과 계산·NinjaTrader 호출·다운로드·생산 실행 예약은 모두 0회다. 기존 전략·계획·캠페인 게이트·이전 결과는 해시를 보존했다.", '',
        '## 판독하는 증거', '',
        '| 항목 | 이번 구현 |', '|---|---|',
        '| 정밀 시각 | .NET ticks와 7자리 시각의 일치, 100ns UTC 변환, 명시한 시간대와 DST |',
        '| 누적 거래 로그 | 매일 전체 거래를 다시 출력하는 CLOCK_TRADE의 이전 prefix를 검사. 단순 행 세기나 set 중복 제거를 하지 않음 |',
        '| 원장 | 제출·실행 콜백·native 거래의 시각/방향/수량/가격/손익을 대조 |',
        '| 분봉·진입 | 원시 Last의 390분 종가, SMA20·모집단 표준편차·밴드 교차, 시간·flat/pending·4회·실현손실 제한을 대조 |',
        '| 비용 | $5/$10 왕복 수수료와 추가 2/4틱을 각 체결에 적용. 같은 native 원장에 대한 산술 시나리오 |',
        '| 집중도 | 10일에 무거래일 0을 포함하고 최고 양의 일손익을 제거. 최고 거래를 제거하거나 음수일을 빼지 않음 |',
        '| 위험 | 고정 체결과 Last 평가 경로의 최종 손익·청산 DD 일치, 보유 DD 범위와 일 시작 대비 손실 |', '',
        '## 합성 검사에서 확인한 경계', '',
        '로그 누락·변조·누적 prefix 불일치, 시각 정밀도 손실, 잘못된 시간대/동일 시각 순서, 빈 분·분 경계 tick·중복 분봉, 수학/신호 불일치, 미체결 진입 대응 불가, 계획/instance 불일치, 비용·최고 수익일·무거래일·손실 제한을 검사했다. 작은 합성 사례의 통과는 실제 시장 결과가 아니다.', '',
        '설치된 TextImportType/MinuteBarsType 소스는 tick 100ns를 보존하고 정확한 분 경계 tick을 다음 [start,end) 봉에 넣는다. 이 소스 확인만으로 실제 수입 데이터가 일치한다고 판단하지 않는다. 원자료와 native BAR를 실제 실행 후 다시 대조해야 한다.', '',
        '## 아직 확인할 수 없는 부분', '',
        '원전략은 청산 주문 각각의 제출·취소·접수 과정을 기록하지 않는다. 따라서 TimeExit/Stop loss라는 체결 이름이나 COUNTS 합계만으로 최초 청산 조건과 stop 발동·체결 인과관계를 검증했다고 표시하지 않는다. 전체 postrun_parity_complete와 strategy_validated는 계속 false다.', '',
        'CLOCK_SUBMIT는 실제 주문 제출 벽시각이 아니라 Time[0]의 주 봉 라벨을 출력한다. 따라서 이 값과 체결 시각의 차이는 봉 종료부터 체결까지의 차이이며 실제 주문 전송 지연을 증명하지 않는다. primary Time[0]→BAR 대응과 COUNTS 전체 재구성도 이번에 검증했다고 표시하지 않는다. 같은 BAR 뒤 청산 콜백의 위치 때문에 진입 판정 순서가 불명확하면 미해결로 남긴다.', '',
        '동일 시각 Last와 체결의 이벤트 순서는 100ns 시각만으로 확정되지 않는다. 보유 중 DD를 범위로 남기며, 서로 다른 거래의 청산·재진입이 같은 시각이면 기존 경로 계산기의 한계로 미해결을 남긴다. 실현 −$900은 추가 진입 제한이며 강제 일손실 한도가 아니다.', '',
        '미래 데이터 10일, 11월 7일 10:00 KST 판정 시각, 출처·설치·수입 데이터 해시, 결과 미리보기 없음, 단일 실행 원장과 실제 허용 실행 경로가 필요하다. 이 순수 함수에 입력 객체나 True를 넣는 것으로 실행 권한이나 전략 인증을 만들 수 없다.', '',
        '비용 기준을 통과하더라도 해당 표본의 산술 결과일 뿐이다. 별도 품질·실행 증거와 더 긴 독립 검증을 충족해야 한다. 리플레이 주문·실시간 모의 체결을 완료했다고 표현하지 않는다.', '',
        '## 증거', '',
        '- [사전 계획](../research/nq-postrun-evaluator-preparation-plan.json)',
        '- [합성 검사와 코드 해시](../research/postrun-preparation-tests.json) / [시도 이력](../research/postrun-preparation-test-attempts.json)',
        '- [준비 결과와 남은 증거](../research/postrun-preparation-result.json)',
        '- [정밀 시각](../research/prospective_clock.py) / [비용·Last 경로](../research/prospective_cost_path.py) / [통합 대조](../research/prospective_postrun.py)',
        '- [대시보드 수신](../research/postrun-preparation-publication.json)', '']
    (ROOT/REPORT).write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    run = dict(id=plan['id'], strategy='NQ 미래 결과 판독기 준비', symbol='NQ DEC26',
        source='Pure postrun evaluator; synthetic evidence only', worker='windows-candidate-research',
        dataset='Manufactured arrays and event logs; no actual market performance', status='completed',
        progress=100, phase='research_preparation', metrics={}, equity=[],
        reason='합성 검사 완료. 실제 미사용 자료·실행·청산 인과관계 증거는 미완료. 채택 전략 없음.',
        params=dict(goal_status='active', strategy_validated=False, native_calls=0,
            tests_passed=tests['tests_run'], report=REPORT, result=result), evidence=REPORT)
    validate_run(run)
    q = Queue()
    config = read_json(ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json')
    emit(run, q.telemetry)
    if post(config['url'], '/api/runs', run, config['token']).get('ok') is not True:
        raise RuntimeError('Dashboard ACK missing; retain prepared report')
    snap = q.telemetry/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json')
    q.control('ack:'+snap.name, file_hash(snap))
    atomic(ROOT/PUBLICATION, dict(id=plan['id'], ack=True, completed_at_utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=PLAN_HASH, result_sha256=file_hash(ROOT/RESULT), report_sha256=file_hash(ROOT/REPORT),
        tests_sha256=file_hash(ROOT/'research/postrun-preparation-tests.json'), telemetry_sha256=file_hash(snap),
        tests_passed=tests['tests_run'], goal_status='active', strategy_validated=False,
        native_calls=0, real_market_performance_calculations=0, protected_hashes_preserved=True))
    ledger = read_json(ROOT/'research/campaign-data-analysis-ledger.json')
    ledger['entries'].append(dict(id=plan['id'], kind='validation_infrastructure_only', status='completed',
        plan=PLAN, plan_sha256=PLAN_HASH, result=RESULT, report=REPORT, publication=PUBLICATION,
        native_runs=0, downloads=0, synthetic_suite_runs=tests['suite_attempt'], tests_passed=tests['tests_run'], dashboard_ack=True))
    atomic(ROOT/'research/campaign-data-analysis-ledger.json', ledger)
    next_action = 'Audit remaining source/deployment/import and executable validation prerequisites without future outcome access; preserve missing exit causality and future-data/decision gates.'
    work = read_json(ROOT/'research/evidence-work-queue.json')
    work['tasks'].append(dict(id=plan['id'], kind='validation_infrastructure_only', status='completed',
        report=REPORT, publication=PUBLICATION, native_runs=0, next_action=next_action))
    atomic(ROOT/'research/evidence-work-queue.json', work)
    backlog = read_json(ROOT/'research/candidate-backlog.json')
    backlog['validation_goal'].update(status='active', readiness_report=REPORT,
        readiness_publication=PUBLICATION, next_action=next_action, strategy_validated=False)
    atomic(ROOT/'research/candidate-backlog.json', backlog)
    verify_protected(ROOT, plan)
    Lifecycle().update('idle', 'Synthetic postrun reconciliation completed and ACKed; actual future data, frozen decision, source/execution and unlogged exit-causality evidence remain missing. Goal active, no validated strategy.', None)
    print(json.dumps(dict(report=REPORT, ack=True, tests=tests['tests_run'], native_calls=0)))


if __name__ == '__main__':
    main()
