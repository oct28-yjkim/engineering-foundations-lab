-- Databricks SQL / supported DBR: MANUAL, SYNTHETIC, NOT EXECUTED HERE.
-- Read README.md first. Run each numbered section separately; STOP on any error.
-- Named parameter :lab_table must be a NEW fully-qualified table in your approved lab schema.
-- No account/schema/grant provisioning, no replacement, deletion, VACUUM, or retention changes.
-- Single-writer fixture: a separate guard + MERGE is not an atomic concurrency check.

-- 1. Explicit destination guard. Identifiers are intentionally restricted for this fixture.
SELECT assert_true(
  coalesce(:lab_table RLIKE '^[A-Za-z_][A-Za-z0-9_]*[.][A-Za-z_][A-Za-z0-9_]*[.]efl_dbx_[A-Za-z0-9_]+$', false),
  'Set lab_table to a NEW catalog.schema.efl_dbx_run_name in your approved lab schema'
);

-- 2. Fresh-session synthetic input. Do NOT add OR REPLACE if a view already exists.
CREATE TEMPORARY VIEW efl_dbx_incoming AS
SELECT * FROM VALUES
  ('A', 1L, 100L, false, 'a1'),
  ('A', 2L, 125L, false, 'a2'),
  ('A', 2L, 125L, false, 'a2'),
  ('B', 1L, 200L, false, 'b1'),
  ('B', 2L, CAST(NULL AS BIGINT), true, 'b2'),
  ('C', 1L, 50L, false, 'c1')
AS v(entity_id, entity_version, amount, is_deleted, event_id);

-- 3. Reject ambiguous business payloads BEFORE choosing the latest version.
SELECT assert_true(count(*) = 0, 'Conflicting payloads for the same entity/version: stop')
FROM (
  SELECT entity_id, entity_version
  FROM efl_dbx_incoming
  GROUP BY entity_id, entity_version
  HAVING count(DISTINCT named_struct('amount', amount, 'deleted', is_deleted)) > 1
);

CREATE TEMPORARY VIEW efl_dbx_latest AS
SELECT entity_id, entity_version, amount, is_deleted, event_id
FROM (
  SELECT *, row_number() OVER (
    PARTITION BY entity_id ORDER BY entity_version DESC, event_id DESC
  ) AS winner
  FROM efl_dbx_incoming
)
WHERE winner = 1;

-- 4. Must fail if this target already exists. Never turn this into CREATE OR REPLACE.
CREATE TABLE IDENTIFIER(:lab_table) (
  entity_id STRING NOT NULL,
  entity_version BIGINT NOT NULL,
  amount BIGINT,
  is_deleted BOOLEAN NOT NULL,
  last_event_id STRING NOT NULL
) USING DELTA;

-- 5. Replay block: rerun this guard + MERGE + final oracle, not the CREATE sections.
SELECT assert_true(count(*) = 0, 'Equal-version target/source conflict: stop')
FROM IDENTIFIER(:lab_table) t
JOIN efl_dbx_latest s
  ON t.entity_id = s.entity_id AND t.entity_version = s.entity_version
WHERE NOT ((t.amount <=> s.amount) AND t.is_deleted = s.is_deleted);

MERGE INTO IDENTIFIER(:lab_table) t
USING efl_dbx_latest s
ON t.entity_id = s.entity_id
WHEN MATCHED AND s.entity_version > t.entity_version THEN
  UPDATE SET t.entity_version = s.entity_version, t.amount = s.amount,
    t.is_deleted = s.is_deleted, t.last_event_id = s.event_id
WHEN NOT MATCHED THEN
  INSERT (entity_id, entity_version, amount, is_deleted, last_event_id)
  VALUES (s.entity_id, s.entity_version, s.amount, s.is_deleted, s.event_id);

-- 6. A late version must not resurrect B after the version-2 tombstone.
MERGE INTO IDENTIFIER(:lab_table) t
USING (SELECT * FROM VALUES ('B', 1L, 200L, false, 'b1')
  AS v(entity_id, entity_version, amount, is_deleted, event_id)) s
ON t.entity_id = s.entity_id
WHEN MATCHED AND s.entity_version > t.entity_version THEN
  UPDATE SET t.entity_version = s.entity_version, t.amount = s.amount,
    t.is_deleted = s.is_deleted, t.last_event_id = s.event_id
WHEN NOT MATCHED THEN
  INSERT (entity_id, entity_version, amount, is_deleted, last_event_id)
  VALUES (s.entity_id, s.entity_version, s.amount, s.is_deleted, s.event_id);

-- 7. Independent expected rows. EXCEPT ALL detects duplicates as well as missing/wrong values.
WITH expected AS (
  SELECT * FROM VALUES
    ('A', 2L, 125L, false, 'a2'),
    ('B', 2L, CAST(NULL AS BIGINT), true, 'b2'),
    ('C', 1L, 50L, false, 'c1')
  AS v(entity_id, entity_version, amount, is_deleted, last_event_id)
), missing AS (
  SELECT * FROM expected
  EXCEPT ALL
  SELECT entity_id, entity_version, amount, is_deleted, last_event_id FROM IDENTIFIER(:lab_table)
), extra AS (
  SELECT entity_id, entity_version, amount, is_deleted, last_event_id FROM IDENTIFIER(:lab_table)
  EXCEPT ALL
  SELECT * FROM expected
)
SELECT assert_true(count(*) = 0, 'Row oracle mismatch: stop')
FROM (SELECT * FROM missing UNION ALL SELECT * FROM extra);

SELECT assert_true(count(*) = 2 AND sum(amount) = 175L, 'Active aggregate mismatch: stop')
FROM IDENTIFIER(:lab_table)
WHERE NOT is_deleted;

SELECT entity_id, entity_version, amount, is_deleted, last_event_id
FROM IDENTIFIER(:lab_table)
ORDER BY entity_id;
