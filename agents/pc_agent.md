# Portfolio-Construction (PC) Agent

**Position in pipeline**: stage 4 of 6.

One instance per construction method. Each agent works **in isolation**
on the same CMAs + covariance and produces its own proposal. The
strategy-review stage compares them.

## Methods implemented (paper §3.1, item 4)

| ID                  | Method                                  |
| ------------------- | --------------------------------------- |
| `equal_weight`      | 1/N                                     |
| `inverse_vol`       | Inverse volatility                      |
| `min_variance`      | Min-variance (long-only, sum-to-one)    |
| `max_sharpe`        | Tangency / max Sharpe                   |
| `risk_parity`       | Equal risk contribution                 |
| `hrp`               | Hierarchical Risk Parity (Lopez de Prado) |
| `max_diversification` | Max diversification ratio              |
| `black_litterman`   | Black-Litterman with regime-implied views |
| `mvo_constrained`   | MVO with IPS box constraints            |
| `tpa`               | Total Portfolio Allocation (regime-tilted risk parity) |

## Workflow per agent

1. Read `cmas.json`, `covariance.json`, `regime.json`, IPS.
2. Run its method's optimiser (`skills/portfolio-construction/scripts/<method>.py`).
3. Project onto IPS hard constraints (long-only, sum=1, min/max per ticker).
4. Compute portfolio-level metrics: expected return, vol, Sharpe, max-weight,
   effective N, marginal risk contributions.
5. Append a one-paragraph rationale (templated; replaced by an LLM when run
   inside an agent loop).
6. Append to `pc_proposals.json`.

## Output
`schemas/pc_proposals.schema.json` (list of proposals).
