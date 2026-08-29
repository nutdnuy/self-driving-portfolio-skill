---
name: covariance
description: This skill should be used when the user asks to "estimate a covariance matrix", "run Ledoit-Wolf shrinkage", "build an EWMA covariance", or validate PSD risk inputs for portfolio construction.
---

# covariance

Covariance estimation for the SAA pipeline.

## Methods

| `method`        | Description |
| --------------- | --- |
| `sample`        | Plain MLE; use only when T ≫ N. |
| `ewma`          | Exponentially-weighted, λ=0.94 (RiskMetrics-style). |
| `ledoit_wolf`   | Linear shrinkage toward a constant-correlation target. **Default.** |

All matrices are returned **annualised** (×252 for daily inputs).

Require at least 60 complete aligned return rows. Symmetrise each estimate and
clip non-positive eigenvalues to a scale-aware floor. Record the original
minimum eigenvalue, repair flag, condition number, aligned sample size, and
missing-data fraction. Treat repair as numerical stabilization, not economic
validation.

## CLI

```bash
python skills/covariance/scripts/build_cov.py \
       --tickers SPY,EFA,EEM,IEF,LQD,TIP,GLD,VNQ,BIL \
       --method ledoit_wolf \
       --as-of 2026-05-08 \
       --out outputs/demo01/covariance.json
```

Run through `pipeline/orchestrator.py` for schema gating and governed output.
