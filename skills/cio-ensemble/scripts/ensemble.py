"""CIO ensemble: combine survivors → recommended portfolio + board memo."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[2] / "portfolio-construction" / "scripts"))
from utils import align_inputs, parse_ips, portfolio_metrics, project_to_box  # noqa: E402


def _stack(survivors: list[dict], tickers: list[str]) -> np.ndarray:
    """Return matrix W (n_methods × n_tickers) of survivor weights."""
    return np.array([[s["weights"][t] for t in tickers] for s in survivors])


def _normalise(w: np.ndarray) -> np.ndarray:
    s = w.sum()
    return w / s if s > 0 else w


def simple_mean(W, **kw):       return _normalise(W.mean(axis=0))
def median(W, **kw):            return _normalise(np.median(W, axis=0))
def trimmed_mean(W, **kw):
    if W.shape[0] < 3:
        return simple_mean(W)
    sorted_W = np.sort(W, axis=0)
    k = max(1, int(0.2 * W.shape[0]))
    trimmed = sorted_W[k:-k] if W.shape[0] - 2 * k > 0 else sorted_W
    return _normalise(trimmed.mean(axis=0))


def borda_weighted(W, borda_points, **kw):
    weights_m = np.array(borda_points, dtype=float)
    if weights_m.sum() <= 0:
        return simple_mean(W)
    weights_m = weights_m / weights_m.sum()
    return _normalise(weights_m @ W)


def confidence_weighted(W, borda_points, mean_confidence, **kw):
    base = np.array(borda_points, dtype=float)
    base *= np.array(mean_confidence, dtype=float)
    if base.sum() <= 0:
        return simple_mean(W)
    base = base / base.sum()
    return _normalise(base @ W)


def sharpe_weighted(W, sharpes, **kw):
    s = np.array(sharpes, dtype=float)
    s = np.maximum(s, 0.0)
    if s.sum() <= 0:
        return simple_mean(W)
    s = s / s.sum()
    return _normalise(s @ W)


def regime_weighted(W, regime_fits, **kw):
    s = np.array(regime_fits, dtype=float)
    s = np.maximum(s, 0.0)
    if s.sum() <= 0:
        return simple_mean(W)
    s = s / s.sum()
    return _normalise(s @ W)


COMBINERS = {
    "simple_mean": simple_mean,
    "borda_weighted": borda_weighted,
    "confidence_weighted": confidence_weighted,
    "median": median,
    "trimmed_mean": trimmed_mean,
    "sharpe_weighted": sharpe_weighted,
    "regime_weighted": regime_weighted,
}

REGIME_TO_COMBINER = {
    "expansion": "sharpe_weighted",
    "recovery":  "sharpe_weighted",
    "late_cycle": "confidence_weighted",
    "recession": "regime_weighted",
}


def _regime_fit(method: str, regime: str) -> float:
    """Hand-coded affinity score (0–1) of each method for each regime."""
    table = {
        "expansion":  {"max_sharpe": 1.0, "tpa": 0.9, "black_litterman": 0.8,
                       "mvo_constrained": 0.8, "max_diversification": 0.7,
                       "risk_parity": 0.6, "hrp": 0.6, "inverse_vol": 0.5,
                       "equal_weight": 0.5, "min_variance": 0.4},
        "late_cycle": {"min_variance": 1.0, "risk_parity": 0.9, "hrp": 0.9,
                       "inverse_vol": 0.8, "max_diversification": 0.8,
                       "tpa": 0.7, "black_litterman": 0.6,
                       "mvo_constrained": 0.5, "equal_weight": 0.5,
                       "max_sharpe": 0.4},
        "recession":  {"min_variance": 1.0, "risk_parity": 0.9, "hrp": 0.9,
                       "tpa": 0.8, "inverse_vol": 0.8,
                       "max_diversification": 0.7, "black_litterman": 0.6,
                       "equal_weight": 0.5, "mvo_constrained": 0.4,
                       "max_sharpe": 0.3},
        "recovery":   {"max_sharpe": 1.0, "black_litterman": 0.9, "tpa": 0.9,
                       "mvo_constrained": 0.8, "max_diversification": 0.7,
                       "risk_parity": 0.7, "hrp": 0.7, "inverse_vol": 0.6,
                       "equal_weight": 0.5, "min_variance": 0.4},
    }
    return table.get(regime, {}).get(method, 0.5)


def ensemble(cmas_path: str, cov_path: str, ips_path: str,
             proposals_path: str, peer_review_path: str,
             regime_path: str, out_path: str | None, memo_path: str | None) -> dict:

    cmas = json.loads(Path(cmas_path).read_text())
    cov = json.loads(Path(cov_path).read_text())
    proposals_obj = json.loads(Path(proposals_path).read_text())
    review = json.loads(Path(peer_review_path).read_text())
    regime_obj = json.loads(Path(regime_path).read_text())
    ips = parse_ips(ips_path)

    data = align_inputs(cmas, cov, ips)
    tickers = data["tickers"]

    # Pull survivor proposals
    surv_names = review["survivors"]
    proposals_by_method = {p["method"]: p for p in proposals_obj["proposals"]}
    missing_survivors = set(surv_names).difference(proposals_by_method)
    if missing_survivors:
        raise RuntimeError(
            f"Peer-review survivors are absent from proposals: {sorted(missing_survivors)}"
        )
    survivors = [proposals_by_method[method] for method in surv_names]
    if not survivors:
        raise RuntimeError("No survivors after peer review — pipeline must escalate.")

    W = _stack(survivors, tickers)
    borda_by_method = {b["method"]: b["borda_points"] for b in review["borda"]}
    borda_points = [borda_by_method.get(s["method"], 0.0) for s in survivors]
    sharpes = [s["metrics"].get("sharpe", 0.0) for s in survivors]
    mean_conf = float(np.mean(data["confidence"]))
    mean_confs = [mean_conf for _ in survivors]
    regime = regime_obj["regime"]
    regime_fits = [_regime_fit(s["method"], regime) for s in survivors]

    all_ensembles = {}
    for name, fn in COMBINERS.items():
        w = fn(W, borda_points=borda_points, mean_confidence=mean_confs,
               sharpes=sharpes, regime_fits=regime_fits)
        # Project to IPS box
        w_proj = project_to_box(w, data["min_w"], data["max_w"])
        all_ensembles[name] = {t: float(x) for t, x in zip(tickers, w_proj, strict=True)}

    # Selection rule
    if regime_obj.get("top1_confidence_low", False):
        chosen = "trimmed_mean"
    else:
        chosen = REGIME_TO_COMBINER.get(regime, "simple_mean")

    weights = np.array([all_ensembles[chosen][t] for t in tickers])
    metrics = portfolio_metrics(weights, data["mu"], data["sigma"], data["cov"])

    # Dissenting view: highest-Borda survivor whose weights are most distant
    if survivors:
        dists = []
        for s in survivors:
            sw = np.array([s["weights"].get(t, 0.0) for t in tickers])
            dists.append(float(np.linalg.norm(sw - weights)))
        idx = int(np.argmax(dists))
        dissent_p = survivors[idx]
        dissenting = {
            "method": dissent_p["method"],
            "weights": dissent_p["weights"],
            "rationale": dissent_p["rationale"],
        }
    else:
        dissenting = None

    # Escalation flags
    vol_cap = ips["vol_cap"]
    min_feasible = ips["min_feasible_proposals"]
    feasible_count = sum(1 for p in proposals_obj["proposals"] if p.get("feasible"))
    adv = review.get("adversarial_challenger") or {}
    escalate = (
        metrics["volatility"] > vol_cap - 0.005
        or feasible_count < min_feasible
        or adv.get("won", False)
        or regime_obj.get("top1_confidence_low", False)
    )
    reasons = []
    if metrics["volatility"] > vol_cap - 0.005:
        reasons.append("recommended vol within 50bps of IPS hard cap")
    if feasible_count < min_feasible:
        reasons.append(
            f"only {feasible_count} feasible PC proposals (<{min_feasible})"
        )
    if adv.get("won", False):
        reasons.append("adversarial diversifier won")
    if regime_obj.get("top1_confidence_low", False):
        reasons.append("low top-1 regime confidence")

    out = {
        "as_of": cmas["as_of"],
        "regime": regime,
        "ensemble_method": chosen,
        "weights": {t: float(x) for t, x in zip(tickers, weights, strict=True)},
        "metrics": metrics,
        "all_ensembles": all_ensembles,
        "dissenting_view": dissenting,
        "escalate_to_human": bool(escalate),
        "escalation_reason": "; ".join(reasons),
    }

    if out_path is not None:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(out, indent=2), encoding="utf-8")
    if memo_path is not None:
        Path(memo_path).parent.mkdir(parents=True, exist_ok=True)
        Path(memo_path).write_text(
            render_board_memo(out, regime_obj, cmas, proposals_obj, review),
            encoding="utf-8",
        )
    return out


def render_board_memo(final: dict, regime_obj: dict, cmas: dict,
                      proposals_obj: dict, review: dict) -> str:
    """Render the human-review memo without mutating the filesystem."""
    lines = []
    lines.append("# Board Memo — Recommended Policy Portfolio")
    lines.append("")
    lines.append(f"**As of:** {final['as_of']}  ")
    lines.append(
        f"**Regime:** {final['regime']} "
        f"(top-1 conf {regime_obj['top1_confidence']:.2f})  "
    )
    lines.append(f"**Ensemble method chosen:** `{final['ensemble_method']}`  ")
    lines.append("")
    lines.append("## 1. Regime call")
    lines.append("")
    lines.append(regime_obj["notes"])
    lines.append("")
    lines.append("## 2. Recommended weights")
    lines.append("")
    lines.append("| Ticker | Weight |")
    lines.append("| --- | --- |")
    for t, w in final["weights"].items():
        lines.append(f"| {t} | {w:.2%} |")
    lines.append("")
    m = final["metrics"]
    lines.append("## 3. Portfolio metrics")
    lines.append("")
    lines.append(f"- Expected return: **{m['expected_return']:.2%}**")
    lines.append(f"- Volatility: **{m['volatility']:.2%}**")
    lines.append(f"- Sharpe: **{m['sharpe']:+.2f}**")
    lines.append(f"- Effective N: **{m['effective_n']:.1f}**")
    lines.append(f"- Max single weight: **{m['max_weight']:.2%}**")
    lines.append("")
    lines.append("## 4. Method comparison (post peer-review)")
    lines.append("")
    lines.append("| Method | Borda | Vol | Sharpe | Eff-N | Max-w |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    proposals_by_method = {p["method"]: p for p in proposals_obj["proposals"]}
    for b in review["borda"]:
        p = proposals_by_method.get(b["method"])
        if not p or not p["metrics"]:
            continue
        pm = p["metrics"]
        lines.append(
            f"| {b['method']} | {b['borda_points']:.0f} | {pm['volatility']:.2%} | "
            f"{pm['sharpe']:+.2f} | {pm['effective_n']:.1f} | {pm['max_weight']:.0%} |"
        )
    lines.append("")
    if final.get("dissenting_view"):
        d = final["dissenting_view"]
        lines.append("## 5. Dissenting view")
        lines.append("")
        lines.append(f"**{d['method']}** disagrees most strongly with the recommended weights.")
        lines.append("")
        lines.append(f"> {d['rationale']}")
        lines.append("")
    if final["escalate_to_human"]:
        lines.append("## 6. Escalation")
        lines.append("")
        lines.append(f"**Escalation flagged.** Reason: {final['escalation_reason']}.")
        lines.append("")
        lines.append("Human portfolio manager review required before implementation.")
        lines.append("")
    else:
        lines.append("## 6. Escalation")
        lines.append("")
        lines.append("No escalation flags fired. Recommendation is within IPS bounds and ")
        lines.append("supported by the IPS-required minimum feasible proposal count.")
        lines.append("")
    lines.append("---")
    lines.append("Generated by the agentic SAA pipeline (Ang/Azimbayev/Kim 2026).")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmas", required=True)
    parser.add_argument("--cov", required=True)
    parser.add_argument("--ips", required=True)
    parser.add_argument("--proposals", required=True)
    parser.add_argument("--peer-review", required=True)
    parser.add_argument("--regime", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--memo", required=True)
    args = parser.parse_args()
    out = ensemble(args.cmas, args.cov, args.ips, args.proposals,
                   args.peer_review, args.regime, args.out, args.memo)
    print(f"Chosen: {out['ensemble_method']}, "
          f"vol={out['metrics']['volatility']:.2%}, "
          f"Sharpe={out['metrics']['sharpe']:+.2f}, "
          f"escalate={out['escalate_to_human']}")
