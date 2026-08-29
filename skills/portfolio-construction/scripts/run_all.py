"""Run all 10 PC methods and emit `pc_proposals.json`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from methods import METHODS  # noqa: E402
from utils import (  # noqa: E402
    align_inputs,
    is_feasible,
    parse_ips,
    portfolio_metrics,
    project_to_box,
)

RATIONALE_TEMPLATE = {
    "equal_weight": "1/N baseline; ignores all CMAs; high effective N by construction.",
    "inverse_vol": (
        "Inverse-volatility weighting; reduces concentration in high-vol assets "
        "without using expected returns."
    ),
    "min_variance": (
        "Variance-minimising portfolio; ignores expected returns; tends to favour "
        "low-vol defensives."
    ),
    "max_sharpe": (
        "Tangency portfolio on the long-only frontier; concentrated in the "
        "highest-Sharpe assets given CMAs."
    ),
    "risk_parity": "Equal-risk-contribution; each asset contributes the same ex-ante volatility.",
    "hrp": (
        "Lopez de Prado HRP; clusters assets and bisects risk recursively, "
        "robust to estimation error in covariance."
    ),
    "max_diversification": "Maximises (Σ wᵢσᵢ)/σ_p; rewards low-correlation combinations.",
    "black_litterman": (
        "BL combining market-implied prior with absolute CMA views weighted by confidence."
    ),
    "mvo_constrained": "MVO with IPS box constraints and risk-aversion λ=5.0.",
    "tpa": (
        "Total Portfolio Allocation — risk parity tilted by regime "
        "(growth-on in expansion/recovery, off in late-cycle/recession)."
    ),
}


def run(cmas_path: str, cov_path: str, ips_path: str, out_path: str | None,
        regime: str = "expansion") -> dict:
    cmas = json.loads(Path(cmas_path).read_text())
    cov = json.loads(Path(cov_path).read_text())
    ips = parse_ips(ips_path)

    data = align_inputs(cmas, cov, ips)

    proposals = []
    for name, fn in METHODS.items():
        try:
            kwargs = {"regime": regime} if name == "tpa" else {}
            raw = fn(data, **kwargs) if kwargs else fn(data)
        except Exception as e:
            proposals.append({
                "method": name,
                "status": "failed",
                "error": f"{type(e).__name__}: {e}"[:500],
                "weights": {t: 0.0 for t in data["tickers"]},
                "metrics": {},
                "feasible": False,
                "rationale": f"FAILED: {e}",
            })
            continue

        proj = project_to_box(raw, data["min_w"], data["max_w"])
        feas = is_feasible(proj, data["min_w"], data["max_w"])
        metrics = portfolio_metrics(proj, data["mu"], data["sigma"], data["cov"])
        proposals.append({
            "method": name,
            "status": "ok",
            "weights": {t: float(w) for t, w in zip(data["tickers"], proj, strict=True)},
            "metrics": metrics,
            "feasible": bool(feas),
            "rationale": RATIONALE_TEMPLATE[name] +
                f" Ex-ante vol {metrics['volatility']:.2%}, Sharpe {metrics['sharpe']:.2f}, "
                f"max-w {metrics['max_weight']:.2%}, eff-N {metrics['effective_n']:.1f}.",
        })

    out = {"as_of": cmas["as_of"], "proposals": proposals}
    if out_path is not None:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmas", required=True)
    parser.add_argument("--cov", required=True)
    parser.add_argument("--ips", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--regime", default="expansion")
    args = parser.parse_args()
    out = run(args.cmas, args.cov, args.ips, args.out, args.regime)
    for p in out["proposals"]:
        m = p["metrics"]
        if not m:
            continue
        print(f"  {p['method']:>22s}  vol={m['volatility']:.2%}  "
              f"Sharpe={m['sharpe']:+.2f}  max-w={m['max_weight']:.0%}  "
              f"feas={p['feasible']}")
