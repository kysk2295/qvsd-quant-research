# QVSD Quant Research

제2회 LIFEUPTRADING × GRINDING LIFE 대회 준비를 위한 전략 연구 저장소입니다.
카페 아이디어 분석, 백테스트 코드, 데이터 출처, 거래 원장과 검증 결과를 함께 관리합니다.

**2026-10-25 현재: NQ 검증 전략 탐색 Goal 활성화, 채택 전략 없음.**
NinjaTrader 역사 백테스트는 수행했지만 독립 미사용 기간과 실제 전략 체결 검증은 미완료입니다. 최근 시장 상태에서 만든 두 가설도 등록한 일관성 기준을 충족하지 못했습니다.

- [Goal의 완료 기준과 다음 단계](docs/nq-validation-goal-2026-10-25.md)
- [단일 실행·결과 검증 준비](docs/nq-prospective-execution-preparation-2026-10-25.md): 합성 검사 35개 통과, 실제 신규 백테스트 0회. 미래 실행 전후의 증거를 분리했으며 생산 연결·전략 검증은 미완료입니다.
- [미래 결과 판독기 준비](docs/nq-postrun-evaluator-preparation-2026-10-25.md): 정밀 체결 로그·분봉/진입·비용·Last 보유 경로의 합성 검사 44개 통과. 실제 미래 성과·청산 주문 인과관계는 미검증입니다.
- [최근 시장 상태](docs/nq-market-state-baseline-2026-10-25.md) / [두 예측 가설의 결과](docs/nq-state-response-study-2026-10-25.md)
- [기존 전략의 확장 지표](docs/extended-metrics-results-2026-10-25.md)
- [10월 23일 데이터 제외 근거](docs/nrd-oct23-quality-diagnosis-2026-10-25.md)

고정된 미래 검증은 10월 26일~11월 6일 10세션, 판정일은 11월 7일 10:00 KST입니다. 통과해도 더 긴 검증 후보까지만 인정합니다. Goal 활성화는 무제한 최적화나 실제 주문 실행을 의미하지 않습니다.

## 현재 자료

- [분석 보고서](research/report.html): 다운로드하여 브라우저에서 열기
- [백테스트](research/backtest.py) / [테스트](research/test_backtest.py)
- [12개 조건의 결과](research/results.json)
- [데이터 출처·해시·누락 검사](research/data_audit.json)
- [Windows 인계 및 데이터 관리](docs/windows-handoff.md)
- [연구 기록](docs/research-log.md)

아래 초기 보고서는 2026-10-24 기준 Yahoo NQ=F·GC=F 공개 5분봉의 2026-08-14~10-23 구간을 사용했습니다.
미니 가격에 마이크로 계약가치를 적용한 대리 검증이며, 실제 마이크로 체결이나 대회 제출용 6개월 검증이 아닙니다.
본문 텍스트를 확인한 카페 글은 45건이며 첨부 자료 전체를 검토한 상태는 아닙니다.

## 실행

Python 3.10 이상, 외부 Python 패키지는 필요하지 않습니다.
Windows에서 IANA 시간대 데이터가 없으면 `py -m pip install tzdata`를 먼저 실행합니다.

```sh
python research/backtest.py
python -m unittest discover -s research -p 'test_*.py' -v
python research/build_report.py
```

명령은 저장된 원시 JSON을 읽습니다. 시세를 새로 다운로드하거나 주문하지 않습니다.
`robustness.json`은 초기 탐색에서 별도로 계산한 결과 스냅샷이며 위 명령으로 재생성되지 않습니다.

## 형상관리

- `main`: 확인한 연구 기준 버전.
- `codex/<주제>`: 전략 변경과 검증 작업 브랜치.
- 전략 변경 커밋에는 가설, 사용 데이터, 실행 조건, 결과와 한계를 함께 기록합니다.
- 원자료를 바꾸면 출처·월물·시간대·기간·SHA-256을 남깁니다.
- 유리한 결과만 남기지 않고 실패한 후보와 비용 가정도 보존합니다.
- 계좌 정보·비밀번호·API 키는 커밋하지 않습니다.
- 대용량 NinjaTrader 원본은 `data/incoming/`에 두며 Git에서 제외합니다. 공유 방식이 정해지면 데이터 매니페스트로 연결합니다.

이 저장소는 연구용이며 실거래 주문 시스템은 포함하지 않습니다.
