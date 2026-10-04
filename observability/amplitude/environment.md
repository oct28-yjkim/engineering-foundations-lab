# Amplitude 실습 환경·데이터·권한 계약

[시작](README.md) · [웹/모바일 LAB](labs/README.md) · [운영 진단](operations.md)

기본 대상은 **소유자에게 허가받은 별도 테스트 프로젝트**입니다. 회사가 Amplitude를 운영한다는 사실만으로 실습 전송·운영 설정 변경·사용자 데이터 조회 권한이 생기는 것은 아닙니다. 계정·프로젝트·API key를 자동 생성하거나 기존 앱에 SDK를 설치하지 않습니다.

## 세 가지 준비 상태

| 상태 | 할 수 있는 일 | 하지 않는 일 |
| --- | --- | --- |
| 계정/송신 허가 없음 | 문서·합성 원장·기대값·소스 읽기, HTTP `--plan`, 단위 검사 | 실제 제품 실행/분석 검증 완료 선언 |
| 읽기 권한만 있음 | 허가된 정제 이벤트·차트 정의·수집 상태 조사 | 사건 주입·SDK 설정 변경·내보내기·프로젝트 수정 |
| 테스트 프로젝트 송신 허가 있음 | 웹 SDK 앱 또는 준비한 모바일 앱에서 합성 사건·UI 검산 | 회사 운영 데이터·실제 사용자 계정·타인 알림/외부 destination 오염 |

테스트/운영 프로젝트 분리는 [공식 시작 안내](https://amplitude.com/docs/data/data-get-started)와 연결합니다. 실습에서 새 프로젝트 구매·plan 변경을 요구하지 않습니다. 조직의 동의·보존·데이터 지역 정책은 담당자 확인을 따르며 이 문서가 법률 판단을 대신하지 않습니다.

## 시작 전 manifest

- 프로젝트의 **비민감 별칭**, test임을 확인한 소유자, 조회·송신 허용 범위, 보존/정리 담당자.
- US/EU 등 실제 데이터 지역과 사용 endpoint, 실제 plan·event/사용량 제약·UI/API 권한. 다른 지역 endpoint를 시험하며 찾지 않습니다.
- Browser SDK/모바일 SDK version·commit/lockfile, OS/browser/device/app build, CMP·autocapture·remote config·queue/storage·flush·retry 설정.
- 원본 업무 행동과 이벤트 이름·발생 위치·필수 속성·version, 익명/로그인/로그아웃의 ID 규약.
- chart의 event/기간/timezone/단위/unique 또는 totals/필터/퍼널 순서·전환 창/retention 방식.
- 알림·목적지 동기화·audience activation·Replay/Experiment가 시험 이벤트에 반응하지 않는지 담당자와 확인. 기본 LAB은 이 기능을 켜지 않습니다.
- 허가된 비용/작업 시간, 새로운 이벤트 이름·고 cardinality 속성이 만드는 영향. 실습용 `lab_run_id`는 선택한 시험 프로젝트에서만 사용합니다.

## 제공 웹 앱의 실행 조건

Python 3.10+ HTTP 서버와 최신 표준 모듈을 지원하는 브라우저가 필요합니다. Docker·Node·npm 설치 없이 웹 앱을 열 수 있습니다. 최초 **명시적 시작 버튼**을 누르면 공식 CDN에서 고정 SDK를 내려받습니다. 회사망이 CDN을 막으면 보안을 우회하지 말고 승인된 배포 경로를 준비합니다.

```text
python -m http.server 18765 --bind 127.0.0.1 --directory observability/amplitude/labs/browser
```

브라우저에서 `http://127.0.0.1:18765/`를 직접 엽니다. 저장소 루트 전체를 서빙하지 않습니다. 서버는 파일 읽기 제공용이며 타 호스트에 공개하지 않습니다. 종료는 해당 터미널에서 Ctrl+C입니다. 서버를 켠 것만으로 SDK나 이벤트가 전송되지는 않습니다.

실제 test key는 UI의 password 입력에만 넣으며 소스·URL·명령행·로그·스크린샷·Git에 기록하지 않습니다. SDK는 전송에 키를 사용하므로 개발자 도구의 request body에도 키가 나타납니다. HAR·Network 원문은 공유하지 말고 필요한 status·크기·합성 ID만 정제합니다. SDK 옵션의 IP 수집 off는 서버/CDN이 연결 메타데이터를 전혀 받지 않는다는 뜻이 아닙니다.

앱은 메모리 저장, 20회 track/5분, 자동 retry 0, 자동 계측·remote config·진단 telemetry off 조건입니다. 새로고침 시 key/원장/미전송 이벤트가 소실될 수 있습니다. 동일 페이지의 Network·local 원장과 서버 가시성을 비교하고 “파일/로컬 저장이 없으므로 전송 취소도 보장된다”고 해석하지 않습니다.

## 모바일과 HTTP의 별도 조건

[모바일](labs/mobile-lab.md)은 허가된 debug/test build·simulator/device와 각 SDK의 버전 고정이 필요합니다. 웹의 메모리 저장·flush·reset 설정을 네이티브 SDK의 보장으로 복사하지 않습니다. 회사 배포 앱·광고 ID·실사용자 세션으로 실습하지 않습니다.

[HTTP runner](labs/http-lab.md)는 Python 표준 라이브러리와 별도의 `AMPLITUDE_LAB_*` 환경변수만 사용합니다. 기본 plan은 key를 읽지 않습니다. API key를 잘못된 region/프로젝트에 보내지 않도록 확인하고, 별칭 일치가 원격 권한 검증은 아니라는 점을 이해해야 합니다.

## 보존·종료

발생기를 멈추고 callback/미해결 전송·조회 상태를 원장에 남깁니다. 웹의 중지/opt-out은 **이미 queue에 있거나 전송 중인 이벤트를 취소하지 않습니다.** 이후 queue가 전송될 수 있으므로 5분 제한은 신규 작업 허용시간이지 네트워크 종료 시한이 아닙니다. identity reset 역시 로컬 식별자 변경이지 과거 사용자 데이터 삭제가 아닙니다. 서버 데이터 정리는 소유자의 별도 보존 절차이며 runner/app은 삭제 API를 제공하지 않습니다. User Privacy/Delete·backfill·광범위 export는 기본 LAB에서 실행하지 않습니다.
