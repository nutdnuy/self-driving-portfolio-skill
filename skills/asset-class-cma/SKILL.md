---
name: asset-class-cma
description: This skill should be used when the user asks to "build capital market assumptions", "estimate asset-class returns", or create regime-conditioned return, volatility, and confidence inputs for portfolio construction.
---

# asset-class-cma

Given a list of tickers and the regime classification, produce a CMA per
ticker.

## Methodology

1. Pull adjusted close prices via yfinance (default 10y daily lookback) and
   reject every row after the shared as-of date.
2. Compute geometric mean return and annualised volatility from log-returns.
3. Apply a regime-conditional tilt to expected return:

   | Asset class proxy | expansion | late_cycle | recession | recovery |
   | --- | --- | --- | --- | --- |
   | Equities (SPY, EFA, EEM, VNQ) | +1.5% | −0.5% | −3.0% | +2.0% |
   | Treasuries (IEF, BIL)         | −0.5% | −0.5% | +1.5% | +0.5% |
   | Credit (LQD)                  |  0.0% | −1.0% | −1.5% | +1.0% |
   | Inflation-linked (TIP, GLD)   | +0.5% | +1.5% | +0.0% | −0.5% |

   Tilts are scaled by the regime's softmax probability so that a
   low-confidence call applies a smaller tilt.

4. Confidence (0–1) = sample-size factor × vol-stability factor
   × regime-confidence factor.

Stop when any IPS ticker is unavailable or has fewer than 60 usable returns.
Never shrink the mandate universe silently.

## CLI

```bash
python skills/asset-class-cma/scripts/build_cma.py \
       --regime outputs/demo01/regime.json \
       --tickers SPY,EFA,EEM,IEF,LQD,TIP,GLD,VNQ,BIL \
       --as-of 2026-05-08 \
       --out outputs/demo01/cmas.json
```

Run through `pipeline/orchestrator.py` for schema gating and governed output.
