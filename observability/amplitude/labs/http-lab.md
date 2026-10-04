# HTTP 수집·분석 진단 보조 LAB

[웹·모바일 기본 경로](README.md) · [runner](http_lab.py) · [합성 입력](fixture.json)

SDK 경로에서 이상이 있을 때 **같은 테스트 프로젝트의 수집/차트 경계**를 별도로 확인하는 도구입니다. SDK queue·앱 lifecycle·사용자 merge를 구현하거나 검증하는 모형이 아닙니다. 계정/송신 허가가 없으면 계획만 검토합니다.

## 1. 무송신 계획과 독립 정답

Python 3.10+ 표준 라이브러리로 저장소 루트에서 실행합니다. 기본/`--plan`/`--help`는 API key를 읽거나 네트워크를 사용하지 않습니다.

```text
python -B observability/amplitude/labs/http_lab.py --plan
```

계획에는 새 `run_id`, `start_time_ms`, 합성 payload와 기대값이 있습니다. event time은 기본적으로 실행 직전 9초 구간입니다. 시각·IDs를 원장에 보존합니다. 재현 시 같은 run ID뿐 아니라 **동일한 시작 시각도** 지정해야 입력이 같습니다.

| 사용자 | View | Checkout | Purchase | total |
| --- | --- | --- | --- | --- |
| A | 2 | 1 | 1 | 4 |
| B | 1 | 1 | 1 | 3 |
| C | 1 | 1 | 0 | 2 |
| D | 1 | 0 | 0 | 1 |
| 합계 | 5건/4명 | 3건/3명 | 2건/2명 | 10건/4명 |

각 user/device는 run별 고유 합성 값입니다. `source=efl-http-v2`, 같은 run filter·시간 범위, **This order / Unique Users / 30분 전환 창**에서는 `4→3→2`, 전환자 A/B, 최종 `2/4=50%`가 기대값입니다. View 총수 5를 분모로 쓰면 다른 질문입니다. 웹 3건과 source/run을 섞지 않습니다. [분석 정의 근거](https://amplitude.com/docs/analytics/charts/funnel-analysis/funnel-analysis-how-amplitude-computes)

## 2. 허가된 테스트 프로젝트에만 선택 전송

[환경 계약](../environment.md)을 먼저 따릅니다. 이 단계는 **외부 SaaS에 이벤트를 남기는 쓰기**입니다. runner는 원격 프로젝트가 test인지 조회하지 못합니다. 지역과 실제 키 소속을 사용자가 확인해야 하며 별칭 일치는 실수 방지일 뿐 인증 경계가 아닙니다.

PowerShell 7 예시입니다. 실제 key를 명령행에 적지 않고 password 입력으로 받습니다. 직전에 확인한 plan의 run/time을 입력하며, 전송 목적·대상을 확인하기 전에는 실행하지 않습니다.

```powershell
# 개인 세션에서 허가된 테스트 프로젝트만 선택; key는 history에 직접 쓰지 않습니다.
$ampRunId = Read-Host 'Reviewed plan run_id (32 lowercase hex)'
$ampStartTime = Read-Host 'Reviewed plan start_time_ms'
$env:AMPLITUDE_LAB_PROJECT_LABEL = 'lab-amplitude-training'
$env:AMPLITUDE_LAB_API_KEY = Read-Host 'Test project API key' -MaskInput
try {
    python -B observability/amplitude/labs/http_lab.py --send-to-test-project --region us --confirm-project-label lab-amplitude-training --run-id $ampRunId --start-time-ms $ampStartTime
    # EU 프로젝트라면 region을 eu로 선택합니다. 지역을 바꿔 가며 시험하지 않습니다.
} finally {
    Remove-Item Env:AMPLITUDE_LAB_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:AMPLITUDE_LAB_PROJECT_LABEL -ErrorAction SilentlyContinue
}
```

환경변수는 같은 권한의 프로세스·진단 도구로부터 비밀 저장소가 아닙니다. 공유 세션·CI·전체 environment 출력은 피합니다. 예시 finally는 이 실습에서 설정한 환경변수 두 개만 세션에서 제거하며, 원격 데이터/키 자체는 삭제하지 않습니다. 기존 같은 이름의 값이 있다면 덮어쓰기 전에 새 전용 셸을 사용합니다.

전송은 고정 US/EU HTTPS host의 HTTP V2에 **합성 10건·POST 1회**입니다. 자동 retry·임의 URL·임의 파일/실사용 payload·delete/export는 없습니다. TLS 검증을 유지하고 proxy/redirect를 사용하지 않습니다. 회사 proxy가 필수이면 우회하지 말고 미준비 상태로 남깁니다. 요청 32KiB/응답 64KiB/socket 작업 10초가 상한이며 전체 hard deadline은 아닙니다. 미래 event와 7일을 넘긴 과거 입력은 전송 거부합니다. 이 7일은 **랩의 보수적 backfill 제한**이지 Amplitude 전체 보존/수용 한계가 아닙니다.

## 3. 응답과 실제 회복을 구분

`RECEIPT_ACCEPTED`는 HTTP 200 + code 200 + 10건 수신 응답만 확인한 상태입니다. chart/funnel/dedup는 항상 별도 미검증으로 표시합니다. 부분 응답·429·다른 상태는 `NEEDS_REVIEW`, transport/해석 오류는 `ERROR`로 중단합니다. 전송을 시작한 뒤 실패하면 서버가 일부/전부 처리했을 수 있어 `전부 미전송`으로 단정하지 않습니다.

raw 응답에는 입력/ID/비밀이 섞일 수 있어 stdout은 status와 허용된 숫자 receipt 필드만 출력합니다. 실제 원인 분류는 자신의 허가된 debugger/보안 로그에서 수행합니다. `events_ingested`를 최종 고유 이벤트 수와 동일시하거나 에러를 없애려고 새 insert ID로 전체 재전송하지 않습니다. [HTTP V2 응답·dedup 계약](https://amplitude.com/docs/apis/analytics/http-v2)

실제 통과는 동일 프로젝트의 User Activity/Event Explorer와 차트에서 10건의 원장, 이벤트별 ID/속성, 정확한 사용자 집합과 `4→3→2`를 확인한 경우입니다. replay는 최초 수신 상태 확인 후 같은 run/time으로 최대 한 번만 별도 선택하고, 서버 dedup가 어떻게 관측됐는지 기록합니다. HTTP runner는 이 수동 횟수 제한을 여러 프로세스 사이에서 강제하지 않습니다.

현재 실제 SaaS 전송은 수행하지 않았습니다. [코드 검증과 미실행 범위](validation.md)를 함께 읽습니다.
