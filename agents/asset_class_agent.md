# Asset-Class Agent

**Position in pipeline**: stage 2 of 6.

One instance is spawned **per ticker** in the IPS asset universe. They run
in parallel.

## Role
Produce a Capital Market Assumption (CMA) for the assigned asset:
expected return, volatility, and a 0–1 confidence score, plus a markdown
investment-case memo.

## Inputs
- `ticker`
- `regime.json`
- IPS time horizon
- Lookback window (default 10 years)

## Workflow
1. `fetch_prices.py` — load adjusted closes via yfinance.
2. `build_cma.py`:
   - historical mean & vol (annualised);
   - macro-regime tilt: nudge expected return by a regime-conditional
     amount (`asset_regime_tilt` table inside the script);
   - confidence = `f(sample_size, vol_stability, regime_score_top1)`.
3. Write a one-paragraph investment-case memo (the LLM does this when run
   from inside an agent loop; the script writes a templated version).

## Output contract
`schemas/cmas.schema.json` (one row per ticker).
