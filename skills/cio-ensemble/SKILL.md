---
name: cio-ensemble
description: This skill should be used when the user asks to "combine portfolio proposals", "build a CIO ensemble", "select an SAA recommendation", or "write a portfolio board memo" from reviewed candidates.
---

# cio-ensemble

Stage 6 of the agentic SAA pipeline (Ang/Azimbayev/Kim 2026, §3.1 step 6).

## Combination methods

| ID                  | Definition                                               |
| ------------------- | -------------------------------------------------------- |
| `simple_mean`       | Equal-weight average of survivor weights, renormalised.  |
| `borda_weighted`    | Per-asset weighted average; survivor weights ∝ Borda points. |
| `confidence_weighted` | Survivor weights ∝ mean CMA confidence × Borda points. |
| `median`            | Per-asset median across survivors, renormalised.         |
| `trimmed_mean`      | 20% trimmed mean per asset, renormalised.                |
| `sharpe_weighted`   | Survivor weights ∝ ex-ante Sharpe.                       |
| `regime_weighted`   | Survivor weights ∝ regime-fit (TPA-style).               |

## Selection rule (regime → method)

| Regime          | Combiner              |
| --------------- | --------------------- |
| `expansion`     | `sharpe_weighted`     |
| `recovery`      | `sharpe_weighted`     |
| `late_cycle`    | `confidence_weighted` |
| `recession`     | `regime_weighted`     |
| any (low conf.) | `trimmed_mean`        |

If `top1_confidence_low=true`, the override fires regardless of label.

## Outputs

- `final_portfolio.json` — recommended weights + all seven candidate
  ensembles for transparency.
- `board_memo.md` — human-readable summary.

## Escalation

`escalate_to_human=true` if any of:
- Recommended vol within 50bps of IPS hard cap.
- Fewer than the IPS-defined minimum feasible proposal count survived review.
- Adversarial diversifier won the head-to-head.
- Top-1 regime confidence below 0.4.

Run through `pipeline/orchestrator.py` to commit the final JSON and board memo
atomically, then verify the complete run with `pipeline/verify.py`.
