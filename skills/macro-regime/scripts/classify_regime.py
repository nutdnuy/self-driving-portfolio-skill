"""Classify the current US macro regime.

Implements the four-regime weighted-scoring framework from
Ang/Azimbayev/Kim (2026) §3.2.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from fetch_macro import fetch_indicators  # noqa: E402

REGIME_WEIGHTS = {
    # rows: regime; cols: (growth, inflation, monetary, fci)
    "expansion":  ( 1.0, -0.5, -0.5, -1.0),
    "late_cycle": ( 1.0,  1.0,  1.0,  0.5),
    "recession":  (-1.0, -0.5,  0.0,  1.0),
    "recovery":   ( 1.0, -1.0, -1.0, -0.5),
}


def _zscore(s: pd.Series, window_years: float = 5.0) -> float:
    """Z-score of the latest reading vs a rolling window (monthly resampling)."""
    s = s.dropna()
    if len(s) < 24:
        return 0.0
    monthly = s.resample("ME").last().dropna()
    win = int(window_years * 12)
    win = min(win, len(monthly))
    recent = monthly.iloc[-win:]
    mu = recent.mean()
    sd = recent.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(np.clip((monthly.iloc[-1] - mu) / sd, -3.0, 3.0))


def _yoy(s: pd.Series) -> pd.Series:
    monthly = s.resample("ME").last().dropna()
    return monthly.pct_change(12).dropna() * 100.0


def build_indicator_vector(df: pd.DataFrame) -> dict[str, float]:
    """Return the four-dimensional indicator vector in [-1, +1]ish space."""
    growth_yoy = _yoy(df["INDPRO"])
    cpi_yoy = _yoy(df["CPIAUCSL"])
    real_curve = (df["DFF"] - df["T10Y3M"]).dropna()
    fci = df["NFCI"].dropna()

    growth = _zscore(growth_yoy)
    inflation = _zscore(cpi_yoy)
    monetary = _zscore(real_curve)
    fci_z = _zscore(fci)
    # tanh squashes z to roughly [-1, 1]
    return {
        "growth": float(np.tanh(growth)),
        "inflation": float(np.tanh(inflation)),
        "monetary": float(np.tanh(monetary)),
        "financial_conditions": float(np.tanh(fci_z)),
    }


def score_regimes(indicators: dict[str, float]) -> dict[str, float]:
    g, i, m, f = (
        indicators["growth"],
        indicators["inflation"],
        indicators["monetary"],
        indicators["financial_conditions"],
    )
    raw = {
        name: w[0] * g + w[1] * i + w[2] * m + w[3] * f
        for name, w in REGIME_WEIGHTS.items()
    }
    # softmax with temperature 1
    arr = np.array(list(raw.values()))
    arr = arr - arr.max()
    exp = np.exp(arr)
    probs = exp / exp.sum()
    return {k: float(v) for k, v in zip(raw.keys(), probs, strict=True)}


def classify(
    as_of: str | date | None = None,
    indicators_df: pd.DataFrame | None = None,
) -> dict:
    df = indicators_df.copy() if indicators_df is not None else fetch_indicators(as_of)
    cutoff = pd.Timestamp(as_of or df.attrs.get("requested_as_of", date.today())).normalize()
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_localize(None)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(None)
    if (df.index > cutoff).any():
        raise ValueError("Macro input contains observations after as_of")
    required = {"INDPRO", "CPIAUCSL", "DFF", "T10Y3M", "NFCI"}
    if not required.issubset(df.columns):
        raise ValueError(f"Macro input is missing required columns: {sorted(required - set(df))}")
    if df.empty:
        raise RuntimeError("FRED fetch returned no data — check connectivity.")
    indicators = build_indicator_vector(df)
    scores = score_regimes(indicators)
    regime = max(scores, key=scores.get)
    top1 = scores[regime]

    notes = (
        f"Regime call: **{regime}** (top-1 confidence {top1:.2f}). "
        f"Growth z={indicators['growth']:+.2f}, "
        f"Inflation z={indicators['inflation']:+.2f}, "
        f"Monetary z={indicators['monetary']:+.2f}, "
        f"FCI z={indicators['financial_conditions']:+.2f}."
    )

    return {
        "as_of": cutoff.date().isoformat(),
        "data_through": str(df.index[-1].date()),
        "vintage_policy": df.attrs.get("vintage_policy", "latest_revision_cutoff"),
        "regime": regime,
        "scores": scores,
        "top1_confidence": top1,
        "top1_confidence_low": top1 < 0.4,
        "indicators": indicators,
        "notes": notes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = classify(args.as_of)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
