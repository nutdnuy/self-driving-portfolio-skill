"""End-to-end demo of the agentic SAA pipeline.

Run from the repo root:

    python examples/run_demo.py

Outputs land in a unique timestamped directory under `outputs/`.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.orchestrator import run_pipeline  # noqa: E402

if __name__ == "__main__":
    run_pipeline(
        ips_path=str(REPO / "ips" / "ips_template.md"),
        lookback_years=10.0,
        cov_method="ledoit_wolf",
        top_k=5,
    )
