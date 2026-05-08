---
name: self-driving-portfolio
description: Run an agentic Strategic Asset Allocation pipeline that classifies the macro regime, builds Capital Market Assumptions, estimates covariance, runs 10 portfolio-construction methods in parallel, peer-reviews them with Borda voting, and combines survivors via 7 ensemble methods. Use when the user asks for a policy portfolio, SAA recommendation, multi-method portfolio comparison, or wants to apply Ang/Azimbayev/Kim (2026) "Self-Driving Portfolio".
---

# Self-Driving Portfolio (Agentic SAA)

This is the **top-level meta-skill**. It coordinates six sub-skills under
`skills/` to produce a recommended policy portfolio governed by an
Investment Policy Statement (IPS).

## When to use

Trigger this skill when the user wants to:

- Build or review a strategic asset allocation
- Compare many portfolio-construction methods on the same CMAs
- Get a regime-aware policy recommendation with a written rationale
- Reproduce the Ang/Azimbayev/Kim (2026) agentic pipeline

## Architecture (paper §3.1, Exhibit 1)

```
                       ┌─────────────────┐
                       │ IPS (human)     │  objectives, constraints, asset universe
                       └────────┬────────┘
                                ▼
   ┌──────────┐     ┌─────────────────────┐     ┌──────────────┐
   │ macro-   │────►│ asset-class-cma     │────►│ covariance   │
   │ regime   │     │ (one per asset)     │     │              │
   └──────────┘     └─────────────────────┘     └──────┬───────┘
                                                       ▼
                                       ┌────────────────────────────┐
                                       │ portfolio-construction     │
                                       │ (10 methods, parallel)     │
                                       └──────────────┬─────────────┘
                                                      ▼
                                       ┌────────────────────────────┐
                                       │ peer-review                │
                                       │ Borda + adversarial diver. │
                                       └──────────────┬─────────────┘
                                                      ▼
                                       ┌────────────────────────────┐
                                       │ cio-ensemble               │
                                       │ 7 combination methods      │
                                       └──────────────┬─────────────┘
                                                      ▼
                                                 weights + memo
```

## Inputs

1. **IPS** — markdown file at `ips/ips_template.md` (or user-supplied).
   Encodes asset universe, objectives, hard constraints, risk tolerance.
2. **As-of date** — defaults to today.
3. **Lookback** — historical window for CMAs (default 10 years).

## Outputs (audit trail)

All written under `outputs/<run-id>/`:

| File | Schema | Producer |
| --- | --- | --- |
| `regime.json` | `schemas/regime.schema.json` | macro-regime |
| `cmas.json` | `schemas/cmas.schema.json` | asset-class-cma |
| `covariance.json` | `schemas/covariance.schema.json` | covariance |
| `pc_proposals.json` | `schemas/pc_proposals.schema.json` | portfolio-construction |
| `peer_review.json` | `schemas/peer_review.schema.json` | peer-review |
| `final_portfolio.json` | `schemas/final_portfolio.schema.json` | cio-ensemble |
| `board_memo.md` | — | cio-ensemble |

## How to run

Programmatic (one-shot, end-to-end):

```bash
python pipeline/orchestrator.py --ips ips/ips_template.md --run-id demo01
# or use the demo:
python examples/run_demo.py
```

Stage-by-stage (when iterating on one component):

```bash
python skills/macro-regime/scripts/classify_regime.py             # writes regime.json
python skills/asset-class-cma/scripts/build_cma.py --regime …     # writes cmas.json
python skills/covariance/scripts/build_cov.py --tickers …         # writes covariance.json
python skills/portfolio-construction/scripts/run_all.py …         # writes pc_proposals.json
python skills/peer-review/scripts/peer_review.py …                # writes peer_review.json
python skills/cio-ensemble/scripts/ensemble.py …                  # writes final_portfolio.json + memo
```

## Workflow for an LLM agent

1. **Read the IPS.** Extract asset universe, hard constraints (min/max weight,
   no-short, sector caps), and objectives (return target, vol cap, horizon).
2. **Run macro-regime** to get the regime label and `regime_score` vector.
   This conditions every downstream stage.
3. **Run asset-class-cma** for every ticker in the universe. Each call
   returns expected return, volatility, confidence, and a markdown
   investment-case memo.
4. **Run covariance** with `method=ledoit_wolf` (default).
5. **Run portfolio-construction** to produce 10 candidate portfolios.
   Each method's script signs its proposal with rationale + risk metrics.
6. **Run peer-review** to score proposals with Borda voting; filter those
   that fail hard IPS constraints; surface an adversarial-diversifier
   challenger if effective N is too low.
7. **Run cio-ensemble** to combine surviving proposals via seven methods,
   pick the regime-appropriate combiner, and write `board_memo.md`.

## Read order (for new agents)

1. `SKILL.md` (this file)
2. `ips/ips_template.md`
3. The sub-skill `SKILL.md` for the stage you are about to run
4. The matching `schemas/<stage>.schema.json` to know the output contract

## Reference

Ang, Azimbayev, Kim (2026), *The Self-Driving Portfolio: Agentic Architecture
for Institutional Asset Management*. arXiv:2604.02279.
