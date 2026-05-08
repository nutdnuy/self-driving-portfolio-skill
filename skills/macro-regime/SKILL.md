---
name: macro-regime
description: Classify the current US macro regime into expansion / late_cycle / recession / recovery using a four-dimensional weighted scoring framework (growth, inflation, monetary policy, financial conditions). Use when an upstream agent needs a regime label and soft regime-score vector to condition CMAs, portfolio-construction tilts, or ensemble selection.
---

# macro-regime

The 4-regime classifier from Ang/Azimbayev/Kim (2026) §3.2.

## Methodology

Four indicator families are scored on a [-1, +1] scale (positive = "hot",
negative = "cold"). Each family is a z-score of recent readings vs a
rolling 5-year baseline.

| Family                | FRED series                          |
| --------------------- | ------------------------------------ |
| Growth                | INDPRO (industrial production, YoY)  |
| Inflation             | CPIAUCSL (headline CPI YoY)          |
| Monetary policy       | DFF − T10Y3M (real-curve proxy: fed funds minus 10y-3m spread) |
| Financial conditions  | NFCI (Chicago Fed; positive = tight) |

The regime score is a fixed-weight projection (paper §3.2):

```
expansion  =  +growth  −0.5·inflation  −0.5·monetary  −1.0·fci
late_cycle =  +growth  +1.0·inflation  +1.0·monetary  +0.5·fci
recession  =  −growth  −0.5·inflation  +0.0·monetary  +1.0·fci
recovery   =  +growth  −1.0·inflation  −1.0·monetary  −0.5·fci
```

Scores are softmax-normalised across the four labels. The argmax is the
regime label; the full vector is exposed downstream.

## Scripts

- `scripts/fetch_macro.py` — pulls FRED data via the public CSV endpoint
  (no API key needed; FRED_API_KEY is honoured if set).
- `scripts/classify_regime.py` — runs the scoring, writes `regime.json`.

## Output contract

`schemas/regime.schema.json`. The `notes` field is filled by the LLM in
agent mode; a templated version is filled when run from CLI.

## CLI

```bash
python skills/macro-regime/scripts/classify_regime.py \
       --as-of 2026-05-08 --out outputs/demo01/regime.json
```
