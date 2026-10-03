-- PostgreSQL exercises
SET search_path TO commerce, public;

-- 1. 데이터 프로파일링
-- 주문 기간, 주문 수, 구매 사용자 수, 총 주문 금액을 한 행으로 조회하세요.

-- 2. 월별 KPI
-- 월별·배송 국가별 주문 수, 구매 사용자, 매출, 평균 주문 금액을 계산하세요.

-- 3. 고객별 최근 주문
-- LATERAL join을 이용해 모든 사용자별 최근 주문 3건을 조회하세요.

-- 4. 카테고리 순위
-- 월별 카테고리 매출을 구하고 dense_rank로 상위 3개 카테고리를 조회하세요.

-- 5. 실행 계획과 복합 인덱스
-- 특정 사용자의 최근 주문 20건 쿼리를 EXPLAIN (ANALYZE, BUFFERS)로 측정하세요.
-- WHERE user_id = ? ORDER BY ordered_at DESC LIMIT 20을 지원하는 인덱스를 설계하고 비교하세요.

-- 6. Partial index
-- 운영자가 오래된 pending 주문을 시간순으로 가져오는 쿼리를 작성하고 측정하세요.
-- 전체 주문 중 pending 상태만을 위한 작은 인덱스를 설계하세요.

-- 7. Covering index
-- 5번 쿼리가 order_id, status, total_amount만 반환한다고 할 때 INCLUDE를 검토하세요.
-- index-only scan이 항상 발생하지 않을 수 있는 이유도 설명하세요.

-- 8. 트랜잭션
-- account 1에서 account 2로 100을 이체하세요.
-- 잔액 부족 시 어느 행도 변경되지 않아야 합니다.
-- 두 account를 항상 같은 순서로 잠가 deadlock 가능성을 낮추세요.

-- 9. 동시성 관찰
-- 별도 세션에서 lock wait를 만든 뒤 blocker PID, blocked PID, wait_event를 조회하세요.

-- 10. 운영 조사
-- a) dead tuple이 많은 테이블
-- b) 오래된 transaction
-- c) total execution time이 큰 누적 쿼리
-- d) 사용되지 않은 user index 후보

