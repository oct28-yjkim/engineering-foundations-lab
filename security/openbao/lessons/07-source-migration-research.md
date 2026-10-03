# 7강. OpenBao: 소스·제품 차이·이전·미니 연구

[커리큘럼](../curriculum.md) · [공통 실습](../../shared/labs/README.md) · [소스 지도](../source-reading.md)


<a id="ob13"></a>
## OB13 — 구현 읽기, 제품 경계, migration

**선수:** 앞선 12모듈, Go interface·context·goroutine·error handling 기초. **불변식:** 실제로 읽은 revision의 구현과 실제 실행한 binary의 결과만 연결합니다.

기준 소스는 `a5db72cef75c24b920ade02065b18dd8eb666bac`입니다. [읽기 지도](../source-reading.md)의 검증된 파일에서 시작하고, module dependency나 plugin이 별도 repository라면 정확한 revision을 추가합니다. 파일명 검색·코드 읽기·test 실행·전체 빌드는 서로 다른 증거입니다.

### 소스 읽기 과제

한 요청을 골라 최소 5symbol·2자료구조·1test를 잇습니다.

| 후보 경로 | 반드시 찾을 경계 |
| --- | --- |
| policy가 거부한 KV read | routing, token/identity, selected ACL, engine 진입 전후 |
| CAS 충돌 | API 입력, 현재 version, 원자적 비교·쓰기, 실패 응답 |
| lease 만료 후 backend 실패 | 만료 판단, revoke 호출, 오류/재시도, 상태 보존 |
| Transit rotation | keyring version, ciphertext version, decrypt 제한 |
| Raft 이후 조회 | commit/apply, node 역할, forwarding, client 오류 |

test를 읽고 잘못된 변이를 하나 설계합니다. 예: deny 누락, CAS 검사 제거, max TTL 무시, stale render를 최신으로 표시. 별도 빌드 환경을 선택했다면 제한된 관련 test를 실제 실행하고 정상/변이 결과를 구분합니다. production 코드를 임의로 배포하지 않습니다.

### 제품별 연구

OpenBao의 현재 구현은 Vault의 과거 파일 배치와 달라질 수 있습니다. 이 revision의 core는 `internal/vault/`, 정책은 `internal/vault/policy/`, routing은 `internal/vault/routing/`, Raft는 `internal/physical/raft/`에서 읽기 지도를 따릅니다. 과거 `vault/core.go` 링크를 그대로 복제하지 않습니다.

OpenBao namespaces·CEL 정책 확장·storage backend 중 하나를 골라 “동일 API로 비교 가능 / 제품 고유 / 미지원 / 미검증”으로 분류합니다. namespace가 있다는 사실을 Vault Enterprise와 완전 호환이라는 결론으로 바꾸지 않습니다. [OpenBao namespaces](https://openbao.org/docs/concepts/namespaces/)와 [2.7.1 릴리스](https://github.com/openbao/openbao/releases/tag/v2.7.1)를 기준으로 질문을 정합니다.

### Migration은 독립된 계약이다

1. source→target의 정확한 제품·버전·edition과 지원 문서를 기록합니다. 역방향도 가능한지는 별도 질문입니다.
2. key/value만이 아니라 metadata/version, auth mount accessor, identity mapping, policy selector, token/lease, plugin, Transit key, PKI issuer/trust, audit 설정을 항목별로 분류합니다.
3. 합성 fixture를 복사하고 허용뿐 아니라 거부, 만료, version, 암호문, 인증서 소비자까지 대조합니다.
4. 새 credential 발급·소비자 전환·옛 credential 폐기·rollback 가능 시점을 정합니다. export 파일에 secret을 넣어 저장소에 커밋하지 않습니다.
5. snapshot의 바이너리 교차 복원을 무검증 시도하지 않습니다. 지원 절차가 없으면 미지원/미검증으로 남기고 API 수준 재구성이나 새 발급을 설계합니다.

**통과:** source trace, 독립 test oracle, 최소 10행 호환성 행렬, 이전 중단/되돌림 조건. 명령어 이름이 같다는 사실은 호환성 증거가 아닙니다.

<a id="ob14"></a>
## OB14 — 2주 미니 연구

앞선 fixture를 재사용하여 **한 경로·한 개선·실패 조건 두 개**만 다룹니다. 새 multi-region cluster나 운영 CA 이전을 2주에 포함하지 않습니다.

추천 주제는 (a) CAS 충돌+응답 유실의 안전한 재시도, (b) Agent auth 장애+app reload 실패의 stale interval 제한, (c) identity alias 변경+policy path 변경의 권한 이전 검산입니다. OFFLINE만 사용하면 제품 보안 대신 모형의 명시된 성질을 연구합니다.

- 1–2일: 업무 불변식, 위협 주체, baseline, 성공/실패 oracle, 자원 상한.
- 3–5일: 정상/실패 입력·원시 결과·반례. 결과에 맞춰 가설을 바꾸면 변경 이력 기록.
- 6–8일: 개선 한 가지와 baseline을 같은 계약으로 비교. 보안 정확성을 성능보다 먼저 확인.
- 9–10일: 동료 재현, 실패한 가설, 미검증 조건, 5분 구술과 보고서 마무리.

**심사 질문:** 무엇을 실제 측정했는가? 어떤 주체·backend·시간 가정이 바뀌면 결론이 깨지는가? root 대신 제한 token을 쓰면 결과가 같은가? 복원 후에도 같은 oracle를 사용할 수 있는가?

큰 통합은 별도 [8주 비밀·identity·복구 캡스톤](../../../capstones/secrets-identity-recovery.md)으로 진행합니다. [평가표](../assessment.md)의 4영역 점수와 필수 gate, 미실행 항목을 함께 제출합니다.
