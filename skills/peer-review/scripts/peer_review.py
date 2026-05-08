"""Multi-agent strategy review with Borda voting + adversarial diversifier."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[2] / "portfolio-construction" / "scripts"))
from utils import parse_ips  # noqa: E402


def _parse_vol_cap(ips_path: str) -> float:
    """Pull the IPS 'Annualised volatility (hard cap)' value."""
    text = Path(ips_path).read_text()
    m = re.search(r"hard cap.*?\|\s*(\d+(?:\.\d+)?)\s*%", text)
    if m:
        return float(m.group(1)) / 100.0
    return 0.18


def _score_proposal(p: dict) -> dict:
    """Deterministic three-axis rubric (stand-in for LLM reviewer)."""
    m = p["metrics"]
    if not m:
        return {"risk_adj_return": 1.0, "diversification": 1.0, "robustness": 1.0}

    sharpe = m.get("sharpe", 0.0)
    eff_n = m.get("effective_n", 1.0)
    max_w = m.get("max_weight", 1.0)
    vol = m.get("volatility", 0.0)

    risk_adj = float(np.clip(2.5 + sharpe * 1.5, 1.0, 5.0))
    diver = float(np.clip(eff_n / 2.0 + (1.0 - max_w) * 2.0, 1.0, 5.0))
    # robustness: penalise extreme vol (too high or too low)
    robust = float(np.clip(5.0 - 8.0 * abs(vol - 0.10), 1.0, 5.0))
    return {
        "risk_adj_return": risk_adj,
        "diversification": diver,
        "robustness": robust,
    }


def _borda(scores: list[float]) -> list[float]:
    """Convert raw scores to Borda points (highest gets n-1)."""
    n = len(scores)
    order = np.argsort(-np.array(scores))
    points = np.zeros(n)
    for rank, idx in enumerate(order):
        points[idx] = n - 1 - rank
    return points.tolist()


def _adversarial_challenger(proposals: list[dict], tickers: list[str]) -> dict:
    """Build an equal-weight challenger across all available IPS tickers.

    A simple but effective adversarial baseline: maximally diversified."""
    n = len(tickers)
    w = {t: 1.0 / n for t in tickers}
    return {
        "method": "adversarial_equal_weight",
        "weights": w,
    }


def review(proposals_path: str, ips_path: str, top_k: int = 5,
           vol_cap: float | None = None) -> dict:
    obj = json.loads(Path(proposals_path).read_text())
    ips = parse_ips(ips_path)
    if vol_cap is None:
        vol_cap = _parse_vol_cap(ips_path)

    surviving = []
    filtered_out = []
    for p in obj["proposals"]:
        if not p.get("feasible", False):
            filtered_out.append({"method": p["method"],
                                 "reason": "infeasible (IPS box / sum)"})
            continue
        vol = p["metrics"].get("volatility", 0.0)
        if vol > vol_cap:
            filtered_out.append({"method": p["method"],
                                 "reason": f"vol {vol:.2%} > cap {vol_cap:.2%}"})
            continue
        surviving.append(p)

    if not surviving:
        return {
            "as_of": obj["as_of"],
            "borda": [],
            "survivors": [],
            "adversarial_challenger": None,
            "filtered_out": filtered_out,
        }

    # Three-axis rubric per proposal
    rubrics = [_score_proposal(p) for p in surviving]
    risk_scores = [r["risk_adj_return"] for r in rubrics]
    div_scores = [r["diversification"] for r in rubrics]
    rob_scores = [r["robustness"] for r in rubrics]

    # Each axis contributes Borda points; sum across axes
    borda = (
        np.array(_borda(risk_scores))
        + np.array(_borda(div_scores))
        + np.array(_borda(rob_scores))
    )

    breakdown = []
    for p, r, b in zip(surviving, rubrics, borda):
        breakdown.append({
            "method": p["method"],
            "borda_points": float(b),
            "mean_review_score": float(np.mean(list(r.values()))),
            "review_breakdown": r,
        })
    breakdown.sort(key=lambda x: -x["borda_points"])

    # Adversarial diversifier check
    adv = None
    winner = breakdown[0]
    winner_p = next(x for x in surviving if x["method"] == winner["method"])
    if winner_p["metrics"].get("effective_n", 1.0) < 4 or \
       winner_p["metrics"].get("max_weight", 0.0) > 0.5:
        challenger = _adversarial_challenger(surviving, ips["tickers"])
        # Head-to-head: compare on risk-adj-return + diversification
        challenger_metrics = {
            "effective_n": float(len(ips["tickers"])),
            "max_weight": 1.0 / len(ips["tickers"]),
        }
        won = challenger_metrics["effective_n"] > winner_p["metrics"]["effective_n"] * 1.2
        adv = {
            "weights": challenger["weights"],
            "won": bool(won),
        }

    survivors = [b["method"] for b in breakdown[:top_k]]

    return {
        "as_of": obj["as_of"],
        "borda": breakdown,
        "survivors": survivors,
        "adversarial_challenger": adv,
        "filtered_out": filtered_out,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", required=True)
    parser.add_argument("--ips", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--vol-cap", type=float, default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = review(args.proposals, args.ips, args.top_k, args.vol_cap)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"Survivors: {out['survivors']}")
    print(f"Filtered out: {[f['method'] for f in out['filtered_out']]}")
