# Research and Investment Limitations

## Data

- Expect yfinance availability, symbol mapping, corporate-action handling, and
  survivorship to differ from institutional data systems.
- Treat the public FRED CSV fallback as latest-revised history truncated by
  observation date. Require authenticated vintage retrieval for a true
  point-in-time macro study.
- Expect differing asset inception dates to reduce complete aligned return
  observations. Stop below the minimum sample rather than imputing silently.

## Estimation

- Treat historical means as noisy and regime tilts as heuristic assumptions.
- Expect covariance and correlations to change under stress.
- Interpret confidence scores as model diagnostics, not calibrated forecast
  probabilities.
- Treat the four-state US macro model as a simplified conditioning signal, not
  a complete global macro process.

## Optimization

- Expect mean-variance and maximum-Sharpe portfolios to be highly sensitive to
  expected-return estimates.
- Treat box constraints as only the constraints explicitly encoded by the
  current IPS parser. Validate liabilities, liquidity, taxes, turnover,
  leverage, derivatives, currency, legal, and operational restrictions
  separately.
- Treat PSD repair as numerical stabilization, not evidence that the model is
  economically correct.

## Implementation

- Exclude transaction costs, market impact, taxes, borrow constraints, and
  execution timing unless independently modeled.
- Require independent data reconciliation, scenario analysis, and human
  approval before any implementation.
- Never infer suitability, guarantee returns, or connect generated weights to
  automated trading.
