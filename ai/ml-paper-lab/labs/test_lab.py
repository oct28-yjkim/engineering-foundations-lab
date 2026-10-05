"""Small-model tests with literal/analytic oracles, not published-result tests."""
import contextlib
import io
import json
import math
import unittest
from copy import deepcopy
from unittest.mock import patch

import lab


class GuardedTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch("socket.socket", side_effect=AssertionError("network forbidden")).start()
        patch("socket.create_connection", side_effect=AssertionError("network forbidden")).start()


class RidgeTests(GuardedTest):
    def test_literal_ols(self):
        self.assertEqual(lab.fit_ridge([-1, 0, 1], [-1, 1, 3], 0), (2, 1))

    def test_literal_ridge_intercept_unpenalized(self):
        self.assertEqual(lab.fit_ridge([-1, 0, 1], [-1, 1, 3], 2), (1, 1))

    def test_constant_feature_regularized_unique_solution(self):
        w, b = lab.fit_ridge([1, 1], [1, 2], 2)
        self.assertEqual((w, b), (0, 1.5))
        objective = sum((y - w - b) ** 2 for y in [1, 2]) + 2 * w * w
        self.assertEqual(objective, 0.5)

    def test_normal_equations_independent_residuals(self):
        xs, ys, alpha = [-2, -.5, 1, 4], [0, 1, 3, 5], 1.3
        w, b = lab.fit_ridge(xs, ys, alpha)
        residuals = [w * x + b - y for x, y in zip(xs, ys)]
        self.assertAlmostEqual(sum(residuals), 0)
        self.assertAlmostEqual(sum(r * x for r, x in zip(residuals, xs)) + alpha * w, 0)

    def test_scaler_literal_population_variance(self):
        scaler = lab.fit_scaler([0, 1, 2])
        self.assertEqual(scaler[0], 1)
        self.assertAlmostEqual(scaler[1], math.sqrt(2 / 3))
        self.assertAlmostEqual(sum(lab.transform([0, 1, 2], scaler)), 0)

    def test_leakage_and_no_universal_regularization_benefit(self):
        result = lab.ridge_lab()["observed"]
        self.assertEqual(result["ols_test_mse"], 0)
        self.assertAlmostEqual(result["ridge_test_mse"], 200 / 49)
        self.assertAlmostEqual(result["leaked_ridge_test_mse"], 800 / 81)
        self.assertEqual(result["leaked_ols_test_mse"], 0)
        self.assertEqual(result["train_scaler"][0], 0)
        self.assertEqual(result["leaked_scaler"][0], 1)

    def test_singular_negative_alpha_and_bad_scaler(self):
        for operation in (lambda: lab.fit_ridge([1, 1], [1, 2], 0),
                          lambda: lab.fit_ridge([1, 2], [1, 2], -1),
                          lambda: lab.fit_scaler([2, 2]),
                          lambda: lab.transform([1, 2], (0, 0))):
            with self.assertRaises(lab.LabError):
                operation()


class LogisticTests(GuardedTest):
    def test_stable_extreme_logits(self):
        self.assertEqual(lab.sigmoid(1000), 1)
        self.assertEqual(lab.sigmoid(-1000), 0)
        self.assertEqual(lab.logistic_loss_gradient([1], [1], 1000, 0)[0], 0)
        self.assertEqual(lab.logistic_loss_gradient([1], [1], -1000, 0)[0], 1000)

    def test_literal_initial_gradient(self):
        loss, gradient = lab.logistic_loss_gradient([-1, 1], [0, 1], 0, 0)
        self.assertAlmostEqual(loss, math.log(2))
        self.assertEqual(gradient, (-.5, 0))

    def test_single_sgd_step(self):
        self.assertEqual(lab.fit_logistic([1], [1], seed=0, epochs=1, rate=.1, l2=0), (.05, .05))

    def test_central_difference_with_and_without_regularization(self):
        for w, b, penalty in ((.7, -.2, .1), (-1.2, .3, 0), (0, 0, .5)):
            self.assertLess(lab.gradient_error([-3, .2, 1.4], [0, 0, 1], w, b, penalty), 1e-7)

    def test_actual_fit_reduces_loss(self):
        xs, ys = [-3, -2, -1, 1, 2, 3], [0, 0, 0, 1, 1, 1]
        w, b = lab.fit_logistic(xs, ys)
        self.assertLess(lab.logistic_loss_gradient(xs, ys, w, b, .02)[0], math.log(2))
        self.assertGreater(w, 0)

    def test_imbalance_accuracy_does_not_measure_positive_recall(self):
        ys = [0] * 19 + [1]
        low, prior = lab.probability_metrics([.01] * 20, ys), lab.probability_metrics([.05] * 20, ys)
        self.assertEqual(low["accuracy"], .95)
        self.assertEqual(low["positive_recall"], 0)
        self.assertEqual(prior["accuracy"], low["accuracy"])
        self.assertAlmostEqual(low["brier"], .0491)
        self.assertAlmostEqual(prior["brier"], .0475)

    def test_no_positive_labels_recall_is_undefined(self):
        self.assertIsNone(lab.probability_metrics([.1, .2], [0, 0])["positive_recall"])

    def test_invalid_label_probability_and_nonfinite(self):
        for operation in (lambda: lab.fit_logistic([0, 1], [0, 2]),
                          lambda: lab.probability_metrics([1.1], [1]),
                          lambda: lab.logistic_loss_gradient([0, 1], [False, True], 0, 0),
                          lambda: lab.sigmoid(float("inf")),
                          lambda: lab.logistic_loss_gradient([0], [1], 0, 0, -1)):
            with self.assertRaises(lab.LabError):
                operation()

    def test_seeded_fit_reproducible(self):
        xs, ys = [-2, -1, 1, 2], [0, 0, 1, 1]
        self.assertEqual(lab.fit_logistic(xs, ys, seed=8), lab.fit_logistic(xs, ys, seed=8))
        self.assertNotEqual(lab.fit_logistic(xs, ys, seed=8), lab.fit_logistic(xs, ys, seed=9))


class EnsembleTests(GuardedTest):
    def test_perfect_literal_split(self):
        model = lab.fit_stump([0, 1, 2, 3], [0, 0, 1, 1])
        self.assertEqual(model, {"threshold": 1.5, "left_probability": 0,
                                 "right_probability": 1, "weighted_gini": 0})
        self.assertEqual(lab.predict_stump(model, [-1, 1.5, 2, 9]), [0, 0, 1, 1])

    def test_gini_weight_and_tie_break(self):
        model = lab.fit_stump([0, 1, 2], [0, 1, 0])
        self.assertEqual(model["threshold"], .5)
        self.assertAlmostEqual(model["weighted_gini"], 1 / 3)

    def test_constant_feature_leaf(self):
        model = lab.fit_stump([1, 1, 1], [0, 0, 1])
        self.assertIsNone(model["threshold"])
        self.assertEqual(lab.predict_stump(model, [1]), [1 / 3])

    def test_probability_average_is_not_hard_vote(self):
        models = [{"threshold": None, "left_probability": .4},
                  {"threshold": None, "left_probability": .8}]
        self.assertAlmostEqual(lab.predict_bagging(models, [0])[0], .6)

    def test_bootstrap_size_replacement_and_seed(self):
        xs, ys = [0, 1, 2, 3], [0, 0, 1, 1]
        fitted, samples = lab.fit_bagging(xs, ys, seed=17, trees=7)
        self.assertEqual(len(fitted), 7)
        self.assertTrue(all(len(sample) == 4 for sample in samples))
        self.assertTrue(any(len(set(sample)) < 4 for sample in samples))
        self.assertTrue(all(0 <= i < 4 for sample in samples for i in sample))
        self.assertEqual((fitted, samples), lab.fit_bagging(xs, ys, seed=17, trees=7))
        self.assertNotEqual(samples, lab.fit_bagging(xs, ys, seed=18, trees=7)[1])

    def test_ensemble_not_required_to_beat_single_model(self):
        result = lab.ensembles_lab()["observed"]
        self.assertGreater(result["bagging_heldout_metrics"]["brier"],
                           result["single_stump_heldout_metrics"]["brier"])

    def test_invalid_ensemble_size(self):
        for trees in (0, 102, True):
            with self.assertRaises(lab.LabError):
                lab.fit_bagging([0, 1], [0, 1], trees=trees)
        with self.assertRaises(lab.LabError):
            lab.predict_bagging([], [0])


class RepresentationTests(GuardedTest):
    def test_literal_centered_pca(self):
        model = lab.pca2([[1, 2], [2, 4], [3, 6], [4, 8]])
        self.assertEqual(model["center"], [2.5, 5])
        self.assertEqual(model["eigenvalues"], [6.25, 0])
        self.assertAlmostEqual(abs(model["direction"][0] / model["direction"][1]), .5)

    def test_pca_sign_invariant_reconstruction(self):
        model = lab.pca2([[1, 2], [2, 4], [3, 6]])
        flipped_direction = [-v for v in model["direction"]]
        flipped_z = [-z for z in model["projections"]]
        reconstructed = [[model["center"][j] + z * flipped_direction[j] for j in range(2)] for z in flipped_z]
        self.assertEqual(reconstructed, model["reconstruction"])

    def test_pca_translation_invariant_direction(self):
        points = [[-1, -2], [0, 0], [1, 2]]
        shifted = [[p[0] + 100, p[1] - 50] for p in points]
        before, after = lab.pca2(points), lab.pca2(shifted)
        self.assertEqual(before["eigenvalues"], after["eigenvalues"])
        self.assertEqual(before["direction"], after["direction"])

    def test_zero_covariance_axis_case(self):
        model = lab.pca2([[2, -1], [2, 0], [2, 1]])
        self.assertEqual(model["direction"], [0, 1])
        self.assertAlmostEqual(model["eigenvalues"][0], 2 / 3)

    def test_pca_scale_invariance_and_eigen_residual(self):
        for scale in (1e-9, 1e-6, 1.0, 1e6):
            for sign in (-1, 1):
                points = [[-scale, -sign * scale], [scale, sign * scale]]
                model = lab.pca2(points)
                direction = model["direction"]
                alignment = abs((direction[0] + sign * direction[1]) / math.sqrt(2))
                self.assertAlmostEqual(alignment, 1.0)
                # Independent covariance times v, normalized before comparing
                # so that a tiny input cannot pass a fixed absolute tolerance.
                eigenvalue = model["eigenvalues"][0]
                self.assertAlmostEqual(eigenvalue / (scale * scale), 2.0)
                for j in range(2):
                    cv = scale * scale * (direction[j] + sign * direction[1 - j])
                    self.assertLess(abs(cv - eigenvalue * direction[j]) / eigenvalue, 1e-12)
                error = sum(sum((a - b) ** 2 for a, b in zip(point, restored))
                            for point, restored in zip(points, model["reconstruction"]))
                self.assertLess(error / (4 * scale * scale), 1e-24)

    def test_kmeans_literal_inertia_centers_partition(self):
        points = [[0, 0], [0, 1], [1, 0], [1, 1], [8, 8], [8, 9], [9, 8], [9, 9]]
        model = lab.kmeans(points)
        self.assertEqual(sorted(model["centers"]), [[.5, .5], [8.5, 8.5]])
        self.assertEqual(model["inertia"], 4)
        self.assertEqual(lab.canonical_partition(model["labels"]), [(0, 1, 2, 3), (4, 5, 6, 7)])
        self.assertTrue(model["converged"])

    def test_cluster_label_permutation_invariance(self):
        self.assertEqual(lab.canonical_partition([1, 1, 0, 0]), lab.canonical_partition([9, 9, 4, 4]))

    def test_kmeans_iteration_bound_and_monotonic_history(self):
        points = [[0, 0], [1, 1], [2, 1], [8, 8], [9, 10], [7, 9]]
        bounded = lab.kmeans(points, iterations=1)
        self.assertEqual(bounded["iterations"], 1)
        self.assertFalse(bounded["converged"])
        history = lab.kmeans(points)["history"]
        self.assertTrue(all(b <= a + 1e-9 for a, b in zip(history, history[1:])))

    def test_representation_invalid_shapes_and_degenerate_data(self):
        for operation in (lambda: lab.pca2([[1, 1], [1, 1]]),
                          lambda: lab.pca2([[0], [1]]),
                          lambda: lab.pca2([[0, math.nan], [1, 2]]),
                          lambda: lab.kmeans([[1, 1], [1, 1]], k=2),
                          lambda: lab.kmeans([[0, 0], [1, 1]], iterations=0),
                          lambda: lab.kmeans([[0, 0], [1, 1]], k=3)):
            with self.assertRaises(lab.LabError):
                operation()


class IntegrationTests(GuardedTest):
    def test_all_lab_determinism_no_input_mutation(self):
        self.assertEqual(lab.run(), lab.run())
        points = [[0, 0], [1, 1], [8, 8], [9, 9]]
        original = deepcopy(points)
        lab.kmeans(points)
        lab.pca2(points)
        self.assertEqual(points, original)

    def test_cli_json_no_file_or_network_operations(self):
        output = io.StringIO()
        with patch("builtins.open", side_effect=AssertionError("file I/O forbidden")), \
             patch("os.open", side_effect=AssertionError("file I/O forbidden")), contextlib.redirect_stdout(output):
            code = lab.main(["--lab", "all"])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(len(result["results"]), 4)
        self.assertTrue(all(item["result"] == "PASS" for item in result["results"]))
        self.assertEqual(result["network_calls"], 0)
        self.assertEqual(result["file_writes"], 0)
        self.assertFalse(result["paper_scale_reproduction"])

    def test_cli_invalid_bounds_and_options(self):
        for args in (["--seed", "-1"], ["--seed", str(2 ** 32)], ["--epochs", "501"],
                     ["--trees", "0"], ["--iterations", "101"], ["--lab", "unknown"],
                     ["--input", "secret.csv"], ["--epochs", "nan"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(lab.main(args), 1)
            self.assertEqual(json.loads(output.getvalue())["result"], "FAIL")
            self.assertNotIn("secret.csv", output.getvalue())

    def test_boundary_budgets_and_seeds(self):
        for seed in (0, 1, 17, 2 ** 32 - 1):
            self.assertEqual(len(lab.run(seed=seed, epochs=1, trees=1, iterations=1)), 4)
        self.assertEqual(len(lab.run(epochs=500, trees=101, iterations=100)), 4)

    def test_explicit_oracle_failure_under_optimization(self):
        with self.assertRaisesRegex(lab.LabError, "oracle_failed_deliberate"):
            lab.check(False, "deliberate")

    def test_invalid_array_bounds_nonfinite_and_lengths(self):
        for operation in (lambda: lab.fit_ridge([], [], 0),
                          lambda: lab.fit_ridge([1, 2], [1], 0),
                          lambda: lab.fit_ridge([1, math.inf], [1, 2], 0),
                          lambda: lab.fit_stump([1] * 129, [0] * 129)):
            with self.assertRaises(lab.LabError):
                operation()


if __name__ == "__main__":
    unittest.main()
