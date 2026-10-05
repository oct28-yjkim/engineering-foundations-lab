"""Bounded, deterministic CPU learning labs; Python 3.10+ standard library only.

No packages, downloads, network, GPU, API, or file writes. These tiny trained
models are educational experiments, not reproductions of complete papers.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from typing import Callable, Sequence


SEED = 20261005


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def finite(value: float, name: str = "value") -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            f"{name} must be numeric")
    require(math.isfinite(value), f"{name} must be finite")
    return float(value)


def positive_int(value: int, name: str) -> None:
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"{name} must be a positive integer")


class Value:
    """Scalar reverse-mode autodiff. No tensors or broadcasting.

    backward() resets intermediate gradients but ACCUMULATES leaf gradients.
    Call zero_grad(parameters) before each training backward pass. Values must
    not be mutated between forward and backward; no higher-order derivatives.
    """

    def __init__(self, data: float, parents: tuple[Value, ...] = ()):
        self.data = finite(data)
        self.grad = 0.0
        self.parents = parents
        self._backward: Callable[[], None] = lambda: None

    @staticmethod
    def as_value(other: float | Value) -> Value:
        return other if isinstance(other, Value) else Value(other)

    def __add__(self, other: float | Value) -> Value:
        other = self.as_value(other)
        out = Value(self.data + other.data, (self, other))

        def backward() -> None:
            self.grad += out.grad
            other.grad += out.grad

        out._backward = backward
        return out

    __radd__ = __add__

    def __mul__(self, other: float | Value) -> Value:
        other = self.as_value(other)
        left, right = self.data, other.data
        out = Value(left * right, (self, other))

        def backward() -> None:
            self.grad += right * out.grad
            other.grad += left * out.grad

        out._backward = backward
        return out

    __rmul__ = __mul__

    def __neg__(self) -> Value:
        return self * -1.0

    def __sub__(self, other: float | Value) -> Value:
        return self + -self.as_value(other)

    def __rsub__(self, other: float | Value) -> Value:
        return self.as_value(other) + -self

    def square(self) -> Value:
        return self * self

    def tanh(self) -> Value:
        result = math.tanh(self.data)
        out = Value(result, (self,))

        def backward() -> None:
            self.grad += (1.0 - result * result) * out.grad

        out._backward = backward
        return out

    def exp(self) -> Value:
        try:
            result = math.exp(self.data)
        except OverflowError as exc:
            raise ValueError("exp overflow") from exc
        out = Value(result, (self,))

        def backward() -> None:
            self.grad += result * out.grad

        out._backward = backward
        return out

    def log(self) -> Value:
        require(self.data > 0.0, "log requires a positive argument")
        before = self.data
        out = Value(math.log(before), (self,))

        def backward() -> None:
            self.grad += out.grad / before

        out._backward = backward
        return out

    def backward(self) -> None:
        # Iterative postorder traversal avoids dependence on recursion limits.
        order: list[Value] = []
        visited: set[int] = set()
        stack = [(self, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                order.append(node)
            elif id(node) not in visited:
                visited.add(id(node))
                stack.append((node, True))
                stack.extend((parent, False) for parent in node.parents)
        if not self.parents:
            self.grad += 1.0
            return
        for node in order:
            if node.parents:
                node.grad = 0.0
        self.grad = 1.0
        for node in reversed(order):
            node._backward()
        for node in order:
            finite(node.grad, "gradient")


def zero_grad(parameters: Sequence[Value]) -> None:
    for parameter in parameters:
        parameter.grad = 0.0


def mean(values: Sequence[Value]) -> Value:
    require(bool(values), "mean requires nonempty values")
    return sum(values, Value(0.0)) * (1.0 / len(values))


def gradient_check(objective: Callable[[], Value], parameters: Sequence[Value],
                   epsilon: float = 1e-5) -> float:
    """Central differences on all supplied coordinates; restores parameters."""
    require(finite(epsilon) > 0, "epsilon must be positive")
    require(bool(parameters), "gradient check needs parameters")
    zero_grad(parameters)
    objective().backward()
    analytical = [parameter.grad for parameter in parameters]
    errors = []
    for parameter, derivative in zip(parameters, analytical):
        original = parameter.data
        try:
            parameter.data = original + epsilon
            plus = objective().data
            parameter.data = original - epsilon
            minus = objective().data
        finally:
            parameter.data = original
        numerical = (plus - minus) / (2.0 * epsilon)
        errors.append(abs(numerical - derivative))
    return max(errors)


class SGDM:
    """v[t] = momentum*v[t-1] + grad; parameter -= learning_rate*v[t]."""

    def __init__(self, parameters: Sequence[Value], learning_rate: float,
                 momentum: float = 0.0):
        self.parameters = list(parameters)
        require(bool(self.parameters), "optimizer needs parameters")
        require(all(isinstance(p, Value) and not p.parents for p in self.parameters),
                "optimizer parameters must be leaf Values")
        require(len({id(p) for p in self.parameters}) == len(self.parameters),
                "duplicate optimizer parameter")
        require(finite(learning_rate) > 0, "learning_rate must be positive")
        require(0 <= finite(momentum) < 1, "momentum must be in [0,1)")
        self.learning_rate = learning_rate
        self.momentum = momentum
        self.velocity = [0.0] * len(self.parameters)

    def step(self) -> None:
        for index, parameter in enumerate(self.parameters):
            grad = finite(parameter.grad, "gradient")
            velocity = self.momentum * self.velocity[index] + grad
            parameter.data = finite(parameter.data - self.learning_rate * velocity)
            self.velocity[index] = velocity


class Adam(SGDM):
    """Adam with per-step bias correction; no weight decay, AMSGrad, or clipping."""

    def __init__(self, parameters: Sequence[Value], learning_rate: float,
                 beta1: float = 0.9, beta2: float = 0.999, epsilon: float = 1e-8):
        super().__init__(parameters, learning_rate)
        require(0 <= finite(beta1) < 1 and 0 <= finite(beta2) < 1,
                "Adam betas must be in [0,1)")
        require(finite(epsilon) > 0, "Adam epsilon must be positive")
        self.beta1, self.beta2, self.epsilon = beta1, beta2, epsilon
        self.second = [0.0] * len(self.parameters)
        self.steps = 0

    def step(self) -> None:
        self.steps += 1
        for index, parameter in enumerate(self.parameters):
            grad = finite(parameter.grad, "gradient")
            self.velocity[index] = self.beta1 * self.velocity[index] + (1 - self.beta1) * grad
            self.second[index] = self.beta2 * self.second[index] + (1 - self.beta2) * grad * grad
            corrected_m = self.velocity[index] / (1 - self.beta1 ** self.steps)
            corrected_v = self.second[index] / (1 - self.beta2 ** self.steps)
            update = self.learning_rate * corrected_m / (math.sqrt(corrected_v) + self.epsilon)
            parameter.data = finite(parameter.data - update)


def train(objective: Callable[[], Value], optimizer: SGDM, steps: int) -> tuple[float, float]:
    positive_int(steps, "steps")
    initial = objective().data
    for _ in range(steps):
        zero_grad(optimizer.parameters)
        loss = objective()
        loss.backward()
        optimizer.step()
    return initial, objective().data


class MLP:
    def __init__(self, seed: int = SEED, hidden: int = 8):
        positive_int(hidden, "hidden")
        rng = random.Random(seed)
        self.hidden = [[Value(rng.uniform(-0.6, 0.6)) for _ in range(3)] for _ in range(hidden)]
        self.output = [Value(rng.uniform(-0.6, 0.6)) for _ in range(hidden + 1)]
        self.parameters = [p for row in self.hidden for p in row] + self.output

    def __call__(self, inputs: Sequence[float]) -> Value:
        require(len(inputs) == 2, "MLP expects exactly two features")
        x, y = [finite(value, "input") for value in inputs]
        hidden = [(row[0] * x + row[1] * y + row[2]).tanh() for row in self.hidden]
        return (sum((w * h for w, h in zip(self.output[:-1], hidden)), self.output[-1])).tanh()


def cross_correlation(signal: Sequence[float | Value], kernel: Sequence[float | Value],
                      bias: float | Value = 0.0) -> list[Value]:
    """Valid, stride-one 1D cross-correlation, the usual neural-network convention."""
    require(bool(kernel) and len(signal) >= len(kernel), "invalid signal/kernel lengths")
    x = [Value.as_value(value) for value in signal]
    w = [Value.as_value(value) for value in kernel]
    return [sum((x[start + k] * w[k] for k in range(len(w))), Value.as_value(bias))
            for start in range(len(x) - len(w) + 1)]


def cross_entropy(logits: Sequence[Value], target: int) -> Value:
    require(bool(logits), "logits must not be empty")
    require(isinstance(target, int) and not isinstance(target, bool) and 0 <= target < len(logits),
            "target is outside vocabulary")
    peak = max(value.data for value in logits)
    return sum(((value - peak).exp() for value in logits), Value(0.0)).log() + peak - logits[target]


class RNN:
    """Tiny Elman tanh RNN; full BPTT within each bounded sequence, reset h[0]=0."""

    def __init__(self, seed: int = SEED, vocabulary: int = 3, hidden: int = 4):
        positive_int(vocabulary, "vocabulary")
        positive_int(hidden, "hidden")
        self.vocabulary, self.hidden_size = vocabulary, hidden
        rng = random.Random(seed)

        def matrix(rows: int, columns: int) -> list[list[Value]]:
            return [[Value(rng.uniform(-0.4, 0.4)) for _ in range(columns)] for _ in range(rows)]

        self.input_weights = matrix(hidden, vocabulary)
        self.recurrent_weights = matrix(hidden, hidden)
        self.output_weights = matrix(vocabulary, hidden)
        self.hidden_bias = [Value(0.0) for _ in range(hidden)]
        self.output_bias = [Value(0.0) for _ in range(vocabulary)]
        self.parameters = ([p for row in self.input_weights for p in row]
                           + [p for row in self.recurrent_weights for p in row]
                           + [p for row in self.output_weights for p in row]
                           + self.hidden_bias + self.output_bias)

    def forward(self, tokens: Sequence[int]) -> list[list[Value]]:
        require(bool(tokens), "sequence must not be empty")
        require(all(isinstance(t, int) and not isinstance(t, bool) and 0 <= t < self.vocabulary
                    for t in tokens), "token is outside vocabulary")
        hidden = [Value(0.0) for _ in range(self.hidden_size)]
        outputs = []
        for token in tokens:
            hidden = [(self.input_weights[i][token] + self.hidden_bias[i]
                       + sum((weight * old for weight, old in zip(self.recurrent_weights[i], hidden)),
                             Value(0.0))).tanh() for i in range(self.hidden_size)]
            outputs.append([sum((w * h for w, h in zip(row, hidden)), bias)
                            for row, bias in zip(self.output_weights, self.output_bias)])
        return outputs

    def loss(self, tokens: Sequence[int]) -> Value:
        require(len(tokens) >= 2, "next-token training needs at least two tokens")
        return mean([cross_entropy(row, target)
                     for row, target in zip(self.forward(tokens[:-1]), tokens[1:])])


def rounded(value: float) -> float:
    # Significant digits retain a small nonzero finite-difference residual.
    return float(f"{finite(value):.9g}")


def result(lab: str, expected: dict, observed: dict, scope: list[str]) -> dict:
    return {"lab": lab, "status": "PASS", "seed": SEED,
            "expected": expected, "observed": observed, "scope": scope}


def backprop_lab() -> dict:
    model = MLP()
    examples = [((-1.0, -1.0), -1.0), ((-1.0, 1.0), 1.0),
                ((1.0, -1.0), 1.0), ((1.0, 1.0), -1.0)]

    def objective() -> Value:
        return mean([(model(inputs) - target).square() for inputs, target in examples])

    error = gradient_check(objective, model.parameters)
    initial_parameters = [p.data for p in model.parameters]
    initial, final = train(objective, SGDM(model.parameters, 0.05, 0.8), 300)
    correct = sum((model(inputs).data > 0) == (target > 0) for inputs, target in examples)
    heldout = [((x + dx, y + dy), label) for (x, y), label in examples
               for dx, dy in [(0.12, -0.08), (-0.1, 0.15)]]
    heldout_correct = sum((model(inputs).data > 0) == (target > 0) for inputs, target in heldout)
    changed = any(p.data != original for p, original in zip(model.parameters, initial_parameters))
    require(error < 1e-6 and final < initial * 0.1 and correct == 4 and heldout_correct == 8 and changed,
            "backprop learning/oracle gate failed")
    shared = Value(3.0)
    intermediate = shared * shared
    (intermediate + intermediate + shared).backward()
    require(shared.grad == 13.0, "shared graph gradient failed")
    return result("backprop", {"gradient_max_abs_error_lt": 1e-6, "train_correct": 4,
                               "heldout_correct": 8, "shared_gradient": 13},
                  {"steps": 300, "parameters": len(model.parameters), "initial_mse": rounded(initial),
                   "final_mse": rounded(final), "train_correct": correct, "heldout_correct": heldout_correct,
                   "gradient_max_abs_error": rounded(error), "shared_gradient": shared.grad,
                   "parameters_changed": changed},
                  ["Actual 2-8-1 tanh MLP training on all four XOR corners.",
                   "Eight fixed near-corner points are excluded from training, not a population estimate.",
                   "Scalar first-order reverse-mode autodiff; no tensor broadcasting or deep-network benchmark."])


def optimization_lab() -> dict:
    reports = {}
    for name, create in [("sgdm", lambda p: SGDM(p, 0.05, 0.8)),
                         ("adam", lambda p: Adam(p, 0.15))]:
        parameters = [Value(4.0), Value(-3.0)]

        def objective() -> Value:
            return (parameters[0] - 1.0).square() + 4.0 * (parameters[1] + 2.0).square()

        initial, final = train(objective, create(parameters), 100)
        require(final < initial * 0.01, f"{name} did not improve fixed objective")
        reports[name] = {"initial_loss": rounded(initial), "final_loss": rounded(final),
                         "point": [rounded(p.data) for p in parameters]}
    first = Value(1.0)
    first.grad = 2.0
    Adam([first], 0.1).step()
    first_expected = 1.0 - 0.1 * 2.0 / (2.0 + 1e-8)
    require(abs(first.data - first_expected) < 1e-12, "Adam bias correction failed")
    leaf = Value(2.0)
    graph = leaf.square()
    graph.backward()
    once = leaf.grad
    graph.backward()
    twice = leaf.grad
    zero_grad([leaf])
    graph.backward()
    require((once, twice, leaf.grad) == (4.0, 8.0, 4.0), "gradient accumulation contract failed")
    reports.update({"steps_per_optimizer": 100, "adam_first_update": rounded(first.data),
                    "accumulation_without_zero_grad": [once, twice], "after_zero_grad": leaf.grad})
    return result("optimization", {"objective_minimum": [1.0, -2.0], "final_loss_fraction_lt": 0.01,
                                   "accumulated_gradient": [4, 8], "reset_gradient": 4}, reports,
                  ["Actual parameter updates on one fixed anisotropic quadratic, not a neural-network optimizer ranking.",
                   "Learning rates differ and were chosen for this fixture; Adam is not claimed universally better.",
                   "SGDM and Adam equations include momentum and Adam bias correction; no scheduler or weight decay."])


def convolution_lab() -> dict:
    signals = [[1., 0., -1., 2., 0., 1.], [0., 1., 2., -1., 1., 0.],
               [-1., 2., 0., 1., -2., 1.], [2., -1., 1., 0., 1., -2.]]
    true_kernel = [0.5, -1.0, 0.25]
    true_bias = 0.1
    # Literal numeric teacher, independent of the autodiff correlation helper.
    targets = [[0.5 * x[i] - x[i + 1] + 0.25 * x[i + 2] + 0.1 for i in range(4)]
               for x in signals]
    kernel = [Value(-0.2), Value(0.3), Value(0.1)]
    bias = Value(0.0)
    parameters = kernel + [bias]

    def objective() -> Value:
        return mean([(prediction - target).square()
                     for x, row in zip(signals, targets)
                     for prediction, target in zip(cross_correlation(x, kernel, bias), row)])

    error = gradient_check(objective, parameters)
    initial, final = train(objective, SGDM(parameters, 0.08), 300)
    heldout = [0.2, -0.7, 1.3, 0.4, -0.9, 0.6]
    predictions = [p.data for p in cross_correlation(heldout, kernel, bias)]
    oracle = [0.5 * heldout[i] - heldout[i + 1] + 0.25 * heldout[i + 2] + 0.1 for i in range(4)]
    heldout_error = max(abs(a - b) for a, b in zip(predictions, oracle))
    parameter_error = max(abs(p.data - wanted) for p, wanted in zip(parameters, true_kernel + [true_bias]))
    # One-step right shift with zero fill keeps interior equivariance but crops a boundary.
    base = [v.data for v in cross_correlation([1., 2., 3., 4.], [1., -1.])]
    shifted = [v.data for v in cross_correlation([0., 1., 2., 3.], [1., -1.])]
    shifted_output = [0.0] + base[:-1]
    require(shifted[1:] == shifted_output[1:] and shifted[0] != shifted_output[0],
            "translation boundary counterexample failed")
    require(error < 1e-6 and final < 1e-8 and heldout_error < 1e-4 and parameter_error < 1e-4,
            "convolution learning/oracle gate failed")
    return result("convolution", {"gradient_max_abs_error_lt": 1e-6, "learned_kernel": true_kernel,
                                  "learned_bias": true_bias, "heldout_max_abs_error_lt": 1e-4,
                                  "full_finite_array_translation_equivariance": False},
                  {"steps": 300, "initial_mse": rounded(initial), "final_mse": rounded(final),
                   "learned_kernel": [rounded(p.data) for p in kernel], "learned_bias": rounded(bias.data),
                   "gradient_max_abs_error": rounded(error), "heldout_max_abs_error": rounded(heldout_error),
                   "shifted_input_output": shifted, "shifted_output": shifted_output},
                  ["Actual shared three-tap filter and bias training, with held-out signal.",
                   "Valid stride-one cross-correlation, not mathematical kernel-flipped convolution.",
                   "Interior shift relation does not imply exact equivariance at a cropped/zero-filled boundary.",
                   "One linear convolutional layer; no pooling/classification, LeNet, or full CNN paper reproduction."])


def sequence_lab() -> dict:
    model = RNN()
    training = [0, 1, 2, 0, 1, 2, 0, 1, 2, 0]
    objective = lambda: model.loss(training)
    error = gradient_check(objective, model.parameters)
    initial_parameters = [p.data for p in model.parameters]
    initial, final = train(objective, Adam(model.parameters, 0.04), 100)
    # Held out by sequence/length, not by transition or vocabulary.
    heldout = [1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1]
    logits = model.forward(heldout[:-1])
    predictions = [max(range(3), key=lambda i: row[i].data) for row in logits]
    correct = sum(a == b for a, b in zip(predictions, heldout[1:]))
    heldout_ce = model.loss(heldout).data
    left = model.forward([0, 1, 2, 0])
    right = model.forward([0, 1, 1, 1])
    prefix_difference = max(abs(a.data - b.data) for lr, rr in zip(left[:2], right[:2])
                            for a, b in zip(lr, rr))
    changed = any(p.data != original for p, original in zip(model.parameters, initial_parameters))
    require(error < 1e-6 and final < initial * 0.1 and correct == 12
            and prefix_difference == 0.0 and changed, "sequence learning/causality gate failed")
    # One autonomous rollout is reported separately from teacher-forced metrics.
    rollout = [0]
    for _ in range(12):
        row = model.forward(rollout)[-1]
        rollout.append(max(range(3), key=lambda i: row[i].data))
    expected_rollout = [i % 3 for i in range(13)]
    require(rollout == expected_rollout, "bounded greedy rollout failed")
    return result("sequence", {"gradient_max_abs_error_lt": 1e-6, "heldout_teacher_forced_correct": 12,
                               "prefix_max_abs_difference": 0.0, "greedy_rollout": expected_rollout},
                  {"steps": 100, "parameters": len(model.parameters), "initial_cross_entropy": rounded(initial),
                   "final_cross_entropy": rounded(final), "heldout_cross_entropy": rounded(heldout_ce),
                   "heldout_teacher_forced_correct": correct, "gradient_max_abs_error": rounded(error),
                   "prefix_max_abs_difference": prefix_difference, "parameters_changed": changed,
                   "greedy_rollout": rollout},
                  ["Actual three-symbol/four-hidden-unit Elman RNN with full BPTT and reset initial state.",
                   "Teacher-forced heldout uses a different phase/length but the same deterministic transitions.",
                   "This first-order periodic fixture does not establish useful long-term memory or language generalization.",
                   "One bounded greedy rollout is not a robust generation evaluation. No LSTM/GRU, attention, or Transformer."])


LABS: dict[str, Callable[[], dict]] = {"backprop": backprop_lab, "optimization": optimization_lab,
                                    "convolution": convolution_lab, "sequence": sequence_lab}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab", choices=[*LABS, "all"], default="all")
    args = parser.parse_args(argv)
    try:
        for name in LABS if args.lab == "all" else [args.lab]:
            print(json.dumps(LABS[name](), ensure_ascii=False, allow_nan=False, sort_keys=True))
    except (ValueError, ArithmeticError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
