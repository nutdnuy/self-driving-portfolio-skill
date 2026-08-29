---
description: Run a new IPS-governed Strategic Asset Allocation pipeline
argument-hint: "<IPS path> <run id> [as-of date]"
allowed-tools: Bash(cd:*), Bash(python:*), Bash(python3:*)
---

Create a new governed SAA research run.

Confirm the IPS path, unique run ID, as-of date, lookback, covariance method,
survivor count, and output root. Resolve the IPS and output root to absolute
paths before changing directories. Do not reuse an existing run directory.

Run:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 pipeline/orchestrator.py \
  --ips "<absolute IPS path>" \
  --run-id "<run id>" \
  --as-of "<YYYY-MM-DD>" \
  --lookback-years 10 \
  --cov-method ledoit_wolf \
  --top-k 5 \
  --output-root "<absolute output root>"
```

Do not continue after a schema, universe, stage-order, PSD, or hash failure.
Report the output directory, verification counts, final weights, key metrics,
FRED vintage policy, and every human-escalation reason. Never place orders.
