"""Deterministic, bounded ML experiments: Python 3.10+ standard library only.

Real small fits on synthetic data, not paper-scale reproductions. No file or
network operations, downloads, external models, or packages are required.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time

LABS = ("ridge", "classification", "ensembles", "representation")
MAX_SAMPLES = 128


class LabError(Exception):
    """Explicit experiment failure, including under python -O."""


def require(condition, message):
    if not condition:
        raise LabError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def bounded_int(value, low, high, name):
    require(type(value) is int and low <= value <= high, "invalid_" + name)


def vector(values, name="vector"):
    require(isinstance(values, (list, tuple)) and 1 <= len(values) <= MAX_SAMPLES,
            "invalid_" + name + "_length")
    require(all(finite(v) for v in values), "nonfinite_" + name)


def paired(xs, ys, binary=False):
    vector(xs, "features")
    vector(ys, "targets")
    require(len(xs) == len(ys), "length_mismatch")
    if binary:
        require(all(type(y) is int and y in (0, 1) for y in ys), "nonbinary_labels")


def mean(values):
    return sum(values) / len(values)


def close(actual, expected, tolerance=1e-9):
    return math.isclose(actual, expected, abs_tol=tolerance, rel_tol=tolerance)


def check(condition, code):
    require(condition, "oracle_failed_" + code)


def fit_scaler(xs):
    vector(xs)
    center = mean(xs)
    scale = math.sqrt(mean([(x - center) ** 2 for x in xs]))
    require(scale > 1e-12, "constant_feature")
    return center, scale


def transform(xs, scaler):
    vector(xs)
    center, scale = scaler
    require(finite(center) and finite(scale) and scale > 0, "invalid_scaler")
    return [(x - center) / scale for x in xs]


def fit_ridge(xs, ys, alpha):
    """1D SSE + alpha*w^2; intercept is fitted and is NOT penalized."""
    paired(xs, ys)
    require(finite(alpha) and alpha >= 0, "invalid_alpha")
    mx, my = mean(xs), mean(ys)
    variance_sum = sum((x - mx) ** 2 for x in xs)
    denominator = variance_sum + alpha
    require(finite(denominator) and denominator > 0, "singular_design")
    w = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominator
    return w, my - w * mx


def predict_linear(model, xs):
    return [model[0] * x + model[1] for x in xs]


def mse(predictions, targets):
    paired(predictions, targets)
    return mean([(p - y) ** 2 for p, y in zip(predictions, targets)])


def ridge_lab(seed=17, **_):
    # No randomness is needed for this exact algebraic counterexample.
    train_x, train_y = [-2, -1, 0, 1, 2], [-3, -1, 1, 3, 5]
    test_x, test_y = [3, 4], [7, 9]
    scaler = fit_scaler(train_x)
    train_z, test_z = transform(train_x, scaler), transform(test_x, scaler)
    ols, ridge = fit_ridge(train_z, train_y, 0), fit_ridge(train_z, train_y, 2)
    ols_mse = mse(predict_linear(ols, test_z), test_y)
    ridge_mse = mse(predict_linear(ridge, test_z), test_y)
    # Intentionally wrong: held-out features enter preprocessing fit.
    leaked_scaler = fit_scaler(train_x + test_x)
    leaked_z = transform(train_x, leaked_scaler)
    leaked_model = fit_ridge(leaked_z, train_y, 2)
    leaked_mse = mse(predict_linear(leaked_model, transform(test_x, leaked_scaler)), test_y)
    leaked_ols = fit_ridge(leaked_z, train_y, 0)
    leaked_ols_mse = mse(predict_linear(leaked_ols, transform(test_x, leaked_scaler)), test_y)
    check(close(ols_mse, 0) and close(ridge_mse, 200 / 49), "ridge_mse")
    check(close(leaked_mse, 800 / 81), "leakage_changes_regularized_fit")
    check(close(mean(train_z), 0) and close(mean(leaked_z), -.5), "scaler_provenance")
    check(abs(ridge[0]) < abs(ols[0]), "coefficient_shrinkage")
    check(close(leaked_ols_mse, ols_mse), "ols_affine_scaling_invariance")
    return {
        "expected": {"train_scaler_mean": 0, "leaked_scaler_mean": 1,
                     "ols_test_mse": 0, "ridge_test_mse": 200 / 49,
                     "leaked_ridge_test_mse": 800 / 81, "ridge_helps_every_holdout": False},
        "observed": {"train_scaler": scaler, "leaked_scaler": leaked_scaler,
                     "train_z_mean": mean(train_z), "leaked_train_z_mean": mean(leaked_z),
                     "ols_model_on_train_z": ols, "ridge_model_on_train_z": ridge,
                     "ols_test_mse": ols_mse, "ridge_test_mse": ridge_mse,
                     "leaked_ridge_test_mse": leaked_mse, "leaked_ols_test_mse": leaked_ols_mse},
        "scope": "Real 1D closed-form fit; SSE penalty, unpenalized intercept; leakage demo only. "
                 "Affine scaling alone does not change this OLS fit. No universal generalization claim.",
    }


def sigmoid(logit):
    require(finite(logit), "nonfinite_logit")
    if logit >= 0:
        return 1 / (1 + math.exp(-logit))
    exponential = math.exp(logit)
    return exponential / (1 + exponential)


def logistic_loss_gradient(xs, ys, w, b, l2=0):
    paired(xs, ys, binary=True)
    require(all(finite(v) for v in (w, b, l2)) and l2 >= 0, "invalid_logistic_parameters")
    logits = [w * x + b for x in xs]
    require(all(finite(z) for z in logits), "nonfinite_logit")
    losses = [max(z, 0) - y * z + math.log1p(math.exp(-abs(z))) for z, y in zip(logits, ys)]
    errors = [sigmoid(z) - y for z, y in zip(logits, ys)]
    return (mean(losses) + .5 * l2 * w * w,
            (mean([e * x for e, x in zip(errors, xs)]) + l2 * w, mean(errors)))


def fit_logistic(xs, ys, seed=17, epochs=120, rate=.05, l2=.02):
    paired(xs, ys, binary=True)
    bounded_int(seed, 0, 2 ** 32 - 1, "seed")
    bounded_int(epochs, 1, 500, "epochs")
    require(finite(rate) and 0 < rate <= 1 and finite(l2) and l2 >= 0, "invalid_sgd_parameters")
    rng, w, b = random.Random(seed), 0.0, 0.0
    order = list(range(len(xs)))
    for _ in range(epochs):
        rng.shuffle(order)
        for i in order:
            error = sigmoid(w * xs[i] + b) - ys[i]
            w, b = w - rate * (error * xs[i] + l2 * w), b - rate * error
    require(finite(w) and finite(b), "nonfinite_fit")
    return w, b


def probability_metrics(probabilities, ys):
    paired(probabilities, ys, binary=True)
    require(all(0 <= p <= 1 for p in probabilities), "invalid_probability")
    return {"accuracy": mean([int((p >= .5) == y) for p, y in zip(probabilities, ys)]),
            "brier": mean([(p - y) ** 2 for p, y in zip(probabilities, ys)]),
            "positive_recall": (sum(p >= .5 and y == 1 for p, y in zip(probabilities, ys)) / sum(ys)
                                if sum(ys) else None)}


def gradient_error(xs, ys, w, b, l2=.1):
    epsilon = 1e-6
    _, analytic = logistic_loss_gradient(xs, ys, w, b, l2)
    dw = (logistic_loss_gradient(xs, ys, w + epsilon, b, l2)[0] -
          logistic_loss_gradient(xs, ys, w - epsilon, b, l2)[0]) / (2 * epsilon)
    db = (logistic_loss_gradient(xs, ys, w, b + epsilon, l2)[0] -
          logistic_loss_gradient(xs, ys, w, b - epsilon, l2)[0]) / (2 * epsilon)
    return max(abs(analytic[0] - dw), abs(analytic[1] - db))


def classification_lab(seed=17, epochs=120, **_):
    xs, ys = [-3, -2, -1, 1, 2, 3], [0, 0, 0, 1, 1, 1]
    model = fit_logistic(xs, ys, seed, epochs)
    initial_loss = logistic_loss_gradient(xs, ys, 0, 0, .02)[0]
    final_loss = logistic_loss_gradient(xs, ys, *model, l2=.02)[0]
    holdout_x, holdout_y = [-2.5, -.5, .5, 2.5], [0, 0, 1, 1]
    holdout = probability_metrics([sigmoid(model[0] * x + model[1]) for x in holdout_x], holdout_y)
    holdout["log_loss"] = logistic_loss_gradient(holdout_x, holdout_y, *model)[0]
    error = gradient_error(xs, ys, .7, -.2)
    imbalanced = [0] * 19 + [1]
    overconfident = probability_metrics([.01] * 20, imbalanced)
    prevalence = probability_metrics([.05] * 20, imbalanced)
    check(final_loss < initial_loss, "logistic_learning")
    check(error < 1e-7, "logistic_gradient")
    check(close(overconfident["accuracy"], .95) and close(prevalence["accuracy"], .95), "imbalance_accuracy")
    check(close(overconfident["brier"], .0491) and close(prevalence["brier"], .0475), "imbalance_brier")
    return {
        "expected": {"initial_regularized_loss": math.log(2), "loss_decreases_on_this_fixture": True,
                     "gradient_max_error_below": 1e-7, "both_constant_accuracy": .95,
                     "constant_p01_brier": .0491, "constant_p05_brier": .0475},
        "observed": {"model": model, "epochs": epochs, "sgd_steps": epochs * len(xs),
                     "initial_regularized_loss": initial_loss, "final_regularized_loss": final_loss,
                     "heldout_metrics": holdout, "gradient_max_error": error,
                     "constant_p01": overconfident, "constant_p05": prevalence},
        "scope": "Actual stable binary logistic SGD; separable tiny fixture, not population calibration. "
                 "Regularized training loss, held-out log loss, accuracy and Brier are different metrics.",
    }


def gini(labels):
    p = mean(labels)
    return 2 * p * (1 - p)


def fit_stump(xs, ys):
    """1D CART-style weighted-Gini split; ascending-threshold tie break."""
    paired(xs, ys, binary=True)
    unique = sorted(set(xs))
    base = {"threshold": None, "left_probability": mean(ys),
            "right_probability": mean(ys), "weighted_gini": gini(ys)}
    best = None
    for a, b in zip(unique, unique[1:]):
        threshold = a / 2 + b / 2
        left = [y for x, y in zip(xs, ys) if x <= threshold]
        right = [y for x, y in zip(xs, ys) if x > threshold]
        require(left and right, "invalid_stump_partition")
        impurity = (len(left) * gini(left) + len(right) * gini(right)) / len(ys)
        candidate = {"threshold": threshold, "left_probability": mean(left),
                     "right_probability": mean(right), "weighted_gini": impurity}
        if best is None or impurity < best["weighted_gini"]:
            best = candidate
    return best if best is not None else base


def predict_stump(model, xs):
    return [model["left_probability"] if model["threshold"] is None or x <= model["threshold"]
            else model["right_probability"] for x in xs]


def fit_bagging(xs, ys, seed=17, trees=31):
    paired(xs, ys, binary=True)
    bounded_int(seed, 0, 2 ** 32 - 1, "seed")
    bounded_int(trees, 1, 101, "trees")
    rng, models, samples = random.Random(seed), [], []
    for _ in range(trees):
        indices = [rng.randrange(len(xs)) for _ in xs]
        samples.append(indices)
        models.append(fit_stump([xs[i] for i in indices], [ys[i] for i in indices]))
    return models, samples


def predict_bagging(models, xs):
    require(1 <= len(models) <= 101, "invalid_ensemble_size")
    predictions = [predict_stump(model, xs) for model in models]
    return [mean([prediction[i] for prediction in predictions]) for i in range(len(xs))]


def ensembles_lab(seed=17, trees=31, **_):
    oracle = fit_stump([0, 1, 2, 3], [0, 0, 1, 1])
    check(oracle == {"threshold": 1.5, "left_probability": 0, "right_probability": 1,
                     "weighted_gini": 0}, "literal_stump")
    xs, ys = [-3, -2, -1, 1, 2, 3], [0, 0, 0, 1, 1, 1]
    models, samples = fit_bagging(xs, ys, seed, trees)
    holdout_x, holdout_y = [-2.5, -.5, .5, 2.5], [0, 0, 1, 1]
    probabilities = predict_bagging(models, holdout_x)
    check(len(models) == trees and all(len(sample) == 6 for sample in samples), "bootstrap_size")
    check(all(0 <= p <= 1 for p in probabilities), "ensemble_probability")
    return {
        "expected": {"literal_stump_threshold": 1.5, "literal_weighted_gini": 0,
                     "trees": trees, "bootstrap_draws_per_tree": 6, "bagging_always_improves": False},
        "observed": {"literal_stump": oracle, "trees": len(models),
                     "bootstrap_unique_counts": [len(set(s)) for s in samples],
                     "heldout_probabilities": probabilities,
                     "bagging_heldout_metrics": probability_metrics(probabilities, holdout_y),
                     "single_stump_heldout_metrics": probability_metrics(predict_stump(fit_stump(xs, ys), holdout_x), holdout_y)},
        "scope": "Actual bootstrap bagging of 1D Gini stumps, averaging leaf probabilities; "
                 "NOT full CART, random-feature Random Forest, boosting, OOB evaluation or uncertainty bounds.",
    }


def points2(points):
    require(isinstance(points, (list, tuple)) and 2 <= len(points) <= MAX_SAMPLES, "invalid_points_length")
    require(all(isinstance(p, (list, tuple)) and len(p) == 2 and all(finite(v) for v in p)
                for p in points), "invalid_2d_points")


def pca2(points):
    points2(points)
    center = [mean([p[j] for p in points]) for j in range(2)]
    centered = [[p[j] - center[j] for j in range(2)] for p in points]
    a, b, c = (mean([p[0] ** 2 for p in centered]),
               mean([p[0] * p[1] for p in centered]), mean([p[1] ** 2 for p in centered]))
    require(all(finite(v) for v in (a, b, c, a + c)), "nonfinite_covariance")
    require(a + c > 0, "zero_variance")
    delta = math.hypot(a - c, 2 * b)
    eigenvalues = [(a + c + delta) / 2, max(0, (a + c - delta) / 2)]
    if b != 0:
        # An absolute off-diagonal cutoff breaks scale invariance. The angle
        # avoids subtracting nearly equal eigenvalues to form an eigenvector.
        angle = 0.5 * math.atan2(2 * b, a - c)
        direction = [math.cos(angle), math.sin(angle)]
    else:
        direction = [1, 0] if a >= c else [0, 1]
    length = math.hypot(*direction)
    direction = [v / length for v in direction]
    projections = [sum(x * v for x, v in zip(p, direction)) for p in centered]
    reconstruction = [[center[j] + z * direction[j] for j in range(2)] for z in projections]
    return {"center": center, "eigenvalues": eigenvalues, "direction": direction,
            "projections": projections, "reconstruction": reconstruction}


def distance2(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def kmeans(points, k=2, seed=17, iterations=50):
    points2(points)
    bounded_int(k, 1, min(8, len(points)), "clusters")
    bounded_int(seed, 0, 2 ** 32 - 1, "seed")
    bounded_int(iterations, 1, 100, "iterations")
    require(len(set(tuple(p) for p in points)) >= k, "too_few_distinct_points")
    rng = random.Random(seed)
    centers = [list(points[rng.randrange(len(points))])]
    # Seeded first point + deterministic farthest-first; NOT k-means++ sampling.
    while len(centers) < k:
        candidate = max(range(len(points)), key=lambda i: min(distance2(points[i], c) for c in centers))
        centers.append(list(points[candidate]))
    previous, history, converged = None, [], False
    for _ in range(iterations):
        labels = [min(range(k), key=lambda j: distance2(p, centers[j])) for p in points]
        groups = [[p for p, label in zip(points, labels) if label == j] for j in range(k)]
        require(all(groups), "empty_cluster")
        centers = [[mean([p[j] for p in group]) for j in range(2)] for group in groups]
        inertia = sum(distance2(p, centers[label]) for p, label in zip(points, labels))
        require(finite(inertia), "nonfinite_inertia")
        check(not history or inertia <= history[-1] + 1e-9, "lloyd_nonincreasing_inertia")
        history.append(inertia)
        if labels == previous:
            converged = True
            break
        previous = labels
    return {"centers": centers, "labels": labels, "inertia": inertia,
            "history": history, "iterations": len(history), "converged": converged}


def canonical_partition(labels):
    return sorted([tuple(i for i, value in enumerate(labels) if value == label) for label in set(labels)])


def representation_lab(seed=17, iterations=50, **_):
    line = [[1, 2], [2, 4], [3, 6], [4, 8]]
    pca = pca2(line)
    reference = [1 / math.sqrt(5), 2 / math.sqrt(5)]
    alignment = abs(sum(a * b for a, b in zip(pca["direction"], reference)))
    reconstruction_error = sum(distance2(a, b) for a, b in zip(line, pca["reconstruction"]))
    check(close(pca["eigenvalues"][0], 6.25) and close(pca["eigenvalues"][1], 0), "pca_eigenvalues")
    check(close(alignment, 1) and reconstruction_error < 1e-20, "pca_sign_invariant_reconstruction")
    blobs = [[0, 0], [0, 1], [1, 0], [1, 1], [8, 8], [8, 9], [9, 8], [9, 9]]
    clusters = kmeans(blobs, 2, seed, iterations)
    partition = canonical_partition(clusters["labels"])
    check(partition == [(0, 1, 2, 3), (4, 5, 6, 7)] and close(clusters["inertia"], 4), "kmeans_literal_partition")
    return {
        "expected": {"pca_population_eigenvalues": [6.25, 0], "absolute_direction_alignment": 1,
                     "kmeans_partition": [[0, 1, 2, 3], [4, 5, 6, 7]], "kmeans_inertia": 4},
        "observed": {"pca_center": pca["center"], "pca_eigenvalues": pca["eigenvalues"],
                     "absolute_direction_alignment": alignment, "pca_reconstruction_squared_error": reconstruction_error,
                     "kmeans": clusters, "canonical_partition": partition},
        "scope": "Centered 2D population covariance PCA + bounded Lloyd k-means; "
                 "sign/cluster-label invariant oracle. Farthest-first is not k-means++. "
                 "Inertia does not establish semantic quality or a global optimum on other data.",
    }


def run(lab="all", seed=17, epochs=120, trees=31, iterations=50):
    require(lab in LABS + ("all",), "unknown_lab")
    bounded_int(seed, 0, 2 ** 32 - 1, "seed")
    bounded_int(epochs, 1, 500, "epochs")
    bounded_int(trees, 1, 101, "trees")
    bounded_int(iterations, 1, 100, "iterations")
    functions = {"ridge": ridge_lab, "classification": classification_lab,
                 "ensembles": ensembles_lab, "representation": representation_lab}
    selected = LABS if lab == "all" else (lab,)
    return [{"lab": name, "seed": seed, "result": "PASS", **functions[name](
        seed=seed, epochs=epochs, trees=trees, iterations=iterations)} for name in selected]


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise LabError("invalid_arguments")


def main(argv=None):
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--lab", choices=LABS + ("all",), default="all")
        parser.add_argument("--seed", type=int, default=17)
        parser.add_argument("--epochs", type=int, default=120)
        parser.add_argument("--trees", type=int, default=31)
        parser.add_argument("--iterations", type=int, default=50)
        args = parser.parse_args(argv)
        start = time.perf_counter()
        results = run(**vars(args))
        print(json.dumps({"mode": "SMALL_ACTUAL_ML_EXPERIMENTS", "results": results,
                          "elapsed_seconds": round(time.perf_counter() - start, 6),
                          "network_calls": 0, "file_writes": 0, "paper_scale_reproduction": False},
                         ensure_ascii=False, allow_nan=False))
        return 0
    except LabError as error:
        print(json.dumps({"result": "FAIL", "code": str(error)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
