"""Shared utilities for portfolio-construction methods."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np


def parse_ips(ips_path: str | Path) -> dict:
    """Tiny markdown parser that extracts the asset universe table from the
    IPS template. Returns dict with keys: tickers, min_w, max_w."""
    text = Path(ips_path).read_text()
    rows = []
    in_table = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("| Ticker") or line.startswith("|Ticker"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if re.match(r"^\|\s*-+\s*\|", line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 4 and re.match(r"^[A-Z][A-Z0-9]+$", cells[0]):
                try:
                    minw = float(cells[2])
                    maxw = float(cells[3])
                except ValueError:
                    continue
                rows.append((cells[0], minw, maxw))
    if not rows:
        raise ValueError(f"No asset universe table found in {ips_path}")
    tickers = [r[0] for r in rows]
    min_w = np.array([r[1] for r in rows])
    max_w = np.array([r[2] for r in rows])
    return {"tickers": tickers, "min_w": min_w, "max_w": max_w}


def project_to_box(w: np.ndarray, min_w: np.ndarray, max_w: np.ndarray,
                   max_iter: int = 200, tol: float = 1e-9) -> np.ndarray:
    """Iterative clip-and-renormalise projection of `w` onto
    {w : sum=1, min_w <= w <= max_w}. Returns clipped weights; if
    not feasible (sum of min_w > 1 or sum of max_w < 1) returns the
    closest clipped solution.
    """
    w = np.array(w, dtype=float)
    if w.sum() == 0:
        w = np.ones_like(w) / len(w)
    w = w / w.sum()
    for _ in range(max_iter):
        w = np.clip(w, min_w, max_w)
        s = w.sum()
        if abs(s - 1.0) < tol:
            return w
        # mass to add or remove
        diff = 1.0 - s
        # distribute among free assets (not at a bound in the right direction)
        if diff > 0:
            free = max_w - w
            if free.sum() <= 0:
                break
            w = w + diff * free / free.sum()
        else:
            free = w - min_w
            if free.sum() <= 0:
                break
            w = w + diff * free / free.sum()
    return np.clip(w, min_w, max_w)


def is_feasible(w: np.ndarray, min_w: np.ndarray, max_w: np.ndarray,
                tol: float = 1e-4) -> bool:
    return (
        abs(w.sum() - 1.0) < tol
        and (w >= min_w - tol).all()
        and (w <= max_w + tol).all()
    )


def portfolio_metrics(w: np.ndarray, mu: np.ndarray, sigma: np.ndarray,
                      cov: np.ndarray, rf: float = 0.04) -> dict:
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
    """Align CMA, covariance, and IPS to a single ordered ticker list
    (intersection)."""
    cmas_by_t = {c["ticker"]: c for c in cmas["cmas"]}
    cov_tickers = cov_obj["tickers"]
    cov_idx = {t: i for i, t in enumerate(cov_tickers)}

    ips_tickers = ips["tickers"]
    chosen = [t for t in ips_tickers if t in cmas_by_t and t in cov_idx]
    n = len(chosen)
    mu = np.array([cmas_by_t[t]["expected_return"] for t in chosen])
    sigma = np.array([cmas_by_t[t]["volatility"] for t in chosen])
    confidence = np.array([cmas_by_t[t]["confidence"] for t in chosen])

    # Pull the sub-matrix in `chosen` order
    full = np.array(cov_obj["covariance"])
    idx = [cov_idx[t] for t in chosen]
    cov = full[np.ix_(idx, idx)]

    # Map IPS box constraints
    ips_idx = {t: i for i, t in enumerate(ips_tickers)}
    min_w = np.array([ips["min_w"][ips_idx[t]] for t in chosen])
    max_w = np.array([ips["max_w"][ips_idx[t]] for t in chosen])

    return {
        "tickers": chosen,
        "n": n,
        "mu": mu,
        "sigma": sigma,
        "confidence": confidence,
        "cov": cov,
        "min_w": min_w,
        "max_w": max_w,
    }
