import contextlib
import io
import json
import math
import unittest
from unittest.mock import patch

import lab


class VectorTests(unittest.TestCase):
    def test_dot_literal(self):
        self.assertEqual(lab.dot([2, -3, 1], [4, 2, -2]), 0)

    def test_matmul_literal_and_identity(self):
        self.assertEqual(lab.matmul([[1, 2]], [[3], [4]]), [[11]])
        self.assertEqual(lab.matmul([[2, -1], [0, 3]], [[1, 0], [0, 1]]),
                         [[2, -1], [0, 3]])

    def test_shapes_are_checked_not_truncated(self):
        for function in (lambda: lab.dot([1, 2], [1]),
                         lambda: lab.matmul([[1], [2, 3]], [[1]]),
                         lambda: lab.matmul([[1, 2]], [[1, 2]])):
            with self.assertRaises(lab.LabError):
                function()

    def test_projection_nonunit_axis_and_scale(self):
        self.assertEqual(lab.projection([3, 4], [2, 0]), [3, 0])
        self.assertEqual(lab.projection([3, 4], [-10, 0]), [3, 0])
        self.assertEqual(lab.projection([3, 4], [1, 1]), [3.5, 3.5])

    def test_projection_pythagorean(self):
        original = [2, 5]
        fitted = lab.projection(original, [3, -1])
        residual = [a - b for a, b in zip(original, fitted)]
        self.assertAlmostEqual(lab.dot(residual, [3, -1]), 0)
        self.assertAlmostEqual(lab.dot(original, original),
                               lab.dot(fitted, fitted) + lab.dot(residual, residual))

    def test_invalid_zero_nan_bool_and_bounds(self):
        for function in (lambda: lab.projection([1, 2], [0, 0]),
                         lambda: lab.dot([True], [1]), lambda: lab.dot([], []),
                         lambda: lab.dot([math.nan], [1]),
                         lambda: lab.dot([1] * 33, [1] * 33)):
            with self.assertRaises(lab.LabError):
                function()


class DerivativeTests(unittest.TestCase):
    def test_quadratic_and_shared_chain(self):
        self.assertAlmostEqual(lab.central_difference(lambda w: (2 * w - 3) ** 2 / 2, 1), -2)
        self.assertAlmostEqual(lab.central_difference(lambda w: (2 * w) ** 2 + 2 * w, 3), 26)

    def test_other_function_independent_analytic(self):
        self.assertAlmostEqual(lab.central_difference(math.sin, 0.4), math.cos(0.4))
        self.assertAlmostEqual(lab.central_difference(lambda x: x ** 3, 2), 12)

    def test_mean_reduction_gradient(self):
        objective = lambda w: ((w - 2) ** 2 + (2 * w - 3) ** 2) / 4
        self.assertAlmostEqual(lab.central_difference(objective, 1), -1.5)

    def test_relu_kink_is_not_differentiable(self):
        self.assertAlmostEqual(lab.central_difference(lambda x: max(0, x), 0), 0.5)
        self.assertNotEqual((max(0, 0) - max(0, -0.01)) / 0.01,
                            (max(0, 0.01) - max(0, 0)) / 0.01)

    def test_difference_invalid_steps_and_objective(self):
        for step in (0, -1, math.inf, True):
            with self.assertRaises(lab.LabError):
                lab.central_difference(math.sin, 1, step)
        with self.assertRaises(lab.LabError):
            lab.central_difference(lambda x: math.nan, 1)


class ProbabilityTests(unittest.TestCase):
    def test_bayes_count_oracle(self):
        self.assertAlmostEqual(lab.posterior(.01, .9, .05), 90 / (90 + 495))
        self.assertEqual(lab.posterior(.3, 1, 0), 1)
        self.assertEqual(lab.posterior(0, 1, .2), 0)

    def test_variance_conventions(self):
        self.assertEqual(lab.variance([1, 3]), 1)
        self.assertEqual(lab.variance([1, 3], 1), 2)
        self.assertEqual(lab.variance([2, 2, 2]), 0)

    def test_nll_and_geometric_mean_probability(self):
        self.assertAlmostEqual(lab.token_nll([.5, .25]), math.log(8) / 2)
        self.assertEqual(lab.token_nll([1, 1]), 0)

    def test_invalid_probability_and_denominator(self):
        for function in (lambda: lab.posterior(.5, 0, 0),
                         lambda: lab.posterior(-.1, .9, .05),
                         lambda: lab.variance([1], 1), lambda: lab.variance([1, 2], True),
                         lambda: lab.token_nll([0]), lambda: lab.token_nll([1.1])):
            with self.assertRaises(lab.LabError):
                function()


class OptimizationTests(unittest.TestCase):
    def test_literal_step_and_overshoot(self):
        self.assertEqual(lab.gradient_step([1, 1], .01), [.99, 0])
        self.assertAlmostEqual(lab.quadratic([.97, -2]), 200.47045)
        self.assertGreater(lab.quadratic(lab.gradient_step([1, 1], .03)),
                           lab.quadratic([1, 1]))

    def test_gradient_matches_finite_difference(self):
        self.assertAlmostEqual(lab.central_difference(lambda x: lab.quadratic([x, .3]), .7), .7)
        self.assertAlmostEqual(lab.central_difference(lambda y: lab.quadratic([.7, y]), .3), 30)

    def test_logsumexp_shift_and_equal_values(self):
        self.assertAlmostEqual(lab.logsumexp([0, 0]), math.log(2))
        self.assertAlmostEqual(lab.logsumexp([1000, 999]) - 1000, lab.logsumexp([0, -1]))

    def test_invalid_gradient_parameters(self):
        for point, rate in (([1], .01), ([1, 2], -1), ([1, 2], math.nan)):
            with self.assertRaises(lab.LabError):
                lab.gradient_step(point, rate)


class IntegrationTests(unittest.TestCase):
    def test_all_offline_and_file_free(self):
        output = io.StringIO()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
             patch("socket.create_connection", side_effect=AssertionError("network forbidden")), \
             patch("builtins.open", side_effect=AssertionError("file forbidden")), \
             patch("os.open", side_effect=AssertionError("file forbidden")), \
             contextlib.redirect_stdout(output):
            self.assertEqual(lab.main([]), 0)
        parsed = json.loads(output.getvalue())
        self.assertEqual([entry["lab"] for entry in parsed["results"]], list(lab.LABS))
        self.assertTrue(all(entry["status"] == "PASS" for entry in parsed["results"]))

    def test_individual_and_determinism(self):
        for name, function in lab.LABS.items():
            self.assertEqual(function(), function())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(lab.main(["--lab", name]), 0)
            self.assertEqual(len(json.loads(output.getvalue())["results"]), 1)

    def test_explicit_oracle_rejection(self):
        with self.assertRaises(lab.LabError):
            lab.same(1, 2)
        with self.assertRaises(lab.LabError):
            lab.same(math.nan, 0)

    def test_cli_invalid_no_input_echo(self):
        for argv in (["--lab", "unknown"], ["--input", "private.csv"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(lab.main(argv), 1)
            self.assertNotIn("private.csv", output.getvalue())


if __name__ == "__main__":
    unittest.main()
