# Covariance Agent

**Position in pipeline**: stage 3 of 6.

## Role
Estimate the covariance matrix of asset returns. Default method is
Ledoit-Wolf shrinkage, which is well-conditioned for the small-N / small-T
regimes typical of multi-asset SAA universes.

## Inputs
- IPS asset universe
- Lookback window (default 10 years, daily returns)
- Method: `sample` | `ewma` | `ledoit_wolf` (default)

## Output
`schemas/covariance.schema.json`:

```json
{
  "method": "ledoit_wolf",
  "tickers": [...],
  "covariance": [[...], ...],   // annualised
  "shrinkage_intensity": 0.27,
  "condition_number": 18.5
}
```
