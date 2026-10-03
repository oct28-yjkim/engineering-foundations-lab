# NATS 심화 과정 평가 기준

[커리큘럼](curriculum.md) · [실습](labs/README.md) · [소스 지도](source-reading.md)

평가 대상은 메시지를 보낸 횟수가 아니라 **라우팅·전달·보관·업무 결과·장애 후 상태를 독립 증거로 설명하는 능력**입니다. 범위는 OFFLINE / LOCAL-NATIVE / CLIENT-LAB / CLUSTER-RECOVERY / SECURITY-OPS / BUILD/RESEARCH로 선언합니다.

## 점수

각 25점, **총 80/100 이상·모든 영역 15/25 이상·필수 gate 전체 통과**가 선언 범위의 완료 기준입니다.

| 영역 | 최소 증거 | 높은 수준의 증거 |
| --- | --- | --- |
| 정확성 25 | subject·ID·sequence·ACK·보관 집합의 독립 기대값 | filter·재전달·시간 경계·불확실 결과까지 같은 불변식으로 검산 |
| 원리/소스 25 | parser→routing→store→consumer의 책임 지도 | 5symbol·2자료구조·1실제 test와 실패 전후 상태를 연결 |
| 실험/반증 25 | baseline·한 변인·잘못된 대조군·반복 절차 | competing hypothesis·fault timing·독립 업무 원장·최소 반례 |
| 운영/재현성 25 | 고정 버전·합성 데이터·자원/시간 상한·미검증 범위 | 그룹별 복구·키 수명·tail/오류율·다른 실행자의 재현 |

## 필수 gate

**추가 기본 운영 gate:** [운영 가이드](operations.md)의 실제 baseline 1개·상이한 증상 2개·경쟁 가설 배제·완화/원복·업무 결과와 지표 회복 증거가 필요합니다. `num_redelivered`를 누적 counter로 계산하거나 healthz만으로 업무 복구를 선언하면 미통과입니다. CPU 모형은 선택 원리 부록이며 필수 선수 조건이 아닙니다. OFFLINE/mock 또는 native 10개 정확성 검사만으로 운영 트랙을 수료하지 않습니다. 환경 부재 시 자료 분석과 실제 실행 미완료를 분리합니다.

1. **라우팅:** `*`는 한 token, 마지막 `>`는 한 개 이상입니다. `orders.>`가 `orders`를 포함한다고 설명하지 않습니다. publish wildcard, 여러 matching subscription, 서로 다른 queue group을 구별합니다.
2. **Core 경계:** queue group은 전달 선택이지 업무 commit이나 영속 보관이 아닙니다. `flush`·request reply·drain 성공을 외부 부작용의 정확히 한 번 완료라고 표시하지 않습니다.
3. **보관·중복:** Limits/Interest/WorkQueue, stream 한계, finite dedup window를 분리합니다. 잘못 재사용한 message ID와 늦은 retry의 위험을 설명합니다.
4. **ACK·업무:** stream sequence·consumer sequence·ACK floor를 혼동하지 않습니다. ACK 유실·업무 commit 후 crash·MaxDeliver·late ACK의 결과를 검산합니다. 자동 DLQ 또는 DB와의 원자적 ACK를 가정하지 않습니다.
5. **복제·복구:** 서버 수, 그룹 replica 수, quorum, disk sync, backup은 다른 개념입니다. 원본과 격리한 복구에서 메시지·consumer·업무 상태를 각각 확인합니다.
6. **보안·운영:** 연결 인증, account 격리, publish/subscribe/API 권한, 관리 endpoint 노출을 별도로 검증합니다. 실제 secret·개인정보·운영 broker를 실습에 사용하지 않습니다.
7. **증거:** 모형·mock·실제 단일 서버·다중 노드·전원 장애의 검증 범위를 분리합니다. source reading이나 테스트 개수 자체를 내구성·보안·성능 증명으로 바꾸지 않습니다.

## 범위별 제출물

| 선언 범위 | 필수 제출물 | 남겨야 할 한계 |
| --- | --- | --- |
| OFFLINE | 네 모형의 기대값·잘못된 대조군·입력 거부·추상화 목록 | network·SDK·disk·consensus·암호 검증 없음 |
| LOCAL-NATIVE | 고정 server/client·소유한 프로세스·실제 protocol·검산·종료 확인 | R=1에서 quorum/HA 및 실제 전원 차단 미검증 |
| CLIENT-LAB | 연결·buffer·timeout·slow consumer·drain의 실행 타임라인 | 다른 SDK·OS·장애 조합은 별도 |
| CLUSTER-RECOVERY | 그룹별 leader/voter·격리·복구·backup manifest·독립 원장 | 단일 host cluster는 host/zone 장애를 대표하지 않음 |
| SECURITY-OPS | 합성 주체의 허용/거부 행렬·TLS·credential 회전·관측·부하 상한 | 권한 표만으로 실제 NKey/JWT 검증이 되지 않음 |
| BUILD/RESEARCH | 고정 source test·KV/CAS 또는 object checksum·비교·반증 | 테스트 한 개로 형식적 안전성·모든 릴리스 호환을 주장하지 않음 |

상태는 “설계 완료 / 실행 완료 / 결과 검증 / 실패 / 미검증” 중 선택합니다. 실제 서버 실습이 불가능하면 숨기지 않고 재현 명령·예상 관측·실행에 필요한 자원을 제출합니다. 그것은 연구 설계이며 실제 실행의 대체 증거는 아닙니다.

## NT14 미니 연구와 구술

한 경로·한 개선·실패 조건 둘을 고릅니다. 예: 작업 원장+ACK에서 업무 commit 직후 종료와 ACK 응답 유실, pull batch 개선에서 느린 worker와 연결 종료, subject 설계에서 과도한 wildcard와 권한 축소입니다. 개선 전후의 의미적 결과를 먼저 같게 만들고 처리량·지연을 비교합니다.

구술에서는 임의 메시지 10개의 publish 시도→수락→보관→전달→업무 반영→ACK→복구 상태를 추적합니다. 다음 반례를 통과해야 합니다.

- publish 응답이 없었지만 저장됐을 수 있는가? 어느 원장에서 확인하는가?
- worker가 DB commit 후 ACK 전에 종료되면 무엇이 재전달되고 무엇이 중복되는가?
- WorkQueue 메시지의 재전달 상한 도달과 stream 삭제는 같은 사건인가?
- 최신 delivered sequence와 ACK floor가 다른 것이 왜 곧 데이터 유실은 아닌가?
- 단일 파일 store의 프로세스 재시작 성공이 전원 장애의 RPO=0을 입증하는가?
- 동일 subject 이름이 다른 account에서 같은 데이터 접근을 뜻하는가?

28주 과정의 완료는 선언 범위에서의 증거 기반 숙련도입니다. 운영 환경 전체 검증이나 “초전문가” 자격을 기간만으로 보장하지 않습니다. 폭넓은 통합 결과는 별도 [8주 캡스톤](../../capstones/nats-delivery-recovery.md)에서 평가합니다.
