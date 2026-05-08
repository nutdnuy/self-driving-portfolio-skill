---
name: portfolio-construction
description: Generate one or many portfolio proposals from CMAs and a covariance matrix using ten construction methods (equal-weight, inverse-vol, min-variance, max-Sharpe, risk parity, HRP, max diversification, Black-Litterman, MVO with constraints, Total Portfolio Allocation). Use when an upstream agent needs candidate portfolios for the strategy review stage.
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
via a small QP-style iterative clip-and-renormalise loop
(`utils.project_to_box`). If the projection cannot reach feasibility in
50 iterations (e.g. the IPS box is internally inconsistent), the
proposal is flagged `feasible=false` and surfaced to the reviewer.

## CLI

```bash
python skills/portfolio-construction/scripts/run_all.py \
       --cmas outputs/demo01/cmas.json \
       --cov  outputs/demo01/covariance.json \
       --ips  ips/ips_template.md \
       --out  outputs/demo01/pc_proposals.json
```
