"""Unit tests for the IPS markdown parser."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

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
