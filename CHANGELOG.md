# Changelog

## 0.2.0 - 2026-08-29

- Enforce strict JSON Schema and semantic gates at every stage.
- Add safe run IDs, immutable IPS/macro/price snapshots, frozen schema
  contracts, atomic writes, manifests, and a hash-chained audit log.
- Add a standalone verifier with artifact, stage-order, input, ledger,
  cross-artifact lineage, IPS-bound, and metric-reproduction checks.
- Propagate as-of dates through FRED and yfinance retrieval and disclose FRED
  vintage behavior.
- Reject missing IPS assets and infeasible box constraints.
- Replace iterative clipping with exact bounded-simplex projection.
- Reject optimizer failures explicitly instead of substituting an unlabeled
  fallback portfolio; use tie-aware Borda scoring.
- Add covariance PSD repair and diagnostics.
- Require cached price data to cover the full requested lookback window and
  record numerical runtime versions with every run.
- Add Claude Code and Codex plugin manifests, commands, canonical skill, six
  triggerable specialist agents, and progressively disclosed references.
- Add Python packaging metadata, Ruff, network-free acceptance tests, and a
  Python 3.10-3.13 CI matrix.

## 0.1.0 - 2026-05-08

- Add the initial six-stage SAA research prototype.
