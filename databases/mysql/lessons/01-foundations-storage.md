# 01. SQL·아키텍처·저장 구조 — 결과 계약에서 페이지까지

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

범위는 OFFLINE / LOCAL-ENGINE / LOCAL-SESSIONS입니다. 아래 준비 SQL은 [실습 안내](../labs/README.md)로 접속한 **개인 학습 schema**에서 최초 한 번 실행합니다. `SELECT DATABASE(), CONNECTION_ID();`로 대상을 확인하고 기존 이름이면 새 suffix를 정합니다. 이 강의는 MySQL/InnoDB용이며 PostgreSQL의 heap·MVCC 구조를 그대로 대입하지 않습니다.

<a id="my01"></a>
## MY01 · SQL 의미와 서버/스토리지 엔진 경계

### 원리

관계의 집합 모델과 SQL의 중복·NULL·정렬 의미를 구별합니다. 요청은 연결/권한 확인, parsing·이름/타입 해석, rewrite·계획, 실행을 거치고 storage-engine handler를 통해 InnoDB의 저장·동시성 기능을 사용합니다. 모든 최적화가 InnoDB에 있거나 모든 잠금이 SQL layer에 있는 것은 아닙니다. [서버/엔진 구조](https://dev.mysql.com/doc/refman/8.4/en/pluggable-storage-overview.html)를 기준으로 책임 경계를 표시합니다.

SQL의 정답은 row count만이 아닙니다. NULL은 0이나 빈 문자열이 아니며, 비교·집계의 의미가 다릅니다. collation은 문자열의 동등성·정렬·unique 제약에 영향을 줍니다. `LIMIT` 결과에 재현성이 필요하면 유일한 tie-breaker를 포함한 `ORDER BY`를 정의합니다. [NULL](https://dev.mysql.com/doc/refman/8.4/en/working-with-null.html), [문자열 비교](https://dev.mysql.com/doc/refman/8.4/en/charset-collation-effect.html)를 읽습니다.

```sql
SELECT VERSION(), @@version_comment, DATABASE(), CONNECTION_ID();
SELECT @@session.sql_mode, @@session.transaction_isolation, @@session.autocommit;
SELECT @@session.time_zone, @@session.character_set_connection,
       @@session.collation_connection, @@global.innodb_page_size;

CREATE TABLE my01_semantics_run01 (
  id BIGINT PRIMARY KEY,
  tenant_id INT NOT NULL,
  label VARCHAR(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  amount DECIMAL(10,2) NULL,
  tag VARCHAR(20) NULL
) ENGINE=InnoDB;
INSERT INTO my01_semantics_run01 VALUES
  (1,1,'Alice',10.00,'x'), (2,1,'alice',NULL,'x'),
  (3,1,'Bob',0.00,NULL), (4,2,'ALICE',20.00,'y');

SELECT COUNT(*), COUNT(amount), SUM(amount) FROM my01_semantics_run01;
SELECT id FROM my01_semantics_run01 WHERE label='alice' ORDER BY id;
SELECT id FROM my01_semantics_run01 WHERE amount IS NULL ORDER BY id;
SELECT id FROM my01_semantics_run01 WHERE amount=0 ORDER BY id;
```

### 실험·반례

1. 독립 기대값은 집계 `(4,3,30.00)`, label 조회 ID `{1,2,4}`, NULL 조회 `{2}`, 0 조회 `{3}`입니다. 이 네 가지를 row count 하나로 대체하지 않습니다.
2. `amount=NULL`, `NOT IN`의 우변에 NULL을 넣은 경우, `COUNT(DISTINCT tag)`의 결과를 **먼저 예측**합니다. 기대와 다르면 3값 논리의 단계로 설명합니다.
3. 별도 새 테이블에 case-sensitive collation을 명시해 같은 문자열 fixture를 비교합니다. 기존 테이블의 collation을 즉석에서 바꾸지 않고 결과 동등성이 유지되는 변경인지 판단합니다.
4. `ONLY_FULL_GROUP_BY`를 끄는 대신 비집계 컬럼이 왜 모호한지 설명합니다. 금액은 DECIMAL·통화·반올림 시점을 계약에 쓰며 FLOAT의 오차를 금액 정합성으로 받아들이지 않습니다.
5. 한 query의 권한/해석/최적화/실행/engine 접근 책임을 표시하고 [소스 지도](../source-reading.md)에서 server→handler→InnoDB 연결 지점을 찾습니다.

**통과:** 정답 SQL·반례 SQL·환경 지문·ID/값 oracle, 5단계 이상 실행 경로를 제출합니다. 쿼리 결과의 순서를 우연한 PK 저장 순서로 보장한다고 설명하면 미통과입니다.

<a id="my02"></a>
## MY02 · clustered index·secondary index·페이지 비용

### 원리

InnoDB의 clustered index leaf는 행 데이터와 연결됩니다. 일반적인 secondary index entry는 secondary key와 clustered key를 포함하므로 PK 폭이 다른 인덱스 비용에도 영향을 줍니다. PK가 없다면 적합한 UNIQUE NOT NULL 인덱스 또는 내부 키 선택 규칙을 확인해야 합니다. [Clustered/secondary indexes](https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html).

CPU `index-lookup`은 lookup 경로를 생각하는 모형이지 InnoDB 페이지 포맷·latch·read-ahead·optimizer가 아닙니다. B-tree 높이만으로 지연 시간을 예측하지 않습니다. leaf 범위, clustered lookup, cache hit, row 폭, 압축/overflow, 동시 write를 함께 고려합니다. [인덱스 물리 구조](https://dev.mysql.com/doc/refman/8.4/en/innodb-physical-structure.html)를 읽습니다.

```sql
CREATE TABLE my02_index_run01 (
  id BIGINT PRIMARY KEY,
  tenant_id INT NOT NULL,
  created_at DATETIME NOT NULL,
  payload VARCHAR(200) NOT NULL,
  KEY ix_tenant_time (tenant_id, created_at)
) ENGINE=InnoDB;
INSERT INTO my02_index_run01 VALUES
  (1,1,'2026-01-01 00:00:00','a'), (2,1,'2026-01-02 00:00:00','b'),
  (3,1,'2026-01-02 00:00:00','c'), (4,2,'2026-01-01 00:00:00','d');

SHOW CREATE TABLE my02_index_run01;
SHOW INDEX FROM my02_index_run01;
EXPLAIN FORMAT=TREE
SELECT id, created_at FROM my02_index_run01
WHERE tenant_id=1 ORDER BY created_at,id;
EXPLAIN FORMAT=TREE
SELECT id, created_at, payload FROM my02_index_run01
WHERE tenant_id=1 ORDER BY created_at,id;
```

### 실험·반례

1. ID 1/2/3이 반환되는 같은 계약에서 `payload` 포함 여부를 비교합니다. covering 가능성과 실제 계획 선택은 다르며 4행에서 table scan 선택은 자연스러울 수 있습니다.
2. 합성 데이터 규모·seed를 고정한 별도 테이블 두 개에서 좁은 증가형 PK와 넓은 키를 비교합니다. 인덱스 공간·쓰기 지연·페이지 변화·읽기 계약을 기록하고 “UUID는 항상 느리다” 같은 보편 명제로 결론 내리지 않습니다.
3. `(tenant_id, created_at)`의 선두 조건, 범위 조건 뒤 컬럼, `ORDER BY`와 tie-breaker를 바꿉니다. 논리적인 index 활용 가능성과 optimizer가 선택한 경로를 별도 표로 냅니다.
4. secondary index만으로 컬럼을 얻을 수 있어도 MVCC 가시성 확인 등으로 clustered record 접근이 필요할 수 있는 경계를 조사합니다. `Using index`를 모든 실행에서 물리 I/O 0이라는 의미로 쓰지 않습니다.
5. 소스에서 record/page/search의 책임을 찾아 primary lookup과 secondary→clustered lookup 경로를 비교합니다. 소스를 읽은 것과 buffer page를 실제 dump한 것은 별도 증거입니다.

**통과:** 한 secondary lookup의 key→PK→행 경로, covering/비covering 대조군, 폭/선택도/쓰기 비용 matrix를 제출합니다. 인덱스를 추가하면 의미·잠금·쓰기 비용 검토 없이 항상 빨라진다고 주장하면 미통과입니다.
