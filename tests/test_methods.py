"""Unit tests for the 10 PC methods using a small synthetic dataset.

Run:
    python -m pytest tests/
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "portfolio-construction" / "scripts"))
from methods import METHODS  # noqa: E402
from utils import is_feasible, project_to_box  # noqa: E402


def make_data(n=5, seed=0):
    rng = np.random.default_rng(seed)
    sigma = rng.uniform(0.05, 0.25, size=n)
    corr = np.full((n, n), 0.3)
    np.fill_diagonal(corr, 1.0)
    cov = corr * np.outer(sigma, sigma)
    mu = rng.uniform(0.02, 0.10, size=n)
    return {
        "n": n,
        "tickers": [f"A{i}" for i in range(n)],
        "mu": mu,
        "sigma": sigma,
        "cov": cov,
        "confidence": np.full(n, 0.7),
        "min_w": np.zeros(n),
        "max_w": np.full(n, 0.5),
    }


def test_all_methods_produce_long_only_summing_to_one():
    data = make_data()
    for name, fn in METHODS.items():
        kwargs = {"regime": "expansion"} if name == "tpa" else {}
        w = fn(data, **kwargs) if kwargs else fn(data)
        proj = project_to_box(w, data["min_w"], data["max_w"])
        assert is_feasible(proj, data["min_w"], data["max_w"]), \
            f"{name} produced infeasible weights {proj}"


def test_equal_weight_is_uniform():
    data = make_data(n=4)
    w = METHODS["equal_weight"](data)
    assert np.allclose(w, 0.25)


def test_inverse_vol_inversely_proportional():
    data = make_data()
    w = METHODS["inverse_vol"](data)
    # higher sigma → lower weight
    assert (np.argsort(w) == np.argsort(-data["sigma"])).all()


def test_min_variance_lower_or_equal_vol_than_equal_weight():
    data = make_data()
    w_min = METHODS["min_variance"](data)
    w_eq = METHODS["equal_weight"](data)
    var_min = w_min @ data["cov"] @ w_min
    var_eq = w_eq @ data["cov"] @ w_eq
    assert var_min <= var_eq + 1e-6


def test_risk_parity_equalises_risk_contributions():
    data = make_data()
    w = METHODS["risk_parity"](data)
    port_vol = float(np.sqrt(w @ data["cov"] @ w))
    rc = w * (data["cov"] @ w) / port_vol
    rc /= rc.sum()
    assert np.allclose(rc, 1.0 / data["n"], atol=5e-3)


def test_box_projection_respects_bounds():
    data = make_data(n=3)
    data["min_w"] = np.array([0.1, 0.1, 0.1])
    data["max_w"] = np.array([0.5, 0.5, 0.5])
    w = np.array([0.8, 0.1, 0.1])
    proj = project_to_box(w, data["min_w"], data["max_w"])
    assert (proj >= data["min_w"] - 1e-9).all()
    assert (proj <= data["max_w"] + 1e-9).all()
    assert abs(proj.sum() - 1.0) < 1e-6
