# Investment Policy Statement (IPS) — Template

This document is the **single source of governance** for the agentic SAA
pipeline. Edit the fields below; downstream agents are instructed to refuse
any recommendation that violates the constraints stated here.

---

## 1. Plan identity

| Field | Value |
| --- | --- |
| Plan name | Demo Multi-Asset Policy Portfolio |
| Sponsor | (institution / individual) |
| As-of date | 2026-05-08 |
| Reporting currency | USD |
| Time horizon | 10 years |

## 2. Objectives

- **Primary objective**: long-term real return ≥ 4.0% p.a.
- **Secondary objective**: maximum drawdown over a rolling 12-month window ≤ 20%.
- **Liability profile**: none (endowment-style, perpetual).

## 3. Risk tolerance

| Metric | Limit |
| --- | --- |
| Annualised volatility (target) | 10–14% |
| Annualised volatility (hard cap) | 18% |
| 95% 1-yr parametric VaR (hard cap) | 22% |
| Effective number of bets | ≥ 4 |

## 4. Asset universe

| Ticker | Asset class                  | Min wt | Max wt |
| ------ | ---------------------------- | ------ | ------ |
| SPY    | US Equity (large cap)        | 0.05   | 0.50   |
| EFA    | DM ex-US Equity              | 0.00   | 0.30   |
| EEM    | EM Equity                    | 0.00   | 0.20   |
| IEF    | US Treasury 7-10Y            | 0.00   | 0.50   |
| LQD    | US Investment-grade credit   | 0.00   | 0.30   |
| TIP    | US TIPS                      | 0.00   | 0.30   |
| GLD    | Gold                         | 0.00   | 0.15   |
| VNQ    | US REITs                     | 0.00   | 0.15   |
| BIL    | T-Bills (cash proxy)         | 0.00   | 0.30   |

## 5. Hard constraints

- Long-only (no short positions).
- Weights sum to 1.0 (fully invested).
- No leverage.
- All ticker-level min/max weights above are *hard* constraints.

## 6. Soft constraints / preferences

- Tracking error vs the 60/40 SPY/IEF benchmark ≤ 6% (preference, not hard).
- Turnover from a 60/40 starting point ≤ 100% in a single rebalance.

## 7. Governance / escalation

- The pipeline produces a *recommendation*. A human portfolio manager must
  review `board_memo.md` and confirm before any trade is implemented.
- If the recommended portfolio's volatility is within 50bps of the hard cap,
  the pipeline must escalate (`escalate_to_human: true` in `final_portfolio.json`).
- If fewer than 5 of the 10 portfolio-construction methods produce
  IPS-feasible portfolios, the pipeline must escalate.

## 8. Benchmarks

| Use | Benchmark |
| --- | --- |
| Strategic | 60% SPY / 40% IEF |
| Risk     | 14% annualised volatility |
