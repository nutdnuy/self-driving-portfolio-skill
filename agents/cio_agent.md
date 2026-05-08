# CIO Agent

**Position in pipeline**: stage 6 of 6 (paper §3.1, item 6).

## Role
Combine the surviving PC proposals into a single recommended portfolio
using an ensemble of seven combination methods, choose the regime-appropriate
combiner, and write the board memo.

## Combination methods

| ID                | Method                                              |
| ----------------- | --------------------------------------------------- |
| `simple_mean`     | Equal-weight average of survivor weights            |
| `borda_weighted`  | Weights ∝ Borda points                              |
| `confidence_weighted` | Weights ∝ mean CMA confidence (×Borda)          |
| `median`          | Per-asset median of survivor weights, renormalised  |
| `trimmed_mean`    | 20% trimmed mean per asset, renormalised            |
| `sharpe_weighted` | Weights ∝ ex-ante Sharpe                            |
| `regime_weighted` | Weights ∝ regime-fit score                          |

## Selection rule

- **Expansion / recovery**: `sharpe_weighted` → growth-tilted survivors win.
- **Late_cycle**: `confidence_weighted` → favours high-conviction defensives.
- **Recession**: `regime_weighted` with min-vol bias.
- **Low top-1 regime confidence**: fall back to `trimmed_mean` (robust).

## Output
1. `final_portfolio.json` (`schemas/final_portfolio.schema.json`).
2. `board_memo.md` — natural-language summary covering:
   - regime call & rationale
   - top CMA highlights
   - method comparison table
   - chosen ensemble & why
   - dissenting views (highest-Borda survivor that disagrees)
   - escalation flags
