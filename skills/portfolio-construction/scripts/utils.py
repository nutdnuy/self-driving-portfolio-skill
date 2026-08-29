"""Shared utilities for portfolio-construction methods."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from pipeline.ips import parse_ips  # noqa: E402, F401

RISK_FREE_RATE = 0.04


def project_to_box(w: np.ndarray, min_w: np.ndarray, max_w: np.ndarray,
                   max_iter: int = 200, tol: float = 1e-9) -> np.ndarray:
    """Project exactly onto ``{x: sum(x)=1, min_w <= x <= max_w}``.

    Solve the Euclidean projection with a monotone Lagrange-multiplier
    bisection. Reject impossible IPS bounds instead of returning a misleading
    almost-feasible vector.
    """
    w = np.array(w, dtype=float)
    min_w = np.array(min_w, dtype=float)
    max_w = np.array(max_w, dtype=float)
    if w.ndim != 1 or min_w.shape != w.shape or max_w.shape != w.shape:
        raise ValueError("w, min_w, and max_w must be one-dimensional arrays of equal length")
    if not np.isfinite(w).all() or not np.isfinite(min_w).all() or not np.isfinite(max_w).all():
        raise ValueError("Projection inputs must be finite")
    if (min_w > max_w).any() or min_w.sum() > 1.0 + tol or max_w.sum() < 1.0 - tol:
        raise ValueError("Cannot project onto infeasible IPS box constraints")

    lower_lambda = float(np.min(w - max_w))
    upper_lambda = float(np.max(w - min_w))
    projected = np.clip(w, min_w, max_w)
    for _ in range(max_iter):
        lagrange = (lower_lambda + upper_lambda) / 2.0
        projected = np.clip(w - lagrange, min_w, max_w)
        total = float(projected.sum())
        if abs(total - 1.0) <= tol:
            break
        if total > 1.0:
            lower_lambda = lagrange
        else:
            upper_lambda = lagrange
    if abs(float(projected.sum()) - 1.0) > max(tol, 1e-8):
        raise RuntimeError("Box projection failed to converge")
    return projected


def is_feasible(w: np.ndarray, min_w: np.ndarray, max_w: np.ndarray,
                tol: float = 1e-8) -> bool:
    return (
        abs(w.sum() - 1.0) < tol
        and (w >= min_w - tol).all()
        and (w <= max_w + tol).all()
    )


def portfolio_metrics(w: np.ndarray, mu: np.ndarray, sigma: np.ndarray,
                      cov: np.ndarray, rf: float = RISK_FREE_RATE) -> dict:
    exp_ret = float(w @ mu)
    var = float(w @ cov @ w)
    vol = float(np.sqrt(max(var, 0.0)))
    sharpe = (exp_ret - rf) / vol if vol > 1e-9 else 0.0
    eff_n = 1.0 / float(np.sum(w ** 2)) if np.sum(w ** 2) > 0 else 0.0
    div_ratio = float((w @ sigma) / vol) if vol > 1e-9 else 1.0
    return {
        "expected_return": exp_ret,
        "volatility": vol,
        "sharpe": float(sharpe),
        "max_weight": float(w.max()),
        "effective_n": float(eff_n),
        "diversification_ratio": div_ratio,
    }


def align_inputs(cmas: dict, cov_obj: dict, ips: dict) -> dict:
    """Align inputs in IPS order and reject any silent universe shrinkage."""
    if cmas.get("as_of") != cov_obj.get("as_of"):
        raise ValueError(
            f"CMA/covariance as_of mismatch: {cmas.get('as_of')} != {cov_obj.get('as_of')}"
        )
    cmas_by_t = {c["ticker"]: c for c in cmas["cmas"]}
    cov_tickers = cov_obj["tickers"]
    cov_idx = {t: i for i, t in enumerate(cov_tickers)}

    ips_tickers = ips["tickers"]
    if set(cmas_by_t) != set(ips_tickers) or set(cov_tickers) != set(ips_tickers):
        raise ValueError(
            "CMA and covariance universes must exactly match the IPS universe; "
            f"IPS={ips_tickers}, CMA={list(cmas_by_t)}, covariance={cov_tickers}"
        )
    if len(cmas_by_t) != len(cmas["cmas"]) or len(cov_idx) != len(cov_tickers):
        raise ValueError("CMA and covariance ticker lists must be unique")
    chosen = list(ips_tickers)
    n = len(chosen)
    mu = np.array([cmas_by_t[t]["expected_return"] for t in chosen])
    sigma = np.array([cmas_by_t[t]["volatility"] for t in chosen])
    confidence = np.array([cmas_by_t[t]["confidence"] for t in chosen])

    # Pull the sub-matrix in `chosen` order
    full = np.array(cov_obj["covariance"])
    if full.shape != (len(cov_tickers), len(cov_tickers)):
        raise ValueError("Covariance dimensions do not match its ticker list")
    idx = [cov_idx[t] for t in chosen]
    cov = full[np.ix_(idx, idx)]

    # Map IPS box constraints
    ips_idx = {t: i for i, t in enumerate(ips_tickers)}
    min_w = np.array([ips["min_w"][ips_idx[t]] for t in chosen])
    max_w = np.array([ips["max_w"][ips_idx[t]] for t in chosen])

    aligned = {
        "tickers": chosen,
        "n": n,
        "mu": mu,
        "sigma": sigma,
        "confidence": confidence,
        "cov": cov,
        "min_w": min_w,
        "max_w": max_w,
    }
    for name in ("mu", "sigma", "confidence", "cov", "min_w", "max_w"):
        if not np.isfinite(aligned[name]).all():
            raise ValueError(f"Aligned input {name} contains NaN or Infinity")
    return aligned
