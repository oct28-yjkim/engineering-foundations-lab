-- ClickHouse 26.8: 각 문제에 예측·실행 증거·반례·판정 기준을 남깁니다.
-- elapsed만 비교하지 말고 query_id/read_rows/read_bytes/memory/ProfileEvents를 수집하세요.

-- 0. seed v2 검증
-- events=500000, sessions=100000, users=50000, UTC 활동일=180.
-- 동일 세션당 5행/사용자1명/국가1개/기기1개, timestamp 5개가 60초 간격인지 검증하세요.
-- purchase 외 revenue=0, cents→Decimal 변환 과정에 Float가 없는지 확인하세요.

-- 1. 프로파일링과 정밀도
-- 이벤트 범위/행 수/정확 users/정확 sessions를 구하세요.
-- uniqExact, uniq, uniqCombined64를 비교하고 상대오차와 메모리 비용을 기록하세요.

-- 2. 일별 KPI
-- 날짜별 정확 DAU, session 수, purchases, 매출을 계산하세요.
-- event가 아예 없는 날은 GROUP BY만으로 생성되지 않습니다. 180일 date spine과 JOIN하세요.
-- session-date와 user-date의 의미를 구분하세요. seed는 세션이 자정을 넘지 않습니다.

-- 3. 사용자 도달률 vs 순서 있는 session funnel
-- 국가별 page_view/cart/purchase 사용자 수의 비율은 순서 퍼널이 아닙니다.
-- windowFunnel(1800, 'strict_increase')로 동일 session 안의
-- page_view→add_to_cart→purchase를 계산하세요. 분모는 page_view 도달 session입니다.
-- 순서 역전, 같은 timestamp, 다른 session, 1800초 초과 반례를 설계하세요.

-- 4. 최신 이벤트
-- argMax에 (event_time,event_id)를 사용하여 시간 동률을 결정하세요.
-- 최종 사용자 수준으로 event type/time을 동일한 row에서 반환하세요.

-- 5. 월별 국가 매출
-- dense_rank 상위 2순위를 구하세요. 동률이 있으면 2행보다 많을 수 있습니다.
-- 정확히 2행만 필요하면 row_number와 country tie-breaker를 비교하세요.

-- 6. pruning 실험
-- event_type+시간 / device+시간 조건을 EXPLAIN indexes=1과 실제 실행으로 비교하세요.
-- EXPLAIN만으로 elapsed를 결론내리지 마세요. partition과 primary-key pruning을 분리하세요.
-- ORDER BY 첫 열의 영향과 index_granularity가 row 단위 index가 아닌 이유를 설명하세요.

-- 7. Map과 누락
-- campaign별 event/revenue를 구하세요. 없는 key를 조회했을 때 default value를 확인하세요.
-- mapContains로 누락과 실제 빈 문자열을 구별하세요.

-- 8. 코호트
-- 최초 관측 활동의 UTC 월요일을 cohort로 하여 주차별 users를 구하세요.
-- signup 코호트가 아님을 명시하고 첫 관측 이전 활동과 관측 종료의 편향을 설명하세요.

-- 9. incremental MV
-- AggregateFunction states로 event count, exact users, purchases, Decimal revenue를 저장하세요.
-- raw→state→Merge 결과 동일성을 검증하세요. finalized distinct 수의 합은 정답이 아닙니다.
-- 02의 backfill은 writer가 멈춘 실습 DB 전용이며 비원자적입니다.
-- live ingest에서는 cutoff/watermark, 별도 backfill 경로, 재시도 중복 제어를 설계하세요.

-- 10. 운영/내부동작
-- 03_internals.sql로 part/mark/column compression/merge/query pipeline을 관측하세요.
-- query_log는 flush 지연과 설정/권한에 영향을 받습니다. 빈 로그를 성공으로 해석하지 마세요.
-- read-only 관측과 mutation/merge를 유발하는 실험의 비용을 구분하세요.
