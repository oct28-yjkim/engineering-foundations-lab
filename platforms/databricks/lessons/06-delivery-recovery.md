# 06. 배포와 복구: 코드·identity·data·checkpoint를 함께 다룬다

[커리큘럼](../curriculum.md) · [실습 범위](../labs/README.md)

<a id="d11"></a>
## D11 — Jobs·Bundles·CI의 authority 경계

notebook을 Git에 넣는 일과 재현 가능한 job 배포는 다릅니다. source revision, artifact/dependency, job graph/parameter, schedule, target catalog/schema, compute budget, run identity, secret reference를 함께 고정해야 합니다. 배포자가 table을 읽을 수 있어도 job run identity가 읽을 수 있는 것은 아닙니다. 반대로 배포권한을 가진 사람이 과도한 run identity를 사용할 수 있는지도 검토합니다.

현재 명칭은 **Declarative Automation Bundles**이며 이전 이름은 Databricks Asset Bundles입니다. CLI·bundle engine·설정 schema는 실제 version을 고정합니다. `validate`, `plan`, `deploy`, `run`은 각각 검증·변경 계획·원격 상태 변경·실행이며 서로 대체하지 않습니다. 특히 bundle 정의에서 resource가 사라지는 변화는 단순 파일 정리가 아니라 원격 제거로 이어질 수 있습니다. [명령 참조](https://docs.databricks.com/aws/en/dev-tools/cli/bundle-commands), [run identity](https://docs.databricks.com/aws/en/dev-tools/bundles/run-as)

**배포 전 설계 리뷰:** 실제 token/host 없이 bundle 초안을 검토합니다. 이는 CPU 성능 실험이 아니라 변경 안전성 검토입니다. 아래 체크리스트를 사람 두 명이 독립 확인하고, 실제 CLI validation을 수행하지 않았다면 YAML 리뷰로만 기록합니다. 이후 [운영 가이드](../operations.md)의 job/task timeline·run identity·오류·rollback 증거로 실제 배포를 검증합니다. bundle의 script/artifact build가 명령을 실행할 수 있으므로 외부 template를 신뢰 없이 실행하지 않습니다.

1. 대상은 새 sandbox workspace/schema이며 prod/default target로 묵시 선택되지 않는가?
2. bundle name·target·deployer·state path·resource ID가 기존 배포와 충돌하지 않는가?
3. deploy principal과 run principal의 privilege가 workload에 필요한 범위만 갖는가?
4. schedule이 기본 비활성이며 동시 실행·retry·timeout·compute 상한이 명시되는가?
5. package lock와 artifact digest, git revision을 job 결과에서 역추적할 수 있는가?
6. output table schema 변경과 reader rollout 순서, checkpoint 호환 검토가 있는가?
7. secret은 값이 아니라 승인된 secret reference로만 관리되는가?
8. 제거/rename/bind/import가 기존 업무 자원을 건드리지 않는가?

**MANAGED-OPTIONAL 순서:** 승인된 sandbox target 확인→권한 최소화→validation→지원되는 plan 검토→별도 변경 승인→deploy→run→정답/권한/비용 검사입니다. 이 저장소가 deploy/run을 자동 실행하거나 CI secret을 생성하지 않습니다. 이 단계의 source 통합은 학생이 수행하는 과제이며 완성된 자동 배포 workflow를 제공했다는 뜻이 아닙니다.

**실패 실험:** data write 성공 후 job task 실패, retry 중 동일 batch 중복, upstream 성공/downstream 실패, 새 reader/구 writer 혼재를 작은 fixture로 재현합니다. Lakeflow Jobs repair/retry가 business state rollback을 수행한다고 가정하지 않습니다. D04의 deterministic event ledger로 output을 재검산하고 job 성공 상태와 데이터 완료 상태를 따로 기록합니다.

**gate:** sandbox에서의 배포/실행 evidence와 local config review가 분리되어야 합니다. `validate` 성공을 권한/비용/실행 정답의 보증으로 쓰면 실패입니다. `destroy`, 자동 승인, 운영 resource bind는 기본 실습에 포함하지 않습니다.

<a id="d12"></a>
## D12 — 복구 객체 목록과 일관된 복구 시점

RESTORE/time travel은 보존된 table history에 의존합니다. source storage 또는 필요한 파일이 사라졌을 때 독립 backup처럼 작동하지 않습니다. shallow clone 역시 source의 파일 생명주기와 관련될 수 있어 독립 재해복구 사본으로 가정하지 않습니다. 복구 수단의 이름보다 **어떤 상태를 어디에 독립 보존하고 실제로 복원했는가**가 중요합니다.

| 복구 객체 | 최소 증거 | 대표 누락 위험 |
| --- | --- | --- |
| table data와 log/protocol | 일관된 version/manifest·checksum·복원 조회 | log만 있고 data 없음, 지원 불가 reader feature |
| catalog/schema/권한/owner | 정의·grant 정책·새 identity mapping | 데이터는 돌아왔지만 타 tenant에게 노출 |
| code/artifact/job/bundle | commit·dependency·parameter·schedule | 구 schema writer가 새 table에 실행 |
| ingestion checkpoint/schema state | 소유 query·format·source retention·재시작 계획 | checkpoint만 복사했지만 source/sink와 불일치 |
| credentials/network/policies | secret 값 제외 reference·회전/발급 절차 | 키 무효·잘못된 region·과도한 egress |
| downstream projection/index | source version·재구축 절차·정답 | RAG index/serving table의 삭제·수정 누락 |

**LOCAL 기본 복구 과제:** quiesce된 synthetic source와 결과·명세를 별도 새 디렉터리에 복원하여 PK/value/tombstone hash를 비교합니다. 모델 또는 local Spark fixture 복원은 Databricks account/UC/region DR 검증이 아닙니다. 무엇을 보존하지 않았는지 반드시 씁니다.

**MANAGED-OPTIONAL 작은 복구:** 비운영 source에서 쓰기를 멈추고 선택한 table version과 관련 정의를 확정합니다. 실제 제품의 지원된 export/copy/backup 방법으로 별도 대상으로 복원합니다. live table directory를 임의의 파일 복사로 훑어도 일관된 Delta snapshot이 얻어진다고 가정하지 않습니다. restore destination의 reader protocol/권한·storage·secret reference를 먼저 점검하고 source를 지우지 않습니다.

복원 후 D04 key/value·tombstone, D05 allow/deny, D07 source replay를 다시 검사합니다. CDF/stream consumer는 복원으로 새 변경이 발생하는지, source version과 sink idempotency가 어떻게 연결되는지 확인합니다. checkpoint를 다른 sink로 무조건 복사하지 않습니다. 재구축이 필요하면 source retention 안에서 새 query identity와 별도 output에 replay한 뒤 대조합니다.

**RPO/RTO 정의:** 마지막 확인된 business event 시점, 백업 기준점, 장애 판정 시작점, 읽기·쓰기·권한·downstream 모두 복구된 종료점을 명시합니다. 테이블이 열리는 시점만으로 end-to-end RTO를 끝내지 않습니다. quiesce 실험에서 손실0이었다는 결과를 지속 쓰기·region 장애의 RPO0으로 일반화하지 않습니다.

**보안 실패 설계:** 만료된 service credential, 잘못된 run principal, secret rotation 후 재시작, audit data 접근 실패를 tabletop 또는 승인된 sandbox에서 검토합니다. secret redaction은 값 추출 가능성을 완전히 제거하는 보안 경계가 아니므로 privileged code 실행 권한을 제한합니다. 생산 키를 비활성화하는 실습은 하지 않습니다.

**gate:** fresh destination에서의 정답·권한·재시작 검증이 있어야 실제 작은 restore PASS입니다. 설계만 한 multi-region/account DR은 DESIGN으로 남깁니다. `VACUUM` safety 해제·source 삭제·공유 job 중단으로 장애를 만들지 않습니다.
