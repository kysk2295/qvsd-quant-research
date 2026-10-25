# NQ 실제 설치·실행 준비 점검

**설치 전략 소스와 백테스트용 전략 목록을 확인했다. 아직 검증된 전략이나 실행 허가는 없다.**

원래 등록한 읽기 호출 5회 후, 예상하지 못한 타입 조회 오류를 확인하기 위해 별도 등록한 읽기 2회를 수행했다. 총 7회 모두 상태·타입·작업 목록 조회다. 백테스트·다운로드·컴파일/재로드·코드 설치·실제 시장 성과 계산은 0회다.

## 확인 결과

| 항목 | 결과 | 의미 |
|---|---|---|
| 설치 전략 파일 | 고정 소스 SHA256과 일치 | 디스크 코드 일치 |
| 백테스트 전략 목록 | CodexBollingerClock, BandLength 기본값 20 확인 | 실행기가 선택하는 목록에 존재 |
| 일반 타입 조회 | no type 응답 | 현재 실행 어셈블리가 조회 대상에서 제외됨 |
| nt_status | current, disagreement=false | 수정시각 검사상 최신; 메서드 코드 동일성 증명은 아님 |
| 엔진 관측 | 세 번의 process/start/assembly 정보 일치 | 관측 사이 세대 변경 없음; 원자적 job 결합 보장은 아님 |
| 작업 목록 | 등록된 2건 모두 done, queued/running 없음 | 목록 상태만 확인. 전체 엔진 idle 입증은 아님 |
| 연결 | 관측 시 연결 목록 비어 있음 | 미래 자료를 받을 연결이 준비됐다는 뜻은 아님 |
| 미래 자료 | 10일 모두 세션 종료 전 | 수집·수입·성과 검증 미실시 |

## 타입 조회 오류의 범위

health의 assemblyName은 실행 중인 NT8Bridge의 Assembly.GetName().Name이며 GUID 형태다. Api_TargetAssemblies는 NinjaTrader.Core/Gui/Custom/Vendor 네 이름만 선택하여 현재 bridge 어셈블리를 제외한다. 반면 백테스트 목록은 실행 중 bridge 어셈블리의 전략을 사용한다. 그 목록에서 해당 전략을 확인했으므로 일반 API의 no type을 전략 미설치·미컴파일로 해석하면 안 된다.

설치된 AddOn 세 파일(Backtest, ChartControl, ResearchControl)은 MCP 소스 저장소 사본과 다르다. 이 차이는 기록했으며 재설치하거나 덮어쓰지 않았다. 소스/DLL 수정시각, 타입 이름, 파일 SHA만으로 로드된 각 메서드가 고정 전략 소스에서 만들어졌다고 증명하지 않는다.

## 자료 수집과 NinjaTrader 반영 사이의 연결

미래 collector는 품질 검사된 YYYY-MM-DD.Last.txt까지만 만들며 NinjaTrader import를 실행하지 않는다. 기존 importer는 nt-import 하위의 NQ DEC26.Last.txt라는 이름과 정확한 SHA256을 요구한다. 따라서 세션 종료와 품질 ACK 이후 원본을 보존한 별도 staging 사본, 단일 import 기록, 동일 작업/경로의 종료 상태, 실제 NQ 데이터 캐시·봉 대조가 필요하다. quality_passed를 import_complete로 바꾸면 안 된다.

기존 importer의 연구 권한·연결 해제·포지션/작업 주문 검사도 그대로 적용된다. 이번 점검은 이 상태를 바꾸거나 권한을 설정하지 않았다. 미래 파일은 열람하지 않았고 단순 날짜표만 검사했다.

## 다음 판단

첫 고정 세션은 10월 27일 05:00 KST에 종료된다. 11월 2일 ET 세션부터는 DST 변경으로 한국 시각 종료가 06:00이다. 성과 판정은 기존 계획대로 11월 7일 10:00 KST 이후다. 취소된 30분 자동화는 재생성하지 않았다.

현재 가능한 준비는 수입 handoff와 실제 단일 실행 경로를 구체화하는 범위다. 모든 준비가 끝나도 아직 발생하지 않은 세션과 더 긴 독립 검증을 대신할 수 없다. 타입 조회 오류를 확인하려고 새 전략 백테스트를 돌리거나 기존 관측 날짜를 다시 최적화하지 않는다.

## 증거

- [원래 5회 점검 계획](../research/nq-deployment-readiness-audit-plan.json) / [별도 2회 타입 확인 계획](../research/deployment-readiness-type-followup-plan.json)
- [원 관측](../research/deployment-readiness-mcp-observations.json) / [타입 후속 관측](../research/deployment-readiness-type-followup-observations.json)
- [설치 파일 해시](../research/deployment-readiness-disk-snapshot.json) / [판정과 남은 증거](../research/deployment-readiness-result.json)
- [대시보드 수신](../research/deployment-readiness-publication.json)
