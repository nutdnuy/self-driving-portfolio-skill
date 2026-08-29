"""Parse and enforce computable Investment Policy Statement controls."""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

TICKER_RE = re.compile(r"[A-Z0-9][A-Z0-9.^=_-]{0,19}")


def parse_ips(ips_path: str | Path) -> dict[str, Any]:
    """Parse the dated universe, hard bounds, and escalation controls."""
    text = Path(ips_path).read_text(encoding="utf-8")
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
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) < 4:
                raise ValueError(f"Malformed IPS asset row: {line}")
            if not TICKER_RE.fullmatch(cells[0]):
                raise ValueError(f"Unsupported ticker in IPS asset row: {cells[0]!r}")
            try:
                min_weight = float(cells[2])
                max_weight = float(cells[3])
            except ValueError as exc:
                raise ValueError(f"Non-numeric IPS weight bound for {cells[0]}") from exc
            rows.append((cells[0], min_weight, max_weight))

    if not rows:
        raise ValueError(f"No asset universe table found in {ips_path}")
    if len(rows) < 2:
        raise ValueError("IPS asset universe must contain at least two tickers")
    tickers = [row[0] for row in rows]
    min_w = np.array([row[1] for row in rows], dtype=float)
    max_w = np.array([row[2] for row in rows], dtype=float)
    if len(tickers) != len(set(tickers)):
        raise ValueError("IPS asset universe contains duplicate tickers")
    if not np.isfinite(min_w).all() or not np.isfinite(max_w).all():
        raise ValueError("IPS bounds must be finite numbers")
    if (min_w < 0).any() or (max_w > 1).any() or (min_w > max_w).any():
        raise ValueError("IPS bounds must satisfy 0 <= min_w <= max_w <= 1")
    if min_w.sum() > 1.0 + 1e-10 or max_w.sum() < 1.0 - 1e-10:
        raise ValueError(
            "IPS box constraints are infeasible: require sum(min_w) <= 1 <= sum(max_w)"
        )

    as_of_match = re.search(
        r"\|\s*As-of date\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|", text, re.IGNORECASE
    )
    as_of = as_of_match.group(1) if as_of_match else None
    if as_of is not None:
        date.fromisoformat(as_of)

    vol_match = re.search(
        r"Annualised volatility \(hard cap\).*?\|\s*(\d+(?:\.\d+)?)\s*%",
        text,
        re.IGNORECASE,
    )
    if vol_match is None:
        raise ValueError("IPS must define Annualised volatility (hard cap) as a percentage")
    vol_cap = float(vol_match.group(1)) / 100.0
    if not 0 < vol_cap <= 1:
        raise ValueError("IPS volatility hard cap must be greater than 0% and at most 100%")

    feasible_match = re.search(r"fewer than\s+(\d+)", text, re.IGNORECASE)
    if feasible_match is None:
        raise ValueError("IPS must define the minimum feasible proposal escalation threshold")
    min_feasible_proposals = int(feasible_match.group(1))
    if min_feasible_proposals <= 0:
        raise ValueError("IPS minimum feasible proposal threshold must be positive")

    return {
        "tickers": tickers,
        "min_w": min_w,
        "max_w": max_w,
        "as_of": as_of,
        "vol_cap": vol_cap,
        "min_feasible_proposals": min_feasible_proposals,
    }


def validate_ips_weights(
    weights: Mapping[str, Any],
    ips: Mapping[str, Any],
    label: str,
    tolerance: float = 1e-6,
) -> None:
    """Reject weight maps that omit assets or violate IPS hard bounds."""
    tickers = ips["tickers"]
    if set(weights) != set(tickers):
        raise ValueError(f"{label} ticker set does not match the IPS universe")
    vector = np.array([float(weights[ticker]) for ticker in tickers], dtype=float)
    if not np.isfinite(vector).all():
        raise ValueError(f"{label} contains NaN or Infinity")
    if abs(float(vector.sum()) - 1.0) > tolerance:
        raise ValueError(f"{label} weights do not sum to 1.0")
    if (vector < ips["min_w"] - tolerance).any():
        raise ValueError(f"{label} violates IPS minimum weights")
    if (vector > ips["max_w"] + tolerance).any():
        raise ValueError(f"{label} violates IPS maximum weights")
