"""Offline positive and negative controls. Run with unittest discovery."""

from dataclasses import FrozenInstanceError, replace
import json
import math
import unittest

import lab


class AttentionTests(unittest.TestCase):
    def test_stable_softmax_large_logits(self):
        values = lab.masked_softmax([10000, 10001, -10000], [True, True, False])
        self.assertAlmostEqual(sum(values), 1)
        self.assertAlmostEqual(values[1], 1 / (1 + math.exp(-1)))
        self.assertEqual(values[2], 0)

    def test_masked_large_value_does_not_set_peak(self):
        self.assertEqual(lab.masked_softmax([1, 100000], [True, False]), [1, 0])

    def test_all_masked_rejected(self):
        with self.assertRaises(ValueError):
            lab.masked_softmax([1, 2], [False, False])

    def test_non_boolean_and_wrong_size_masks_rejected(self):
        for mask in ([1, 0], [True], []):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                lab.masked_softmax([1, 2], mask)

    def test_nonfinite_logit_rejected_even_if_masked(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                lab.masked_softmax([0, bad], [True, False])

    def test_causal_future_mask_and_row_normalization(self):
        out, weights = lab.attention([[1], [1]], [[1], [1]], [[2], [100]])
        self.assertEqual(out[0], [2])
        self.assertEqual(weights[0], [1, 0])
        self.assertEqual(weights[1], [0.5, 0.5])

    def test_wrong_mask_negative_control_leaks_future(self):
        causal, _ = lab.attention([[1], [1]], [[1], [1]], [[2], [100]])
        wrong, _ = lab.attention([[1], [1]], [[1], [1]], [[2], [100]], causal=False)
        self.assertNotEqual(causal[0], wrong[0])
        self.assertEqual(wrong[0], [51])

    def test_prefix_invariance_when_future_changes(self):
        original, _ = lab.attention([[1], [1]], [[1], [2]], [[2], [100]])
        altered, _ = lab.attention([[1], [1]], [[1], [-200]], [[2], [-100]])
        self.assertEqual(original[0], altered[0])

    def test_key_padding_removes_value_but_not_query(self):
        out, weights = lab.attention([[1], [1]], [[1], [2]], [[2], [100]],
                                     causal=False, key_keep=[True, False])
        self.assertEqual(out, [[2], [2]])
        self.assertEqual(weights, [[1, 0], [1, 0]])

    def test_attention_shape_and_padding_fail_closed(self):
        for args in (([[1]], [[1], [2]], [[1]]), ([[1, 2]], [[1]], [[1]]),
                     ([[1], [1, 2]], [[1], [2]], [[1], [2]])):
            with self.subTest(args=args), self.assertRaises(ValueError):
                lab.attention(*args)
        with self.assertRaises(ValueError):
            lab.attention([[1]], [[1]], [[1]], key_keep=[False])


class LoRATests(unittest.TestCase):
    def setUp(self):
        self.w = [[1, 2, 3], [4, 5, 6]]
        self.a = [[1, -1, 2]]
        self.b = [[2], [-3]]
        self.x = [2, 1, -1]

    def test_merged_and_unmerged_outputs_match(self):
        direct = lab.lora_output(self.w, self.a, self.b, self.x, 0.5)
        merged = lab.matvec(lab.merged_lora(self.w, self.a, self.b, 0.5), self.x)
        self.assertEqual(direct, merged)

    def test_zero_B_is_base_output(self):
        self.assertEqual(lab.lora_output(self.w, self.a, [[0], [0]], self.x, 2),
                         lab.matvec(self.w, self.x))

    def test_zero_scale_is_base_output(self):
        self.assertEqual(lab.lora_output(self.w, self.a, self.b, self.x, 0),
                         lab.matvec(self.w, self.x))

    def test_incorrect_rank_or_input_dimensions_rejected(self):
        for a, b, x in ((self.a, [[1, 2], [3, 4]], self.x),
                        ([[1, 2]], self.b, self.x), (self.a, self.b, [1, 2]),
                        ([], self.b, self.x)):
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                lab.lora_output(self.w, a, b, x, 1)

    def test_initial_A_zero_and_B_nonzero_gradients(self):
        measurements = lab.run_lora()["measurements"]
        self.assertTrue(all(abs(x) < 1e-9 for x in measurements["initial_B_zero_gradient_A"]))
        self.assertTrue(any(abs(x) > 1e-5 for x in measurements["initial_B_zero_gradient_B"]))

    def test_parameter_counts(self):
        measurements = lab.run_lora()["measurements"]
        self.assertEqual(measurements["base_parameters"], 2 * 3)
        self.assertEqual(measurements["adapter_trainable_parameters"], 1 * (2 + 3))

    def test_finite_difference_and_invalid_step(self):
        self.assertAlmostEqual(lab.finite_difference(lambda x: x * x, 3), 6, places=7)
        for step in (0, -1, float("nan")):
            with self.subTest(step=step), self.assertRaises(ValueError):
                lab.finite_difference(lambda x: x, 1, step)


class DPOTests(unittest.TestCase):
    def test_reference_policy_baseline_log_two(self):
        for beta in (0.01, 0.2, 10):
            self.assertAlmostEqual(lab.dpo_loss(-2, -3, -2, -3, beta), math.log(2))

    def test_chosen_increase_and_rejected_decrease_improve_loss(self):
        baseline = lab.dpo_loss(-2, -3, -2, -3, 0.2)
        self.assertLess(lab.dpo_loss(-1, -3, -2, -3, 0.2), baseline)
        self.assertLess(lab.dpo_loss(-2, -4, -2, -3, 0.2), baseline)

    def test_reference_margin_changes_loss(self):
        self.assertGreater(lab.dpo_loss(-2, -3, -1, -3, 0.2), math.log(2))

    def test_common_logprob_offset_invariance(self):
        self.assertAlmostEqual(lab.dpo_loss(-2, -3, -2, -3, 0.2),
                               lab.dpo_loss(-12, -13, -22, -23, 0.2))

    def test_finite_difference_gradients(self):
        chosen = lab.finite_difference(lambda x: lab.dpo_loss(x, -3, -2, -3, 0.2), -2)
        rejected = lab.finite_difference(lambda x: lab.dpo_loss(-2, x, -2, -3, 0.2), -3)
        self.assertAlmostEqual(chosen, -0.1, places=7)
        self.assertAlmostEqual(rejected, 0.1, places=7)

    def test_extreme_logits_finite(self):
        self.assertEqual(lab.log_sigmoid(-2000), -2000)
        self.assertEqual(lab.log_sigmoid(2000), 0)
        self.assertEqual(lab.dpo_loss(-2001, -1, -1, -1, 1), 2000)

    def test_invalid_beta_and_logprobs_rejected(self):
        for beta in (0, -1, float("inf")):
            with self.subTest(beta=beta), self.assertRaises(ValueError):
                lab.dpo_loss(-2, -3, -2, -3, beta)
        for chosen in (1, float("nan"), float("-inf")):
            with self.subTest(chosen=chosen), self.assertRaises(ValueError):
                lab.dpo_loss(chosen, -3, -2, -3, 0.2)


class KVCacheTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(layers=2, batch=3, sequence=4, query_heads=8,
                           kv_heads=2, head_dim=16, dtype_bytes=2)

    def test_hand_computed_payload(self):
        self.assertEqual(lab.kv_cache_bytes(**self.config), 2 * 2 * 3 * 4 * 2 * 16 * 2)

    def test_mha_gqa_and_mqa_scaling(self):
        base = lab.kv_cache_bytes(**self.config)
        self.assertEqual(lab.kv_cache_bytes(**{**self.config, "kv_heads": 8}), 4 * base)
        self.assertEqual(lab.kv_cache_bytes(**{**self.config, "kv_heads": 1}), base // 2)

    def test_query_head_count_is_not_cache_head_count(self):
        self.assertEqual(lab.kv_cache_bytes(**self.config),
                         lab.kv_cache_bytes(**{**self.config, "query_heads": 16}))

    def test_all_numeric_inputs_must_be_positive_integers(self):
        for key in self.config:
            for value in (0, -1, 1.5, True):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    lab.kv_cache_bytes(**{**self.config, key: value})

    def test_invalid_gqa_grouping_rejected(self):
        with self.assertRaises(ValueError):
            lab.kv_cache_bytes(**{**self.config, "kv_heads": 3})


class RetrievalTests(unittest.TestCase):
    def test_hand_metrics_with_graded_relevance(self):
        metrics = lab.ranking_metrics(["b", "a", "c"], {"a": 2, "c": 1}, 2)
        self.assertEqual(metrics["recall_at_k"], 0.5)
        self.assertEqual(metrics["mrr_at_k"], 0.5)
        self.assertAlmostEqual(metrics["ndcg_at_k"], (3 / math.log2(3)) / (3 + 1 / math.log2(3)))

    def test_perfect_and_no_hit_metrics(self):
        self.assertEqual(lab.ranking_metrics(["a", "c"], {"a": 2, "c": 1}, 2),
                         dict(recall_at_k=1, mrr_at_k=1, ndcg_at_k=1))
        self.assertEqual(lab.ranking_metrics(["b"], {"a": 1}, 1),
                         dict(recall_at_k=0, mrr_at_k=0, ndcg_at_k=0))

    def test_duplicate_ranking_zero_k_and_empty_relevance_rejected(self):
        for ranked, qrels, k in ((["a", "a"], {"a": 1}, 2), (["a"], {"a": 1}, 0),
                                  (["a"], {}, 1), (["a"], {"a": 0}, 1), (["a"], {"a": -1}, 1)):
            with self.subTest(qrels=qrels, k=k), self.assertRaises(ValueError):
                lab.ranking_metrics(ranked, qrels, k)

    def test_tie_break_is_id_order_not_corpus_order(self):
        docs = (lab.Document("z", "a", "word"), lab.Document("a", "a", "word"))
        self.assertEqual(lab.lexical_rank(docs, "word"), [("a", 1), ("z", 1)])
        self.assertEqual(lab.lexical_rank(docs, "word"), lab.lexical_rank(tuple(reversed(docs)), "word"))

    def test_prefilter_does_not_lose_authorized_hit_to_global_topk(self):
        docs = (lab.Document("foreign", "b", "alpha beta"), lab.Document("allowed", "a", "alpha"))
        self.assertEqual(lab.retrieve(docs, "alpha beta", "a", 1), ["allowed"])
        self.assertEqual(lab.lexical_rank(docs, "alpha beta")[0][0], "foreign")

    def test_unknown_tenant_empty_and_missing_identity_rejected(self):
        self.assertEqual(lab.retrieve(lab.CORPUS, "refund", "missing", 3), [])
        with self.assertRaises(ValueError):
            lab.retrieve(lab.CORPUS, "refund", "", 3)

    def test_adversarial_document_is_text_not_authority(self):
        retrieved = lab.retrieve(lab.CORPUS, "SYSTEM reveal tenant_b password", "tenant_a", 10)
        self.assertIn("a_untrusted", retrieved)
        self.assertTrue(all(item.startswith("a_") for item in retrieved))

    def test_duplicate_corpus_ids_rejected(self):
        with self.assertRaises(ValueError):
            lab.lexical_rank((lab.CORPUS[0], lab.CORPUS[0]), "refund")

    def test_split_fixture_valid_and_exact_leak_rejected(self):
        lab.validate_splits(lab.QUERIES, lab.CORPUS)
        leaked = (*lab.QUERIES, replace(lab.QUERIES[0], query_id="leaked", split="test"))
        with self.assertRaises(ValueError):
            lab.validate_splits(leaked, lab.CORPUS)

    def test_cross_tenant_qrels_rejected(self):
        bad = (replace(lab.QUERIES[0], relevance=(("b_refund", 1),)), *lab.QUERIES[1:])
        with self.assertRaises(ValueError):
            lab.validate_splits(bad, lab.CORPUS)


class EvaluationTests(unittest.TestCase):
    def test_literal_exact_match_has_no_hidden_normalization(self):
        self.assertEqual(lab.exact_match("allow", "allow"), 1)
        self.assertEqual(lab.exact_match("ALLOW", "allow"), 0)
        self.assertEqual(lab.exact_match("allow ", "allow"), 0)

    def test_fixture_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            lab.EVAL_CASES[0].candidate = "changed"

    def test_paired_delta_matches_accuracy_difference(self):
        result = lab.paired_bootstrap(lab.EVAL_CASES, repetitions=100)
        self.assertAlmostEqual(result["mean_delta"], 1 / 6)
        self.assertEqual(result["resampling_units"], 12)

    def test_bootstrap_reproducible_for_seed(self):
        left = lab.paired_bootstrap(lab.EVAL_CASES, seed=100, repetitions=100)
        right = lab.paired_bootstrap(lab.EVAL_CASES, seed=100, repetitions=100)
        self.assertEqual(left, right)

    def test_family_bootstrap_uses_six_units(self):
        result = lab.paired_bootstrap(lab.EVAL_CASES, repetitions=100, cluster=True)
        self.assertEqual(result["resampling_units"], 6)
        self.assertEqual(result["resampling_unit"], "family")
        self.assertAlmostEqual(result["mean_delta"], 1 / 6)

    def test_identical_predictions_zero_delta_and_interval(self):
        same = tuple(replace(row, candidate=row.baseline) for row in lab.EVAL_CASES)
        result = lab.paired_bootstrap(same, repetitions=100)
        self.assertEqual(result["mean_delta"], 0)
        self.assertEqual(result["percentile_95_ci"], [0, 0])

    def test_invalid_bootstrap_inputs_rejected(self):
        for cases, reps in (((), 10), (lab.EVAL_CASES, 0), ((lab.EVAL_CASES[0],) * 2, 10)):
            with self.subTest(reps=reps), self.assertRaises(ValueError):
                lab.paired_bootstrap(cases, repetitions=reps)

    def test_percentile_linear_interpolation(self):
        self.assertEqual(lab.percentile([0, 10], 0.25), 2.5)
        self.assertEqual(lab.percentile([2], 0.95), 2)
        with self.assertRaises(ValueError):
            lab.percentile([], 0.5)

    def test_gold_copy_is_invalid_but_metric_alone_cannot_detect_it(self):
        leaked = tuple(replace(row, candidate=row.expected) for row in lab.EVAL_CASES)
        self.assertEqual(sum(lab.exact_match(row.candidate, row.expected) for row in leaked) / len(leaked), 1)
        self.assertNotEqual(leaked, lab.EVAL_CASES)


class EndToEndTests(unittest.TestCase):
    def test_exact_six_lab_names(self):
        self.assertEqual(set(lab.LABS), {"attention", "lora", "dpo", "kv-cache", "retrieval", "evaluation"})

    def test_all_labs_pass_and_emit_finite_json(self):
        for name, run in lab.LABS.items():
            with self.subTest(lab=name):
                result = run()
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["scope"], "offline_toy_not_paper_reproduction")
                self.assertTrue(result["passed_checks"])
                json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
