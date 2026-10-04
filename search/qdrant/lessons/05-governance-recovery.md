# 05. 비용 제약, 보안, 전환과 복구

[과정](../curriculum.md) · [수동 고급 LAB](../labs/advanced.md) · [운영](../operations.md)

<a id="qd09"></a>
## QD09 — strict mode는 인가 시스템이 아니다

strict mode의 목적은 collection에서 허용하는 요청 비용/형태를 제한하는 것입니다. `enabled`와 개별 제한은 별개이며 기본값이 배포마다 같다고 가정하지 않습니다. [공식 administration](https://qdrant.tech/documentation/ops-configuration/administration/)의 제한을 읽고 수동 LAB에서 query limit 거부를 관찰합니다. unindexed filtering 제한은 별도 확장 과제입니다.

1. 제한 전 정상 요청의 결과 ID를 저장합니다. 설정을 바꾸기 전에 해당 collection이 자기 disposable 대상인지 확인합니다.
2. 의도적으로 한 제한을 넘긴 요청의 status/diagnostic을 기록합니다. 오류를 무조건 retry하지 않습니다.
3. 필터에 맞는 index 또는 작은 query limit으로 교정하고 동일 정답이 돌아오는지 확인합니다. 제한 전체를 끄는 조치를 기본 해결책으로 삼지 않습니다.
4. node-wide quota와 collection strict mode의 범위를 비교합니다. 하나의 collection이 다른 collection의 memory를 해제할 수 있다고 가정하지 않습니다. quota 실측은 별도 환경 과제입니다.

보안은 별도 환경에서 [공식 security](https://qdrant.tech/documentation/security/)를 따라 API key·TLS·JWT RBAC와 신뢰 경계를 검증합니다. localhost·합성 값·포트 격리는 피해 범위를 줄이는 LAB 조건이지 운영 보안 통과가 아닙니다. P2P 포트는 외부에 공개하지 않습니다.

필수 권한 matrix는 `관리자 / 제한 reader / 권한 없음` × `query / write / collection 관리`입니다. 허용 요청이 실제로 성공하는 양성 대조군과 금지 요청이 실패하는 음성 대조군을 함께 확인합니다. tenant query filter는 client가 바꾸면 없어질 수 있으므로 단독 인가 장치가 아닙니다. Cloud 조직 RBAC와 서버 데이터 API 권한도 구분합니다.

제출: strict-mode 거부/회복, 권한 설계와 실제 검증 범위, 비밀 보관/로그 제거, 제한을 채택하지 않을 경우의 대안. 실제 key/token/업무 payload를 저장소에 넣지 않습니다.

<a id="qd10"></a>
## QD10 — alias를 바꾸는 것과 데이터를 복원하는 것은 다르다

alias의 목적은 client가 사용할 논리 이름과 실제 collection을 분리하는 것입니다. [공식 collections](https://qdrant.tech/documentation/manage-data/collections/)의 alias 전환을 수동 LAB의 새 두 collection으로 관찰합니다. 전환 이전/이후 query ID를 검산하고 원래 mapping으로 되돌립니다. 기존 collection을 자동 삭제하지 않습니다.

새 모델 이행에는 named vector schema 추가/삭제라는 다른 선택지도 있습니다. 1.19.1 고정 API에서 지원하는 경로를 읽고 backfill 완료율·모델 revision·dual write·빠진 vector를 검산하는 **별도 과제**로 둡니다. alias swap만으로 embedding 생성, 이미 진행 중인 요청, 모든 client의 schema 전환이 해결되지 않습니다.

snapshot은 [공식 복원 계약](https://qdrant.tech/documentation/snapshots/)을 확인한 뒤 **동일 버전의 새 target collection**으로 복원하는 것이 기본입니다. 제공 수동 예제는 같은 서버에서 다른 collection 이름으로 복원하며 별도 host 손실/외부 보관 복구까지 입증하지 않습니다. 원본 대상 덮어쓰기나 운영 snapshot 다운로드를 연습하지 않습니다.

| 단계 | 관측·독립 정답 | 제약/반례 |
| --- | --- | --- |
| 만들기 | snapshot 이름/대상/크기/checksum·point ledger | 파일 생성만으로 복구 완료 아님 |
| 독립 복원 | 새 collection의 schema·IDs·payload·vector·exact query | count 동일이어도 잘못된 ID/모델일 수 있음 |
| 변경 이후 복원 비교 | snapshot 이후 쓴 ID가 없는지 확인 | 과거 snapshot이 최신 write까지 포함한다고 기대 금지 |
| cutover/회복 | alias mapping·새 write·업무 query 검산 | replica/alias/backup을 서로 대체물로 취급 금지 |

업그레이드는 [공식 upgrades](https://qdrant.tech/documentation/upgrades/)의 지원 경로, release fixes, client/API 호환과 snapshot 복원 조건을 매번 확인합니다. 이전 binary 재시작을 안전한 downgrade라고 가정하지 않습니다. 큰 버전 건너뛰기·rolling upgrade·Cloud 관리 작업은 기본 LAB 밖입니다.

제출: alias 전환 원장, snapshot 시점/범위/복원 증거, 구버전 상태 보존·중단 조건·rollback 대안. RPO는 snapshot 주기만이 아니라 실제 허용 가능한 누락 write로, RTO는 어떤 업무 query가 통과할 때까지인지 정의합니다.
