# HashiCorp Vault 심화 과정 평가 기준

[커리큘럼](curriculum.md) · [공통 실습](../shared/labs/README.md) · [소스 지도](source-reading.md)

평가 대상은 비밀 보유가 아니라 **권한·시간·외부 소비자·실패 후 상태를 증명하는 능력**입니다. 실행 범위가 OFFLINE인지 LOCAL-DEV인지, 추가 AUTH/LIFECYCLE/HA/RESTORE/BUILD인지 먼저 선언합니다.

## 점수

각 25점, 총 **80/100 이상·모든 영역 15/25 이상**과 필수 gate 모두 통과가 선언 범위의 완료 기준입니다.

| 영역 | 최소 증거 | 높은 수준의 증거 |
| --- | --- | --- |
| 정확성 25 | 실제 주체·경로·버전·시간의 허용/거부 oracle | 경합·만료·불확실 응답·복원 후 외부 소비자까지 검산 |
| 원리/소스 25 | barrier·policy·lease·storage 책임과 고정 revision | 5symbol·2자료구조·1test를 요청·실패 경로와 연결 |
| 실험/반증 25 | baseline·한 변인·음성 대조군·재현 절차 | 경쟁 가설·반복·시간 오차·실패 주입과 수정 검증 |
| 운영/재현성 25 | 합성 자산·자원 상한·비밀 제거·범위 기록 | key custody·의존성·복원·접근 폐기의 독립 재현 |

## 필수 gate

1. **위협·seal:** 초기화, unseal, rekey, barrier rotation, auto-unseal, recovery key의 역할을 구별합니다. online 서버의 root/host 침해를 암호화 저장만으로 막는다고 주장하면 미통과입니다.
2. **인증·인가:** root가 아닌 실제 주체별 양성/음성 대조군, KV v2의 실제 data/metadata 경로, exact와 glob selector의 차이를 냅니다. list 응답이 읽기 정책으로 필터링된다는 가정을 금합니다.
3. **수명·외부 상태:** token과 secret lease, renewal 요청과 실제 TTL, 만료와 backend revoke 완료, KV soft delete와 destroy를 분리합니다.
4. **암호·PKI:** 직접 만든 암호 모형을 운영 구현으로 쓰지 않습니다. Transit 회전 이후 기존 암호문, 인증서 폐기 이후 client 검증을 각각 시험합니다.
5. **감사·소비자:** 비밀 원문 없는 상관 기록, audit 출력 실패, Agent/앱의 오래된 파일·연결·캐시 상태를 다룹니다. 모든 endpoint가 같은 방식으로 audit된다고 단정하지 않습니다.
6. **HA·복원:** snapshot 파일과 실제 독립 복원, Raft majority와 endpoint 읽기 계약, restore 데이터와 외부 credential 유효성을 구별합니다. seal 자산 접근 가능성을 복원 gate에 포함합니다.
7. **범위·안전:** HashiCorp Vault Community 2.1.1 기준과 다른 제품/edition을 구분합니다. dev 모드·mock·정적 검사를 실제 seal/HA/운영 보안 통과로 표시하지 않습니다. 운영 키·공유 volume·외부 계정에 실패를 주입하지 않습니다.

## 범위별 최소 결과물

| 범위 | 제출물 | 증명하지 않는 것 |
| --- | --- | --- |
| OFFLINE | CPU 4개·수작업 기대값·틀린 대조군·생략 조건 | 제품 policy matcher, 암호 강도, 실시간 만료, 실제 Raft |
| LOCAL-DEV | 제품/이미지 고정·합성 fixture·API 응답·정확한 거부 | 운영 TLS, init/unseal, 영속성, HA, 백업 |
| AUTH-LAB | 서로 다른 주체·claim·token tree·정책 revision·TLS 실패 | 단일 root 세션의 성공만으로 최소 권한 완료 불가 |
| LIFECYCLE-LAB | 발급·갱신·만료·폐기·앱 reload 및 외부 소비자 결과 | 서버 TTL·revoke 응답만으로 모든 연결 종료 불가 |
| HA/RESTORE-LAB | 영속 다중 노드·격리 복원·key custody·업무 원장·RPO/RTO | 실행하지 않은 region/KMS/OS 침해 시나리오 |
| BUILD | 고정 소스·도구·실제 test 결과·실패 전후 비교 | 파일 경로 확인이나 코드 읽기만으로 빌드 성공 불가 |

“설계 완료 / 실행 완료 / 결과 검증 / 미검증 / 실패”를 구별합니다. 추가 환경을 실행하지 않아도 기록은 제출할 수 있지만 전체 운영 역량 완료로 표시할 수 없습니다.

## VL14: 2주 미니 연구

앞선 자산으로 한 경로·개선 하나·실패 둘을 고릅니다. 예: CAS 재시도에서 응답 유실+동시 갱신, Agent 갱신에서 auth 장애+앱 reload 실패, 권한 이전에서 path 변경+identity alias 변화입니다. 보안 결론에는 독립 oracle와 거부 검사가 필요하며, 성능 결론에는 동일 권한/결과·오류율·표본 수가 필요합니다.

동료가 요청 10개를 선택하여 인증→정책→engine→소비자 상태를 추적할 수 있어야 합니다. 실패를 실행하지 않았으면 연구 설계로만 제출합니다. 별도 [8주 캡스톤](../../capstones/secrets-identity-recovery.md)은 다중 노드·복원·rotation·소비자 운영까지 범위를 넓힙니다.
