# ML 시스템 설계 리뷰 양식

[과정](../curriculum.md) · [진단 지침](../operations.md)

한 업무 문제와 한 모델 변경만 선택합니다. 빈 칸을 업계 평균이나 추정 수치로 채우지 말고 **가정 / 예상 / 실측 / 미확정**을 구분합니다. credential·사용자 원문·개인 식별자는 넣지 않습니다.

## 문제와 대안

- 누구의 어떤 결정을 언제 돕는가? 예측 단위와 action은 무엇인가?
- ML 없는 규칙/수동/현재 시스템의 기준선은 무엇인가?
- 모델 metric과 업무 결과는 어떻게 다르며, 잘못된 결정의 비용은 무엇인가?
- ML을 도입하지 않거나 사용을 중지할 조건은 무엇인가?

## 데이터와 정보 경계

- entity/group·event time·available time·prediction time·label 정의/도착 시점:
- source revision·권한/동의·보존/삭제·label 관측 편향:
- split 단위와 중복 검사·point-in-time 선택·late event/backfill 정책:
- feature schema·단위·결측/default·freshness·전처리 version:
- offline/online feature parity를 확인할 같은 입력과 독립 예상값:

## 평가와 배포 계약

- baseline/candidate·model/feature/preprocess revision, fixed paired cases:
- 전체/집단별 지표·분모·label coverage·최소 증거와 판단 보류 조건:
- offline 선택, shadow/canary/A-B 목적과 노출 대상·종료/승격 기준:
- label 지연 중 서비스 health와 품질을 각각 누가 판단하는가?
- latency/availability/freshness/cost 예산의 단위와 근거; 부하/표본/측정 조건:

## 실패와 복구

| 실패 한 가지 | 관측 신호·분모 | 경쟁 가설 2개 | 선택한 조치·승인자 | 동일 입력의 복구 증거 |
| --- | --- | --- | --- | --- |
| 예: 전처리 버전 불일치 | 미기입 | 미기입 | 미기입 | 미실행 |

- rollback 단위: weight 외 코드·전처리·schema·cache·writer/reader·진행 중 요청:
- 중복 요청·timeout·부분 실패·재처리·fallback의 상태와 책임:
- retraining trigger, 새 평가·승인·lineage·기존 모델 보존/복구 조건:
- 인가/TLS·로그 마스킹·감사·privacy·허가된 공정성 평가 범위:

## 근거와 결론

- 제공 LAB으로 확인한 것과 추가 구현/외부 환경에서만 확인 가능한 것:
- code revision·명령·환경·실제 관측·재현 순서:
- 설계 선택 하나, 대안 하나, 그 선택이 실패하는 조건 하나:
- 미확정 가정과 담당자·후속 검증·중단 예산:

기본 fixture의 작은 accuracy/응답 시간은 운영 기준값이 아닙니다. 배포 보류·비ML 선택·추가 label 대기도 근거가 있으면 유효한 결론입니다. 이 양식은 Stanford 공식 과제나 production readiness 인증이 아닙니다.
