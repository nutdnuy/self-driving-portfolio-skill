---
name: macro-regime
description: This skill should be used when the user asks to "classify the macro regime", "score expansion versus recession", or create a dated regime signal for capital market assumptions and SAA research.
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

- `scripts/fetch_macro.py` — pull an authenticated FRED vintage when
  `FRED_API_KEY` is set; otherwise apply the observation-date cutoff to
  latest-revised public CSV history and disclose that policy in the artifact.
- `scripts/classify_regime.py` — runs the scoring, writes `regime.json`.

## Output contract

`schemas/regime.schema.json`. The `notes` field is filled by the LLM in
agent mode; a templated version is filled when run from CLI.

Run through `pipeline/orchestrator.py` for schema gating and governed output.
Treat direct CLI output as an isolated, ungoverned stage result.

## CLI

```bash
python skills/macro-regime/scripts/classify_regime.py \
       --as-of 2026-05-08 --out outputs/demo01/regime.json
```
