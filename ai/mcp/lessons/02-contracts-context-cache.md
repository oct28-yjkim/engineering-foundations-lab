# 02. tool 계약·resource·prompt·pagination·cache

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="mc03"></a>
## MC03: JSON Schema와 업무 계약은 다른 검증이다

선수 조건: MC02, JSON value 종류, JSON Schema, 부작용. `reservation_create(quantity)`의 인자가 정수여도 재고·tenant·승인·중복 조건을 만족한다는 뜻은 아닙니다. 입력 validation, 권한, 업무 불변식, 결과 serialization을 별도 단계로 둡니다.

현재 tool schema는 JSON Schema 2020-12를 기본으로 하며 output schema가 있는 경우 structured result를 그 계약에 맞춰야 합니다. `structuredContent`는 object만이 아니라 JSON value를 허용합니다. annotations는 server가 설명한 힌트이며 권한 증명이 아닙니다. [공식 tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

### 실험

1. `quantity=1`, `0`, `-1`, `1.5`, `true`, `null`, 누락, 여분 필드의 기대 결과를 손으로 작성합니다. 특히 Python의 bool/int 관계를 JSON type 판정과 혼동하지 않습니다.
2. [CPU `tool-contract`](../labs/README.md)가 구현한 작은 schema/계약 부분집합을 확인합니다. `$ref`, 조합 schema, 모든 format 검증을 수행한다고 주장하지 않습니다.
3. input shape 실패와 존재하지만 허용되지 않은 item, 부족한 재고, backend 장애를 별도 결과로 분류합니다. HTTP 성공 status가 tool 또는 업무 성공을 보장하지 않는 예를 만듭니다.
4. output의 누락/null/잘못된 type을 주입하고 client 측 검산 결과를 남깁니다. 텍스트에는 성공, structured result에는 실패가 적힌 경우 어느 값을 믿는지 명시합니다.
5. read-only 힌트를 붙인 합성 도구가 실제 원장을 바꾸는 대조군을 설계합니다. annotation 검사만으로 부작용을 막지 못함을 외부 원장으로 확인합니다.

제출물은 wire shape·JSON Schema·업무 규칙·access control·side effect 열을 가진 판정표입니다. server가 tool을 노출했다는 것과 특정 인자를 실행할 권한을 승인했다는 것은 별개입니다. “입력이 유효하므로 실행”이라는 한 단계 설계를 금합니다.

소스 과제: 함수 signature→schema 생성→인자 validation→handler→result 생성 경로를 추적합니다. Python SDK가 어떤 입력을 강제 변환하는지, application이 추가한 strict rule은 무엇인지 실제 테스트로 확인합니다. schema 확장이나 원격 `$ref` 처리는 무제한 fetch/recursion의 이유가 될 수 없습니다.

<a id="mc04"></a>
## MC04: context primitive·pagination·주체별 캐시

resource는 URI로 식별하는 context, prompt는 이름·인자로 얻는 message template로 다루되, 두 경우 모두 내용 자체를 실행 허가로 사용하지 않습니다. prompt가 “시스템 지침”처럼 보이거나 resource URI가 로컬 파일처럼 보여도 host 정책을 우회하는 근거가 되지 않습니다. [Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources), [Prompts](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)

2026-07-28의 cacheable complete result에는 `ttlMs`와 `cacheScope`가 있습니다. TTL은 불변성 보장이 아니라 신선도 힌트입니다. private cache는 다른 authorization context에 공유하지 않습니다. pagination은 페이지 간 snapshot 일관성을 보장하지 않으며 cursor는 opaque하게 취급합니다. MRTR 입력을 포함한 retry 결과는 이 캐시로 재사용하지 않습니다. [공식 caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching)

### 실험

1. [CPU `principal-cache`](../labs/README.md)에서 같은 method/인자라도 다른 principal·tenant·인가 context의 결과가 섞이지 않는지 검산합니다. 모형 필드가 실제 access token verification을 대체하지 않음을 적습니다.
2. 같은 사용자라도 token 교체·scope 축소·정책 revision 변경 후 과거 결과를 재사용할지 보수적으로 설계합니다. raw token을 cache key 로그에 남기지 않습니다.
3. 수신 시각 100, TTL 50인 합성 항목의 149/150/151 시점 결과를 적습니다. 관련 변경 알림은 TTL보다 앞서 무효화하는 대조군을 만듭니다.
4. 2페이지를 읽는 사이 item이 추가/삭제된 합성 목록을 만듭니다. 중복 제거를 했다는 것만으로 누락 없는 snapshot을 얻었다고 하지 않습니다.
5. `public`으로 잘못 표시한 tenant 전용 도구 목록과 resource를 설계 검토합니다. cacheScope는 읽기 endpoint의 access control을 대신하지 않습니다.
6. URI·prompt 인자·tool description 길이에 application 상한을 둡니다. resource 내용의 “다음 링크를 자동 실행” 같은 문장을 데이터로 유지하는 host 테스트를 추가합니다.

제출물: 캐시 key/무효화 표, 변경 전후 principal별 결과, 페이지 변화 원장, stale 결과를 사용할 수 있는 업무와 거부해야 하는 업무의 구분. `tools/list`의 deterministic order는 재현성을 돕지만 도구의 의미·권한이 고정됐다는 뜻은 아닙니다.

구술: 목록에서 숨긴 도구를 이름으로 직접 호출하면 어디서 거부하는가? TTL이 남아 있는데 policy가 축소되면 캐시만 지워서 충분한가? resource link가 `resources/list`에 없으면 반드시 잘못된 결과인가?
