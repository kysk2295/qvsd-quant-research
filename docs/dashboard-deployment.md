# 전략 실험 대시보드 배포 기록

검증일: 2026-10-25 (한국 시간)

- URL: https://dashboard-production-812c.up.railway.app
- Railway 프로젝트: qvsd-research-lab / 서비스: dashboard
- 앱 코드 및 Windows 연결 코드: `dashboard/`
- 인프라 설정: `.railway/railway.ts`. 기존 volume `/data` 보존을 plan에서 확인한 뒤 적용했다.
- 브라우저 로그인 필요. 비밀번호는 Railway 변수와 Mac의 Git 제외 파일 `.dashboard-access.txt`에만 보관한다.
- Windows `QVSD-Dashboard-Reporter` 예약 작업: 사용자 로그온 시 실행, 중복 실행 방지. 전송기 종료 시 래퍼가 15초 후 재시작, 작업 자체 실패 시 1분 간격 최대 3회 재시도.
- 데이터는 SQLite 영구 볼륨에 저장. 여러 재배포 후에도 25개 기록과 작업자 연결을 확인했다.

## 확인한 동작

- Chrome에서 실제 로그인, 3초 갱신, Windows online 표시, 상태 필터, 전략 검색, 실험 상세와 계좌 곡선.
- 390px 모바일 화면에서 카드·필터·작업자 상태 표시.
- 서버 인증·위조 세션·외부 Origin 거부·1회용 pairing·비정상 수치·중복 업로드·완료 상태 회귀 방지·오프라인 표시·저장 재연결: 6개 테스트 통과. Windows에서도 같은 6개 통과.
- 기존 연구 회귀 테스트 8개 통과.
- 미인증 `/api/state` 요청은 401로 차단.
- 기존 예비 결과 12건, Windows에서 실제 재실행한 12건, native NQ 연구 상태 1건을 수신했다. 재현 결과는 기존 Yahoo 대리 데이터이며 새로운 독립 검증이 아니다.

## 실행 범위

대시보드와 전송기는 상시 관찰용이다. 연구 전략을 자동 생성하거나 무한 최적화하는 엔진은 포함하지 않는다. 새 실험은 `dashboard.reporter.emit`으로 진행 상태와 결과를 기록해야 한다. 완료는 계산 완료이며 채택 승인이 아니다. Windows가 절전·오프라인이면 전송도 멈추고 45초 후 연결 끊김으로 표시된다. 전송기의 heartbeat만으로 개별 실험 프로세스의 생존 여부를 확정하지 않는다.

`graphify update .`는 실행했으나 로컬 graphify 실행기의 Python 경로가 없어 실패했다. 대시보드 실행·테스트·배포에는 영향을 주지 않는다.
