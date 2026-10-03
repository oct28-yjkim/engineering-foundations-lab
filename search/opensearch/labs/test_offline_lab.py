"""Deterministic contract tests: no OpenSearch/Lucene or ANN engine is tested."""
import contextlib
import io
import json
import math
import unittest

from offline_lab import (LABS, ScoredDoc, VisibilityState, bm25, bm25_lab, delete,
                         distributed_topk, distributed_topk_lab, document_frequency,
                         hybrid_filter_lab, main, positions, put, recall_at_k,
                         realtime_get, refresh, refresh_lab, rrf, search_snapshot,
                         tenant_candidates, terms_topk, tokenize, topk)


class TokenTests(unittest.TestCase):
    def test_ascii_token_rule(self):
        self.assertEqual(tokenize("Cat-cat_42, DOG!"), ("cat", "cat", "42", "dog"))

    def test_non_ascii_not_analyzed(self):
        self.assertEqual(tokenize("검색 café"), ("caf",))

    def test_no_stemming(self):
        self.assertEqual(tokenize("run running runs"), ("run", "running", "runs"))

    def test_no_stopword_removal(self):
        self.assertEqual(tokenize("the cat"), ("the", "cat"))

    def test_empty(self):
        self.assertEqual(tokenize(" ... "), ())

    def test_invalid_text(self):
        for value in (None, 3, True, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tokenize(value)

    def test_zero_based_positions(self):
        self.assertEqual(positions("cat dog cat"), {"cat": (0, 2), "dog": (1,)})

    def test_df_counts_documents_not_occurrences(self):
        self.assertEqual(document_frequency({"a": "cat cat dog", "b": "cat"}), {"cat": 2, "dog": 1})


class BM25Tests(unittest.TestCase):
    def setUp(self):
        self.corpus = {"a": "cat cat dog", "b": "cat", "c": "dog mouse"}

    def test_hand_computed_a_score(self):
        self.assertAlmostEqual(dict(bm25(self.corpus, "cat", 1, 1))["a"], math.log(1.6) * 8 / 7)

    def test_hand_computed_b_score(self):
        self.assertAlmostEqual(dict(bm25(self.corpus, "cat", 1, 1))["b"], math.log(1.6) * 4 / 3)

    def test_length_normalization_changes_order(self):
        self.assertEqual([doc for doc, _ in bm25(self.corpus, "cat", 1, 1)], ["b", "a"])
        self.assertEqual([doc for doc, _ in bm25(self.corpus, "cat", 1, 0)], ["a", "b"])

    def test_equal_tf_no_length_normalization_tie(self):
        self.assertEqual([doc for doc, _ in bm25({"z": "cat", "a": "cat dog dog"}, "cat", 1, 0)],
                         ["a", "z"])

    def test_frequency_saturates(self):
        corpus = {"one": "x", "two": "x x", "four": "x x x x"}
        scores = dict(bm25(corpus, "x", 1, 0))
        self.assertAlmostEqual(scores["two"] / scores["one"], 4 / 3)
        self.assertAlmostEqual(scores["four"] / scores["one"], 8 / 5)

    def test_rare_term_has_higher_idf(self):
        scores = dict(bm25({"a": "rare common", "b": "common filler"}, "rare common", 1, 0))
        self.assertGreater(scores["a"], scores["b"] * 2)

    def test_distinct_query_terms(self):
        self.assertEqual(bm25(self.corpus, "cat cat"), bm25(self.corpus, "cat"))

    def test_query_term_order_irrelevant(self):
        self.assertEqual(bm25(self.corpus, "cat dog"), bm25(self.corpus, "dog cat"))

    def test_additive_query_contributions(self):
        cat, dog, both = (dict(bm25(self.corpus, query)) for query in ("cat", "dog", "cat dog"))
        self.assertAlmostEqual(both["a"], cat["a"] + dog["a"])

    def test_unknown_query(self):
        self.assertEqual(bm25(self.corpus, "bird"), [])

    def test_empty_query(self):
        self.assertEqual(bm25(self.corpus, ""), [])

    def test_empty_corpus(self):
        self.assertEqual(bm25({}, "cat"), [])

    def test_all_empty_documents(self):
        self.assertEqual(bm25({"a": "", "b": "..."}, "cat"), [])

    def test_empty_document_counts_in_model_n(self):
        # Our N=2, df=1, avgdl=1/2; not Lucene's sparse field docCount.
        self.assertAlmostEqual(dict(bm25({"a": "cat", "b": ""}, "cat", 1, 1))["a"],
                               math.log(2) * 2 / 3)

    def test_tie_break_is_id_ascending(self):
        self.assertEqual([doc for doc, _ in bm25({"z": "cat", "a": "cat"}, "cat")], ["a", "z"])

    def test_input_not_mutated(self):
        before = self.corpus.copy()
        bm25(self.corpus, "cat")
        self.assertEqual(self.corpus, before)

    def test_invalid_corpus(self):
        for corpus in ([], None, {"": "cat"}, {1: "cat"}, {"a": None}):
            with self.subTest(corpus=corpus), self.assertRaises(ValueError):
                bm25(corpus, "cat")

    def test_invalid_k1(self):
        for k1 in (0, -1, True, "1", math.nan, math.inf, -math.inf, 10**400):
            with self.subTest(k1=k1), self.assertRaises(ValueError):
                bm25(self.corpus, "cat", k1=k1)

    def test_invalid_b(self):
        for b in (-0.1, 1.1, True, "1", math.nan, math.inf):
            with self.subTest(b=b), self.assertRaises(ValueError):
                bm25(self.corpus, "cat", b=b)

    def test_tiny_positive_k1_approaches_idf(self):
        scores = dict(bm25(self.corpus, "cat", k1=1e-320))
        self.assertAlmostEqual(scores["a"], math.log(1.6))
        self.assertAlmostEqual(scores["b"], math.log(1.6))

    def test_huge_finite_k1_does_not_spuriously_overflow(self):
        self.assertTrue(all(math.isfinite(score) for _, score in bm25(self.corpus, "cat", k1=1e308)))

    def test_lab_oracles(self):
        self.assertEqual(bm25_lab()["df"], {"cat": 2, "dog": 2, "mouse": 1})


class VisibilityTests(unittest.TestCase):
    def test_initial_missing(self):
        self.assertIsNone(realtime_get(VisibilityState(), "a"))
        self.assertEqual(search_snapshot(VisibilityState(), "cat"), [])

    def test_put_visible_to_get_not_search(self):
        state = put(VisibilityState(), "a", "cat")
        self.assertEqual(realtime_get(state, "a"), "cat")
        self.assertEqual(search_snapshot(state, "cat"), [])

    def test_refresh_exposes_write(self):
        self.assertEqual(search_snapshot(refresh(put(VisibilityState(), "a", "cat")), "cat"), ["a"])

    def test_update_preserves_old_reader(self):
        old = refresh(put(VisibilityState(), "a", "cat"))
        new = put(old, "a", "dog")
        self.assertEqual(realtime_get(new, "a"), "dog")
        self.assertEqual(search_snapshot(new, "cat"), ["a"])
        self.assertEqual(search_snapshot(new, "dog"), [])

    def test_refresh_replaces_old_reader(self):
        state = refresh(put(refresh(put(VisibilityState(), "a", "cat")), "a", "dog"))
        self.assertEqual(search_snapshot(state, "cat"), [])
        self.assertEqual(search_snapshot(state, "dog"), ["a"])

    def test_delete_preserves_reader_until_refresh(self):
        state = delete(refresh(put(VisibilityState(), "a", "cat")), "a")
        self.assertIsNone(realtime_get(state, "a"))
        self.assertEqual(search_snapshot(state, "cat"), ["a"])
        self.assertEqual(search_snapshot(refresh(state), "cat"), [])

    def test_delete_missing_is_modeled_write(self):
        self.assertEqual(delete(VisibilityState(), "missing"), VisibilityState(write_sequence=1))

    def test_empty_text_differs_from_missing(self):
        self.assertEqual(realtime_get(put(VisibilityState(), "a", ""), "a"), "")

    def test_refresh_idempotent(self):
        state = refresh(put(VisibilityState(), "a", "cat"))
        self.assertEqual(refresh(state), state)

    def test_old_state_immutable(self):
        original = put(VisibilityState(), "a", "cat")
        put(original, "a", "dog")
        refresh(original)
        delete(original, "a")
        self.assertEqual(original, VisibilityState((("a", "cat"),), (), 1, 0))

    def test_search_is_token_and_not_substring(self):
        state = refresh(put(put(VisibilityState(), "a", "cat dog"), "b", "catfish dog"))
        self.assertEqual(search_snapshot(state, "cat dog"), ["a"])
        self.assertEqual(search_snapshot(state, "CAT CAT"), ["a"])

    def test_empty_query_no_hits(self):
        self.assertEqual(search_snapshot(refresh(put(VisibilityState(), "a", "cat")), ""), [])

    def test_search_tie_sorted_ids(self):
        state = refresh(put(put(VisibilityState(), "z", "cat"), "a", "cat"))
        self.assertEqual(search_snapshot(state, "cat"), ["a", "z"])

    def test_sequence_advances_writes_only(self):
        state = put(put(VisibilityState(), "a", "cat"), "b", "dog")
        self.assertEqual((state.write_sequence, state.search_sequence), (2, 0))
        self.assertEqual((refresh(state).write_sequence, refresh(state).search_sequence), (2, 2))

    def test_invalid_write(self):
        for doc_id, text in (("", "cat"), (True, "cat"), ("a", None)):
            with self.subTest(doc_id=doc_id, text=text), self.assertRaises(ValueError):
                put(VisibilityState(), doc_id, text)

    def test_invalid_state_structure(self):
        invalid = [None, VisibilityState(realtime=[]), VisibilityState(realtime=(("a", "x"), ("a", "y"))),
                   VisibilityState(realtime=(("a", None),)), VisibilityState(search_sequence=1),
                   VisibilityState(write_sequence=True), VisibilityState(write_sequence=-1)]
        for state in invalid:
            with self.subTest(state=state), self.assertRaises(ValueError):
                refresh(state)

    def test_invalid_get_delete_identifier(self):
        for operation in (realtime_get, delete):
            with self.subTest(operation=operation.__name__), self.assertRaises(ValueError):
                operation(VisibilityState(), "")

    def test_lab_final_trace(self):
        result = refresh_lab()
        self.assertEqual(result["trace"][-1]["searchable"], {})
        self.assertEqual(result["trace"][-1]["search_sequence"], 3)


class TopKTests(unittest.TestCase):
    def setUp(self):
        self.shards = [[ScoredDoc("a", 100), ScoredDoc("b", 99), ScoredDoc("c", 98)],
                       [ScoredDoc("d", 97), ScoredDoc("e", 96)]]

    def test_exact_global_reference(self):
        self.assertEqual([doc.doc_id for doc in topk(self.shards[0] + self.shards[1], 3)], ["a", "b", "c"])

    def test_local_k_sufficient(self):
        self.assertEqual(distributed_topk(self.shards, 3, 3), self.shards[0])

    def test_local_budget_smaller_can_lose(self):
        self.assertEqual([doc.doc_id for doc in distributed_topk(self.shards, 3, 1)], ["a", "d"])

    def test_ties_use_global_comparator(self):
        shards = [[ScoredDoc("z", 1), ScoredDoc("a", 1)], [ScoredDoc("c", 1), ScoredDoc("b", 1)]]
        self.assertEqual([doc.doc_id for doc in distributed_topk(shards, 3, 3)], ["a", "b", "c"])

    def test_exact_property_across_partitions(self):
        docs = [ScoredDoc(f"id-{i:02d}", (i * 7) % 13) for i in range(31)]
        for n_shards in (1, 2, 3, 7):
            shards = [docs[slot::n_shards] for slot in range(n_shards)]
            for k in (1, 2, 9, 31, 40):
                with self.subTest(n_shards=n_shards, k=k):
                    self.assertEqual(distributed_topk(shards, k, k), topk(docs, k))

    def test_empty_shards(self):
        self.assertEqual(distributed_topk([[], []], 3, 3), [])

    def test_negative_scores_comparator(self):
        self.assertEqual(topk([ScoredDoc("a", -3), ScoredDoc("b", -1)], 1), [ScoredDoc("b", -1)])

    def test_input_not_mutated(self):
        before = [list(shard) for shard in self.shards]
        distributed_topk(self.shards, 2, 2)
        self.assertEqual(self.shards, before)

    def test_invalid_k(self):
        for k in (0, -1, True, 1.5):
            with self.subTest(k=k), self.assertRaises(ValueError):
                distributed_topk(self.shards, k, 2)

    def test_invalid_candidate_budget(self):
        for budget in (0, -1, True, None, 1.5):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                distributed_topk(self.shards, 2, budget)

    def test_duplicate_id_within_shard(self):
        with self.assertRaises(ValueError):
            topk([ScoredDoc("a", 1), ScoredDoc("a", 2)], 2)

    def test_duplicate_id_across_shards(self):
        with self.assertRaises(ValueError):
            distributed_topk([[ScoredDoc("a", 1)], [ScoredDoc("a", 2)]], 1, 1)

    def test_invalid_scores(self):
        for score in (math.nan, math.inf, -math.inf, True, "1", 10**400):
            with self.subTest(score=score), self.assertRaises(ValueError):
                topk([ScoredDoc("a", score)], 1)

    def test_invalid_document_or_container(self):
        for docs in (None, [None], [ScoredDoc("", 1)], {"a": 1}):
            with self.subTest(docs=docs), self.assertRaises(ValueError):
                topk(docs, 1)

    def test_terms_bucket_counterexample(self):
        shards = [{"shared": 9, "a": 10}, {"shared": 9, "b": 10}]
        self.assertEqual(terms_topk(shards, 1), [("shared", 18)])
        self.assertEqual(terms_topk(shards, 1, 1), [("a", 10)])
        self.assertEqual(terms_topk(shards, 1, 2), [("shared", 18)])

    def test_terms_winner_count_can_be_undercounted(self):
        shards = [{"x": 10, "y": 9}, {"x": 1, "z": 2}]
        self.assertEqual(terms_topk(shards, 1, 1), [("x", 10)])
        self.assertEqual(terms_topk(shards, 1), [("x", 11)])

    def test_terms_ties_empty_and_no_mutation(self):
        shards = [{"b": 2, "a": 2}, {}]
        self.assertEqual(terms_topk(shards, 2), [("a", 2), ("b", 2)])
        self.assertEqual(terms_topk([], 2), [])
        self.assertEqual(shards, [{"b": 2, "a": 2}, {}])

    def test_invalid_terms(self):
        for shards in ([{"x": 0}], [{"x": -1}], [{"x": True}], [{"x": 1.5}], [{"": 1}], [None]):
            with self.subTest(shards=shards), self.assertRaises(ValueError):
                terms_topk(shards, 1)

    def test_invalid_terms_budget(self):
        with self.assertRaises(ValueError):
            terms_topk([{"a": 1}], 1, 0)

    def test_lab_distinction(self):
        self.assertEqual(distributed_topk_lab()["terms_global_top1"], [("shared", 18)])


class FusionTests(unittest.TestCase):
    def setUp(self):
        self.tenants = {"a1": "A", "a2": "A", "b1": "B", "b2": "B"}
        self.ranking = ["b1", "b2", "a1", "a2"]

    def test_one_based_rrf_and_missing_contribution(self):
        result = rrf([["a", "b"], ["b", "c"]])
        self.assertEqual([doc for doc, _ in result], ["b", "a", "c"])
        self.assertAlmostEqual(dict(result)["b"], 123 / 3782)
        self.assertAlmostEqual(dict(result)["a"], 1 / 61)
        self.assertAlmostEqual(dict(result)["c"], 1 / 62)

    def test_rrf_zero_constant_valid(self):
        self.assertEqual(rrf([["a", "b"]], 0), [("a", 1), ("b", 0.5)])

    def test_rrf_tie_break(self):
        result = rrf([["z", "a"], ["a", "z"]])
        self.assertEqual([doc for doc, _ in result], ["a", "z"])
        self.assertEqual(result[0][1], result[1][1])

    def test_rrf_ranker_order_irrelevant(self):
        self.assertEqual(rrf([["a", "b"], ["b", "c"]]), rrf([["b", "c"], ["a", "b"]]))

    def test_rrf_empty_lists(self):
        self.assertEqual(rrf([[], []]), [])
        self.assertEqual(rrf([]), [])

    def test_rrf_duplicate_within_list_rejected(self):
        with self.assertRaises(ValueError):
            rrf([["a", "a"]])

    def test_rrf_same_doc_across_lists_accumulates(self):
        self.assertEqual(rrf([["a"], ["a"]], 0), [("a", 2)])

    def test_rrf_invalid_constant(self):
        for value in (-1, True, math.nan, math.inf, "60", 10**400):
            with self.subTest(value=value), self.assertRaises(ValueError):
                rrf([["a"]], value)

    def test_rrf_invalid_ranking(self):
        for rankings in (None, [None], ["abc"], [[None]], [[""]]):
            with self.subTest(rankings=rankings), self.assertRaises(ValueError):
                rrf(rankings)

    def test_prefilter_recovers_eligible_candidates(self):
        self.assertEqual(tenant_candidates(self.ranking, self.tenants, "A", 2, True), ["a1", "a2"])

    def test_global_truncate_then_filter_can_be_empty(self):
        self.assertEqual(tenant_candidates(self.ranking, self.tenants, "A", 2, False), [])

    def test_full_budget_filters_agree(self):
        self.assertEqual(tenant_candidates(self.ranking, self.tenants, "A", 4, False),
                         tenant_candidates(self.ranking, self.tenants, "A", 4, True))

    def test_filter_absent_tenant_empty(self):
        self.assertEqual(tenant_candidates(self.ranking, self.tenants, "C", 2, True), [])

    def test_filter_preserves_rank_order(self):
        self.assertEqual(tenant_candidates(["a2", "b1", "a1"], self.tenants, "A", 2, True), ["a2", "a1"])

    def test_filter_input_not_mutated(self):
        tenant_candidates(self.ranking, self.tenants, "A", 2, True)
        self.assertEqual(self.ranking, ["b1", "b2", "a1", "a2"])
        self.assertEqual(self.tenants, {"a1": "A", "a2": "A", "b1": "B", "b2": "B"})

    def test_filter_unknown_doc_rejected(self):
        with self.assertRaises(ValueError):
            tenant_candidates(["unknown"], self.tenants, "A", 1, True)

    def test_filter_invalid_parameters(self):
        for tenant, budget, prefilter in (("", 2, True), ("A", 0, True), ("A", True, True), ("A", 2, 1)):
            with self.subTest(tenant=tenant, budget=budget, prefilter=prefilter), self.assertRaises(ValueError):
                tenant_candidates(self.ranking, self.tenants, tenant, budget, prefilter)

    def test_filter_invalid_tenants(self):
        for tenants in (None, {"a1": ""}, {"a1": True}):
            with self.subTest(tenants=tenants), self.assertRaises(ValueError):
                tenant_candidates(["a1"], tenants, "A", 1, True)

    def test_recall_hand_oracle(self):
        self.assertEqual(recall_at_k(["a", "b", "c"], {"a", "c"}, 2), 0.5)
        self.assertEqual(recall_at_k(["a", "b", "c"], {"a", "c"}, 3), 1)

    def test_recall_empty_results(self):
        self.assertEqual(recall_at_k([], {"a"}, 2), 0)

    def test_recall_empty_relevance_is_not_zero(self):
        with self.assertRaises(ValueError):
            recall_at_k(["a"], set(), 1)

    def test_recall_invalid_relevance_or_ranking(self):
        for ranking, relevant in ((["a", "a"], {"a"}), (["a"], ["a"]), (["a"], {None})):
            with self.subTest(ranking=ranking, relevant=relevant), self.assertRaises(ValueError):
                recall_at_k(ranking, relevant, 1)

    def test_recall_invalid_k(self):
        with self.assertRaises(ValueError):
            recall_at_k(["a"], {"a"}, True)

    def test_lab_recall_counterexample(self):
        result = hybrid_filter_lab()
        self.assertEqual(result["prefilter_recall_at_2"], 1)
        self.assertEqual(result["truncate_then_filter_recall_at_2"], 0)


class CLITests(unittest.TestCase):
    def test_all_labs_json(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(["--lab", "all"]), 0)
        result = json.loads(stream.getvalue())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(list(result["labs"]), list(LABS))

    def test_each_lab_selection(self):
        for name in LABS:
            stream = io.StringIO()
            with self.subTest(name=name), contextlib.redirect_stdout(stream):
                self.assertEqual(main(["--lab", name]), 0)
            self.assertEqual(list(json.loads(stream.getvalue())["labs"]), [name])

    def test_default_all(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            main([])
        self.assertEqual(len(json.loads(stream.getvalue())["labs"]), 4)

    def test_invalid_lab(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--lab", "not-a-lab"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
