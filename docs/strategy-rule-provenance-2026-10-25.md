# 원전 규칙과 NQ 연구 변형의 적용 범위

현재 검증은 각 원전의 충실한 재현이 아니라 **별도로 정의한 NQ 변형의 구현·체결·원장 검증**이다. 구현이 명세대로 작동한다는 근거와 그 명세가 적절하다는 근거는 다르다. 하루 최대 4회와 48틱 손절의 적절성을 비교 검증한 근거는 확인되지 않았다. 따라서 기존 성과 판정은 해당 제한 버전에만 적용한다.

## 공통 제약의 이력

- 최초 커밋 `1f6cd9e`의 `research/backtest.py`에 이미 하루 `n>=4` 차단이 있다. 그 제한을 선택한 비교 실험은 확인되지 않는다.
- `85e1116`의 RSI 코드 주석에서 48틱의 근거는 **12포인트×$20 + 2포인트×$20 + $10 = $290**이라는 연구 위험 예산이다. 원전의 최적 손절값이나 실제 손실 상한이 아니다.
- 저장된 대회 자료는 **라운드당 최소 4회 진입**이라고 요약한다. **하루 최대 4회 연구 제약**과 단위·방향·목적이 다르다. 두 숫자가 같다는 이유로 혼동의 원인을 단정할 수 없다. 현재 [공지 원문](https://cafe.naver.com/f-e/cafes/31685329/articles/55)은 직접 재확인하지 못했다.
- 대부분의 네이티브 코드는 주문 제출 시 횟수를 올린다. 거절·취소가 있다면 체결 수나 대회가 인정하는 진입 수와 같지 않을 수 있다. Cafe의 일일 손실 차단은 gross 기준이며, RSI/볼린저/MACD/스토캐스틱은 거래당 $10을 차감한 realized 기준이다.

## 후보별 차이

| 후보 | 원전/출처와의 주요 차이 | 실제 횟수 제한 | 기존 판정 범위 |
|---|---|---|---|
| RSI2 | 일봉에서 5분봉, 롱 전용, 고정 손절·시간 청산 추가 | 4회/일 | ETH 지표 워밍업을 사용한 NQ 롱 변형 |
| 볼린저 | 밴드 가격의 stop-entry/OCA를 flat-only 시장가로 변경; SMA·시간 청산과 48틱 보호 손절 추가 | 4회/일 | 첫 네 적격 기회 중심의 NQ 변형 |
| NR7 | RTH를 일봉으로 정의, 분봉 종가 확인, 48틱 손절 | **1회/일** | ChartSchool 해석의 추가 변형; Crabel 원전 재현 아님 |
| Cafe 범위 | 원전의 완전한 주문 명세 미확인; 연구자가 OR/IB·필터·청산을 정량화 | 4회/일 | 구조적 손절과 위험 예산을 통과한 셋업만 |
| MACD | 원전 방향 전환을 flat-only 진입/청산으로 변경; RTH 재설정·시간 제한·48틱 추가 | 4회/일 | 제한된 장중 변형의 부정적 결과 |
| 빠른 스토캐스틱 | 원문 50/100포인트 손절/목표를 12/24포인트로 변경; 시간 제한 추가 | 4회/일 | 해당 크기·세션의 변형 결과 |

출처: [RSI2](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2), [TradingView 볼린저 코드](https://www.tradingview.com/support/solutions/43000599826-bollinger-bands-strategy-directed/), [ChartSchool NR7](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7), [TradingView MACD](https://www.tradingview.com/support/solutions/43000644943-macd-strategy/), [AlgoTest 예제](https://docs.algotest.in/signals/pinescripts/stochastic_oscillator_strategy/). Cafe는 저장된 `research/build_report.py` 요약과 자체 `research/backtest.py`가 확인 가능한 근거이며, 원문 전체와의 일치 검증으로 취급하지 않는다.

각 후보의 진입·손절·청산·재진입·봉·세션·최대횟수, 코드 행 위치와 해시는 `research/strategy-rule-provenance-review.json`에 기록했다. RSI의 진입 시각은 코드상 봉 **시작** 09:40 이상 15:30 미만이며, 5분봉 **종료 판단**은 09:45~15:30이다. 이전 명세의 09:40~15:29는 판단 시각을 명확히 구분하지 못했다. 코드나 기존 결과는 변경하지 않았다.

대시보드의 현재 코드 비교 명세는 참조용이다. 각 과거 실행의 저장된 `source_hash`가 검토 코드와 일치하는지 별도 표시한다. 일치하지 않거나 해시가 없으면 과거 버전까지 동일한 규칙이라고 주장하지 않는다. 과거 입력·출처 해시·평가 이력을 보존한다.

## 위험 정책과 전략 고유 손절을 분리

전략이 무효가 되는 가격이나 고유 청산 규칙을 먼저 정한다. 그 거리와 1NQ 계약가치·비용으로 위험을 계산하고 연구 예산에 맞는지 판단한다. 예산을 넘으면 **1NQ 조건에서 부적합**으로 기록한다. 손절을 억지로 48틱으로 줄이거나 위험 예산을 늘리지 않는다. 스토캐스틱 원문 50포인트 손절은 1NQ에서 비용 전 $1,000이므로 $300 연구 예산과 양립하지 않는다. 무손절을 설명하는 RSI 원전도 현재 위험 명세 아래에서 그대로 실행 가능하다고 취급하지 않는다.

Cafe 코드는 이미 구조적 손절을 유지하고 예산 초과 셋업을 거절한다. 다만 이 필터가 남긴 표본의 결과를 원전 전체 성과로 일반화할 수 없다. 네 번 제한도 이후 기회를 제외하므로, 공통 제한을 썼다는 사실만으로 공정하거나 충분한 전략 비교가 되지는 않는다. 각 제약의 효과는 아직 분리해 검증하지 않았다.

## 동결 계획과 미실행 질문

볼린저의 실행 방식·시간 제한·횟수 제한은 원전 대비 중대한 변경이다. 이 사실이 기존 원장 수치를 무효로 만들지는 않지만, 원전 전략의 수익성을 검증했다는 해석은 성립하지 않는다. 미래 계획은 **현재 제한된 NQ 전략 자체**를 대상으로 유지한다. 코드·비용·날짜·평가 시각·후보 선정·계획 해시는 변경하지 않았다. 원전 복제나 다른 설계를 원하면 별도 사전 명세와 새로운 미관측 기간이 필요하다.

원문 확보, 전략 고유 손절의 예산 적합성, 횟수 제한 효과, 원전 주문 방식, 봉/세션 및 시간 청산 효과를 각각 유한 연구 질문으로 backlog에만 기록했다. 실행 예산은 0이며 새 후보 실행·재계산·최적화를 하지 않았다. 기존 부정적 결과 역시 원전 또는 전략 계열 전체의 실패로 확대하지 않는다.

저장된 대회 보고서는 10월 29일 18:00 마감을 언급하나, 최신 공지와 시간대는 재확인하지 못했다. 11월 7일 10:00 KST는 별도의 연구 평가 시점이며 대회 제출 준비 완료를 뜻하지 않는다.

## 장 마감 뒤 데이터 수집 명령

첫 등록 세션은 10월 26일 ET16:00, 즉 **10월 27일 KST05:00**에 종료한다. 11월 2일부터 종료 시각은 KST06:00이다. 종료 즉시 제공자가 파일을 제공한다는 보장은 없다.

Windows PowerShell에서 다음과 같이 실행한다. 먼저 실행하는 dry-run은 요청을 보내지 않는다.

```powershell
Set-Location 'C:\Users\User\Documents\Codex\qvsd-experiment-runner'
& 'C:\Users\User\Documents\Codex\2026-10-04\dlrj\work\nt8-mcp\.venv\Scripts\python.exe' -X utf8 -m runner.future_data_collector
& 'C:\Users\User\Documents\Codex\2026-10-04\dlrj\work\nt8-mcp\.venv\Scripts\python.exe' -X utf8 -m runner.future_data_collector --execute
```

전제조건: 기존 권한으로 NinjaTrader/연구 브리지가 동작하고 Historical Data 창의 다운로드 버튼이 읽기 가능하며 활성화되어 있어야 한다. Playback은 이미 연결 해제되어 있어야 한다. 수집기가 연결·해제, 권한 활성화, 주문을 수행하지 않는다. 조건 미충족 시 멈추며 차단된 경로를 재시도하지 않는다. 미래 성과 실행과도 연결되지 않는다.

한 번의 호출은 최대 3일을 처리하되, 비동기 다운로드를 한 건 제출하면 반환한다. 이후 별도 요청에서 완료 파일을 확인·검사·게시한다. 예약 작업이나 계속 도는 수집기는 없다. 날짜별 요청 1회·총 10회 원장을 먼저 기록하며 불확실 응답에서 자동 재요청하지 않는다.

산출물:

- 원본: `C:\Users\User\Documents\NinjaTrader 8\db\replay\NQ 12-26\YYYYMMDD.nrd`
- 제출 원장: 저장소 `data/runner/future-data-intake/state.json`
- 품질·파생 파일: `data/runner/future-data-intake/quality/YYYY-MM-DD.quality.json`, `.parquet`, `.Last.txt`, `.Last.manifest.json`
- 실행 상태: `research/future-data-collector-readiness.json`
- 품질 게시: 대시보드 ID `bollinger-future-data-YYYY-MM-DD`; ACK는 원장의 `quality_ack`와 telemetry ACK 기록. 손익·자산 곡선은 비어 있다.

현재 실제 미래 다운로드/검증 0회. 전체 실제 수집 완료 여부는 첫 이용 가능 세션에서 확인해야 한다.
