"""Ten portfolio-construction methods.

Each function takes a `data` dict produced by `utils.align_inputs` and
returns a numpy array of weights (NOT projected to the box — that is the
caller's job).
"""
from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.optimize import minimize
from scipy.spatial.distance import squareform


# --------------------------------------------------------------------------
# Heuristics
# --------------------------------------------------------------------------

def equal_weight(data: dict) -> np.ndarray:
    n = data["n"]
    return np.ones(n) / n


def inverse_vol(data: dict) -> np.ndarray:
    inv = 1.0 / np.maximum(data["sigma"], 1e-6)
    return inv / inv.sum()


# --------------------------------------------------------------------------
# Optimisation-based
# --------------------------------------------------------------------------

def _solve_qp(cov: np.ndarray, mu: np.ndarray | None,
              min_w: np.ndarray, max_w: np.ndarray,
              risk_aversion: float | None = None) -> np.ndarray:
    """Long-only sum-to-one MVO solver via SLSQP."""
    n = cov.shape[0]
    bounds = [(float(lo), float(hi)) for lo, hi in zip(min_w, max_w)]
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]

    def obj(w):
        risk = w @ cov @ w
        if mu is None or risk_aversion is None:
            return risk
        return -(w @ mu) + risk_aversion * risk

    x0 = np.ones(n) / n
    res = minimize(obj, x0, method="SLSQP", bounds=bounds,
                   constraints=cons, options={"maxiter": 200, "ftol": 1e-9})
    return res.x if res.success else x0


def min_variance(data: dict) -> np.ndarray:
    return _solve_qp(data["cov"], None, data["min_w"], data["max_w"])


def max_sharpe(data: dict) -> np.ndarray:
    n = data["n"]
    bounds = [(float(lo), float(hi)) for lo, hi in zip(data["min_w"], data["max_w"])]
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    rf = 0.04

    def neg_sharpe(w):
        ret = w @ data["mu"] - rf
        vol = np.sqrt(max(w @ data["cov"] @ w, 1e-12))
        return -ret / vol

    x0 = np.ones(n) / n
    res = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds,
                   constraints=cons, options={"maxiter": 300, "ftol": 1e-9})
    return res.x if res.success else x0


def mvo_constrained(data: dict, risk_aversion: float = 5.0) -> np.ndarray:
    return _solve_qp(data["cov"], data["mu"], data["min_w"], data["max_w"],
                     risk_aversion=risk_aversion)


def max_diversification(data: dict) -> np.ndarray:
    n = data["n"]
    bounds = [(float(lo), float(hi)) for lo, hi in zip(data["min_w"], data["max_w"])]
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]

    def neg_div(w):
        vol = np.sqrt(max(w @ data["cov"] @ w, 1e-12))
        wsig = w @ data["sigma"]
        return -wsig / vol

    x0 = inverse_vol(data)
    res = minimize(neg_div, x0, method="SLSQP", bounds=bounds,
                   constraints=cons, options={"maxiter": 300, "ftol": 1e-9})
    return res.x if res.success else x0


# --------------------------------------------------------------------------
# Risk-based
# --------------------------------------------------------------------------

def risk_parity(data: dict) -> np.ndarray:
    """Equal risk contribution via convex Newton iteration."""
    cov = data["cov"]
    n = data["n"]
    w = np.ones(n) / n
    target = 1.0 / n
    for _ in range(500):
        port_vol = float(np.sqrt(max(w @ cov @ w, 1e-12)))
        mrc = cov @ w / port_vol  # marginal risk contribution
        rc = w * mrc / port_vol   # risk contribution shares
        if np.max(np.abs(rc - target)) < 1e-7:
            break
        # multiplicative update
        w = w * (target / np.maximum(rc, 1e-12)) ** 0.5
        w = np.maximum(w, 1e-8)
        w = w / w.sum()
    return w


def hrp(data: dict) -> np.ndarray:
    """Lopez de Prado (2016) Hierarchical Risk Parity."""
    cov = data["cov"]
    n = data["n"]
    if n == 1:
        return np.ones(1)

    # Correlation distance matrix
    sd = np.sqrt(np.diag(cov))
    corr = cov / np.outer(sd, sd)
    corr = np.clip(corr, -1.0, 1.0)
    dist = np.sqrt(0.5 * (1.0 - corr))
    np.fill_diagonal(dist, 0.0)

    # Hierarchical clustering
    condensed = squareform(dist, checks=False)
    link = linkage(condensed, method="single")

    # Quasi-diagonalisation
    def get_quasi_diag(link):
        link = link.astype(int)
        sort_ix = list(link[-1, 0:2])
        num_items = link[-1, 3]
        while max(sort_ix) >= num_items:
            new_ix = []
            for i in sort_ix:
                if i < num_items:
                    new_ix.append(i)
                else:
                    j = i - num_items
                    new_ix.append(int(link[j, 0]))
                    new_ix.append(int(link[j, 1]))
            sort_ix = new_ix
        return sort_ix

    sort_ix = get_quasi_diag(link)

    # Recursive bisection
    def cluster_var(c, idx):
        sub = c[np.ix_(idx, idx)]
        ivp = 1.0 / np.diag(sub)
        ivp /= ivp.sum()
        return float(ivp @ sub @ ivp)

    weights = np.ones(n)
    clusters = [sort_ix]
    while clusters:
        new_clusters = []
        for cl in clusters:
            if len(cl) <= 1:
                continue
            mid = len(cl) // 2
            left, right = cl[:mid], cl[mid:]
            v_left = cluster_var(cov, left)
            v_right = cluster_var(cov, right)
            alpha = 1.0 - v_left / (v_left + v_right)
            for i in left:
                weights[i] *= alpha
            for i in right:
                weights[i] *= (1.0 - alpha)
            new_clusters.extend([left, right])
        clusters = new_clusters
    return weights / weights.sum()


# --------------------------------------------------------------------------
# View-based
# --------------------------------------------------------------------------

def black_litterman(data: dict, tau: float = 0.05,
                    market_weights: np.ndarray | None = None) -> np.ndarray:
    """Black-Litterman with regime-implied views.

    Equilibrium prior is implied by market weights (defaults to inverse-vol).
    Each asset's CMA expected return is treated as an absolute view, with
    confidence drawn from `cmas[i].confidence`.
    """
    cov = data["cov"]
    n = data["n"]
    if market_weights is None:
        market_weights = inverse_vol(data)

    # Risk-aversion implied by 6% equity risk premium / market vol
    delta = 3.0
    pi = delta * cov @ market_weights  # equilibrium expected excess returns

    # Each asset is its own view (P = identity)
    P = np.eye(n)
    Q = data["mu"]
    confidence = np.maximum(data["confidence"], 0.05)
    # View uncertainty: lower confidence → larger Ω
    Omega = np.diag(np.diag(P @ (tau * cov) @ P.T) / confidence)

    tcov = tau * cov
    inv_omega = np.linalg.inv(Omega)
    inv_tcov = np.linalg.inv(tcov)
    M = np.linalg.inv(inv_tcov + P.T @ inv_omega @ P)
    bl_mu = M @ (inv_tcov @ pi + P.T @ inv_omega @ Q)

    # Plug back into MVO
    w = np.linalg.solve(delta * (cov + M), bl_mu)
    if (w < 0).any() or w.sum() <= 0:
        w = np.maximum(w, 0)
        if w.sum() <= 0:
            return inverse_vol(data)
    return w / w.sum()


# --------------------------------------------------------------------------
# Total Portfolio Allocation (regime-tilted RP)
# --------------------------------------------------------------------------

def tpa(data: dict, regime: str = "expansion") -> np.ndarray:
    """Risk-parity baseline with a regime-conditional equity/defensive tilt."""
    base = risk_parity(data)
    sigma = data["sigma"]
    # crude bucket: high vol = "growth-like", low vol = "defensive"
    growth_mask = sigma > np.median(sigma)
    tilt = {
        "expansion": +0.10,
        "late_cycle": -0.05,
        "recession": -0.20,
        "recovery": +0.10,
    }.get(regime, 0.0)

    if abs(tilt) < 1e-9:
        return base

    growth_w = base[growth_mask].sum()
    defensive_w = base[~growth_mask].sum()
    if growth_w == 0 or defensive_w == 0:
        return base

    new = base.copy()
    delta = tilt * min(growth_w, defensive_w)
    new[growth_mask] += delta * (base[growth_mask] / growth_w)
    new[~growth_mask] -= delta * (base[~growth_mask] / defensive_w)
    new = np.maximum(new, 0)
    return new / new.sum()


METHODS = {
    "equal_weight": equal_weight,
    "inverse_vol": inverse_vol,
    "min_variance": min_variance,
    "max_sharpe": max_sharpe,
    "risk_parity": risk_parity,
    "hrp": hrp,
    "max_diversification": max_diversification,
    "black_litterman": black_litterman,
    "mvo_constrained": mvo_constrained,
    "tpa": tpa,
}
