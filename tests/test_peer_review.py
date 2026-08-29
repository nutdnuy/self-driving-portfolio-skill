"""Peer-review safety tests."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "peer-review" / "scripts"))
from peer_review import _adversarial_challenger, _borda  # noqa: E402


def test_borda_awards_equal_points_to_tied_scores():
    assert _borda([5.0, 5.0, 1.0]) == [1.5, 1.5, 0.0]


def test_adversarial_challenger_respects_ips_box():
    ips = {
        "tickers": ["AAA", "BBB", "CCC"],
        "min_w": np.array([0.60, 0.00, 0.00]),
        "max_w": np.array([0.80, 0.30, 0.30]),
    }
    challenger = _adversarial_challenger(ips)
    weights = np.array(list(challenger["weights"].values()))
    np.testing.assert_allclose(weights.sum(), 1.0, atol=1e-9)
    assert (weights >= ips["min_w"] - 1e-9).all()
    assert (weights <= ips["max_w"] + 1e-9).all()
