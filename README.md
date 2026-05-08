# self-driving-portfolio-skill

A working-prototype Claude Skill that implements the agentic Strategic Asset
Allocation (SAA) pipeline described in:

> Ang, A., Azimbayev, N., Kim, A. (2026).
> **The Self-Driving Portfolio: Agentic Architecture for Institutional Asset Management.**
> Working paper (April 1, 2026). arXiv:2604.02279.

The skill orchestrates a six-stage pipeline of specialized sub-agents that
takes an Investment Policy Statement (IPS) and produces a recommended policy
portfolio with a full natural-language audit trail.

```
IPS  ─►  Macro Regime  ─►  Asset-Class CMAs  ─►  Covariance  ─►
        Portfolio Construction (10 methods)  ─►  Peer Review + Borda Vote  ─►
        CIO Ensemble  ─►  Recommended Weights + Board Memo
```

## What's in this repo

```
self-driving-portfolio-skill/
├── SKILL.md                        # Top-level meta-skill (read this first)
├── ips/ips_template.md             # IPS template — the human-authored governing doc
├── agents/                         # Markdown job-descriptions for each agent role
├── skills/                         # Six reusable sub-skills (paper §3.2)
│   ├── macro-regime/               # 4-regime classifier (FRED data)
│   ├── asset-class-cma/            # CMAs from prices + macro signal
│   ├── covariance/                 # sample / EWMA / Ledoit-Wolf shrinkage
│   ├── portfolio-construction/     # 10 PC methods
│   ├── peer-review/                # Borda voting + adversarial diversifier
│   └── cio-ensemble/               # 7 combination methods + board memo
├── pipeline/orchestrator.py        # End-to-end pipeline runner
├── examples/run_demo.py            # 9-asset, US-multi-asset demo
├── schemas/                        # JSON output contracts
└── tests/                          # Unit tests for the math
```

## Quick start

```bash
git clone https://github.com/nutdnuy/self-driving-portfolio-skill.git
cd self-driving-portfolio-skill
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run the end-to-end demo (uses yfinance for prices, FRED-public CSVs for macro)
python examples/run_demo.py
```

The demo writes outputs to `outputs/<run-id>/`:

- `regime.json` — macro regime classification + scores
- `cmas.json` — per-asset expected return, volatility, confidence
- `covariance.json` — covariance matrix (Ledoit-Wolf shrunk)
- `pc_proposals.json` — 10 portfolio proposals with rationales
- `peer_review.json` — Borda-count results + adversarial diversifier
- `final_portfolio.json` — recommended weights + ensemble breakdown
- `board_memo.md` — natural-language summary for human review

No API keys are required. `FRED_API_KEY` is optional; without it, macro data
is pulled from FRED's public CSV endpoints.

## How to use this as a Claude Skill

This repo is a *Claude Skill* in the same sense as the public Anthropic
skills repo: every folder in `skills/` contains a `SKILL.md` describing
methodology, an output `schema.json`, and `scripts/` for computation. Claude
(or any LLM agent) reads the SKILL.md, calls the scripts, and writes
structured JSON + markdown outputs.

To invoke from Claude Code:

```
/skill self-driving-portfolio
```

…or point an agent at `SKILL.md` and let it run the pipeline.

## Agent / skill mapping (paper §3.1, §3.2)

| Paper stage                    | Sub-skill              | Agent description           | PC methods                                              |
| ------------------------------ | ---------------------- | --------------------------- | ------------------------------------------------------- |
| 1. Macro regime classification | `macro-regime`         | `agents/macro_agent.md`     | —                                                       |
| 2. Asset-class CMAs            | `asset-class-cma`      | `agents/asset_class_agent.md` | —                                                     |
| 3. Covariance estimation       | `covariance`           | `agents/covariance_agent.md` | —                                                      |
| 4. Portfolio construction      | `portfolio-construction` | `agents/pc_agent.md`      | EW, IV, MinVar, MaxSharpe, RP, HRP, MaxDiv, BL, MV-cons, TPA |
| 5. Multi-agent strategy review | `peer-review`          | `agents/reviewer_agent.md`  | Borda count + adversarial diversifier                   |
| 6. CIO ensemble                | `cio-ensemble`         | `agents/cio_agent.md`       | 7 combination methods                                   |

## Disclaimer

Research/educational prototype. Not investment advice. The recommended
weights produced by this pipeline are a starting point for human review,
not a substitute for fiduciary judgment.

## License

MIT — see [LICENSE](LICENSE).
