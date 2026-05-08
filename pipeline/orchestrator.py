"""End-to-end pipeline runner for the self-driving portfolio.

Executes the six stages sequentially and writes one output per stage to
`outputs/<run-id>/`:

  1. regime.json
  2. cmas.json
  3. covariance.json
  4. pc_proposals.json
  5. peer_review.json
  6. final_portfolio.json + board_memo.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "macro-regime" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "asset-class-cma" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "covariance" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "portfolio-construction" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "peer-review" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "cio-ensemble" / "scripts"))

from classify_regime import classify  # noqa: E402
from build_cma import build_cmas  # noqa: E402
from build_cov import build_cov  # noqa: E402
from run_all import run as run_pc  # noqa: E402
from peer_review import review  # noqa: E402
from ensemble import ensemble as run_ensemble  # noqa: E402
from utils import parse_ips  # noqa: E402


def run_pipeline(ips_path: str, run_id: str = "demo01",
                 lookback_years: float = 10.0,
                 cov_method: str = "ledoit_wolf",
                 top_k: int = 5) -> dict:
    out_dir = REPO / "outputs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ips = parse_ips(ips_path)
    tickers = ips["tickers"]

    # ---------- 1. macro regime ----------
    print(f"\n[1/6] Classifying macro regime…")
    regime = classify()
    (out_dir / "regime.json").write_text(json.dumps(regime, indent=2))
    print(f"  → regime: {regime['regime']} (top-1 conf {regime['top1_confidence']:.2f})")

    # ---------- 2. CMAs ----------
    print(f"\n[2/6] Building CMAs for {len(tickers)} assets…")
    cmas = build_cmas(tickers, regime, lookback_years=lookback_years)
    (out_dir / "cmas.json").write_text(json.dumps(cmas, indent=2))
    print(f"  → CMAs built for {len(cmas['cmas'])} tickers")

    # ---------- 3. covariance ----------
    print(f"\n[3/6] Estimating covariance ({cov_method})…")
    cov = build_cov(tickers, method=cov_method, years=lookback_years)
    (out_dir / "covariance.json").write_text(json.dumps(cov, indent=2))
    print(f"  → shrinkage λ={cov['shrinkage_intensity']:.3f}, "
          f"cond={cov['condition_number']:.1f}")

    # ---------- 4. portfolio construction ----------
    print(f"\n[4/6] Running 10 PC methods…")
    pc_proposals = run_pc(
        str(out_dir / "cmas.json"),
        str(out_dir / "covariance.json"),
        ips_path,
        str(out_dir / "pc_proposals.json"),
        regime=regime["regime"],
    )
    feas = sum(1 for p in pc_proposals["proposals"] if p["feasible"])
    print(f"  → {feas}/{len(pc_proposals['proposals'])} feasible proposals")

    # ---------- 5. peer review ----------
    print(f"\n[5/6] Peer review + Borda voting…")
    peer = review(
        str(out_dir / "pc_proposals.json"),
        ips_path,
        top_k=top_k,
    )
    (out_dir / "peer_review.json").write_text(json.dumps(peer, indent=2))
    print(f"  → survivors: {peer['survivors']}")

    # ---------- 6. CIO ensemble ----------
    print(f"\n[6/6] CIO ensemble + board memo…")
    final = run_ensemble(
        str(out_dir / "cmas.json"),
        str(out_dir / "covariance.json"),
        ips_path,
        str(out_dir / "pc_proposals.json"),
        str(out_dir / "peer_review.json"),
        str(out_dir / "regime.json"),
        str(out_dir / "final_portfolio.json"),
        str(out_dir / "board_memo.md"),
    )
    print(f"  → chosen: {final['ensemble_method']}, "
          f"vol={final['metrics']['volatility']:.2%}, "
          f"Sharpe={final['metrics']['sharpe']:+.2f}")
    if final["escalate_to_human"]:
        print(f"  ! ESCALATE: {final['escalation_reason']}")

    print(f"\nAll outputs in {out_dir}/")
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ips", default=str(REPO / "ips" / "ips_template.md"))
    parser.add_argument("--run-id", default="demo01")
    parser.add_argument("--lookback-years", type=float, default=10.0)
    parser.add_argument("--cov-method", default="ledoit_wolf")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    run_pipeline(args.ips, args.run_id, args.lookback_years,
                 args.cov_method, args.top_k)
