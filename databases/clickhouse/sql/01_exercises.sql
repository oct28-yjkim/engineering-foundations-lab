-- ClickHouse exercises
-- 각 문제를 풀 때 elapsed, processed rows/bytes를 기록하세요.

-- 1. 데이터 프로파일링
-- 이벤트 기간, 전체 행 수, 사용자 수, 세션 수를 한 행으로 조회하세요.

-- 2. 일별 KPI
-- 날짜별 DAU, 세션 수, 구매 건수, 매출을 계산하세요.
-- 매출이 없는 날짜도 0으로 표현되는지 확인하세요.

-- 3. 전환 퍼널
-- 국가별로 page_view 사용자, add_to_cart 사용자, purchase 사용자를 구하고
-- page_view 대비 구매 전환율을 백분율로 계산하세요.

-- 4. 사용자별 최근 이벤트
-- 각 user_id의 가장 최근 event_type, event_time을 argMax로 구하세요.

-- 5. 상위 국가
-- 월별 매출 상위 2개 국가를 window function으로 구하세요.

-- 6. 정렬 키와 pruning
-- 아래 두 쿼리를 EXPLAIN indexes = 1로 비교하세요.
-- A: event_type과 event_time으로 필터
-- B: device와 event_time으로 필터
-- 어느 쿼리가 더 적은 granule을 읽으며, 그 이유는 무엇인가요?

-- 7. Map 다루기
-- campaign별 이벤트 수와 구매 매출을 계산하세요.

-- 8. 코호트 재방문
-- 사용자별 최초 활동 주를 코호트로 정의하고, 활동 주차별 활성 사용자 수를 구하세요.

-- 9. 사전 집계
-- 일자·국가·기기별 events, unique users, purchases, revenue를 저장하는
-- target table과 incremental materialized view를 만드세요.
-- 중요: unique users는 단순 합산할 수 있는지 판단하고 적절한 table engine을 선택하세요.

-- 10. 운영 조사
-- lab 데이터베이스에서 다음을 조회하세요.
-- a) 테이블별 active part 수와 크기
-- b) 가장 많은 메모리를 쓴 최근 SELECT 5개
-- c) 완료되지 않은 mutation
