"""Contract, finite-state, and provenance tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.governance import (
    GovernanceError,
    GovernedRun,
    SchemaGateError,
    StageOrderError,
    VerificationError,
    validate_artifact,
    verify_run,
)

AS_OF = "2026-05-08"
TICKERS = ["AAA", "BBB"]


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


def _artifacts() -> dict[str, dict]:
    metrics = {
        "expected_return": 0.06,
        "volatility": 0.08426149773176358,
        "sharpe": 0.23735633163877062,
        "max_weight": 0.5,
        "effective_n": 2.0,
        "diversification_ratio": 1.3054598240132387,
    }
    weights = {"AAA": 0.5, "BBB": 0.5}
    return {
        "regime": {
            "as_of": AS_OF,
            "data_through": "2026-04-30",
            "vintage_policy": "latest_revision_cutoff",
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
            "notes": "Synthetic regime fixture.",
        },
        "cmas": {
            "as_of": AS_OF,
            "data_through": "2026-05-08",
            "lookback_years": 5.0,
            "regime": "expansion",
            "cmas": [
                {
                    "ticker": ticker,
                    "expected_return": 0.06,
                    "volatility": 0.12 if ticker == "AAA" else 0.10,
                    "confidence": 0.7,
                    "regime_tilt": 0.01,
                    "memo": f"Synthetic CMA for {ticker}.",
                }
                for ticker in TICKERS
            ],
        },
        "covariance": {
            "as_of": AS_OF,
            "data_through": "2026-05-08",
            "method": "ledoit_wolf",
            "tickers": TICKERS,
            "covariance": [[0.0144, 0.002], [0.002, 0.01]],
            "shrinkage_intensity": 0.25,
            "condition_number": 1.6444743963351023,
            "lookback_years": 5.0,
            "min_eigenvalue": 0.0092267862505363,
            "psd_repaired": False,
            "n_observations": 2,
            "missing_fraction": 0.0,
        },
        "pc_proposals": {
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
        },
        "peer_review": {
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
        },
        "final_portfolio": {
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
        },
    }


def _commit_valid_inputs(run: GovernedRun) -> None:
    run.commit_input(
        "macro",
        b"date,INDPRO,CPIAUCSL,DFF,T10Y3M,NFCI\n2026-04-30,1,1,1,1,1\n",
        {
            "as_of": AS_OF,
            "data_through": "2026-04-30",
            "vintage_policy": "latest_revision_cutoff",
            "series": ["INDPRO", "CPIAUCSL", "DFF", "T10Y3M", "NFCI"],
            "rows": 1,
        },
    )
    run.commit_input(
        "prices",
        (
            b"date,AAA,BBB\n"
            b"2026-05-06,98,101\n"
            b"2026-05-07,99,100\n"
            b"2026-05-08,100,100\n"
        ),
        {
            "as_of": AS_OF,
            "data_through": AS_OF,
            "tickers": TICKERS,
            "lookback_years": 5.0,
            "rows": 3,
        },
    )


def _complete_run(
    tmp_path: Path, stage_artifacts: dict[str, dict] | None = None
) -> Path:
    ips_path = tmp_path / "source-ips.md"
    _write_ips(ips_path)
    run = GovernedRun(
        tmp_path / "outputs",
        "test-run",
        ips_path,
        {
            "as_of": AS_OF,
            "lookback_years": 5.0,
            "covariance_method": "ledoit_wolf",
            "risk_free_rate": 0.04,
            "top_k": 1,
        },
    )
    _commit_valid_inputs(run)
    for stage, payload in (stage_artifacts or _artifacts()).items():
        run.commit_json(stage, payload)
    run.commit_attachment("board_memo.md", "# Board memo\n")
    run.complete()
    return run.run_dir


def test_complete_run_verifies(tmp_path: Path):
    run_dir = _complete_run(tmp_path)
    report = verify_run(run_dir)
    assert report["ok"] is True
    assert report["artifacts_verified"] == 7
    assert report["contracts_verified"] == 6
    assert report["inputs_verified"] == 3
    assert report["events_verified"] == 11
    assert report["cross_artifact_verified"] is True


def test_artifact_tampering_is_detected(tmp_path: Path):
    run_dir = _complete_run(tmp_path)
    target = run_dir / "cmas.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["cmas"][0]["expected_return"] = 9.99
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(VerificationError, match="mismatch"):
        verify_run(run_dir)


def test_schema_contract_tampering_is_detected(tmp_path: Path):
    run_dir = _complete_run(tmp_path)
    target = run_dir / "contracts" / "cmas.schema.json"
    target.write_text("{}", encoding="utf-8")
    with pytest.raises(VerificationError, match="contract .* mismatch"):
        verify_run(run_dir)


def test_raw_input_tampering_is_detected(tmp_path: Path):
    run_dir = _complete_run(tmp_path)
    target = run_dir / "inputs" / "prices.csv"
    target.write_bytes(target.read_bytes().replace(b"100,100", b"101,100"))
    with pytest.raises(VerificationError, match="Input snapshot hash mismatch"):
        verify_run(run_dir)


def test_cross_artifact_lineage_mismatch_is_detected(tmp_path: Path):
    artifacts = _artifacts()
    artifacts["cmas"]["regime"] = "recession"
    run_dir = _complete_run(tmp_path, artifacts)
    with pytest.raises(VerificationError, match="CMA regime differs"):
        verify_run(run_dir)


def test_rehashed_ips_violation_is_detected_by_cross_contract(tmp_path: Path):
    artifacts = _artifacts()
    artifacts["pc_proposals"]["proposals"][0]["weights"] = {
        "AAA": 0.9,
        "BBB": 0.1,
    }
    run_dir = _complete_run(tmp_path, artifacts)
    with pytest.raises(VerificationError, match="violates IPS maximum weights"):
        verify_run(run_dir)


def test_stage_order_is_fail_closed(tmp_path: Path):
    ips_path = tmp_path / "ips.md"
    _write_ips(ips_path)
    run = GovernedRun(tmp_path / "outputs", "order-test", ips_path, {})
    _commit_valid_inputs(run)
    with pytest.raises(StageOrderError, match="Expected stage 'regime'"):
        run.commit_json("cmas", _artifacts()["cmas"])


def test_stage_commit_requires_raw_inputs(tmp_path: Path):
    ips_path = tmp_path / "ips.md"
    _write_ips(ips_path)
    run = GovernedRun(tmp_path / "outputs", "missing-inputs", ips_path, {})
    with pytest.raises(StageOrderError, match="governed inputs"):
        run.commit_json("regime", _artifacts()["regime"])


@pytest.mark.parametrize("run_id", ["../escape", "/absolute", "has space", "", "."])
def test_unsafe_run_ids_are_rejected(tmp_path: Path, run_id: str):
    ips_path = tmp_path / "ips.md"
    _write_ips(ips_path)
    with pytest.raises(GovernanceError):
        GovernedRun(tmp_path / "outputs", run_id, ips_path, {})


def test_schema_rejects_unknown_properties():
    payload = _artifacts()["regime"] | {"untrusted_field": "ignored?"}
    with pytest.raises(SchemaGateError, match="Additional properties"):
        validate_artifact("regime", payload)


def test_semantic_gate_rejects_bad_weight_sum():
    payload = _artifacts()["final_portfolio"]
    payload["weights"] = {"AAA": 0.7, "BBB": 0.7}
    with pytest.raises(SchemaGateError, match="sum to 1.0"):
        validate_artifact("final_portfolio", payload)
