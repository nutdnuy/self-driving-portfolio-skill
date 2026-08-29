---
name: peer-review
description: This skill should be used when the user asks to "review portfolio proposals", "rank strategies with Borda voting", "filter IPS violations", or test a candidate portfolio against an adversarial diversifier.
---

# peer-review

Implements the multi-agent strategy review protocol from
Ang/Azimbayev/Kim (2026) §3.1 step 5.

## Steps

1. **Hard-constraint filter** (drop infeasible proposals).
2. **Risk filter** (drop proposals with vol > IPS hard cap).
3. **Three-axis review**: a deterministic rubric rates every surviving
   proposal 1–5 on
   *risk-adjusted return*, *diversification*, *robustness*.
4. **Borda count**: per-axis rankings are converted to tie-aware Borda points;
   points are summed across the three axes.
5. **Adversarial diversifier**: if the Borda winner has effective N < 4 or
   a max weight > 50%, generate an IPS-projected equal-weight challenger. Mark
   it as winning the concentration challenge only when effective N improves by
   more than 20%.
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

Run through `pipeline/orchestrator.py` for schema gating and governed output.
