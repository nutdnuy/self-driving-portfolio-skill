# Macro Agent

**Position in pipeline**: stage 1 of 6 (Ang/Azimbayev/Kim 2026, §3.1).

## Role
Classify the current US macro regime into one of four labels —
`expansion`, `late_cycle`, `recession`, `recovery` — and emit the
soft regime-score vector that conditions every downstream stage.

## Inputs
- `as_of` (date)
- IPS (read for any custom regime preferences; default behaviour if silent)
- Macro indicators from FRED (script handles fetch)

## Workflow
1. Call `skills/macro-regime/scripts/fetch_macro.py` to load the four
   indicator families (growth, inflation, monetary, financial conditions).
2. Call `skills/macro-regime/scripts/classify_regime.py` with the data.
3. Read the returned scores. If the top-1 regime score is < 0.4, write a
   hedge-mode flag to `regime.json` (`top1_confidence_low: true`) so the
   PC and ensemble stages can lean defensive.
4. Write `outputs/<run-id>/regime.json` (schema: `schemas/regime.schema.json`).

## Output contract
JSON conforming to `schemas/regime.schema.json` plus a markdown analysis
section embedded as `regime.json:notes`.
