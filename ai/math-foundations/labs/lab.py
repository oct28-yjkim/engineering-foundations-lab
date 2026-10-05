"""Bounded, offline math checks. No packages, files, network or model training."""
from __future__ import annotations

import argparse
import json
import math


class LabError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise LabError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def vector(values):
    require(isinstance(values, (list, tuple)) and 1 <= len(values) <= 32,
            "vector must have 1..32 elements")
    require(all(finite(v) for v in values), "finite numeric elements required")


def dot(a, b):
    vector(a)
    vector(b)
    require(len(a) == len(b), "dot dimension mismatch")
    result = sum(x * y for x, y in zip(a, b))
    require(finite(result), "nonfinite dot result")
    return result


def matrix(values):
    require(isinstance(values, (list, tuple)) and 1 <= len(values) <= 16,
            "matrix must have 1..16 rows")
    for row in values:
        vector(row)
    require(all(len(row) == len(values[0]) for row in values), "ragged matrix")


def matmul(a, b):
    matrix(a)
    matrix(b)
    require(len(a[0]) == len(b), "matrix dimension mismatch")
    return [[dot(row, column) for column in zip(*b)] for row in a]


def projection(x, direction):
    denominator = dot(direction, direction)
    require(denominator > 0, "zero direction has no projection axis")
    coefficient = dot(x, direction) / denominator
    result = [coefficient * value for value in direction]
    vector(result)
    return result


def central_difference(function, value, step=1e-5):
    require(finite(value) and finite(step) and step > 0, "invalid finite difference inputs")
    left, right = function(value - step), function(value + step)
    require(finite(left) and finite(right), "nonfinite objective")
    result = (right - left) / (2 * step)
    require(finite(result), "nonfinite derivative")
    return result


def posterior(prior, true_positive_rate, false_positive_rate):
    values = (prior, true_positive_rate, false_positive_rate)
    require(all(finite(v) and 0 <= v <= 1 for v in values), "probabilities must be in [0,1]")
    joint = prior * true_positive_rate
    evidence = joint + (1 - prior) * false_positive_rate
    require(evidence > 0, "conditioning event has zero probability")
    return joint / evidence


def variance(values, ddof=0):
    vector(values)
    require(type(ddof) is int and ddof in (0, 1) and len(values) > ddof,
            "invalid variance denominator")
    mean = sum(values) / len(values)
    result = sum((x - mean) ** 2 for x in values) / (len(values) - ddof)
    require(finite(result), "nonfinite variance")
    return result


def token_nll(probabilities):
    vector(probabilities)
    require(all(0 < p <= 1 for p in probabilities), "positive target probabilities required")
    return -sum(math.log(p) for p in probabilities) / len(probabilities)


def quadratic(point):
    vector(point)
    require(len(point) == 2, "two coordinates required")
    return 0.5 * (point[0] ** 2 + 100 * point[1] ** 2)


def gradient_step(point, rate):
    vector(point)
    require(len(point) == 2 and finite(rate) and rate > 0, "invalid gradient step")
    result = [point[0] * (1 - rate), point[1] * (1 - 100 * rate)]
    vector(result)
    return result


def logsumexp(values):
    vector(values)
    peak = max(values)
    return peak + math.log(sum(math.exp(v - peak) for v in values))


def same(actual, expected):
    require(finite(actual) and math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-8),
            "independent oracle mismatch")


def vectors_lab():
    product = matmul([[1, 2], [3, 4]], [[2, 0, 1], [0, 1, -1]])
    require(product == [[2, 2, -1], [6, 4, -1]], "literal matrix oracle mismatch")
    projected = projection([3, 4], [2, 0])
    residual = [value - fitted for value, fitted in zip([3, 4], projected)]
    same(dot([1, 2], [3, -1]), 1)
    require(projected == [3, 0], "literal projection oracle mismatch")
    same(dot(residual, [2, 0]), 0)
    try:
        dot([1, 2], [1])
    except LabError:
        mismatch_rejected = True
    else:
        mismatch_rejected = False
    require(mismatch_rejected, "dimension failure not detected")
    return {"expected": {"dot": 1, "projection": [3, 0], "residual_dot_axis": 0},
            "observed": {"dot": dot([1, 2], [3, -1]), "matmul": product,
                         "projection": projected, "residual": residual,
                         "dimension_mismatch_rejected": mismatch_rejected},
            "scope": "Small vector/matrix and orthogonal projection checks; no embedding quality claim."}


def derivatives_lab():
    objective = lambda w: (2 * w - 3) ** 2 / 2
    derivative = central_difference(objective, 1)
    same(derivative, -2)
    shared = central_difference(lambda w: (2 * w) ** 2 + 2 * w, 3)
    same(shared, 26)
    # Mean of per-example half squared errors, not a sum.
    loss = lambda w, b: ((w + b - 2) ** 2 + (2 * w + b - 3) ** 2) / 4
    dw = central_difference(lambda w: loss(w, 0), 1)
    db = central_difference(lambda b: loss(1, b), 0)
    same(dw, -1.5)
    same(db, -1)
    relu_center = central_difference(lambda w: max(0, w), 0)
    same(relu_center, 0.5)
    return {"expected": {"scalar_gradient": -2, "shared_gradient": 26,
                         "mean_half_mse_gradient": [-1.5, -1]},
            "observed": {"scalar_gradient": derivative, "shared_gradient": shared,
                         "mean_half_mse_gradient": [dw, db],
                         "finite_difference_errors": [
                             {"h": h, "error": abs(central_difference(objective, 1, h) + 2)}
                             for h in (1e-2, 1e-4, 1e-6, 1e-8)],
                         "relu_central_at_zero": relu_center,
                         "relu_left_slope": 0, "relu_right_slope": 1},
            "scope": "ReLU has NO derivative at zero; central value 0.5 is not its derivative. No autodiff engine."}


def probability_lab():
    value = posterior(0.01, 0.9, 0.05)
    same(value, 2 / 13)
    same(variance([1, 3]), 1)
    same(variance([1, 3], 1), 2)
    nll = token_nll([0.5, 0.25])
    same(math.exp(nll), math.sqrt(8))
    return {"expected": {"positive_predictive_probability": 2 / 13,
                         "population_variance": 1, "sample_variance": 2,
                         "perplexity": math.sqrt(8)},
            "observed": {"positive_predictive_probability": value,
                         "synthetic_counts": {"items": 10000, "true_positive": 90, "false_positive": 495},
                         "population_variance": variance([1, 3]),
                         "sample_variance": variance([1, 3], 1),
                         "mean_target_nll_nats": nll, "perplexity": math.exp(nll)},
            "scope": "Synthetic part-quality check, not observed prevalence. NLL uses target probabilities, not a full distribution."}


def optimization_lab():
    start = [1, 1]
    slow = gradient_step(start, 0.01)
    unstable = gradient_step(start, 0.03)
    same(quadratic(start), 50.5)
    same(quadratic(slow), 0.49005)
    same(quadratic(unstable), 200.47045)
    path = list(start)
    for _ in range(100):
        path = gradient_step(path, 0.01)
    same(path[0], 0.99 ** 100)
    same(path[1], 0)
    stable = logsumexp([1000, 999])
    same(stable, 1000 + math.log1p(math.exp(-1)))
    try:
        math.exp(1000)
    except OverflowError:
        naive_overflow = True
    else:
        naive_overflow = False
    require(naive_overflow, "overflow counterexample missing")
    return {"expected": {"initial_loss": 50.5, "rate_0_01_first_loss": 0.49005,
                         "rate_0_03_first_loss": 200.47045, "hessian_eigenvalue_ratio": 100},
            "observed": {"initial_loss": quadratic(start), "rate_0_01_first_loss": quadratic(slow),
                         "rate_0_03_first_loss": quadratic(unstable), "stable_100_steps": path,
                         "stable_100_steps_loss": quadratic(path), "logsumexp": stable,
                         "naive_exp_overflow": naive_overflow},
            "scope": "Two-coordinate quadratic and stable arithmetic; not neural training or an optimizer benchmark."}


LABS = {"vectors": vectors_lab, "derivatives": derivatives_lab,
        "probability": probability_lab, "optimization": optimization_lab}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise LabError("invalid CLI option")


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument("--lab", choices=["all", *LABS], default="all")
    try:
        args = parser.parse_args(argv)
        selected = LABS if args.lab == "all" else {args.lab: LABS[args.lab]}
        results = [{"lab": name, "status": "PASS", **function()}
                   for name, function in selected.items()]
        print(json.dumps({"mode": "MATH_ORACLES", "network_calls": 0, "file_writes": 0,
                          "results": results}, allow_nan=False))
        return 0
    except (LabError, OverflowError):
        print(json.dumps({"status": "FAIL", "reason": "math or input contract failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
