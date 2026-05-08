"""Covariance estimation for SAA: sample, EWMA, Ledoit-Wolf shrinkage."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[2] / "asset-class-cma" / "scripts"))
from fetch_prices import fetch_prices  # noqa: E402

ANN = 252.0


def _to_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return np.log(prices / prices.shift(1)).dropna()


def sample_cov(returns: pd.DataFrame) -> np.ndarray:
    return returns.cov().values * ANN


def ewma_cov(returns: pd.DataFrame, lam: float = 0.94) -> np.ndarray:
    X = returns.values - returns.values.mean(axis=0, keepdims=True)
    n, k = X.shape
    cov = np.zeros((k, k))
    weights = (1.0 - lam) * (lam ** np.arange(n)[::-1])
    weights /= weights.sum()
    for i, w in enumerate(weights):
        cov += w * np.outer(X[i], X[i])
    return cov * ANN


def ledoit_wolf_constant_corr(returns: pd.DataFrame) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf shrinkage toward a constant-correlation target.

    Returns (annualised_cov, intensity).  Closed-form per Ledoit & Wolf (2004).
    """
    X = returns.values
    X = X - X.mean(axis=0, keepdims=True)
    t, n = X.shape
    if t < 2 or n < 2:
        return returns.cov().values * ANN, 0.0

    sample = (X.T @ X) / t

    # Constant-correlation target
    var = np.diag(sample)
    sd = np.sqrt(var)
    corr = sample / np.outer(sd, sd)
    np.fill_diagonal(corr, 1.0)
    avg_corr = (corr.sum() - n) / (n * (n - 1))
    target = avg_corr * np.outer(sd, sd)
    np.fill_diagonal(target, var)

    # pi: sum of asymptotic variances of sample-cov entries
    Y = X * X
    pi_mat = (Y.T @ Y) / t - sample ** 2
    pi = pi_mat.sum()

    # rho: covariance of sample-cov with target (constant-correlation)
    # Use Ledoit-Wolf (2004) equation A.1
    rho_diag = np.sum(np.diag(pi_mat))
    term = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            v_ij = (X[:, i] ** 2 * X[:, j] - sample[i, j] * X[:, i] ** 2).mean()
            v_ji = (X[:, j] ** 2 * X[:, i] - sample[i, j] * X[:, j] ** 2).mean()
            term[i, j] = (sd[j] / sd[i]) * v_ij + (sd[i] / sd[j]) * v_ji
    rho_off = 0.5 * avg_corr * term.sum()
    rho = rho_diag + rho_off

    # gamma: distance between sample and target
    gamma = ((sample - target) ** 2).sum()

    if gamma <= 0:
        intensity = 0.0
    else:
        kappa = (pi - rho) / gamma
        intensity = float(np.clip(kappa / t, 0.0, 1.0))

    shrunk = intensity * target + (1.0 - intensity) * sample
    return shrunk * ANN, intensity


def build_cov(tickers: list[str], method: str = "ledoit_wolf",
              years: float = 10.0) -> dict:
    prices = fetch_prices(tickers, years=years)
    available = [t for t in tickers if t in prices.columns]
    rets = _to_returns(prices[available])

    if method == "sample":
        cov = sample_cov(rets)
        intensity = 0.0
    elif method == "ewma":
        cov = ewma_cov(rets)
        intensity = 0.0
    elif method == "ledoit_wolf":
        cov, intensity = ledoit_wolf_constant_corr(rets)
    else:
        raise ValueError(f"unknown method {method}")

    cond = float(np.linalg.cond(cov))

    return {
        "as_of": str(rets.index[-1].date()),
        "method": method,
        "tickers": available,
        "covariance": cov.tolist(),
        "shrinkage_intensity": float(intensity),
        "condition_number": cond,
        "lookback_years": years,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--method", default="ledoit_wolf",
                        choices=["sample", "ewma", "ledoit_wolf"])
    parser.add_argument("--years", type=float, default=10.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = build_cov(args.tickers.split(","), args.method, args.years)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"method={out['method']}, shrinkage={out['shrinkage_intensity']:.3f}, "
          f"cond={out['condition_number']:.1f}")
