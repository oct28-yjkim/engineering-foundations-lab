-- PostgreSQL 18: 각 문제는 SQL, 예측, 실행 계획, 반례, 해석을 함께 제출합니다.
SET search_path TO commerce, public;
SET TIME ZONE 'UTC';

-- 0. seed v2 불변식
-- users=10000, products=1000, orders=100000, order_items=300000,
-- UTC 2026-01-01 <= ordered_at < 2026-06-30, distinct date=180을 검증하세요.
-- 모든 주문의 total_amount = sum(quantity*unit_price), 주문당 3줄을 확인하세요.
-- user_id=42의 주문 상태 분포를 확인하고 modulo 기반 seed의 상관 오류를 설명하세요.

-- 1. 데이터 프로파일링
-- 주문 기간, 모든 상태의 주문 수/사용자/금액을 구하세요.
-- 이것을 매출로 부를 수 없는 이유, 주문시간과 결제시간의 차이를 설명하세요.

-- 2. 월별 KPI
-- UTC 월·배송 국가별 paid/shipped 주문 수, 구매 사용자, 주문 기준 매출,
-- 평균 주문 금액을 numeric으로 계산하세요. 이 모델은 환불·세금·통화변환을 제외합니다.
-- line JOIN으로 인한 fan-out이 order-level sum을 어떻게 왜곡하는지 반례를 만드세요.

-- 3. 고객별 최근 주문
-- 우선 사용자 10명으로 LATERAL 최근 3건을 관찰하세요.
-- (ordered_at DESC, order_id DESC)로 동률을 결정하고 LEFT JOIN의 이유를 설명하세요.
-- 5번 인덱스를 만든 후에만 전체 10000명으로 확대하여 loops/buffers를 비교하세요.

-- 4. 카테고리 순위
-- 월별 paid/shipped item 매출의 상위 3순위를 dense_rank로 구하세요.
-- 동률이면 3행을 초과할 수 있습니다. 정확히 3행을 원할 때의 결정 규칙도 작성하세요.

-- 5. 실행 계획과 복합 인덱스
-- user_id=42의 최근 주문 20건을 EXPLAIN (ANALYZE, BUFFERS, SETTINGS)로 측정하세요.
-- 위 조건의 정렬까지 지원하는 인덱스를 설계하세요.
-- seed에는 사용자당 10건뿐이므로 LIMIT 20만으로 대규모 서비스 결론을 내리지 마세요.
-- 새 실습 DB 기준 before/after와 재실행 후 warm-cache 차이를 분리하세요.

-- 6. Partial index
-- 2026-04-01 UTC 이전 pending 주문 100건을 시간순으로 조회하세요.
-- predicate implication, prepared statement의 generic plan에서의 한계를 설명하세요.

-- 7. Covering index
-- user_id=42에 order_id/status/ordered_at/total_amount를 반환하세요.
-- INCLUDE의 추가 저장·쓰기 비용과 visibility map / Heap Fetches 관계를 검증하세요.
-- 두 후보 인덱스를 동시에 둔 측정은 각각의 비용을 격리한 실험이 아닙니다.

-- 8. 트랜잭션
-- 1→2 계좌 100 이체. 두 행 존재, 잔액, 합계 보존을 검증하세요.
-- 일정한 잠금 순서를 사용하고 기본 실습은 ROLLBACK으로 종료하세요.
-- READ COMMITTED/REPEATABLE READ/SERIALIZABLE에서 재시도 범위를 설명하세요.

-- 9. 동시성 관찰 (독립 세션 2개 필요)
-- 실습 전용 DB에서 lock wait를 만들고 blocked/blocker/wait_event를 조사하세요.
-- blocker 세션을 ROLLBACK하여 종료; 자동 pg_terminate_backend로 처리하지 마세요.

-- 10. 운영 조사
-- dead tuple 추정, transaction age, cumulative query time, index 사용량을 수집하세요.
-- 누적값→기간 delta, 통계 reset, track_io_timing, 관측자 비용을 설명하세요.
-- idx_scan=0만으로 인덱스를 삭제할 수 없는 이유를 반례로 제시하세요.

-- 11. 내부동작 확장
-- 03_internals.sql의 heap/VM/WAL/lock/stats 증거를 단계별 커리큘럼과 연결하세요.
-- EXPLAIN ANALYZE는 SELECT도 실제 실행하며 instrumentation overhead가 존재합니다.
