# 비밀·신원·회수·복구 연구 — 선택 8주

[OpenBao](../security/openbao/README.md) · [Vault](../security/vault/README.md) · [제품 차이](../security/shared/comparison.md)

트랙의 27–28주 미니 연구를 통과한 뒤 선택하는 **추가 8주·96시간** 프로젝트입니다. 두 제품을 모두 배포할 의무는 없습니다. 하나를 선택해 정확히 검증하며 비교는 동일 fixture를 각기 독립된 환경에서 수행합니다.

## 연구 질문

“워크로드가 최소 권한으로 비밀을 얻고, 만료/회전/장애 후에도 허용된 요청만 처리하며, 복원 이후 과거 자격 증명이 예상 밖 권한을 되찾지 않는가?”

애플리케이션·secret manager·DB·감사 수집기·키 보관자는 서로 다른 신뢰 경계입니다. secret manager의 성공 응답만으로 전체 계약을 판정하지 않습니다. 기본 dev Compose는 이 환경을 제공하지 않습니다. S2 환경 구성 자체가 과제입니다.

## 범위와 안전 계약

- 자신이 통제하는 격리 대상, 합성 테넌트 A/B, 공개 가짜 데이터, 비운영 DB/CA를 사용합니다. 운영 export/import·root token 복사·외부 SaaS 호출은 금지합니다.
- 제품·edition·image digest·plugin·client·storage·seal·TLS·clock·audit 설정을 고정합니다. 원본 data directory와 독립 restore 대상의 식별자를 제출합니다.
- cloud KMS가 필요하면 별도 비용/권한 승인을 받고 키 삭제 방지·복구 책임을 정합니다. 기본은 Shamir 운영 절차의 학습이며 shares의 원문을 보고서에 넣지 않습니다.
- audit device 장애·quorum loss·만료·DB revoke 실패 주입 전 되돌리는 절차와 stop 조건을 적습니다. 운영 장애나 exploit 실험은 범위 밖입니다.

## 8주 작업 계획

| 주 | 구현/실험 | 독립 oracle와 제출물 |
| --- | --- | --- |
| 1 | threat model·데이터 흐름·역할/권한 분리 | principal×path×operation 기대표, deny·metadata list 누출·root 제외 조건 |
| 2 | 업무 신원 인증, issuer/audience/subject 제약, token TTL·parent | 잘못된 audience/subject·만료·다른 테넌트 거부; claim 원문 없는 결과 |
| 3 | PostgreSQL 또는 MySQL 전용 동적 계정과 제한 role | DB에서 실제 CRUD 허용/거부, lease 시간표, 갱신·max TTL·외부 회수 실패 |
| 4 | static KV/CAS와 앱 secret 회전 또는 transit/PKI 중 하나 | stale CAS 거부·앱 reload 지연·기존 세션, 혹은 rewrap/CRL client 검증 |
| 5 | audit와 비밀 비노출 관측 | 요청 ID 대조·누락/지연·HMAC 적용/예외·모든 audit destination 장애 시 실제 동작 |
| 6 | 제품별 독립 3 voter Raft, leader/follower 장애 | ACK·term/index·latency·정족수 상태·client retry 기록; minority가 write를 승인하지 않는지 |
| 7 | snapshot→독립 restore, seal key/권한·DB 외부 상태 대조 | KV·policy·identity·lease·외부 DB credential의 복원 전후 차이, 측정 RPO/RTO |
| 8 | 반례 최소화·소스 경로·최종 회귀 | 처음 가설의 반증, 보완책, 정상/실패 재실행, 미검증 범위와 운영 권고 초안 |

DB는 전용 합성 instance·schema·role로 한정합니다. 기존 저장소 DB/네트워크를 자동 연결하지 않습니다. revoke가 `DROP USER`에 성공해도 이미 연결한 세션의 접근이 언제 종료되는지는 DB/driver 계약에 따라 별도로 검증해야 합니다. 정상·신규 연결·기존 connection pool을 구분합니다.

## 필수 시간표 세 가지

1. `credential 발급 → DB 접속 → lease 만료 → revoke 시도 실패 → 재시도 성공 → 기존 session/new connection 관찰`. TTL 숫자가 0이라는 이유로 외부 권한 소멸을 판정하지 않습니다.
2. `key version 증가 → 새 ciphertext/secret 발급 → 소비자 reload → 구 key 사용 잔존 → 단계적 폐기`. transit rotate는 기존 ciphertext를 자동 재암호화하지 않으며 성급한 min version 변경은 데이터 접근을 막을 수 있습니다.
3. `snapshot 시점 → 정책/lease 변경 → 장애 → 독립 restore → 외부 DB/PKI 상태와 재조정`. snapshot은 외부 서비스의 원자적 snapshot이 아니며 rollback으로 과거 token/정책이 되살아나는지 검사해야 합니다.

Raft는 고정 membership의 과반수 수학만으로 read-after-write·leader freshness·내구성을 증명할 수 없습니다. read 경로·forwarding·복제 index와 client retry의 요청 식별자를 기록합니다. CPU `raft-quorum`은 여기의 대체 시험이 아닙니다.

## 합격 기준

원리/위협 모델 25 + 구현·소스 25 + 독립 oracle/실패 주입 25 + 복구·운영 증거 25, 총 80점 이상이며 각 영역 15점 이상입니다. 다음은 점수와 관계없는 gate입니다.

- 다른 테넌트·만료·잘못된 신원·metadata enumeration의 거부를 각각 확인한다. root로만 성공한 실험은 불합격이다.
- 외부 DB의 실제 회수를 확인하며 token/lease 화면의 상태로 대신하지 않는다.
- ACK/실패/timeout을 분리하고 동작이 불명확한 요청은 재조정한다.
- 독립 대상에서 복원하고 seal key·권한 접근 가능성, snapshot에 없는 외부 상태를 함께 확인한다.
- token·key·JWT·DB 암호·snapshot·audit raw payload가 Git/LLM prompt/telemetry에 유출되지 않는다. 발견 시 보고서를 비식별화하고 해당 합성 자격 증명을 폐기한 뒤 재시험한다.
- unsupported 제품 간 복원이나 Enterprise 기능을 기본 image에서 검증했다고 주장하지 않는다.

실험 기록은 [공통 방법](../databases/shared/experiment-method.md)에 맞춰 입력·독립 정답·version·시간선·반례·원인·수정·회귀·남은 위험을 담습니다. 정상 흐름의 성공 스크린샷만으로 완료하지 않습니다.
