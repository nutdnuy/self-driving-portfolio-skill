"""Run the six-stage Strategic Asset Allocation pipeline under governance.

Every stage result must pass a strict JSON Schema and semantic gate before the
next stage can read it. The runner snapshots the IPS, writes atomically, and
records artifact hashes in a hash-chained audit log.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import platform
import sys
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "skills" / "macro-regime" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "asset-class-cma" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "covariance" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "portfolio-construction" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "peer-review" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "cio-ensemble" / "scripts"))

from build_cma import build_cmas  # noqa: E402
from build_cov import build_cov  # noqa: E402
from classify_regime import classify  # noqa: E402
from ensemble import ensemble as run_ensemble  # noqa: E402
from ensemble import render_board_memo  # noqa: E402
from fetch_macro import fetch_indicators  # noqa: E402
from fetch_prices import fetch_prices  # noqa: E402
from peer_review import review  # noqa: E402
from run_all import run as run_pc  # noqa: E402
from utils import RISK_FREE_RATE, parse_ips  # noqa: E402

from pipeline import __version__  # noqa: E402
from pipeline.governance import GovernedRun, verify_run  # noqa: E402


def generate_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"sdp-{stamp}"


def engine_source_sha256() -> str:
    """Hash the deterministic engine source used by a run."""
    source_files = sorted((REPO / "pipeline").glob("*.py"))
    source_files.extend(sorted((REPO / "skills").glob("*/scripts/*.py")))
    digest = hashlib.sha256()
    for path in source_files:
        relative = path.relative_to(REPO).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def runtime_versions() -> dict[str, str]:
    """Record numerical/runtime versions needed to reproduce a run."""
    packages = ("numpy", "pandas", "scipy", "yfinance", "jsonschema")
    return {
        "python": platform.python_version(),
        **{package: importlib.metadata.version(package) for package in packages},
    }


def dataframe_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Serialize a dated input frame deterministically for the run snapshot."""
    snapshot = frame.copy().sort_index()
    snapshot.index.name = "date"
    rendered = snapshot.to_csv(
        date_format="%Y-%m-%d",
        float_format="%.17g",
        lineterminator="\n",
    )
    return rendered.encode("utf-8")


def _normalise_as_of(value: str | None, ips_as_of: str | None) -> str:
    selected = value or ips_as_of
    if not selected:
        raise ValueError("Provide --as-of or add an As-of date row to the IPS")
    parsed = date.fromisoformat(selected)
    if parsed > date.today():
        raise ValueError(f"as_of cannot be in the future: {parsed}")
    return parsed.isoformat()


def _check_stage_context(
    stage: str,
    payload: Mapping[str, Any],
    expected_as_of: str,
    expected_tickers: list[str] | None = None,
) -> None:
    if payload.get("as_of") != expected_as_of:
        raise ValueError(
            f"{stage} as_of mismatch: {payload.get('as_of')!r} != {expected_as_of!r}"
        )
    data_through = payload.get("data_through")
    if data_through and date.fromisoformat(data_through) > date.fromisoformat(expected_as_of):
        raise ValueError(f"{stage} contains data after the requested as_of date")
    if expected_tickers is None:
        return
    if stage == "cmas":
        actual = [row["ticker"] for row in payload["cmas"]]
    elif stage == "covariance":
        actual = payload["tickers"]
    else:
        return
    if actual != expected_tickers:
        raise ValueError(
            f"{stage} universe/order mismatch: expected {expected_tickers}, received {actual}"
        )


def run_pipeline(
    ips_path: str,
    run_id: str | None = None,
    lookback_years: float = 10.0,
    cov_method: str = "ledoit_wolf",
    top_k: int = 5,
    as_of: str | None = None,
    output_root: str | Path | None = None,
) -> dict:
    """Execute a new, immutable run and return the final portfolio object."""
    if lookback_years <= 0:
        raise ValueError("lookback_years must be positive")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if cov_method not in {"sample", "ewma", "ledoit_wolf"}:
        raise ValueError(f"Unsupported covariance method: {cov_method}")

    initial_ips = parse_ips(ips_path)
    cutoff = _normalise_as_of(as_of, initial_ips["as_of"])
    selected_run_id = run_id or generate_run_id()
    parameters = {
        "engine_version": __version__,
        "engine_source_sha256": engine_source_sha256(),
        "runtime_versions": runtime_versions(),
        "as_of": cutoff,
        "lookback_years": lookback_years,
        "covariance_method": cov_method,
        "risk_free_rate": RISK_FREE_RATE,
        "top_k": top_k,
    }
    governed = GovernedRun(
        output_root or (REPO / "outputs"),
        selected_run_id,
        ips_path,
        parameters,
    )
    snapshot_ips_path = governed.run_dir / "inputs" / "ips.md"

    try:
        ips = parse_ips(snapshot_ips_path)
        if ips["tickers"] != initial_ips["tickers"] or ips["as_of"] != initial_ips["as_of"]:
            raise RuntimeError("IPS changed while the run snapshot was being created")
        tickers = ips["tickers"]

        print("\n[inputs] Fetching and snapshotting raw macro and price data...")
        macro_frame = fetch_indicators(cutoff)
        governed.commit_input(
            "macro",
            dataframe_csv_bytes(macro_frame),
            {
                "as_of": cutoff,
                "data_through": str(macro_frame.index.max().date()),
                "vintage_policy": macro_frame.attrs["vintage_policy"],
                "series": list(macro_frame.columns),
                "rows": int(len(macro_frame)),
            },
        )
        price_frame = fetch_prices(tickers, years=lookback_years, as_of=cutoff)
        governed.commit_input(
            "prices",
            dataframe_csv_bytes(price_frame),
            {
                "as_of": cutoff,
                "data_through": str(price_frame.index.max().date()),
                "tickers": list(price_frame.columns),
                "lookback_years": lookback_years,
                "rows": int(len(price_frame)),
            },
        )
        print(
            f"  -> macro rows={len(macro_frame)}, price rows={len(price_frame)}, "
            f"vintage={macro_frame.attrs['vintage_policy']}"
        )

        print("\n[1/6] Classifying macro regime...")
        regime = classify(cutoff, macro_frame)
        _check_stage_context("regime", regime, cutoff)
        governed.commit_json("regime", regime)
        print(
            f"  -> regime: {regime['regime']} "
            f"(top-1 confidence {regime['top1_confidence']:.2f})"
        )

        print(f"\n[2/6] Building CMAs for {len(tickers)} assets...")
        cmas = build_cmas(tickers, regime, lookback_years, cutoff, price_frame)
        _check_stage_context("cmas", cmas, cutoff, tickers)
        governed.commit_json("cmas", cmas)
        print(f"  -> CMAs built for {len(cmas['cmas'])} tickers")

        print(f"\n[3/6] Estimating covariance ({cov_method})...")
        covariance = build_cov(tickers, cov_method, lookback_years, cutoff, price_frame)
        _check_stage_context("covariance", covariance, cutoff, tickers)
        governed.commit_json("covariance", covariance)
        print(
            f"  -> shrinkage={covariance['shrinkage_intensity']:.3f}, "
            f"condition={covariance['condition_number']:.1f}, "
            f"PSD repaired={covariance['psd_repaired']}"
        )

        print("\n[4/6] Running 10 deterministic portfolio methods...")
        pc_proposals = run_pc(
            str(governed.run_dir / "cmas.json"),
            str(governed.run_dir / "covariance.json"),
            str(snapshot_ips_path),
            None,
            regime=regime["regime"],
        )
        _check_stage_context("pc_proposals", pc_proposals, cutoff)
        governed.commit_json("pc_proposals", pc_proposals)
        feasible_count = sum(
            1 for proposal in pc_proposals["proposals"] if proposal["feasible"]
        )
        print(f"  -> {feasible_count}/{len(pc_proposals['proposals'])} feasible proposals")

        print("\n[5/6] Running peer review and Borda voting...")
        peer = review(
            str(governed.run_dir / "pc_proposals.json"),
            str(snapshot_ips_path),
            top_k=top_k,
        )
        _check_stage_context("peer_review", peer, cutoff)
        governed.commit_json("peer_review", peer)
        print(f"  -> survivors: {peer['survivors']}")

        print("\n[6/6] Building CIO ensemble and board memo...")
        final = run_ensemble(
            str(governed.run_dir / "cmas.json"),
            str(governed.run_dir / "covariance.json"),
            str(snapshot_ips_path),
            str(governed.run_dir / "pc_proposals.json"),
            str(governed.run_dir / "peer_review.json"),
            str(governed.run_dir / "regime.json"),
            None,
            None,
        )
        _check_stage_context("final_portfolio", final, cutoff)
        governed.commit_json("final_portfolio", final)
        memo = render_board_memo(final, regime, cmas, pc_proposals, peer)
        governed.commit_attachment("board_memo.md", memo)
        verify_run(governed.run_dir, require_complete=False)
        governed.complete()

        verification = verify_run(governed.run_dir)
        print(
            f"  -> chosen: {final['ensemble_method']}, "
            f"vol={final['metrics']['volatility']:.2%}, "
            f"Sharpe={final['metrics']['sharpe']:+.2f}"
        )
        if final["escalate_to_human"]:
            print(f"  ! ESCALATE: {final['escalation_reason']}")
        print(
            f"\nVerified {verification['inputs_verified']} inputs, "
            f"{verification['contracts_verified']} contracts, "
            f"{verification['artifacts_verified']} artifacts, and "
            f"{verification['events_verified']} audit events in {governed.run_dir}/"
        )
        return final
    except BaseException as exc:
        governed.fail(exc)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ips", default=str(REPO / "ips" / "ips_template.md"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD; defaults to the IPS date")
    parser.add_argument("--lookback-years", type=float, default=10.0)
    parser.add_argument(
        "--cov-method",
        default="ledoit_wolf",
        choices=["sample", "ewma", "ledoit_wolf"],
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-root", default=str(REPO / "outputs"))
    args = parser.parse_args()
    run_pipeline(
        args.ips,
        args.run_id,
        args.lookback_years,
        args.cov_method,
        args.top_k,
        args.as_of,
        args.output_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
