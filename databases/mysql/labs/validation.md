# MySQL 검증 기록

확인일 **2026-10-04**. 실행 환경은 Windows·CPython **3.12.14**, Docker CLI 27.5.1·Compose 2.32.4-desktop.1입니다. 코드는 Python 3.10 이상을 대상으로 하지만 모든 Python minor/OS 조합에서 실행한 것은 아닙니다.

## 수행 결과

| 검사 | 결과 | 증거 범위 |
| --- | --- | --- |
| CPU `--lab all` | 4개 PASS, 일반/`-O` 각각 실행 | 논리 lookup·read view·record wait graph·commit evidence 모형 |
| `test_offline_lab.py` | 79개 PASS, 일반/`-O` 각각 실행 | 독립 기대값·경계 입력·불변성·실패 대조군 |
| `test_engine_lab.py` | 60개 PASS, 일반/`-O` 각각 실행 | Docker/MySQL subprocess의 모의 응답, SQL client 계약·대상 제한 |
| 전체 신규 테스트 | 139개 PASS, 일반/`-O` 각각 실행 | 같은 139개 테스트를 두 모드로 실행; 실제 서버 검증 아님 |
| native `--help` | PASS, subprocess 없음 | 선택 실행 인자 안내 |
| Compose `config --quiet` | PASS | 구문/설정 구조만 확인, 이미지 시작 아님 |
| 기존 OpenSearch·LLM·IaC 테스트 | 각각 139·50·82개 PASS | 기존 CPU/mock 실습 회귀 검사 |
| Markdown·내부 링크 검사 | 179문서·내부 링크 1,057개, 오류 0 | 파일/anchor 존재·code fence 짝; MySQL 7강·14 anchor 확인 |

핵심 CPU oracle은 `-O`에서 제거되지 않는 예외 기반 검사입니다. 테스트 코드에 있는 assertion과 실제 lab의 runtime 검증을 구분합니다. 독립 리뷰에서 SQL literal 정답·동일 session의 commit/rollback·신규 DB 범위, read-view watermark·version 순서·2PC 가정을 대조했습니다.

## 실제 엔진은 미검증

Docker Linux 엔진 pipe `dockerDesktopLinuxEngine`이 없어 server에 연결할 수 없었습니다. 실제 이미지 pull·컨테이너 생성·MySQL SQL 실행은 **수행하지 않았습니다**. Docker Desktop을 자동 시작하거나 host 설정을 변경하지 않았고, DB·계정·클라우드 자원을 생성하지 않았습니다.

공식 소스 tag/commit와 경로, Docker Official Image `8.4.11` 제공 여부 및 image 정의의 Unix socket 경로는 읽기 전용으로 확인했습니다. [소스 지도](../source-reading.md)의 C++/MTR 빌드·테스트는 미수행입니다. 공식 매뉴얼의 핵심 계약은 웹 열람으로 확인했으나 자동 HEAD 링크 점검은 사이트에서 403으로 거부되어 일괄 접근성 PASS로 집계하지 않았습니다.

다중 세션 MVCC·실제 deadlock/MDL·crash 내구성·backup restore/PITR·replica/승격·보안/TLS·운영 성능은 별도 미검증입니다. 단위 테스트가 제공하는 성공 응답은 실제 MySQL이 반환한 결과가 아닙니다.

## 사용자 환경에서 엔진 검증하기

[환경·안전 경계](README.md)를 읽고 개인 로컬 Docker 대상임을 확인한 뒤 선택 실행합니다.

```text
docker compose -f databases/mysql/compose.yaml up -d --wait
python -B databases/mysql/labs/engine_lab.py --run-local
```

실제 출력의 `mode: local_engine`과 `status: PASS`, 신규 `efl_mysql_<UUID>` DB, 계정 2개·주문 4개·잔액 8750/6250 및 제약 오류 oracle을 확인합니다. image digest·서버 설정·실행 로그와 실패 stage를 새 보고서에 남깁니다. healthcheck 성공이나 mock PASS로 대신하지 않습니다.

실패했거나 timeout이 발생하면 namespace를 보존하고 서버의 실제 상태를 별도로 확인합니다. 성공해도 이 작은 단일 세션 fixture만 통과한 것이며 위의 미검증 경계가 자동으로 해소되지는 않습니다.
