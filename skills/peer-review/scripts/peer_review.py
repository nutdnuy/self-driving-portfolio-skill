"""Multi-agent strategy review with Borda voting + adversarial diversifier."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[2] / "portfolio-construction" / "scripts"))
from utils import parse_ips, project_to_box  # noqa: E402


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
    """Convert raw scores to tie-aware Borda points (highest gets n-1)."""
    n = len(scores)
    values = np.asarray(scores, dtype=float)
    order = np.argsort(-values, kind="stable")
    points = np.zeros(n)
    rank = 0
    while rank < n:
        end = rank + 1
        while end < n and values[order[end]] == values[order[rank]]:
            end += 1
        tied_points = [n - 1 - position for position in range(rank, end)]
        points[order[rank:end]] = float(np.mean(tied_points))
        rank = end
    return points.tolist()


def _adversarial_challenger(ips: dict) -> dict:
    """Build an IPS-feasible equal-weight challenger.

    A simple but effective adversarial baseline: maximally diversified."""
    tickers = ips["tickers"]
    raw = np.full(len(tickers), 1.0 / len(tickers))
    projected = project_to_box(raw, ips["min_w"], ips["max_w"])
    weights = {
        ticker: float(weight)
        for ticker, weight in zip(tickers, projected, strict=True)
    }
    return {
        "method": "adversarial_equal_weight",
        "weights": weights,
    }


def review(proposals_path: str, ips_path: str, top_k: int = 5,
           vol_cap: float | None = None) -> dict:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    obj = json.loads(Path(proposals_path).read_text())
    ips = parse_ips(ips_path)
    if vol_cap is None:
        vol_cap = ips["vol_cap"]
    if vol_cap <= 0:
        raise ValueError("vol_cap must be positive")

    surviving = []
    filtered_out = []
    for p in obj["proposals"]:
        if p.get("status") != "ok":
            filtered_out.append({"method": p["method"], "reason": "method failed"})
            continue
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
    for p, r, b in zip(surviving, rubrics, borda, strict=True):
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
        challenger = _adversarial_challenger(ips)
        # Concentration challenge: require a material effective-N improvement.
        challenger_weights = np.array(list(challenger["weights"].values()))
        challenger_metrics = {
            "effective_n": float(1.0 / np.sum(challenger_weights**2)),
            "max_weight": float(challenger_weights.max()),
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
