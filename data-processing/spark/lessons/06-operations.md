# 강의 6 — 실행 성공에서 운영 가능한 서비스로

기준 Spark 4.0.4. 로컬 실습 외에 관측 스택·Spark Connect 서버·Kubernetes·클라우드를 자동 구성하지 않습니다. CLUSTER-DESIGN과 실제 승인된 CLUSTER-LAB 증거를 분리합니다.

<a id="sp11"></a>
## SP11 — driver 위치, 배포 방식, 관측의 식별자

### 원리

client/cluster deploy mode는 driver의 위치에 관한 구분이고 Spark Connect는 client와 Spark driver 사이의 API 연결 구조에 관한 구분입니다. 둘을 같은 옵션이라고 부르지 않습니다. Standalone/YARN/Kubernetes의 지원 범위도 같지 않습니다. 예를 들어 4.0.4 Standalone의 Python application은 cluster deploy mode를 지원하지 않으므로 존재하지 않는 배포 조합을 실험 계획에 넣지 않습니다. [배포 모드](https://spark.apache.org/docs/4.0.4/cluster-overview.html), [application 제출](https://spark.apache.org/docs/4.0.4/submitting-applications.html).

Spark Connect에서는 client가 unresolved logical plan을 전달하고 server 측이 실행합니다. classic SparkContext/RDD/JVM 직접 접근에 의존하는 진단 코드는 같은 방식으로 동작한다고 가정하지 않습니다. client/server 버전·지원 API·인증 경로를 별도로 확인합니다. [Connect 구조](https://spark.apache.org/docs/4.0.4/spark-connect-overview.html).

### 추가 구현·설계 과제

1. local classic에서 application ID→SQL execution ID→job ID→stage attempt→task attempt를 연결하는 작은 보고서를 작성합니다. task 실패와 stage 재시도를 중복 없이 셉니다.
2. event logging을 별도 새 학습 경로에 켜고 실행 중 UI와 종료 후 history 자료를 대조합니다. history server 구성은 추가 과제입니다. [공식 관측 지표](https://spark.apache.org/docs/4.0.4/monitoring.html).
3. 제출 환경·driver·executor의 Python/JAR 의존성 manifest를 작성합니다. driver에서 import 성공한 것이 모든 executor에서 성공함을 뜻하는지 검사합니다.
4. Connect를 선택하면 같은 작은 DataFrame 질의를 classic과 별도 격리 Connect 환경에서 실행하고 결과·API 차이를 기록합니다. 서버나 cluster가 없으면 통신/인증 설계만 제출합니다.
5. 클라이언트 종료, driver 종료, executor 종료가 영향을 주는 실행·state 범위를 따로 그립니다. 실제 중단은 자신이 만든 격리 프로세스만 대상으로 합니다.

### 운영 질문

- executor utilization이 낮으면 입력이 작은가, driver가 느린가, shuffle 대기인가, 자원 할당을 기다리는가?
- job 성공인데 output이 stale하면 실제 사용자가 읽은 경로·table version·cache가 무엇인가?
- retry가 증가했는데 성공률은 유지된다면 비용·tail latency·외부 side effect는 어떻게 바뀌는가?
- event log가 누락된 시간과 sink commit 시간이 다른 host clock에서 왔다면 인과 순서를 무엇으로 확인하는가?

### 최소 통과

배포 구조 한 장, version manifest, 식별자 매핑, 관측 공백과 데이터 접근 경계를 제출합니다. local UI를 외부에 공개하지 않습니다. 권한 없는 사용자에게 UI/history/event log 접근이 차단되는지의 부정 시험은 실제 보안 구성을 갖춘 선택 환경에서만 실행 통과할 수 있습니다.

<a id="sp12"></a>
## SP12 — 복구·비용·보안을 같은 설계에서 검토하기

### 복구 계약

RPO는 “checkpoint가 몇 분마다 있나”만으로 결정되지 않습니다. source retention, checkpoint/state 저장소, sink의 commit 복원, code/config 버전, credential 재설정이 모두 실행 가능해야 합니다. RTO는 재기동 시간에 state load·backlog catch-up·oracle 검증·사용자 전환까지 포함할지 먼저 정의합니다.

```text
RTO = 탐지 + 의사결정 + 환경/상태 복원 + 재처리 + 정합성 검증 + 전환
backlog 소거 가능 조건(단순 모형): 처리율 μ > 도착률 λ
```

µ와 λ는 같은 단위·같은 부하 분포로 측정해야 합니다. replay 시 작은 파일·skew·외부 sink 제한 때문에 평상시 µ를 유지하지 못할 수 있습니다.

### 세 실패 도메인

| 실패 | 재료 | 검증할 결과 |
| --- | --- | --- |
| 코드 오류 후 재처리 | 변경 없는 raw fixture와 새 output/checkpoint | 전후 ID별 diff·오류 입력 quarantine·새 버전 의미 |
| checkpoint 접근 불가 | 별도 복구 설계, 보존 input/sink 원장 | 임의 삭제 대신 restore 또는 새 replay의 중복·누락 계약 |
| source 보존 기간 초과 | 누락 구간이 명시된 복제 fixture | 복구 불가능 판정·대체 snapshot·업무 보고 기준 |

실제 운영 checkpoint를 삭제하거나 source retention을 줄여 장애를 만들지 않습니다. 학습용 복제 데이터에서만 복구 가정을 깨뜨립니다.

### 비용 모형과 실험

비용은 CPU 실행 시간뿐 아니라 노드/서비스 과금 단위, idle·재시도·storage·request·egress를 포함합니다. [오프라인 budget 모형](../labs/README.md)은 입력한 가상 단가를 계산할 뿐 Databricks나 cloud 견적이 아닙니다. 자원 2배 조건에서 시간·총 resource-seconds·정확성을 비교하여 빠르지만 더 비싼 결과도 허용합니다. 실제 cloud 확장은 사용자가 선택한 계정·예산·종료 조건을 정한 뒤 수행합니다.

### 보안의 경계

Spark job은 일반적인 SQL 결과 조회보다 넓은 코드 실행 권한을 가질 수 있습니다. network authentication, transport encryption, UI 접근, event log ACL, storage credential, 실행 주체를 분리합니다. 일부 보안 설정은 기본으로 활성화되지 않으며 배포별 책임이 다릅니다. [Spark 보안 문서](https://spark.apache.org/docs/4.0.4/security.html).

합성 tenant A/B 경로를 만들었다고 자동으로 격리되지 않습니다. 실제 storage/실행 identity 권한을 적용하고 A의 읽기 허용, B의 읽기 거부, UI·event log를 통한 우회 접근을 각각 확인합니다. 같은 process의 변수나 경로 이름은 보안 경계가 아닙니다. 로그 redaction 하나로 payload 전체의 개인정보가 제거된다고 주장하지 않습니다.

### 최소 통과

정의된 RPO/RTO·입력 보존·복구 oracle, 비용 상한·정리 목록, 최소 권한의 positive/negative 검사 계획을 제출합니다. 실제 cluster가 없다면 실행 가능한 local replay와 설계 항목을 별도 점수화합니다. cloud 계정·서비스 배포·원격 권한 변경은 기본 과제가 아닙니다.
