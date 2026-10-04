# 제품별 DB Compose 분리 검증

검사일: 2026-10-04. 루트 `compose.yaml`을 제거하고 PostgreSQL·ClickHouse 구성을 각 제품 디렉터리로 분리한 변경의 기록입니다. 기존 검증 문서는 당시 실행 이력으로 보존합니다.

## 확인한 범위

- Docker Compose `v2.32.4-desktop.1`로 제품별 기본 구성 7개의 `config --format json` 파싱 통과.
- 모든 기본 프로젝트 이름이 서로 다르며, PostgreSQL·ClickHouse 기본 network/volume 이름도 독립적임을 확인.
- SQL bind mount가 이동 전과 같은 실제 파일·디렉터리를 가리키며 읽기 전용 설정을 유지하는지 확인.
- 이전 Git 커밋의 루트 구성을 표준입력으로 정규화하여 새 제품별 구성과 비교: 두 service는 고정 `container_name` 제거를 제외하고 image·환경·command·ports·mount·healthcheck 설정이 동일함.
- 선택 legacy-volume override는 해당 환경 변수 누락 시 두 제품 모두 config 단계에서 실패(exit 15). 합성 volume 이름을 명시한 경우 `external: true`와 입력한 이름으로 해석됨을 확인. 실제 volume을 생성하거나 연결한 검사가 아님.
- 기본 + legacy-volume + 합성 image digest override의 3파일 병합도 검사: image 선택·external volume·SQL bind 경로 유지. digest는 파싱 검사용 값으로 실제 이미지 존재·실행을 검증하지 않음.
- 루트 Compose 파일이 남아 있지 않음을 확인. 문서의 명령·상대 링크·고정 컨테이너 이름 참조를 새 경로에 맞춰 검사.
- Markdown 263개·내부 링크 1,731개의 경로·anchor·코드 fence 검사 오류 0, `git diff --check` 통과.

## 실제로 실행하지 않은 것

`desktop-linux` Docker context의 엔진 pipe가 없어 `docker info` 연결에 실패했습니다. 엔진을 시작하거나 설정을 바꾸지 않았습니다. 따라서 이미지 다운로드, DB 기동, SQL 실행, 기존 container/volume 조사, 백업·복원·기존 volume 전환은 **미실행**입니다.

설정 파싱 성공은 실제 기동·데이터 호환성·복구 검증을 의미하지 않습니다. 파일 분리 과정에서 기존 컨테이너를 정지·삭제하거나 volume을 복사·삭제하지 않았습니다. [기존 데이터 전환](compose-migration.md)은 필요한 사용자가 대상·백업·이미지 호환성을 확인한 뒤 선택하는 별도 절차입니다.
