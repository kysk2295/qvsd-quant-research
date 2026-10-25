# NQ 미래 자료 가져오기 준비

**품질 확인 자료를 NinjaTrader에 넘기는 코드를 연결했다. 실제 가져오기와 전략 검증은 아직 실행하지 않았다.**

합성 검사 47개가 통과했다. 등록된 최대 4회 중 전체 검사 3회를 사용했다. 테스트는 임시 합성 파일과 가짜 전송만 사용했으며, 실제 시장 파일 열람·다운로드·NT 호출·import·백테스트는 모두 0회다.

첫 검사 실패 기록도 보존했다. Windows에서 테스트용 SQLite 연결이 닫히지 않아 파일 잠금 오류가 발생했고, 중단된 예약의 예외 형식을 테스트가 잘못 기대한 부분이 있었다. 이를 수정한 두 번째 검사는 통과했다. 이후 독립 리뷰에서 실제 importer의 Int64 거래량 상한을 확인해 입력 검사와 초과값 fixture를 추가했고, 마지막 검사가 통과했다.

## 연결한 동작

1. 고정 계획·대상 날짜·실제 세션 종료 시각을 먼저 확인한다. 종료 전에는 시장 파일을 열지 않는다.
2. quality_passed 기록, NRD 원본·Parquet·Last 해시, 날짜별 품질 보고서, 대시보드 telemetry와 ACK 기록을 대조한다.
3. 원본 Last에는 정규장 밖 자료도 들어 있으므로 해당 날짜 뉴욕 09:30 이상 16:00 미만 행만 추린다. 선택한 행의 바이트와 순서, 100ns 시각을 보존하고 390분·양의 거래량·가격 틱을 검사한다. 따라서 전체 Last 파일의 단순 복제는 아니며 원본·추출본 해시를 각각 기록한다.
4. nt-import 아래 날짜·품질 해시별 고유 폴더에 NQ DEC26.Last.txt를 만든다. 기존 완성 파일은 다시 검증하며, 손상·부분 작성 파일은 덮어쓰지 않는다.
5. 실제 제출 시 기존 연구 권한과 연결 상태를 읽고, 날짜별 예약·제출 의도를 디스크에 먼저 저장한 뒤 기존 /research/import에 한 번만 POST한다. 권한 활성화·연결 변경·주문 호출은 없다.
6. 같은 경로와 엔진 관측을 묶어 한 번씩 상태를 읽는다. 잘못된 경로·파일 변경·엔진 변경·불명확한 응답은 보존하고 자동 재제출을 막는다. done의 행수·종목·원응답 해시도 저장 후 다시 확인한다.

## 완료의 범위와 한계

NinjaTrader importer는 고유 job ID나 서버 idempotency key가 없으며 전역 상태 하나만 제공한다. 로컬 예약은 날짜당 POST를 최대 한 번으로 제한하지만, 예약 직후 중단되면 실제 POST 없이 그 기회를 소진할 수 있다. 경로와 전후 엔진 관측은 제한된 연결 증거이며 원자적인 서버 식별 증명은 아니다.

done은 importer가 반환한 상태다. 실제 tick/minute cache 내용과 390분 봉, 이후 체결·손익 원장의 일치는 별도로 확인해야 한다. quality_passed 상태는 그대로 두고 import 상태를 별도 저장한다. 이번 작업은 기존 도구에 노출되지 않은 import endpoint만 좁은 로컬 전송으로 연결했으며, 실제 호출이나 차단 경로의 재시도는 하지 않았다.

## 이후 실행 순서

세션 종료 후 기존 collector의 품질 검사와 ACK가 끝난 날짜에만 다음 명령을 사용한다. 현재는 미래 자료가 없으므로 실행하지 않았다.

```powershell
python -m runner.future_data_importer 2026-10-26 --stage
python -m runner.future_data_importer 2026-10-26 --submit
python -m runner.future_data_importer 2026-10-26 --observe
```

각 명령은 유한하며 예약 실행이나 반복 루프가 아니다. unknown·error·중간 파일을 삭제해 재시도하지 않는다. 기존 서버의 연구 권한·연결·포지션/작업 주문 검사는 계속 적용된다.

첫 대상 세션 종료는 10월 27일 05:00 KST, 성과 판정은 11월 7일 10:00 KST 이후다. 지금 남은 구현은 고정된 한 번의 실제 백테스트 제출·조회·결과 판독 경로를 연결하는 작업이다. 이 연결까지 마치면 미발생 세션을 기다리며 추가 준비나 같은 자료 최적화를 반복하지 않는다. 10일 검증 통과도 더 긴 독립 검증 후보를 뜻한다.

## 증거

- [사전 계획](../research/nq-future-import-preparation-plan.json)
- [합성 검사와 코드 해시](../research/future-import-preparation-tests.json)
- [모든 검사 시도](../research/future-import-preparation-test-attempts.json)
- [상태·남은 단계](../research/future-import-preparation-result.json)
- [대시보드 수신](../research/future-import-preparation-publication.json)
