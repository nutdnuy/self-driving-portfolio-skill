"""Build Capital Market Assumptions per ticker, conditioned on regime."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from fetch_prices import fetch_prices  # noqa: E402


# Asset bucket → regime tilt (annualised, additive to historical mean)
TILTS = {
    "equity":     {"expansion": 0.015, "late_cycle": -0.005, "recession": -0.030, "recovery":  0.020},
    "treasury":   {"expansion": -0.005, "late_cycle": -0.005, "recession":  0.015, "recovery":  0.005},
    "credit":     {"expansion":  0.000, "late_cycle": -0.010, "recession": -0.015, "recovery":  0.010},
    "infl_link":  {"expansion":  0.005, "late_cycle":  0.015, "recession":  0.000, "recovery": -0.005},
    "cash":       {"expansion":  0.000, "late_cycle":  0.000, "recession":  0.005, "recovery":  0.000},
}

BUCKET_MAP = {
    "SPY": "equity", "EFA": "equity", "EEM": "equity", "VNQ": "equity",
    "IEF": "treasury",
    "LQD": "credit",
    "TIP": "infl_link", "GLD": "infl_link",
    "BIL": "cash",
}


def historical_stats(prices: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    rets = np.log(prices / prices.shift(1)).dropna(how="all")
    # annualised geometric mean & vol from daily log-returns
    mu = rets.mean() * 252.0
    sigma = rets.std(ddof=1) * np.sqrt(252.0)
    return mu, sigma


def build_cmas(
    tickers: list[str],
    regime_obj: dict,
    lookback_years: float = 10.0,
) -> dict:
    prices = fetch_prices(tickers, years=lookback_years)
    available = [t for t in tickers if t in prices.columns]
    mu, sigma = historical_stats(prices[available])

    regime = regime_obj["regime"]
    top1 = regime_obj.get("top1_confidence", 1.0)

    cmas = []
    for t in available:
        bucket = BUCKET_MAP.get(t, "equity")
        tilt = TILTS[bucket][regime] * top1  # scale tilt by regime confidence
        exp_ret = float(mu[t]) + tilt
        vol = float(sigma[t])
        n_obs = int(prices[t].dropna().shape[0])

        sample_factor = float(np.clip(n_obs / 2520.0, 0.0, 1.0))  # 10y of dailies
        # vol stability: 1 - normalised dispersion of rolling 1y vol
        rets = np.log(prices[t] / prices[t].shift(1)).dropna()
        rolling_vol = rets.rolling(252).std() * np.sqrt(252.0)
        if len(rolling_vol.dropna()) > 0 and vol > 0:
            disp = float(np.clip(rolling_vol.std() / vol, 0.0, 1.0))
        else:
            disp = 0.5
        stability = 1.0 - disp

        confidence = float(np.clip(0.4 * sample_factor + 0.3 * stability + 0.3 * top1, 0.0, 1.0))

        memo = (
            f"{t}: hist μ={mu[t]:.2%}, σ={vol:.2%} over {n_obs} obs. "
            f"Regime '{regime}' (conf {top1:.2f}) applies a {tilt:+.2%} tilt → "
            f"expected return {exp_ret:.2%}. Confidence {confidence:.2f}."
        )

        cmas.append({
            "ticker": t,
            "expected_return": exp_ret,
            "volatility": vol,
            "confidence": confidence,
            "regime_tilt": tilt,
            "memo": memo,
        })

    return {
        "as_of": regime_obj["as_of"],
        "lookback_years": lookback_years,
        "regime": regime,
        "cmas": cmas,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--regime", required=True, help="path to regime.json")
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--lookback-years", type=float, default=10.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    regime_obj = json.loads(Path(args.regime).read_text())
    out = build_cmas(args.tickers.split(","), regime_obj, args.lookback_years)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
