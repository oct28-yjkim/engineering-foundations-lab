# MySQL: Zero to Hero → InnoDB Internals & Production Engineering

SQL 기초에서 InnoDB의 페이지·버퍼·redo·undo·read view를 거쳐 잠금, 최적화, 복구·복제, 소스 코드까지 연결하는 **28주·14모듈·7강** 과정입니다. 목표는 설정값을 외우는 것이 아니라, 업무 불변식이 언제 깨지는지 재현하고 관측·구현 근거로 개선안을 검증하는 것입니다. 학습 기간 자체가 전문성을 보장하지는 않습니다.

기준은 **MySQL Community Server 8.4 LTS / InnoDB**, 재현용 이미지는 `mysql:8.4.11`입니다. 이 번호를 MySQL 전체 배포판의 최신 버전이라는 의미로 사용하지 않습니다. 실제 서버 버전·이미지 digest·설정은 매 실행에 기록하고, 소스 기준은 [읽기 지도](source-reading.md)에서 확인합니다. MariaDB, Aurora MySQL, HeatWave, NDB의 내부 동작·운영 보장을 이 트랙의 결과로 대체하지 않습니다.

## 학습 순서

1. [커리큘럼](curriculum.md)과 [공통 선수 지식](../shared/foundations.md)을 읽고 SQL·자료구조·OS·트랜잭션 진입 수준을 확인합니다.
2. [CPU 실험](labs/offline.md)으로 기대값과 반례를 만든 뒤 [실제 엔진 실습](labs/README.md)을 선택 실행합니다.
3. 각 강의의 수동 실험에서 세션 순서·결과·오류를 기록하고 [소스 지도](source-reading.md)로 책임 경계를 추적합니다.
4. [평가 기준](assessment.md)에 범위별 증거를 모읍니다. 실행하지 않은 복구·복제·보안은 미검증으로 남깁니다.

| 모듈 | 강의 | 핵심 질문 |
| --- | --- | --- |
| MY01–02 | [SQL·아키텍처·인덱스](lessons/01-foundations-storage.md) | SQL의 의미와 저장 구조가 정확성·I/O에 어떻게 연결되는가? |
| MY03–04 | [버퍼·redo·undo·read view](lessons/02-buffer-redo-mvcc.md) | commit된 변경은 무엇에 기록되며, 각 읽기는 어떤 버전을 보는가? |
| MY05–06 | [잠금·deadlock·재시도](lessons/03-locking-transactions.md) | 불변식을 지키는 동시 실행과 안전한 재시도를 어떻게 설계하는가? |
| MY07–08 | [최적화·통계·실행·인덱스 설계](lessons/04-optimizer-execution.md) | 추정이 틀린 지점과 실제 비용을 분리할 수 있는가? |
| MY09–10 | [DDL·유지보수·백업·PITR](lessons/05-maintenance-recovery.md) | 온라인 변경과 복원이 실제로 업무 상태를 보존하는가? |
| MY11–12 | [binlog·GTID·복제·HA](lessons/06-binlog-replication.md) | 접수·내구성·전송·적용·읽기 가시성의 경계는 어디인가? |
| MY13–14 | [운영·보안·소스·연구](lessons/07-production-research.md) | 장애 가설을 구현과 반례로 좁히고 독립적으로 재현할 수 있는가? |

권장 페이스는 **28주 × 주 12시간 = 336시간**이며 선수 지식 보충, 별도 토폴로지 구축, 미통과 실험 반복은 추가 시간입니다. MY14는 앞선 자산을 재사용하는 **2주 미니 연구**입니다. 큰 통합은 별도 [8주 트랜잭션·복구 캡스톤](../../capstones/mysql-transaction-recovery.md)으로 분리합니다.

## 제공 범위와 실행 경계

| 표시 | 제공·학습 내용 | 완료 증거 |
| --- | --- | --- |
| OFFLINE | `index-lookup`, `read-view`, `deadlock`, `commit-recovery`의 CPU 모형 | 독립 기대값·반례·모형의 생략 조건 |
| LOCAL-ENGINE | 선택 실행용 단일 MySQL 환경과 기초 엔진 실습 | 실제 서버 출력·정확한 행/값·오류 검산 |
| LOCAL-SESSIONS | 강의의 2–3세션 MVCC·잠금·MDL 수동 과제 | 실행 순서·connection ID·대기·최종 불변식 |
| RESTORE-LAB | 별도 target의 백업 복원·binlog PITR·실패 주입 설계 | 복원 후 업무 원장·경계·RPO/RTO; 자동 배포 없음 |
| REPLICA-LAB | 비동기/세미동기·GTID·승격·Group Replication 비교 과제 | 실제 다중 서버·실패 이력·읽기 검산; 자동 배포 없음 |
| SECURITY-LAB / BUILD | 서로 다른 주체의 권한/TLS 시험, 일치하는 소스의 debug/test 과제 | 실제 자격 증명별 거부·허용, 빌드/테스트 출력 |

CPU의 `commit-recovery`는 durable marker를 입력받는 결정 모형입니다. 실제 redo 파일, fsync, binlog 복구, 전원 상실을 구현하지 않습니다. 단일 노드의 성공은 HA·PITR·replica 가시성·운영 보안을 증명하지 않습니다. 현재 검증 상태는 [검증 기록](labs/validation.md)에 따릅니다.

저장소 루트에서 CPU 실험부터 실행할 수 있습니다.

```bash
python -B databases/mysql/labs/offline_lab.py --lab all
```

Docker 시작·접속·보존 절차는 [실습 안내](labs/README.md)의 전용 구성을 따릅니다. 기존 PostgreSQL/ClickHouse 볼륨이나 운영 서버를 실험 대상으로 사용하지 않습니다. 강의의 준비 SQL은 개인 실습 schema에서 최초 한 번 실행하며, 재실행은 새 suffix를 사용합니다. `CREATE TABLE IF NOT EXISTS`로 예상과 다른 기존 fixture를 숨기거나 초기화를 위해 전체 schema/volume을 삭제하지 않습니다.

DDL은 implicit commit을 일으킬 수 있고, `EXPLAIN ANALYZE`는 대상 쿼리를 실제 실행합니다. `ROLLBACK`은 외부 API·이미 전송한 메시지·이미 발생한 I/O를 취소하지 않습니다. [공통 실험 방법](../shared/experiment-method.md)에 가설·음성 대조군·자원 상한·미검증 경계를 기록합니다.

공식 기준: [MySQL 8.4 매뉴얼](https://dev.mysql.com/doc/refman/8.4/en/), [8.4 릴리스 노트](https://dev.mysql.com/doc/relnotes/mysql/8.4/en/).
