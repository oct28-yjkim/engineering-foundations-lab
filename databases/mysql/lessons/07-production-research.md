# 07. 운영·보안·소스·연구 — 관측에서 반증 가능한 설명으로

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [평가](../assessment.md)

MY13은 기존 실험의 운영·소스 근거를 보강하고, MY14는 한 단면을 2주 안에 재현하는 미니 연구입니다. 코드 읽기, 실제 server 관측, 별도 SECURITY-LAB, debug BUILD를 구분합니다. 제공 로컬 실습 계정의 편의 권한을 운영 애플리케이션의 권장 권한으로 사용하지 않습니다.

<a id="my13"></a>
## MY13 · 관측·보안·성능 진단·소스 기반 반증

### 관측에서 가설로

“DB가 느리다”를 connection 획득, client/network, statement 실행, row/MDL wait, log flush, page I/O, CPU, replica 적용, application retry로 분해합니다. queue 길이나 buffer hit ratio 하나로 원인을 결정하지 않습니다. client end-to-end 시간과 서버 계측 시간의 범위도 다릅니다. [Performance Schema](https://dev.mysql.com/doc/refman/8.4/en/performance-schema.html)의 instrument·consumer·수집 범위·overhead를 확인합니다.

| 증상 | 경쟁 가설 | 추가로 필요한 관측 |
| --- | --- | --- |
| commit p99 증가 | redo/binlog flush, storage 지연, group commit 대기 | durability 설정·commit 표본·I/O·queue·오류 |
| SELECT latency 증가 | plan/cardinality 변화, cold pages, row/MDL wait | exact query/plan·분포·rows/loops·wait 원장 |
| disk 사용 증가 | 데이터 증가, undo/purge 지연, binlog retention, DDL 공간 | 파일 유형·retention·view 수명·작업 timeline |
| replica stale read | receiver 지연, apply 지연/오류, 오래된 client snapshot | 필요한 GTID·received/applied·transaction 경계 |
| deadlock 증가 | 접근 순서·index/plan 변화, 긴 transaction, FK/범위 경합 | 순환 graph·실제 index·업무 단위·retry 비율 |

먼저 짧은 구간의 합성 workload를 관측한 뒤 변인 하나를 바꿉니다. 장시간 general log·전역 tracing을 켜거나 전체 세션을 kill하는 식의 진단은 기본 실습에 포함하지 않습니다. statement literal·slow log·binlog에는 비밀/개인정보가 담길 수 있으므로 synthetic data와 비밀 제거 규칙을 사용합니다.

### SECURITY-LAB: 권한은 필터가 아니다

MySQL의 계정은 사용자/host 매칭과 인증·권한·role 활성 상태를 함께 검토합니다. 접속 성공과 해당 object에 대한 작업 허용은 다른 단계입니다. `USER()`와 `CURRENT_USER()`를 비교하되 다른 계정의 비밀을 조회하지 않습니다. [Access control](https://dev.mysql.com/doc/refman/8.4/en/access-control.html).

별도 학습 환경에 read-only 분석자, bounded write 앱, migration 관리자 역할을 설계하고 서로 다른 자격 증명으로 시험합니다. global 관리·FILE·계정 관리 등 불필요한 권한을 부여하지 않습니다. tenant WHERE 조건은 그 자체로 DB 인가 경계가 아니며, view/procedure의 invoker/definer 의미와 base table 직접 접근을 함께 검증해야 합니다.

| 주체 | 허용 양성 대조군 | 금지 음성 대조군 |
| --- | --- | --- |
| 분석자 | 허용 view의 합성 행 조회 | base table/금지 컬럼·UPDATE·DDL |
| 앱 | 지정 schema의 업무 transaction | 다른 schema·GRANT·서버 설정 변경 |
| migration 관리자 | 지정 변경과 검산 | 불필요한 사용자 관리·운영 데이터 유출 경로 |

TLS 시험은 암호화 여부뿐 아니라 CA/hostname 검증 실패, 잘못된 서버 신원, plaintext 거부 정책을 포함합니다. 로컬 socket 접속이나 loopback port가 있다고 네트워크 TLS를 검증한 것은 아닙니다. [Encrypted connections](https://dev.mysql.com/doc/refman/8.4/en/using-encrypted-connections.html). 계정/권한·인증 플러그인·audit 기능의 제공 범위도 Community/Enterprise별로 확인합니다.

### 소스·테스트 추적

1. [고정 소스 지도](../source-reading.md)에서 MY04 read view, MY05 lock wait, MY11 commit 협조 중 하나를 택합니다.
2. 입력 SQL→진입점→자료구조 변경→동기화/오류 경계→결과 반환의 **symbol 5개·자료구조 2개**를 연결합니다. 호출 관계가 있을 수 있다는 정적 근거와 실제 호출을 관측한 증거를 분리합니다.
3. upstream test 한 개의 초기 상태, 세션 동기화, 기대 오류·결과를 읽고 본인 fixture와 차이를 적습니다. MTR test를 일반 mysql SQL 파일처럼 실행하지 않습니다.
4. BUILD를 수행한다면 같은 revision, compiler/OS, debug 옵션, MTR 실행 범위와 raw 결과를 기록합니다. 별도 test 서버를 사용하고 release 서버에 debugger를 붙이지 않습니다.
5. 구현에서 바꿀 조건 하나를 제안하고 그 잘못된 변경을 잡는 최소 test를 만듭니다. 구현 수정이나 빌드를 하지 않았다면 설계로 표시합니다.

**통과:** 두 경쟁 가설의 배제 근거, 권한 허용/거부 표 또는 명시적 미검증, 소스 trace·test oracle·자기 반례가 필요합니다. 정적 파일 검색 결과를 실제 경로 실행이나 보안 완료의 증거로 쓰면 미통과입니다.

<a id="my14"></a>
## MY14 · 2주 최소 연구: 한 경로·한 개선·두 실패 조건

새로운 전체 플랫폼을 구축하지 않습니다. MY01–MY13의 fixture·측정·ledger를 재사용하고 연구 질문 하나를 고릅니다. 논문은 [소스·논문 지도](../source-reading.md)의 원문에서 가정과 용어를 읽되 System R=MySQL optimizer, 논문의 SI=InnoDB RR, ARIES=InnoDB 동일 구현이라는 등식을 두지 않습니다.

| 연구 단면 | baseline → 변경 하나 | 최소 실패 조건 두 개 |
| --- | --- | --- |
| 업무 불변식 | RR의 사전 COUNT → 유효한 guard/검사 프로토콜 | 동시 판단, retry 후 바뀐 상태 |
| 요청 멱등성 | 단순 재전송 → key+digest+결과 원장 | 같은 요청 중복, commit 응답 유실 |
| query 최적화 | 단일 index → 근거 있는 복합 index/통계 변화 | tenant skew, 분포/상관관계 변화 |
| 복구 경계 | 단순 count 검산 → 업무 ledger 검산 | 누락된 transaction, 중복/잘못된 replay 경계 |

복구 경계를 선택하더라도 이미 준비된 RESTORE-LAB만 재사용합니다. 선택 모형만 수행하면 원리 연구로 기록하며 실제 운영 관문은 미완료입니다. 단일 노드 운영 연구에는 [기준선·사건·회복 증거](../operations.md)를 함께 제출합니다.

### 1주차: 예측·baseline·실패

- 업무 질문, 정확성 불변식, 허용 실패 모델, 예상 효과와 악화 가능성을 한 페이지에 적습니다.
- fixture·환경 지문·독립 oracle을 고정하고 baseline의 정상 결과와 두 실패 조건을 재현합니다.
- 논문/구현의 관련 가정을 분리한 뒤 개선 하나를 적용합니다. 기준이 여러 개 바뀌면 효과를 귀속할 수 없으므로 scope를 줄입니다.
- primary metric 하나와 guardrail을 정합니다. 예: throughput이면 중복/누락 0·bounded retry·최종 잔액, query latency이면 결과/순서 동일·write cost·공간 상한입니다.

### 2주차: 수정 검증·반증·재현

- baseline/개선의 정상·실패·수정 후 재실행을 비교하고, 의도적으로 잘못된 구현이 oracle에서 실패하는지 확인합니다.
- 성능은 반복·표본 수·실패율·cache·concurrency·불확실성을 함께 보고합니다. correctness만 검증했다면 성능 향상은 주장하지 않습니다.
- 동료가 임의 request ID 최대 10개 또는 query 5개를 골라 입력→판단→commit/retry→최종 값을 추적하도록 합니다.
- 실행하지 않은 서버 crash·전원 상실·복제·PITR·TLS는 미검증으로 남기고, 다음 실험이 결론을 어떻게 반증할 수 있는지 적습니다.

### 최종 제출

`질문/가설 → 계약/실패 모델 → 환경/fixture → baseline → 실패 반례 → 변경 → 재검증 → 소스/논문 가정 비교 → 운영 trade-off → 한계` 순서의 보고서, 실행/검산 절차, sanitized raw evidence를 제출합니다. 정확성 25·원리/소스 25·실험/반증 25·운영/재현성 25의 [평가 기준](../assessment.md)을 적용합니다.

**통과:** 총 80점 이상·각 영역 15점 이상·필수 gate 전부 충족입니다. 연구 기간을 마쳤다는 이유로 전체 production 전문가 과정이나 실행하지 않은 상위 범위가 자동 완료되지는 않습니다.

큰 통합은 별도 [8주 MySQL 트랜잭션·복구 캡스톤](../../../capstones/mysql-transaction-recovery.md)에서 진행합니다. 여기에 복제·승격·PITR·CDC·운영 전환을 추가할 수 있지만 실제 수행한 토폴로지와 증거만 완료로 기록합니다.
