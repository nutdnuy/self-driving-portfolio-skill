"""Covariance safety tests."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "covariance" / "scripts"))
from build_cov import nearest_psd  # noqa: E402


def test_nearest_psd_repairs_negative_eigenvalue():
    repaired, min_eigenvalue, changed = nearest_psd(np.array([[1.0, 2.0], [2.0, 1.0]]))
    assert min_eigenvalue < 0
    assert changed is True
    assert np.linalg.eigvalsh(repaired).min() > 0
    assert np.allclose(repaired, repaired.T)
