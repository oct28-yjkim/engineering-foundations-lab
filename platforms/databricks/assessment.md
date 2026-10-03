# Databricks 심화 과정 평가 기준

**기본 운영 gate:** [운영 가이드](operations.md)에 따라 실제 query/job/pipeline baseline 1개와 서로 다른 사건 2개의 가설 배제·완화·원복·업무/지표 회복을 제출합니다. 승인된 실제 환경 또는 권한 있는 기존 실제 사건 증거를 사용하고 수집 지연·권한·비용 범위를 표시합니다. CPU 모형은 선택 원리 부록이며 필수 선수 조건·managed 수료 조건이 아닙니다. 자료 분석만 수행했다면 직접 실행/복구 미완료를 별도로 남깁니다.

[커리큘럼](curriculum.md) · [실습 준비](labs/README.md) · [소스와 논문](source-reading.md)

평가의 핵심은 **테이블 내용, 권한, 재처리, 운영 비용과 복구를 함께 검증하는 것**입니다. 관리형 workspace가 없으면 원리·소스·CPU 모형·구체 실험 설계까지 평가할 수 있습니다. 실제 managed 기능 검증은 미실행으로 남깁니다.

## 공통 점수

정확성·원리/소스·실험/반증·운영/재현성 **각 25점, 총 80 이상·영역별 15 이상·필수 게이트 전부 통과**가 선언한 범위의 기준입니다.

| 영역 | 최소 증거 | 전문가 수준 증거 |
| --- | --- | --- |
| 정확성 25 | key/version/delete·권한·commit의 업무 계약과 oracle | late/duplicate/conflict·권한 철회·부분 복원 후 상태 검산 |
| 원리/소스 25 | Spark·Delta·Runtime·Photon·UC의 서로 다른 책임 | 원논문/공개 구현·비공개 경계·배포 버전 차이를 명시한 인과 설명 |
| 실험/반증 25 | 고정 입력/결과·baseline·한 변인·음성 요청 | concurrency·retry·permission/cache·파일/plan 대안 설명과 비용 포함 |
| 운영/재현성 25 | 자원·권한·시간·비용 상한과 manifest | 실제 job identity·artifact·audit·독립 restore·서비스/업무 gate 복구 |

## 필수 게이트

1. **대상과 권한:** cloud/region/workspace, catalog/schema/table/volume, runtime 또는 SQL warehouse, run-as principal을 기록합니다. 두 사용자 또는 서비스 identity의 허용/거절을 구분하며 `SELECT` 허용과 외부 cloud storage 직접 접근을 혼동하지 않습니다.
2. **정합성:** 원본 event ID와 entity version을 분리합니다. 중복 source의 winner를 결정하고 같은 version의 상충 payload를 조용히 임의 선택하지 않습니다. MERGE 성공 자체를 CDC 정합성 증명으로 쓰지 않습니다.
3. **테이블과 업무 transaction:** Delta snapshot/commit을 임의의 여러 테이블·외부 side effect의 원자성으로 확대하지 않습니다. 사용 기능의 실제 transaction 범위는 runtime 계약을 확인합니다.
4. **플랫폼 차이:** OSS Spark/Delta/Unity Catalog와 관리형 Databricks·Photon·Lakeflow의 버전/기능/운영 책임을 구분합니다. 최신 공개 source를 관리형 내부 코드라고 하지 않습니다.
5. **비용과 데이터:** 과금 단위·DBU와 다른 cloud 비용·idle/startup/retry를 포함합니다. 실제 가격은 실행 시점에 확인하고, 권한 없는 project는 생성하지 않습니다. source/credential·실사용자 데이터·전체 환경 변수를 Git/로그에 넣지 않습니다.
6. **복구:** time travel·RESTORE·clone을 자동으로 독립 backup으로 부르지 않습니다. 파일·log·catalog·권한·job/config·checkpoint·secret 참조 중 무엇을 복원했고 무엇이 빠졌는지 확인합니다. retention 제한과 삭제 위험을 무시한 VACUUM/로그 삭제는 실습 기본값이 아닙니다.
7. **검증 상태:** 설계, CPU 모형, 실제 workspace 실행, 독립 oracle 확인을 별도 표시합니다. SQL을 읽거나 파서를 통과한 것은 DBR에서 실행한 결과가 아닙니다.

## 제공 실습의 의미

[Delta SQL fixture](labs/delta-contract.sql)는 사용자가 지정한 **새 학습용 테이블**을 만들고 business version·중복·tombstone·재실행 계약을 검사할 예제입니다. workspace 비용과 데이터를 변경하므로 준비 안내를 먼저 읽고 직접 단계별 실행합니다. 여기서는 실행하지 않았습니다.

[Spark CPU 모형](../../data-processing/spark/labs/README.md)의 merge/watermark/budget는 추가 패키지 없이 원리를 확인하는 도구입니다. 실제 Delta transaction log, UC 권한 집행, Lakeflow checkpoint, DBU 청구서 검증은 아닙니다.

## D14의 2주 단면

이미 만든 작은 Bronze/Silver/Gold 중 **한 개의 업무 흐름**을 재사용하여 정상 run, replay/late/conflict 반례, 두 identity의 허용/거절, 비용 manifest와 복구 증거를 묶습니다. 모든 관리형 기능을 새로 개발하지 않습니다. workspace가 없으면 자세한 실행/판정 계획까지 제출하고 managed gate는 미통과로 둡니다.

리뷰에서는 “MERGE가 성공했는데 값이 틀린 이유”, “table 권한이 없는데 storage 경로로 읽히는 경우”, “Photon on/off 비교의 공정성”, “재시작 때 checkpoint를 지우면 바뀌는 보장”, “삭제된 객체 bytes와 catalog만으로 복구할 수 있는가”를 본인의 증거로 설명합니다. [선택 8주 통합 연구](../../capstones/governed-lakehouse.md)는 미니 프로젝트와 별도입니다.
