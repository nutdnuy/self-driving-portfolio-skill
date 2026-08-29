---
name: portfolio-construction
description: This skill should be used when the user asks to "compare portfolio construction methods", "run risk parity", "build a minimum-variance portfolio", or generate IPS-constrained SAA candidates.
---

# portfolio-construction

Ten portfolio-construction methods, each producing one proposal that
respects IPS hard constraints (long-only, sum-to-one, per-ticker box).

## Methods

| ID                    | Description                                              |
| --------------------- | -------------------------------------------------------- |
| `equal_weight`        | 1/N                                                      |
| `inverse_vol`         | weights ∝ 1/σ                                            |
| `min_variance`        | argmin wᵀΣw                                              |
| `max_sharpe`          | argmax (wᵀμ − r_f) / √(wᵀΣw)                             |
| `risk_parity`         | equal risk contribution                                  |
| `hrp`                 | Hierarchical Risk Parity (Lopez de Prado)                |
| `max_diversification` | argmax (wᵀσ) / √(wᵀΣw)                                   |
| `black_litterman`     | BL with regime-implied views                             |
| `mvo_constrained`     | MVO with explicit IPS box constraints + risk-aversion λ  |
| `tpa`                 | Total Portfolio Allocation: regime-tilted risk parity    |

## Constraint projection

After every optimiser, weights are projected onto the IPS feasible set
with the exact Euclidean bounded-simplex projection
(`utils.project_to_box`). Solve the Lagrange multiplier by monotone bisection.
Reject the IPS before optimization when `sum(min_w) > 1` or
`sum(max_w) < 1`; never return an almost-feasible vector.

## CLI

```bash
python skills/portfolio-construction/scripts/run_all.py \
       --cmas outputs/demo01/cmas.json \
       --cov  outputs/demo01/covariance.json \
       --ips  ips/ips_template.md \
       --out  outputs/demo01/pc_proposals.json
```

Run through `pipeline/orchestrator.py` for schema gating and governed output.
