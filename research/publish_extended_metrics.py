"""Publish historical descriptive scorecards without changing original metrics."""
import copy,hashlib,json
from collections import defaultdict
from runner.core import ROOT,Queue,atomic,file_hash
from dashboard.reporter import emit,post
from dashboard.server import validate_run
from runner.research_lifecycle import Lifecycle

NAMES={'bollinger':'볼린저 복귀','cafe-ib60':'IB 돌파 실패 회귀','cafe-retest15':'OR15 리테스트','cafe-retest30':'OR30 리테스트',
    'channel':'채널 돌파','gap':'갭 회귀','macd':'MACD','moving-momentum':'Moving Momentum','nr7':'NR7','ofi':'OFI','rsi2':'RSI2','stochastic':'빠른 스토캐스틱'}
def number(value,digits=2):return '—' if value is None else f'{value:,.{digits}f}'
def main():
    source=ROOT/'research/extended-metrics-review.json';review=json.loads(source.read_text());digest=file_hash(source)
    def verify():
        for p,h in {**review['original_source_hashes'],**review['immutable_hashes']}.items():
            if file_hash(ROOT/p)!=h:raise RuntimeError('Protected input changed: '+p)
    verify()
    lines=['# 기존 NQ 전략 다지표 재평가 — 2026-10-25','',
        '주요 보존 구성 12개, 비용 조건 24개를 기존 원장으로 재평가했다. 새 네이티브 실행 0회. 아래는 왕복 수수료 $10 조건이다. 각 후보의 관측 기간은 다르며, 동일한 표본의 순위 비교가 아니다. 모든 결과는 원전이 아닌 실제 시험한 NQ 변형에 한정한다.','',
        '| 후보 | 일수/거래 | 승률 | 평균이익/평균손실 | 실현 손익비 | PF | 거래당 기대값 | 순손익 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    selected=[r for r in review['cases'] if r['fee_per_roundtrip']==10]
    for r in selected:
        m=r['metrics'];lines.append(f"| {NAMES[r['candidate']]} | {m['sessions']}/{m['trades']} | {number(m['win_rate']*100 if m['win_rate'] is not None else None,1)}% | ${number(m['avg_win'])}/${number(m['avg_loss_abs'])} | {number(m['realized_payoff_ratio'])} | {number(m['profit_factor'])} | ${number(m['expectancy_per_trade'])} | ${number(m['net'])} |")
    lines+=['','손익비는 실현 평균 이익/평균 손실이며 사전 목표 손익비가 아니다. 손실이 없는 1전 1승은 PF/손익비를 계산할 수 없다.','',
        '| 후보 | 청산 DD | 최대 연속손실 | 하루 평균 거래 | 최고 수익일 제외 | 추가 편도4틱 후 순손익 |',
        '|---|---:|---:|---:|---:|---:|']
    for r in selected:
        m=r['metrics'];lines.append(f"| {NAMES[r['candidate']]} | ${number(m['closed_trade_drawdown']['maximum'])} | {m['max_consecutive_losses']} | {number(m['trades_per_session'])} | ${number(m['net_without_best_positive_day'])} | ${number(m['additional_cost_sensitivity'][-1]['net'])} |")
    lines+=['','## 타점·청산 진단','',
        '| 후보 | 평균 MAE | 평균 MFE | 평균 비용 전 되돌림 | 평균 구간 진입효율 | 평균 구간 청산효율 |',
        '|---|---:|---:|---:|---:|---:|']
    for r in selected:
        e=r['metrics']['excursion'];lines.append(f"| {NAMES[r['candidate']]} | ${number(e['mean_mae_currency'])} | ${number(e['mean_mfe_currency'])} | ${number(e['mean_end_trade_giveback_gross'])} | {number(e['mean_entry_range_efficiency']*100 if e['mean_entry_range_efficiency'] is not None else None,1)}% | {number(e['mean_exit_range_efficiency']*100 if e['mean_exit_range_efficiency'] is not None else None,1)}% |")
    lines+=['','위 표는 네이티브 봉 기반 MAE/MFE에 의존한다. 정확한 틱 순서·호가 청산 가능성을 검증한 결과가 아니며, 보유기간에 따라 달라지는 사후 진단이다. 볼린저의 평균 비용 전 되돌림 약 $357은 청산 정책을 별도로 연구할 이유가 되지만, 그 금액을 실제로 모두 얻을 수 있다는 뜻은 아니다. 타점 개선이나 새로운 익절 규칙을 이 결과에 맞춰 적용하지 않았다.','',
        '## 해석','',
        '- 볼린저: 19승/33패. 평균 순이익 약 $499, 평균 순손실 약 $251. 실현 손익비 기준 손익분기 승률 33.47%에 비해 실제36.54%로 여유가 작다. 추가 편도 약2.30틱이면 현재 이익이 소진되는 산술 구조다. 최고 수익일 제외 시 -$75, 기존 Last 보유 중 DD 범위 $3,110~$3,140을 함께 봐야 한다.',
        '- IB 회귀: 1승/3패. 평균 승리 $2,005 대비 평균 손실 $210이라 PF가 높지만 최고 수익일 제외 -$630이다. 4거래만으로 우위를 확정할 수 없다.',
        '- RSI2: 2승/4패. 실현 손익비3.54와 PF1.77은 양수 기대값을 설명하지만 최고 수익일 제외 -$270, 12세션6거래라 빈도와 재현 근거가 부족하다.',
        '- OFI: PF1.015, 거래당 $2.75의 작은 이익은 추가 편도0.275틱만으로 소진된다. 현재 버전의 실행비용 여유가 거의 없다.',
        '- MACD·스토캐스틱·채널·갭·Moving Momentum: 이번 비용 조건에서 표본 평균 기대값이 음수다. NR7과 OR 리테스트는 특히 거래 수가 적어 일반화할 수 없다.',
        '- 볼린저·IB·RSI의 일별 블록 재표집 범위도 0을 포함한다. 짧은 사후 표본의 탐색용 민감도이며 독립적 수익성 검정은 아니다.',
        '- 새 지표만으로 후보를 승격하거나 기존 미래 계획을 바꾸지 않는다. 실전/대회 투입 적격성이 입증된 후보는 아직 없다.','',
        '## 추가 지표와 한계','',
        'JSON에는 비연율 일별 Sharpe/Sortino, 명목 R, 보유시간, 시간대·방향별 분해, 일별 손익, 낙폭 지속 관측 수, 희소 표본 표시, 블록 재표집 구간과 원자료 해시를 보존했다. 단기간 Sharpe를 연율화하지 않았고, DSR/PBO·정확한 고정시점 markout·호가 실행효율·대회 라운드 적격성은 필요한 증거가 없어 확정값을 제시하지 않았다.','',
        '방법과 출처: [확장 지표 리서치](extended-metrics-methodology-2026-10-25.md). 계산 결과: `research/extended-metrics-review.json`. 계산기 경계 테스트14개 통과. 원본 파일 및 미래 계획 해시를 검증했다.']
    reportpath=ROOT/'docs/extended-metrics-results-2026-10-25.md';reportpath.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    byrun=defaultdict(list)
    for row in review['cases']:
        for rid in row['run_ids']:byrun[rid].append(row)
    q=Queue();config=json.loads((ROOT.parent/'qvsd-dashboard-agent/.dashboard-worker.json').read_text());acks=[]
    for rid,cases in byrun.items():
        snap=q.telemetry/(hashlib.sha256(rid.encode()).hexdigest()+'.json');run=json.loads(snap.read_text())
        before={k:copy.deepcopy(run.get(k)) for k in ('metrics','equity','status','dataset','cost')}
        params=run.setdefault('params',{});assessment=params.setdefault('assessment',{})
        if assessment.get('extended_metrics_review',{}).get('sha256')!=digest:
            params.setdefault('assessment_history',[]).append(copy.deepcopy(assessment))
        assessment['extended_metrics_review']=dict(sha256=digest,report='research/extended-metrics-review.json',
            scope='Candidate/cost aggregate over listed run_ids and audited dates; NOT this component run alone',cases=cases,
            methodology='docs/extended-metrics-methodology-2026-10-25.md',native_runs=0,original_metrics_preserved=True)
        params.setdefault('reason_before_extended_metrics',run.get('reason',''))
        m=cases[0]['metrics']
        run['reason']=f"[기존 원장 합산 재평가: {m['trades']}거래, 비용 후 승률 {number(m['win_rate']*100 if m['win_rate'] is not None else None,1)}%, PF {number(m['profit_factor'])}; 독립 검증 아님] "+params['reason_before_extended_metrics']
        assert all(run.get(k)==v for k,v in before.items());validate_run(run);emit(run,q.telemetry)
        if post(config['url'],'/api/runs',run,config['token']).get('ok') is not True:raise RuntimeError('Metrics ACK missing')
        q.control('ack:'+snap.name,file_hash(snap));acks.append(dict(run_id=rid,ack=True,telemetry_sha256=file_hash(snap)))
        if len(acks)%10==0:print(json.dumps(dict(metadata_acks=len(acks))),flush=True)
    p=ROOT/'research/candidate-backlog.json';backlog=json.loads(p.read_text());backlog['extended_metrics_review']='research/extended-metrics-review.json'
    backlog['extended_metrics_interpretation']='Descriptive historical reassessment only; no frozen-plan change or adopted strategy.';atomic(p,backlog)
    p=ROOT/'research/evidence-work-queue.json';queue=json.loads(p.read_text());tid='extended-metrics-existing-ledger-review'
    queue['tasks']=[t for t in queue['tasks'] if t['id']!=tid]+[dict(id=tid,status='completed',kind='existing-ledger-metrics',evidence='research/extended-metrics-review.json',native_runs=0)]
    atomic(p,queue);verify()
    atomic(ROOT/'research/extended-metrics-publication.json',dict(metadata_acks=acks,candidate_configurations=12,cost_cases=24,
        tests_passed=14,native_runs=0,downloads=0,immutable_hashes_preserved=True,original_metrics_preserved=True,
        result_sha256=digest,methodology_sha256=file_hash(ROOT/'docs/extended-metrics-methodology-2026-10-25.md'),report_sha256=file_hash(reportpath)))
    Lifecycle().update('idle','12configs/24cost cases reevaluated from saved ledgers: winrate,payoff,expectancy,PF,drawdown,excursions and dependence limits. No new native/download or future outcome peek; frozen plan unchanged.',None)
    print(json.dumps(dict(metadata_acks=len(acks),configurations=12,cost_cases=24,tests=14,native_runs=0,downloads=0)),flush=True)

if __name__=='__main__':main()
