"""Independent oracles, failure contracts, and bounded real-learning checks."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch


LAB_PATH = Path(__file__).with_name("lab.py")
SPEC = importlib.util.spec_from_file_location("dl_cpu_lab_under_test", LAB_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load DL lab")
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)


class AutodiffTests(unittest.TestCase):
    def test_numeric_validation(self):
        for value in [True, "1", float("nan"), float("inf"), -float("inf")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                lab.Value(value)

    def test_shared_edge_derivative(self):
        x = lab.Value(3.0)
        y = x * x
        (y + y + x).backward()
        self.assertEqual(x.grad, 13.0)

    def test_shared_subgraph_three_paths(self):
        x, y = lab.Value(2.0), lab.Value(-3.0)
        shared = x * y
        (shared.square() + 2 * shared).backward()
        self.assertEqual(x.grad, 30.0)
        self.assertEqual(y.grad, -20.0)

    def test_leaf_accumulation_and_reset(self):
        x = lab.Value(2.0)
        y = x.square()
        y.backward()
        y.backward()
        self.assertEqual(x.grad, 8.0)
        lab.zero_grad([x])
        y.backward()
        self.assertEqual(x.grad, 4.0)

    def test_leaf_root_accumulates(self):
        x = lab.Value(2.0)
        x.backward()
        x.backward()
        self.assertEqual(x.grad, 2.0)

    def test_elementary_derivatives(self):
        for name, function, oracle in [
            ("tanh", lambda x: x.tanh(), 1 - math.tanh(0.3) ** 2),
            ("exp", lambda x: x.exp(), math.exp(0.3)),
            ("log", lambda x: x.log(), 1 / 0.3),
            ("reverse subtraction", lambda x: 2 - x, -1.0),
        ]:
            with self.subTest(name=name):
                x = lab.Value(0.3)
                function(x).backward()
                self.assertAlmostEqual(x.grad, oracle, places=12)

    def test_invalid_elementary_domains(self):
        for value in [0.0, -1.0]:
            with self.assertRaises(ValueError):
                lab.Value(value).log()
        with self.assertRaises(ValueError):
            lab.Value(1000.0).exp()
        with self.assertRaises(ValueError):
            lab.mean([])

    def test_composition_independent_finite_difference(self):
        x, y = lab.Value(0.7), lab.Value(-0.2)
        objective = lambda: ((x * y + x).tanh() + (x - y).exp()).log()
        objective().backward()

        def numeric(a, b):
            return math.log(math.tanh(a * b + a) + math.exp(a - b))

        epsilon = 1e-5
        expected_x = (numeric(0.7 + epsilon, -0.2) - numeric(0.7 - epsilon, -0.2)) / (2 * epsilon)
        expected_y = (numeric(0.7, -0.2 + epsilon) - numeric(0.7, -0.2 - epsilon)) / (2 * epsilon)
        self.assertAlmostEqual(x.grad, expected_x, places=8)
        self.assertAlmostEqual(y.grad, expected_y, places=8)

    def test_gradient_check_restores_parameters(self):
        x = lab.Value(0.7)
        self.assertLess(lab.gradient_check(lambda: (3 * x).tanh(), [x]), 1e-7)
        self.assertEqual(x.data, 0.7)

    def test_gradient_check_invalid_step(self):
        x = lab.Value(1.0)
        for epsilon in [0.0, -1.0, float("nan")]:
            with self.assertRaises(ValueError):
                lab.gradient_check(lambda: x.square(), [x], epsilon)

    def test_long_graph_without_recursion(self):
        x = lab.Value(1.0)
        y = x
        for _ in range(2000):
            y = y + 1.0
        y.backward()
        self.assertEqual(x.grad, 1.0)


class OptimizerTests(unittest.TestCase):
    def test_sgdm_hand_calculated_two_steps(self):
        parameter = lab.Value(1.0)
        optimizer = lab.SGDM([parameter], 0.1, 0.9)
        parameter.grad = 2.0
        optimizer.step()
        self.assertAlmostEqual(parameter.data, 0.8)
        parameter.grad = -1.0
        optimizer.step()
        self.assertAlmostEqual(optimizer.velocity[0], 0.8)
        self.assertAlmostEqual(parameter.data, 0.72)

    def test_adam_bias_corrected_two_steps(self):
        parameter = lab.Value(1.0)
        optimizer = lab.Adam([parameter], 0.1, beta1=0.8, beta2=0.9, epsilon=1e-6)
        parameter.grad = 2.0
        optimizer.step()
        first = 1 - 0.1 * 2 / (2 + 1e-6)
        self.assertAlmostEqual(parameter.data, first, places=12)
        parameter.grad = -1.0
        optimizer.step()
        # m2=.8*.4 + .2*(-1)=.12; v2=.9*.4 + .1*1=.46.
        second_m = 0.12 / (1 - 0.8 ** 2)
        second_v = 0.46 / (1 - 0.9 ** 2)
        self.assertAlmostEqual(parameter.data, first - 0.1 * second_m / (math.sqrt(second_v) + 1e-6),
                               places=12)
        self.assertEqual(optimizer.steps, 2)

    def test_zero_gradient_leaves_fresh_adam_parameter_unchanged(self):
        parameter = lab.Value(2.0)
        lab.Adam([parameter], 0.1).step()
        self.assertEqual(parameter.data, 2.0)

    def test_optimizer_rejects_invalid_inputs(self):
        parameter = lab.Value(1.0)
        constructors = [lambda: lab.SGDM([], 0.1), lambda: lab.SGDM([parameter, parameter], 0.1),
                        lambda: lab.SGDM([parameter.square()], 0.1),
                        lambda: lab.SGDM([parameter], 0), lambda: lab.SGDM([parameter], 0.1, 1),
                        lambda: lab.Adam([parameter], 0.1, beta1=-0.1),
                        lambda: lab.Adam([parameter], 0.1, beta2=1.0),
                        lambda: lab.Adam([parameter], 0.1, epsilon=0)]
        for constructor in constructors:
            with self.assertRaises(ValueError):
                constructor()

    def test_nonfinite_gradient_rejected(self):
        for optimizer in [lab.SGDM, lab.Adam]:
            parameter = lab.Value(1.0)
            parameter.grad = float("nan")
            with self.assertRaises(ValueError):
                optimizer([parameter], 0.1).step()

    def test_train_requires_positive_integer_steps(self):
        x = lab.Value(1.0)
        for steps in [0, -1, True, 1.5]:
            with self.assertRaises(ValueError):
                lab.train(lambda: x.square(), lab.SGDM([x], 0.1), steps)


class LayerTests(unittest.TestCase):
    def test_mlp_rejects_wrong_features(self):
        for inputs in [[], [1.0], [1.0, 2.0, 3.0], [1.0, float("nan")]]:
            with self.assertRaises(ValueError):
                lab.MLP()(inputs)

    def test_mlp_seed_determinism_and_difference(self):
        a, b, c = lab.MLP(11), lab.MLP(11), lab.MLP(12)
        self.assertEqual([p.data for p in a.parameters], [p.data for p in b.parameters])
        self.assertNotEqual([p.data for p in a.parameters], [p.data for p in c.parameters])

    def test_local_rng_does_not_change_global_state(self):
        before = random.getstate()
        lab.MLP()
        lab.RNN()
        self.assertEqual(random.getstate(), before)

    def test_correlation_literal_values_and_kernel_orientation(self):
        actual = [v.data for v in lab.cross_correlation([1, 2, 4, 8], [2, -1], 0.5)]
        self.assertEqual(actual, [0.5, 0.5, 0.5])
        # Kernel-flipped mathematical convolution yields [3.5,6.5,12.5], not the same operator.
        self.assertNotEqual(actual, [3.5, 6.5, 12.5])

    def test_correlation_weight_sharing_gradient(self):
        kernel = [lab.Value(2.0), lab.Value(-1.0)]
        bias = lab.Value(0.5)
        sum(lab.cross_correlation([1, 2, 4, 8], kernel, bias), lab.Value(0.0)).backward()
        self.assertEqual([p.grad for p in kernel], [7.0, 14.0])
        self.assertEqual(bias.grad, 3.0)

    def test_correlation_input_gradient(self):
        signal = [lab.Value(x) for x in [1, 2, 4, 8]]
        sum(lab.cross_correlation(signal, [2, -1]), lab.Value(0.0)).backward()
        self.assertEqual([x.grad for x in signal], [2.0, 1.0, 1.0, -1.0])

    def test_invalid_correlation_dimensions(self):
        for signal, kernel in [([], [1]), ([1], []), ([1], [1, 2])]:
            with self.assertRaises(ValueError):
                lab.cross_correlation(signal, kernel)

    def test_translation_boundary_counterexample(self):
        original = [v.data for v in lab.cross_correlation([1, 2, 3, 4], [1, -1])]
        shifted = [v.data for v in lab.cross_correlation([0, 1, 2, 3], [1, -1])]
        self.assertEqual(shifted[1:], original[:-1])
        self.assertNotEqual(shifted, [0.0] + original[:-1])

    def test_cross_entropy_uniform_oracle(self):
        logits = [lab.Value(0) for _ in range(3)]
        loss = lab.cross_entropy(logits, 1)
        loss.backward()
        self.assertAlmostEqual(loss.data, math.log(3), places=12)
        for got, expected in zip([v.grad for v in logits], [1 / 3, -2 / 3, 1 / 3]):
            self.assertAlmostEqual(got, expected, places=12)

    def test_cross_entropy_stability_and_shift_invariance(self):
        self.assertAlmostEqual(lab.cross_entropy([lab.Value(1000), lab.Value(1000)], 0).data,
                               math.log(2), places=12)
        self.assertAlmostEqual(lab.cross_entropy([lab.Value(2), lab.Value(-1)], 1).data,
                               lab.cross_entropy([lab.Value(102), lab.Value(99)], 1).data, places=12)

    def test_cross_entropy_rejects_invalid_target(self):
        for target in [-1, 3, True, 0.5]:
            with self.assertRaises(ValueError):
                lab.cross_entropy([lab.Value(0) for _ in range(3)], target)

    def test_rnn_seed_and_dimensions(self):
        a, b = lab.RNN(9), lab.RNN(9)
        self.assertEqual([p.data for p in a.parameters], [p.data for p in b.parameters])
        self.assertEqual(len(a.parameters), 47)
        self.assertEqual([len(row) for row in a.forward([0, 1, 2])], [3, 3, 3])
        for args in [{"hidden": 0}, {"vocabulary": True}]:
            with self.assertRaises(ValueError):
                lab.RNN(**args)

    def test_rnn_token_contract(self):
        model = lab.RNN()
        for tokens in [[], [3], [-1], [True], [0.5]]:
            with self.assertRaises(ValueError):
                model.forward(tokens)
        with self.assertRaises(ValueError):
            model.loss([0])

    def test_rnn_prefix_causality_and_state_reset(self):
        model = lab.RNN()
        values = lambda rows: [[value.data for value in row] for row in rows]
        left = values(model.forward([0, 1, 2, 0]))
        right = values(model.forward([0, 1, 1, 2]))
        self.assertEqual(left[:2], right[:2])
        self.assertNotEqual(left[2:], right[2:])
        self.assertEqual(left, values(model.forward([0, 1, 2, 0])))

    def test_rnn_full_bptt_finite_difference(self):
        model = lab.RNN(seed=5, hidden=2)
        self.assertLess(lab.gradient_check(lambda: model.loss([0, 1, 2, 0]), model.parameters), 1e-6)


class RealLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # All real training is executed with network and application file access forbidden.
        with patch("socket.socket", side_effect=RuntimeError("network is forbidden")), \
             patch("socket.create_connection", side_effect=RuntimeError("network is forbidden")), \
             patch("builtins.open", side_effect=RuntimeError("file access is forbidden")):
            cls.reports = {name: function() for name, function in lab.LABS.items()}

    def test_all_reports_finite_json_and_scoped(self):
        for name, report in self.reports.items():
            with self.subTest(name=name):
                self.assertEqual(report["status"], "PASS")
                self.assertEqual(report["lab"], name)
                self.assertTrue(report["scope"])
                json.dumps(report, allow_nan=False)

    def test_mlp_really_learns_and_changes_parameters(self):
        observed = self.reports["backprop"]["observed"]
        self.assertTrue(observed["parameters_changed"])
        self.assertLess(observed["final_mse"], observed["initial_mse"] * 0.1)
        self.assertEqual(observed["train_correct"], 4)
        self.assertEqual(observed["heldout_correct"], 8)

    def test_optimizer_no_universal_adam_claim(self):
        observed = self.reports["optimization"]["observed"]
        self.assertLess(observed["sgdm"]["final_loss"], observed["adam"]["final_loss"])
        self.assertEqual(observed["after_zero_grad"], 4)

    def test_filter_really_recovers_independent_teacher(self):
        observed = self.reports["convolution"]["observed"]
        self.assertLess(observed["final_mse"], observed["initial_mse"] * 0.001)
        for got, expected in zip(observed["learned_kernel"], [0.5, -1.0, 0.25]):
            self.assertAlmostEqual(got, expected, places=4)
        self.assertLess(observed["heldout_max_abs_error"], 1e-4)

    def test_rnn_really_learns_teacher_forced_and_rollout(self):
        observed = self.reports["sequence"]["observed"]
        self.assertTrue(observed["parameters_changed"])
        self.assertLess(observed["final_cross_entropy"], observed["initial_cross_entropy"] * 0.1)
        self.assertEqual(observed["heldout_teacher_forced_correct"], 12)
        self.assertEqual(observed["greedy_rollout"], [i % 3 for i in range(13)])

    def test_training_determinism(self):
        self.assertEqual(lab.backprop_lab(), self.reports["backprop"])
        self.assertEqual(lab.sequence_lab(), self.reports["sequence"])


class CLITests(unittest.TestCase):
    def test_invalid_cli_choice(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            lab.main(["--lab", "unknown"])
        self.assertEqual(caught.exception.code, 2)

    def test_failure_is_error_not_pass(self):
        output = io.StringIO()
        with patch.dict(lab.LABS, {"backprop": lambda: lab.require(False, "injected failure")}), \
             contextlib.redirect_stdout(output):
            self.assertEqual(lab.main(["--lab", "backprop"]), 1)
        self.assertEqual(json.loads(output.getvalue()), {"status": "ERROR", "error": "injected failure"})

    def test_real_cli_all_normal_and_optimized(self):
        outputs = []
        for flags in [[], ["-O"]]:
            process = subprocess.run([sys.executable, "-B", *flags, str(LAB_PATH), "--lab", "all"],
                                     text=True, encoding="utf-8", capture_output=True, timeout=30,
                                     check=False)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            reports = [json.loads(line) for line in process.stdout.splitlines()]
            self.assertEqual([r["lab"] for r in reports], list(lab.LABS))
            self.assertTrue(all(r["status"] == "PASS" for r in reports))
            outputs.append(reports)
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
