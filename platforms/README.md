# Backend Platform Engineering

플랫폼 기능을 연결하는 방법과 그 기능이 지키는 보장·권한·복구 경계를 함께 공부합니다. 첫 트랙은 [Supabase](supabase/README.md)이며, PostgreSQL을 중심으로 Auth·API·Realtime·Storage·Functions·운영 계층을 연결합니다.

## 시작점

- [28주 커리큘럼](supabase/curriculum.md): 14모듈과 심화 강의 7개
- [독립 local 준비](supabase/labs/local-lab.md): 제공 fixture와 실제 제품 실행의 차이
- [소스 지도](supabase/source-reading.md): 단일 repo/버전이 아닌 서비스별 구현 경계
- [평가](supabase/assessment.md): 정상 동작과 권한 거절·복구를 같은 수준으로 검증
- [보안·관측 앱 캡스톤](../capstones/secure-observable-app.md): Sentry와 결합한 앱 수준 연구

[PostgreSQL 트랙](../databases/postgresql/README.md)을 선행하면 RLS·WAL·동시성·인덱스·복구를 깊게 연결할 수 있습니다. 먼저 작은 Supabase 앱을 만들고 부족한 SQL·HTTP·JWT·OS 기초를 돌아가서 보충하는 경로도 가능합니다. 라이브러리 호출 성공만으로 보안·내구성·정합성을 판정하지 않습니다.

## 경계별 질문

| 경계 | 증명할 것 | 독립 증거 |
| --- | --- | --- |
| 사용자 → Auth/API | 실제로 검증한 사용자와 권한 범위 | 서명·만료·세션·role 매핑, 비밀 없는 이력 |
| API → PostgreSQL | grants와 RLS의 허용/거절, view/RPC의 권한 | 두 tenant의 응답 및 변경 전후 상태 |
| DB → Realtime | 권한·연결·reconnect·상태 동기화의 범위 | client 이력과 원본 최신 상태 대조 |
| 앱 → Storage/Function | 경로별 인가와 부작용의 멱등성 | 객체 bytes/hash·URL 수명·실제 변경 원장 |
| 배포 → 운영/복구 | migration·pooler·backup의 전체 상태 | 별도 복원 후 권한·DB·객체·앱 oracle |

여기서 tenant admin은 시스템의 privileged service identity와 다릅니다. “서버 코드에서 호출했다”는 이유만으로 모든 사용자 요청에 RLS 우회 key를 쓰지 않습니다. 또한 [Kafka](../streaming/kafka/README.md)의 durable log 계약을 Realtime의 모든 기능에 적용하거나, [Sentry](../observability/sentry/README.md)에 DB·Auth payload를 무조건 보내는 설계를 피하고 실제 계약을 검증합니다.
