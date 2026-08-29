"""Network-free orchestration acceptance tests."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from pipeline import orchestrator
from pipeline.governance import SchemaGateError, verify_run

AS_OF = "2026-05-08"


def _write_ips(path: Path) -> None:
    path.write_text(
        """# Test IPS

| Field | Value |
| --- | --- |
| As-of date | 2026-05-08 |

| Annualised volatility (hard cap) | 18% |

| Ticker | Asset class | Min wt | Max wt |
| --- | --- | --- | --- |
| AAA | Asset A | 0.00 | 0.80 |
| BBB | Asset B | 0.00 | 0.80 |

If fewer than 1 proposal is feasible, escalate.
""",
        encoding="utf-8",
    )


def _install_stage_stubs(monkeypatch: pytest.MonkeyPatch, calls: dict) -> None:
    metrics = {
        "expected_return": 0.06,
        "volatility": 0.08426149773176358,
        "sharpe": 0.23735633163877062,
        "max_weight": 0.5,
        "effective_n": 2.0,
        "diversification_ratio": 1.3054598240132387,
    }
    weights = {"AAA": 0.5, "BBB": 0.5}

    dates = pd.date_range("2026-04-23", periods=8, freq="D")
    macro_frame = pd.DataFrame(
        {
            "INDPRO": range(8),
            "CPIAUCSL": range(8),
            "DFF": range(8),
            "T10Y3M": range(8),
            "NFCI": range(8),
        },
        index=dates,
    )
    macro_frame.attrs["requested_as_of"] = AS_OF
    macro_frame.attrs["vintage_policy"] = "fred_vintage_as_of"
    price_frame = pd.DataFrame(
        {"AAA": [99.0, 100.0, 101.0], "BBB": [101.0, 100.0, 99.0]},
        index=pd.to_datetime(["2026-05-06", "2026-05-07", "2026-05-08"]),
    )
    price_frame.attrs["requested_as_of"] = AS_OF
    price_frame.attrs["data_through"] = AS_OF

    def classify(as_of, indicators_df):
        calls["classify_as_of"] = as_of
        assert indicators_df.equals(macro_frame)
        return {
            "as_of": as_of,
            "data_through": "2026-04-30",
            "vintage_policy": "fred_vintage_as_of",
            "regime": "expansion",
            "scores": {
                "expansion": 0.4,
                "late_cycle": 0.2,
                "recession": 0.2,
                "recovery": 0.2,
            },
            "top1_confidence": 0.4,
            "top1_confidence_low": False,
            "indicators": {
                "growth": 0.1,
                "inflation": -0.1,
                "monetary": 0.0,
                "financial_conditions": -0.1,
            },
            "notes": "Synthetic regime.",
        }

    def build_cmas(tickers, regime, lookback, as_of, prices):
        calls["cma_as_of"] = as_of
        assert prices.equals(price_frame)
        return {
            "as_of": as_of,
            "data_through": as_of,
            "lookback_years": lookback,
            "regime": regime["regime"],
            "cmas": [
                {
                    "ticker": ticker,
                    "expected_return": 0.06,
                    "volatility": 0.12 if ticker == "AAA" else 0.10,
                    "confidence": 0.7,
                    "regime_tilt": 0.01,
                    "memo": f"CMA for {ticker}.",
                }
                for ticker in tickers
            ],
        }

    def build_cov(tickers, method, years, as_of, prices):
        calls["cov_as_of"] = as_of
        assert prices.equals(price_frame)
        return {
            "as_of": as_of,
            "data_through": as_of,
            "method": method,
            "tickers": tickers,
            "covariance": [[0.0144, 0.002], [0.002, 0.01]],
            "shrinkage_intensity": 0.2,
            "condition_number": 1.6444743963351023,
            "lookback_years": years,
            "min_eigenvalue": 0.009,
            "psd_repaired": False,
            "n_observations": 2,
            "missing_fraction": 0.0,
        }

    def run_pc(cmas_path, cov_path, ips_path, out_path, regime):
        assert out_path is None
        return {
            "as_of": AS_OF,
            "proposals": [
                {
                    "method": "equal_weight",
                    "status": "ok",
                    "weights": weights,
                    "metrics": metrics,
                    "feasible": True,
                    "rationale": "Synthetic proposal.",
                }
            ],
        }

    def review(proposals_path, ips_path, top_k):
        return {
            "as_of": AS_OF,
            "borda": [
                {
                    "method": "equal_weight",
                    "borda_points": 0.0,
                    "mean_review_score": 3.0,
                    "review_breakdown": {
                        "risk_adj_return": 3.0,
                        "diversification": 3.0,
                        "robustness": 3.0,
                    },
                }
            ],
            "survivors": ["equal_weight"],
            "adversarial_challenger": None,
            "filtered_out": [],
        }

    def ensemble(*args):
        assert args[-2:] == (None, None)
        return {
            "as_of": AS_OF,
            "regime": "expansion",
            "ensemble_method": "sharpe_weighted",
            "weights": weights,
            "metrics": metrics,
            "all_ensembles": {"sharpe_weighted": weights},
            "dissenting_view": {
                "method": "equal_weight",
                "weights": weights,
                "rationale": "Synthetic proposal.",
            },
            "escalate_to_human": False,
            "escalation_reason": "",
        }

    monkeypatch.setattr(orchestrator, "classify", classify)
    monkeypatch.setattr(orchestrator, "fetch_indicators", lambda as_of: macro_frame)
    monkeypatch.setattr(
        orchestrator,
        "fetch_prices",
        lambda tickers, years, as_of: price_frame,
    )
    monkeypatch.setattr(orchestrator, "build_cmas", build_cmas)
    monkeypatch.setattr(orchestrator, "build_cov", build_cov)
    monkeypatch.setattr(orchestrator, "run_pc", run_pc)
    monkeypatch.setattr(orchestrator, "review", review)
    monkeypatch.setattr(orchestrator, "run_ensemble", ensemble)
    monkeypatch.setattr(orchestrator, "render_board_memo", lambda *args: "# Memo\n")


def test_pipeline_propagates_as_of_and_produces_verifiable_run(tmp_path: Path, monkeypatch):
    ips_path = tmp_path / "ips.md"
    _write_ips(ips_path)
    calls = {}
    _install_stage_stubs(monkeypatch, calls)

    final = orchestrator.run_pipeline(
        str(ips_path),
        run_id="acceptance",
        lookback_years=5.0,
        cov_method="ledoit_wolf",
        top_k=1,
        output_root=tmp_path / "outputs",
    )

    assert final["weights"] == {"AAA": 0.5, "BBB": 0.5}
    assert calls == {
        "classify_as_of": AS_OF,
        "cma_as_of": AS_OF,
        "cov_as_of": AS_OF,
    }
    report = verify_run(tmp_path / "outputs" / "acceptance")
    assert report["artifacts_verified"] == 7
    assert report["contracts_verified"] == 6
    assert report["inputs_verified"] == 3
    manifest = json.loads(
        (tmp_path / "outputs" / "acceptance" / "run_manifest.json").read_text()
    )
    assert manifest["parameters"]["as_of"] == AS_OF


def test_pipeline_records_failure_before_invalid_artifact(tmp_path: Path, monkeypatch):
    ips_path = tmp_path / "ips.md"
    _write_ips(ips_path)
    calls = {}
    _install_stage_stubs(monkeypatch, calls)
    monkeypatch.setattr(
        orchestrator,
        "classify",
        lambda as_of, indicators_df: {
            "as_of": as_of,
            "data_through": as_of,
            "vintage_policy": "latest_revision_cutoff",
            "regime": "expansion",
            "scores": {
                "expansion": 0.7,
                "late_cycle": 0.2,
                "recession": 0.2,
                "recovery": 0.2,
            },
            "top1_confidence": 0.7,
            "top1_confidence_low": False,
            "indicators": {
                "growth": 0.1,
                "inflation": 0.0,
                "monetary": 0.0,
                "financial_conditions": 0.0,
            },
            "notes": "Invalid probabilities.",
        },
    )

    with pytest.raises(SchemaGateError, match="sum to 1.0"):
        orchestrator.run_pipeline(
            str(ips_path), run_id="failed", output_root=tmp_path / "outputs"
        )

    run_dir = tmp_path / "outputs" / "failed"
    assert not (run_dir / "regime.json").exists()
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["failure"]["failed_before_stage"] == "regime"
    assert verify_run(run_dir, require_complete=False)["status"] == "failed"
