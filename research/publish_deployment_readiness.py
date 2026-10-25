"""Summarize already-recorded metadata. No NinjaTrader or market-data calls."""
import hashlib
import json
from datetime import datetime, timezone

from runner.core import ROOT, Queue, atomic, file_hash
from runner.research_lifecycle import Lifecycle
from dashboard.reporter import emit, post
from dashboard.server import validate_run
from research.validation_packet import read_json, verify_protected

PLAN = 'research/nq-deployment-readiness-audit-plan.json'
PLAN_HASH = 'ecd3a897fd00fabfcb394ae02febced391acdd09f533243a9574850e01294bff'
FOLLOW = 'research/deployment-readiness-type-followup-plan.json'
REPORT = 'docs/nq-deployment-readiness-audit-2026-10-25.md'
RESULT = 'research/deployment-readiness-result.json'
PUBLICATION = 'research/deployment-readiness-publication.json'


def main():
    if (ROOT/PUBLICATION).exists() or (ROOT/RESULT).exists():
        raise FileExistsError('Already published/attempted; inspect evidence')
    plan = read_json(ROOT/PLAN)
    if file_hash(ROOT/PLAN) != PLAN_HASH:
        raise ValueError('Original read-only plan changed')
    verify_protected(ROOT, plan)
    original = read_json(ROOT/'research/deployment-readiness-mcp-observations.json')
    follow = read_json(ROOT/'research/deployment-readiness-type-followup-observations.json')
    if original['readonly_mcp_invocations'] != 5 or follow['readonly_mcp_invocations'] != 2:
        raise ValueError('Read-only count mismatch')
    observations = {r['name']:r for r in original['records']+follow['records']}
    if any(r['response'].get('isError') is True for r in observations.values()):
        raise ValueError('Transport error; observations not complete')
    h1 = observations['deploy_health_before']['parsed'][0]
    h2 = observations['deploy_health_after']['parsed'][0]
    h3 = observations['deploy_health_followup']['parsed'][0]
    fields = ('pid','processStartUtc','startedAt','assemblyName','assemblyLocation')
    stable = all({k:h[k] for k in fields} == {k:h1[k] for k in fields} for h in (h2,h3))
    status = observations['deploy_status']['parsed'][0]
    api = observations['deploy_api']['parsed'][0]
    jobs = observations['deploy_jobs']['parsed']
    catalog = observations['deploy_strategies_followup']['parsed']
    target = [r for r in catalog if r.get('fullName') == 'NinjaTrader.NinjaScript.Strategies.CodexBollingerClock']
    if len(target) != 1:
        raise ValueError('Exact backtest-selector type not uniquely observed')
    disk = read_json(ROOT/'research/deployment-readiness-disk-snapshot.json')
    sources = [r for r in disk['files'] if r['path'].endswith('CodexBollingerClock.cs')]
    prospective = read_json(ROOT/'research/bollinger-prospective-plan.json')
    source_match = len(sources) == 2 and all(r.get('sha256') == prospective['source_code_sha256'] for r in sources)
    intake = read_json(ROOT/'data/runner/future-data-intake/state.json')
    dates = prospective['evaluation_dates']
    if set(intake['entries']) != set(dates):
        raise ValueError('Intake dates changed')
    now = datetime.now(timezone.utc)
    sessions = [dict(date=d, status=intake['entries'][d]['status'],
                     session_close_utc=intake['entries'][d]['session_close_utc'],
                     closed=now>=datetime.fromisoformat(intake['entries'][d]['session_close_utc'])) for d in dates]
    evidence = [PLAN,FOLLOW,'research/deployment-readiness-mcp-observations.json',
                'research/deployment-readiness-type-followup-observations.json',
                'research/deployment-readiness-disk-snapshot.json']
    result = dict(id=plan['id'], recorded_at_utc=now.isoformat(),
        previous_goal_turn='progress: 96bf44c', current_goal_turn='progress: actual installed/runtime metadata resolved generic API false negative and import handoff gap',
        evidence_sha256={p:file_hash(ROOT/p) for p in evidence}, original_readonly_calls=5,
        separately_registered_followup_calls=2, readonly_mcp_calls=7, native_backtests=0,
        downloads=0, compile_reload=0, source_install=0, performance_calculations=0,
        installed_strategy_source_matches_frozen=source_match,
        backtest_selector_type_visible=True, observed_strategy_inputs=target[0]['inputs'],
        engine_generation_observations_match=stable, engine_observation={k:h1[k] for k in fields},
        generic_api_error=api.get('error'),
        generic_api_excludes_running_assembly=(h1['assemblyName'] not in ['NinjaTrader.Core','NinjaTrader.Gui','NinjaTrader.Custom','NinjaTrader.Vendor']),
        nt_status_current_by_mtime=(status.get('verdict')=='current'), nt_status_disagreement=status.get('disagreement'),
        addon_source_differences=status.get('installedVsRepo',{}).get('differs'),
        backtest_job_metadata=jobs, queued_or_running_job_ids=[j['id'] for j in jobs if j.get('state') in ('queued','running')],
        full_engine_idle_proven=False, compiled_method_source_identity_proven=False,
        connected_sources_observed=h3['connections'], current_any_live=h3['anyLive'], current_any_non_sim=h3['anyNonSim'],
        future_sessions=sessions, actual_download_requests=intake['actual_download_requests'],
        native_import_complete=False, actual_future_market_bytes_accessed=False,
        import_handoff=dict(collector_output='data/runner/future-data-intake/quality/YYYY-MM-DD.Last.txt',
            required_staging_path='data/runner/nt-import/<unique-batch-and-date>/NQ DEC26.Last.txt',
            required_format='Existing UTC 100ns Last text, byte-identical hash-preserved staging copy',
            importer_preconditions=['Existing research permission','No connected feeds','No open position/working order as checked by importer','Source path and SHA256 check'],
            completion_evidence=['Observe same import operation/path state and reported instrument/point count','Audit resulting NQ tick/minute cache hashes and actual native RTH bars before accepting parity'],
            executed=False),
        remaining=['Unclosed fixed ten dates and Nov7 decision time',
                   'Verified loaded method/source and current source/data hashes at actual execution',
                   'Finite native import handoff and data cache/parity evidence',
                   'Actual counted one-run transport integration and postrun evidence',
                   'Unlogged exit-order causality, longer independent validation and permitted forward execution'],
        ready_for_native=False, strategy_validated=False, goal_status='active',
        conclusion='Available source and backtest-selected type, but no actual prospective validation or current release')
    atomic(ROOT/RESULT,result)
    lines = ['# NQ 실제 설치·실행 준비 점검', '',
        '**설치 전략 소스와 백테스트용 전략 목록을 확인했다. 아직 검증된 전략이나 실행 허가는 없다.**', '',
        '원래 등록한 읽기 호출 5회 후, 예상하지 못한 타입 조회 오류를 확인하기 위해 별도 등록한 읽기 2회를 수행했다. 총 7회 모두 상태·타입·작업 목록 조회다. 백테스트·다운로드·컴파일/재로드·코드 설치·실제 시장 성과 계산은 0회다. 전략 목록 조회에는 기본값 확인을 위한 임시 전략 인스턴스 생성·속성 읽기·해제가 포함되며, 순수 reflection만 수행한 것은 아니다.', '',
        '## 확인 결과', '',
        '| 항목 | 결과 | 의미 |', '|---|---|---|',
        '| 설치 전략 파일 | 고정 소스 SHA256과 일치 | 디스크 코드 일치 |',
        '| 백테스트 전략 목록 | CodexBollingerClock, BandLength 기본값 20 확인 | 실행기가 선택하는 목록에 존재 |',
        '| 일반 타입 조회 | no type 응답 | 현재 실행 어셈블리가 조회 대상에서 제외됨 |',
        '| nt_status | current, disagreement=false | 수정시각 검사상 최신; 메서드 코드 동일성 증명은 아님 |',
        '| 엔진 관측 | 세 번의 process/start/assembly 정보 일치 | 세 번의 관측에서 세대 변경 징후 없음; 원자적 job 결합 보장은 아님 |',
        '| 작업 목록 | 등록된 2건 모두 done, queued/running 없음 | 목록 상태만 확인. 전체 엔진 idle 입증은 아님 |',
        '| 연결 | 관측 시 연결 목록 비어 있음 | 미래 자료를 받을 연결이 준비됐다는 뜻은 아님 |',
        '| 미래 자료 | 10일 모두 세션 종료 전 | 수집·수입·성과 검증 미실시 |', '',
        '## 타입 조회 오류의 범위', '',
        'health의 assemblyName은 실행 중인 NT8Bridge의 Assembly.GetName().Name이며 GUID 형태다. Api_TargetAssemblies는 NinjaTrader.Core/Gui/Custom/Vendor 네 이름만 선택하여 현재 bridge 어셈블리를 제외한다. 반면 백테스트 목록은 실행 중 bridge 어셈블리의 전략을 사용한다. 그 목록에서 해당 전략을 확인했으므로 일반 API의 no type을 전략 미설치·미컴파일로 해석하면 안 된다.', '',
        '설치된 AddOn 세 파일(Backtest, ChartControl, ResearchControl)은 MCP 소스 저장소 사본과 다르다. 이 차이는 기록했으며 재설치하거나 덮어쓰지 않았다. 소스/DLL 수정시각, 타입 이름, 파일 SHA만으로 로드된 각 메서드가 고정 전략 소스에서 만들어졌다고 증명하지 않는다.', '',
        '## 자료 수집과 NinjaTrader 반영 사이의 연결', '',
        '미래 collector는 품질 검사된 YYYY-MM-DD.Last.txt까지만 만들며 NinjaTrader import를 실행하지 않는다. 기존 importer는 nt-import 하위의 NQ DEC26.Last.txt라는 이름과 정확한 SHA256을 요구한다. 따라서 세션 종료와 품질 ACK 이후 원본을 보존한 별도 staging 사본, 단일 import 기록, 동일 작업/경로의 종료 상태, 실제 NQ 데이터 캐시·봉 대조가 필요하다. quality_passed를 import_complete로 바꾸면 안 된다.', '',
        '기존 importer의 연구 권한·연결 해제·포지션/작업 주문 검사도 그대로 적용된다. 이번 점검은 이 상태를 바꾸거나 권한을 설정하지 않았다. 미래 파일은 열람하지 않았고 단순 날짜표만 검사했다.', '',
        '## 다음 판단', '',
        '첫 고정 세션은 10월 27일 05:00 KST에 종료된다. 11월 2일 ET 세션부터는 DST 변경으로 한국 시각 종료가 06:00이다. 성과 판정은 기존 계획대로 11월 7일 10:00 KST 이후다. 취소된 30분 자동화는 재생성하지 않았다.', '',
        '현재 가능한 준비는 수입 handoff와 실제 단일 실행 경로를 구체화하는 범위다. 모든 준비가 끝나도 아직 발생하지 않은 세션과 더 긴 독립 검증을 대신할 수 없다. 타입 조회 오류를 확인하려고 새 전략 백테스트를 돌리거나 기존 관측 날짜를 다시 최적화하지 않는다.', '',
        '## 증거', '',
        '- [원래 5회 점검 계획](../research/nq-deployment-readiness-audit-plan.json) / [별도 2회 타입 확인 계획](../research/deployment-readiness-type-followup-plan.json)',
        '- [원 관측](../research/deployment-readiness-mcp-observations.json) / [타입 후속 관측](../research/deployment-readiness-type-followup-observations.json)',
        '- [설치 파일 해시](../research/deployment-readiness-disk-snapshot.json) / [판정과 남은 증거](../research/deployment-readiness-result.json)',
        '- [대시보드 수신](../research/deployment-readiness-publication.json)', '']
    (ROOT/REPORT).write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    run=dict(id=plan['id'],strategy='NQ 실제 설치·실행 준비',symbol='NQ DEC26',
        source='Read-only NT metadata and installed source audit',worker='windows-candidate-research',
        dataset='No market data or performance inspection',status='completed',progress=100,phase='research_preparation',
        metrics={},equity=[],reason='고정 소스와 백테스트 선택 타입 확인. 일반 API는 실행 assembly 제외. 실제 미래 자료/import/검증은 미완료.',
        params=dict(goal_status='active',strategy_validated=False,readonly_mcp_calls=7,native_backtests=0,result=result),evidence=REPORT)
    validate_run(run);q=Queue();config=read_json(ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json')
    emit(run,q.telemetry)
    if post(config['url'],'/api/runs',run,config['token']).get('ok') is not True:
        raise RuntimeError('Dashboard ACK missing')
    snap=q.telemetry/(hashlib.sha256(run['id'].encode()).hexdigest()+'.json')
    q.control('ack:'+snap.name,file_hash(snap))
    atomic(ROOT/PUBLICATION,dict(id=plan['id'],ack=True,completed_at_utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=PLAN_HASH,followup_plan_sha256=file_hash(ROOT/FOLLOW),result_sha256=file_hash(ROOT/RESULT),
        report_sha256=file_hash(ROOT/REPORT),telemetry_sha256=file_hash(snap),readonly_mcp_calls=7,native_backtests=0,
        strategy_validated=False,goal_status='active',protected_hashes_preserved=True))
    attempt=read_json(ROOT/'research/deployment-readiness-audit-attempt.json')
    attempt.update(status='completed',original_readonly_mcp_calls=5,remaining_reads=[],followup_plan=FOLLOW,
        separately_registered_followup_readonly_calls=2,publication=PUBLICATION)
    atomic(ROOT/'research/deployment-readiness-audit-attempt.json',attempt)
    ledger=read_json(ROOT/'research/campaign-data-analysis-ledger.json')
    ledger['entries'].append(dict(id=plan['id'],kind='deployment_readiness_only',status='completed',plan=PLAN,
        followup_plan=FOLLOW,report=REPORT,result=RESULT,publication=PUBLICATION,readonly_mcp_calls=7,native_runs=0,downloads=0,dashboard_ack=True))
    atomic(ROOT/'research/campaign-data-analysis-ledger.json',ledger)
    next_action='Complete finite audited Last staging/import handoff and counted real transport wiring; no execution until fixed data/decision/release prerequisites. Do not repeat synthetic passing suites without new concern.'
    work=read_json(ROOT/'research/evidence-work-queue.json')
    work['tasks'].append(dict(id=plan['id'],kind='deployment_readiness_only',status='completed',report=REPORT,
        publication=PUBLICATION,native_runs=0,next_action=next_action))
    atomic(ROOT/'research/evidence-work-queue.json',work)
    backlog=read_json(ROOT/'research/candidate-backlog.json')
    backlog['validation_goal'].update(status='active',readiness_report=REPORT,readiness_publication=PUBLICATION,next_action=next_action,strategy_validated=False)
    atomic(ROOT/'research/candidate-backlog.json',backlog)
    verify_protected(ROOT,plan)
    Lifecycle().update('idle','Actual read-only deployment audit ACKed: frozen strategy source matches and backtest selector sees type. Generic API excludes active GUID assembly. Future data/import, source/compiled identity and actual release evidence remain pending; no validated strategy.',None)
    print(json.dumps(dict(report=REPORT,ack=True,readonly_mcp_calls=7,native_backtests=0,source_match=source_match,type_visible=True)))


if __name__=='__main__':
    main()
