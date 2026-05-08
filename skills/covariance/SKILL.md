---
name: covariance
description: Estimate the asset-return covariance matrix using sample, EWMA, or Ledoit-Wolf shrinkage estimators. Use when an upstream agent needs an annualised covariance matrix to feed portfolio-construction methods.
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

## CLI

```bash
python skills/covariance/scripts/build_cov.py \
       --tickers SPY,EFA,EEM,IEF,LQD,TIP,GLD,VNQ,BIL \
       --method ledoit_wolf \
       --out outputs/demo01/covariance.json
```
