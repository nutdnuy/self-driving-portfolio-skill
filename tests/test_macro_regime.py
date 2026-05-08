"""Unit tests for the macro-regime scoring math (no FRED dependency)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "macro-regime" / "scripts"))
from classify_regime import REGIME_WEIGHTS, score_regimes  # noqa: E402


def test_softmax_probabilities_sum_to_one():
    indicators = {"growth": 0.3, "inflation": -0.2, "monetary": 0.0,
                  "financial_conditions": -0.1}
    s = score_regimes(indicators)
    total = sum(s.values())
    assert abs(total - 1.0) < 1e-9
    assert all(0.0 <= v <= 1.0 for v in s.values())


def test_strong_growth_low_inflation_favours_expansion():
    s = score_regimes({"growth": 1.0, "inflation": -1.0,
                       "monetary": -0.5, "financial_conditions": -1.0})
    assert max(s, key=s.get) in {"expansion", "recovery"}


def test_negative_growth_tight_fci_favours_recession():
    s = score_regimes({"growth": -1.0, "inflation": 0.0,
                       "monetary": 0.0, "financial_conditions": 1.0})
    assert max(s, key=s.get) == "recession"


def test_regime_weights_complete():
    for name in ["expansion", "late_cycle", "recession", "recovery"]:
        assert name in REGIME_WEIGHTS
        assert len(REGIME_WEIGHTS[name]) == 4
