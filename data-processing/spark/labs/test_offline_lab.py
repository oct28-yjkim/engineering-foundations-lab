"""Offline model tests; no Spark, Delta Lake or cloud service is tested."""
import contextlib
import io
import json
import math
import unittest

from offline_lab import (VersionedRow, WatermarkModel, budget_lab, budget_plan, main,
                         merge_lab, merge_versions, partition, partition_skew_lab,
                         watermark_lab, weighted_mean)


class PartitionTests(unittest.TestCase):
    def test_hash_stable(self):
        self.assertEqual(partition("hot", 4), partition("hot", 4))

    def test_hash_range(self):
        self.assertTrue(all(0 <= partition(str(i), 7) < 7 for i in range(200)))

    def test_unicode(self):
        self.assertIn(partition("테넌트", 3), range(3))

    def test_invalid_partition_count(self):
        for count in [0, -1, True, 2.5]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                partition("key", count)

    def test_invalid_key(self):
        with self.assertRaises(ValueError):
            partition(None, 4)

    def test_weighted_counterexample(self):
        self.assertEqual(weighted_mean([(100, 1), (0, 9)]), 10)

    def test_negative_values_allowed(self):
        self.assertEqual(weighted_mean([(-6, 2), (6, 2)]), 0)

    def test_empty_partials(self):
        with self.assertRaises(ValueError):
            weighted_mean([])

    def test_invalid_partial(self):
        for value in [(math.nan, 1), (math.inf, 1), (True, 1), (1, 0), (1, True)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                weighted_mean([value])

    def test_partial_sum_overflow(self):
        with self.assertRaises(ValueError):
            weighted_mean([(1e308, 1), (1e308, 1)])

    def test_fixture_conservation(self):
        result = partition_skew_lab()
        self.assertEqual(sum(result["plain_partition_rows"]), result["rows"])
        self.assertEqual(sum(result["salted_partition_rows"]), result["rows"])
        self.assertTrue(result["two_stage_means_equal_reference"])


class MergeTests(unittest.TestCase):
    def test_highest_version(self):
        self.assertEqual(merge_versions({}, [VersionedRow("a", 2, "new"),
                         VersionedRow("a", 1, "old")])["a"].value, "new")

    def test_duplicate_and_replay(self):
        row = VersionedRow("a", 1, "x")
        state = merge_versions({}, [row, row])
        self.assertEqual(merge_versions(state, [row]), state)

    def test_tombstone_retained(self):
        tomb = VersionedRow("a", 3, None, True)
        self.assertEqual(merge_versions({"a": tomb}, [VersionedRow("a", 2, "old")]), {"a": tomb})

    def test_newer_business_version_may_recreate(self):
        tomb = VersionedRow("a", 3, None, True)
        self.assertEqual(merge_versions({"a": tomb}, [VersionedRow("a", 4, "new")])["a"].value, "new")

    def test_conflict_in_batch(self):
        with self.assertRaises(ValueError):
            merge_versions({}, [VersionedRow("a", 1, "x"), VersionedRow("a", 1, "y")])

    def test_conflict_with_current(self):
        state = {"a": VersionedRow("a", 2, "x")}
        with self.assertRaises(ValueError):
            merge_versions(state, [VersionedRow("a", 2, "y")])
        self.assertEqual(state["a"].value, "x")

    def test_older_conflict_still_rejected(self):
        with self.assertRaises(ValueError):
            merge_versions({"a": VersionedRow("a", 3, "z")},
                           [VersionedRow("a", 1, "x"), VersionedRow("a", 1, "y")])

    def test_bad_rows(self):
        for row in [VersionedRow("", 1, "x"), VersionedRow("a", 0, "x"),
                    VersionedRow("a", True, "x"), VersionedRow("a", 1, "x", True),
                    VersionedRow("a", 1, None), VersionedRow("a", 1, "x", 1)]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                merge_versions({}, [row])

    def test_state_key_mismatch(self):
        with self.assertRaises(ValueError):
            merge_versions({"b": VersionedRow("a", 1, "x")}, [])

    def test_input_not_mutated(self):
        state = {"a": VersionedRow("a", 1, "x")}
        merge_versions(state, [VersionedRow("a", 2, "y")])
        self.assertEqual(state["a"].version, 1)

    def test_fixture(self):
        self.assertEqual(merge_lab()["visible_keys"], ["a"])


class WatermarkTests(unittest.TestCase):
    def test_previous_batch_watermark(self):
        model = WatermarkModel()
        self.assertIsNone(model.batch([("a", 12)])["entry_watermark"])
        self.assertEqual(model.batch([])["entry_watermark"], 7)

    def test_exact_boundary_accepted(self):
        model = WatermarkModel()
        model.batch([("a", 12)])
        result = model.batch([("boundary", 7), ("late", 6)])
        self.assertEqual(result["accepted_ids"], ["boundary"])
        self.assertEqual(result["dropped_ids"], ["late"])

    def test_window_end_boundary(self):
        model = WatermarkModel()
        model.batch([("a", 0), ("b", 15)])
        self.assertEqual(model.batch([])["emitted"], [{"start": 0, "end": 10, "count": 1}])

    def test_duplicate_ids_not_deduplicated(self):
        model = WatermarkModel()
        self.assertEqual(model.batch([("a", 1), ("a", 1)])["pending"], {0: 2})

    def test_idle_keeps_pending(self):
        model = WatermarkModel()
        model.batch([("a", 25)])
        self.assertEqual(model.batch([])["pending"], {20: 1})
        self.assertEqual(model.batch([])["pending"], {20: 1})

    def test_out_of_order_does_not_rewind(self):
        model = WatermarkModel()
        model.batch([("a", 25)])
        model.batch([("old", 1)])
        self.assertEqual(model.max_time, 25)

    def test_invalid_time_atomic(self):
        for timestamp in [None, -1, True, 1.5]:
            model = WatermarkModel()
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                model.batch([("a", 1), ("bad", timestamp)])
            self.assertEqual(model.pending, {})

    def test_invalid_configuration(self):
        for window, delay in [(0, 5), (10, 0), (True, 2)]:
            with self.subTest(window=window), self.assertRaises(ValueError):
                WatermarkModel(window, delay)

    def test_empty_initial_batch(self):
        self.assertEqual(WatermarkModel().batch([])["emitted"], [])

    def test_fixture(self):
        self.assertTrue(watermark_lab()["idle_does_not_advance_event_time"])


class BudgetTests(unittest.TestCase):
    def test_exact_cap(self):
        self.assertTrue(budget_plan(2, 1, 1, 5)["within_cap"])

    def test_retry_doubles_units(self):
        self.assertEqual(budget_plan(2, 1, 2, 20)["modeled_resource_units"], 10)

    def test_zero_hours(self):
        self.assertEqual(budget_plan(2, 0, 1, 0)["modeled_resource_units"], 0)

    def test_invalid_integer_inputs(self):
        for workers, attempts in [(0, 1), (2, 0), (True, 1), (2, 1.5)]:
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                budget_plan(workers, 1, attempts, 10)

    def test_invalid_numeric_inputs(self):
        for hours in [-1, math.inf, math.nan, True]:
            with self.subTest(hours=hours), self.assertRaises(ValueError):
                budget_plan(2, hours, 1, 10)

    def test_overflow(self):
        with self.assertRaises(ValueError):
            budget_plan(2, 1e308, 2, 10)

    def test_fixture(self):
        self.assertFalse(budget_lab()["one_full_retry"]["within_cap"])


class CliTests(unittest.TestCase):
    def test_all_reports_scope(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(["--lab", "all"]), 0)
        result = json.loads(stream.getvalue())
        self.assertEqual(len(result["labs"]), 4)
        self.assertTrue(all("scope" in lab for lab in result["labs"].values()))


if __name__ == "__main__":
    unittest.main()
