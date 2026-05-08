---
name: cio-ensemble
description: Combine surviving portfolio proposals into one recommended policy portfolio using seven ensemble methods, pick the regime-appropriate combiner, and produce a board memo for human review. Use as the final stage of the SAA pipeline.
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
- Fewer than 5 IPS-feasible proposals survived peer review.
- Adversarial diversifier won the head-to-head.
- Top-1 regime confidence below 0.4.
