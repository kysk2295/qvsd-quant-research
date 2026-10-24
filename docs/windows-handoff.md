# Windows에서 이어서 작업하기

## 저장소 받기

GitHub의 저장소 소유자 계정으로 인증한 뒤 실행합니다.

```powershell
git clone https://github.com/kysk2295/qvsd-quant-research.git
cd qvsd-quant-research
```

이미 받은 경우 변경 사항을 먼저 커밋하고 `git pull --ff-only`로 최신 버전을 받습니다.
서로 다른 PC에서 같은 브랜치를 동시에 수정하지 말고 `codex/<주제>` 브랜치로 작업합니다.

## NinjaTrader 자료 내보내기

공식 안내: https://static.ninjatrader.com/support/helpGuides/nt8/exporting.htm

1. Historical Data → Export를 엽니다.
2. 기간 중 거래한 NQ·GC 월물을 각각 선택합니다. 가능하면 MNQ·MGC도 확보합니다.
3. 우선 Minute / Last, 가능하면 Tick / Last와 Bid·Ask를 내보냅니다.
4. 2026-04-01~10-23을 우선 확보합니다. 4월은 워밍업용, 공식 평가 시작은 5월 1일입니다.
5. 10월 28일 장이 끝난 후 최종 제출 기간까지 추가합니다.
6. 파일을 `data/incoming/`에 저장합니다. 이 폴더의 원본은 자동으로 GitHub에 올라가지 않습니다.

공식 Export는 UTC와 봉 종료시각을 사용합니다. 현재 Yahoo 입력의 시작시각 라벨과 그대로 혼합하지 않습니다.
현재 backtest.py는 Yahoo JSON 입력용입니다. NinjaTrader txt를 읽는 어댑터는 아직 없습니다.

각 파일의 제공사·상품·월물·기간·데이터 종류·시간대·Merge policy·거래시간 템플릿을 기록합니다.
PowerShell에서 `Get-FileHash <파일경로> -Algorithm SHA256`으로 해시를 구할 수 있습니다.
계정 비밀번호나 API 키는 자료에 넣지 않습니다.

## 다음 검증

- 공식 대회 운영 시간과 수수료·슬리피지 기준 확인.
- 월물별 6개월 원자료 품질 검사 및 입력 어댑터 작성.
- 5/30/60분, 1000/3000틱, 40/100레인지 비교.
- 대회 시간창 내 최소 4회 진입 미달률 확인.
- 미실현 손익과 동시 보유 한도를 포함한 통합 계좌 검증.
- Strategy Analyzer와 Playback 재현. 이후 모의 운용 판단.
