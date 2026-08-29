"""Unit tests for the IPS markdown parser."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "portfolio-construction" / "scripts"))
from utils import parse_ips  # noqa: E402


def test_parse_default_ips():
    ips = parse_ips(REPO / "ips" / "ips_template.md")
    assert "SPY" in ips["tickers"]
    assert "IEF" in ips["tickers"]
    assert len(ips["tickers"]) == len(ips["min_w"]) == len(ips["max_w"])
    assert (ips["min_w"] >= 0).all()
    assert (ips["max_w"] <= 1).all()
    assert (ips["max_w"] >= ips["min_w"]).all()
    assert ips["as_of"] == "2026-05-08"
    assert ips["vol_cap"] == pytest.approx(0.18)
    assert ips["min_feasible_proposals"] == 5


def test_parse_ips_rejects_impossible_bounds(tmp_path):
    path = tmp_path / "impossible.md"
    path.write_text(
        """| Ticker | Asset | Min wt | Max wt |
| --- | --- | --- | --- |
| AAA | A | 0.60 | 0.80 |
| BBB | B | 0.60 | 0.80 |
"""
    )
    with pytest.raises(ValueError, match="infeasible"):
        parse_ips(path)


def test_parse_ips_rejects_malformed_asset_row(tmp_path):
    path = tmp_path / "malformed.md"
    path.write_text(
        """| Ticker | Asset | Min wt | Max wt |
| --- | --- | --- | --- |
| AAA | A | not-a-number | 0.80 |

| Annualised volatility (hard cap) | 18% |
If fewer than 1 proposal is feasible, escalate.
"""
    )
    with pytest.raises(ValueError, match="Non-numeric"):
        parse_ips(path)


def test_parse_ips_requires_diversifiable_universe(tmp_path):
    path = tmp_path / "single-asset.md"
    path.write_text(
        """| Ticker | Asset | Min wt | Max wt |
| --- | --- | --- | --- |
| AAA | A | 0.00 | 1.00 |

| Annualised volatility (hard cap) | 18% |
If fewer than 1 proposal is feasible, escalate.
"""
    )
    with pytest.raises(ValueError, match="at least two"):
        parse_ips(path)
