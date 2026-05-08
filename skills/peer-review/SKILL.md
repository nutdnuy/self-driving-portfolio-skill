---
name: peer-review
description: Apply structured deliberation to portfolio-construction proposals — drop hard-constraint failures, score with three-axis peer review, aggregate via Borda count, and surface an adversarial-diversifier challenger. Use when an upstream agent has a list of candidate portfolios that need to be filtered and ranked before ensemble combination.
---

# peer-review

Implements the multi-agent strategy review protocol from
Ang/Azimbayev/Kim (2026) §3.1 step 5.

## Steps

1. **Hard-constraint filter** (drop infeasible proposals).
2. **Risk filter** (drop proposals with vol > IPS hard cap).
3. **Three-axis peer review**: each agent (in this prototype, a deterministic
   rubric stands in for the LLM reviewer) rates every other proposal 1–5 on
   *risk-adjusted return*, *diversification*, *robustness*.
4. **Borda count**: each reviewer's rankings are converted to Borda points;
   points are summed.
5. **Adversarial diversifier**: if the Borda winner has effective N < 4 or
   a max weight > 50%, generate an inverse-vol challenger; the panel
   re-votes head-to-head.
6. Output the top-K (default 5) survivors plus the breakdown.

## CLI

```bash
python skills/peer-review/scripts/peer_review.py \
       --proposals outputs/demo01/pc_proposals.json \
       --ips ips/ips_template.md \
       --top-k 5 \
       --vol-cap 0.18 \
       --out outputs/demo01/peer_review.json
```
