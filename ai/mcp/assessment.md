# MCP 심화 과정 평가 기준

[커리큘럼](curriculum.md) · [실습](labs/README.md) · [소스 지도](source-reading.md)

평가 대상은 서버를 연결한 횟수가 아니라 **요청 계약·권한·부작용·실패 후 상태를 증명하는 능력**입니다. 선언 범위는 OFFLINE / LOCAL-SDK / HTTP-LAB / AUTH-LAB / RECOVERY-LAB / BUILD/INTEROP로 나눕니다.

## 점수

각 25점, **총 80/100 이상·모든 영역 15/25 이상·필수 gate 모두 통과**가 선언 범위의 완료 기준입니다.

| 영역 | 최소 증거 | 높은 수준의 증거 |
| --- | --- | --- |
| 정확성 25 | revision·주체·schema·결과 계층별 양성/음성 oracle | 권한 변화·불확실 완료·중복·다른 구현에서도 검산 |
| 원리/소스 25 | framing→validation→dispatch→result 책임 지도 | 5symbol·2자료구조·1test를 실패 전후와 연결 |
| 실험/반증 25 | baseline·한 변인·틀린 대조군·반복 절차 | competing hypothesis·fault timing·독립 업무 원장 |
| 운영/재현성 25 | 고정 버전·합성 데이터·자원/시간 상한·민감 정보 제거 | 인증/동의/캐시 분리·회복 절차·host별 한계의 독립 재현 |

## 필수 gate

[실제 SDK 기준선·서로 다른 두 문제의 진단·회복](operations.md)을 제품 실습 완료에 추가로 요구합니다. 오류 층·지연/종료·업무 결과를 조치 전후로 비교하여 [운영 보고서](../../operations/incident-report-template.md)를 제출합니다. 원리 모형/mock PASS는 보조 학습 결과이며 실제 운영 완료가 아닙니다. 제공 stdio smoke와 추가 계측·HTTP/권한 과제의 수행 범위를 구분합니다.

1. **신뢰:** tool/resource/prompt 내용과 사용자의 실행 권한을 분리합니다. annotation·roots·모델의 응답을 보안 경계로 사용하지 않습니다.
2. **revision:** modern 2026-07-28과 legacy 2025-11-25의 계약을 섞지 않습니다. SDK 2.3.0이라는 이름만으로 모든 protocol·extension·host 조합 지원을 주장하지 않습니다.
3. **계약:** HTTP 오류·JSON-RPC 오류·`isError`·schema 적합·업무 결과를 각각 검산합니다. CPU 부분 validator를 JSON Schema 전체 구현이라고 하지 않습니다.
4. **인증·tenant:** issuer/audience/scope 검증, 작업 동의, downstream 접근 제어, private cache 격리를 분리합니다. token passthrough와 합성 다른 tenant 접근은 거부되어야 합니다.
5. **재시도·상태:** RPC ID와 업무 operation key, MRTR 재시도와 일반 장애 재시도, 취소 요청과 side-effect rollback을 구분합니다. timeout 결과를 무조건 실패 또는 재실행 가능으로 단정하지 않습니다.
6. **관측·운영:** raw token·개인정보·secret·민감 URI를 trace에 남기지 않습니다. 대기열·body/SSE 크기·concurrency·deadline 상한과 graceful 종료를 확인합니다.
7. **증거·안전:** LOCAL-SDK를 OAuth/HTTP/운영 보안 검증으로 부르지 않습니다. 부하·위협·fault injection은 소유한 합성 환경에만 적용하고 실행하지 않은 항목은 미검증으로 남깁니다.

## 범위별 제출물

| 범위 | 필수 제출물 | 미검증으로 남길 항목 |
| --- | --- | --- |
| OFFLINE | CPU 4모형·독립 기대값·오류 입력·추상화 목록 | 실제 framing·SDK·네트워크·암호·인증 |
| LOCAL-SDK | 고정 SDK·실제 child process·입력/결과 검산·종료 확인 | HTTP/SSE·OAuth·특정 LLM host |
| HTTP-LAB | header/body·Origin·JSON/SSE·끊김·proxy 결과 | 실행하지 않은 TLS/CDN/OS 조합 |
| AUTH-LAB | issuer/resource/scope/동의·다른 주체 음성 대조군 | 정적 token 모형만으로 실제 OAuth 보안 |
| RECOVERY-LAB | 업무 원장·중복·MRTR·취소·확장별 상태 | 메모리 ledger만으로 crash durability |
| BUILD/INTEROP | 고정 source test·feature matrix·최소 재현 | source 읽기만으로 빌드 성공·타 host 호환 |

“설계 완료 / 실행 완료 / 결과 검증 / 미검증 / 실패”를 구별합니다. 실제 모델 API나 GPU를 사용하지 않아도 프로토콜·권한·복구를 학습할 수 있습니다. 모델을 연결한 확장 평가에서는 결정적 보안 검증과 확률적 tool 선택 품질을 별도 점수로 냅니다.

## MC14: 2주 미니 연구

한 경로·한 개선·실패 조건 둘을 고릅니다. 예: private cache key 개선에서 token 교체+정책 revision 변경, 중복 실행 억제에서 응답 유실+동시 retry, HTTP routing 개선에서 오래된 schema+header/body 불일치입니다. 개선 전후 권한과 업무 결과는 같아야 하며, 성능에는 표본 수·오류율·tail latency·자원 사용량을 함께 냅니다.

구술에서는 임의 요청 10개를 선택하여 주체→schema→권한→handler→side effect→관측 결과까지 추적합니다. 학습자가 “여기까지는 알고, 이 조건에서는 모른다”고 말할 수 있어야 합니다. 미실행 실패는 연구 설계로만 인정하며 [8주 캡스톤](../../capstones/mcp-tool-boundary-recovery.md) 결과와 혼동하지 않습니다.
