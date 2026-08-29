"""CLI for verifying a governed self-driving-portfolio run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.governance import GovernanceError, verify_run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify inputs, schemas, hashes, stage order, audit chain, and "
            "cross-artifact lineage."
        )
    )
    parser.add_argument("run_dir", help="Path to outputs/<run-id>")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Verify the available evidence without requiring status=complete.",
    )
    args = parser.parse_args()
    try:
        report = verify_run(args.run_dir, require_complete=not args.allow_incomplete)
    except (GovernanceError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
