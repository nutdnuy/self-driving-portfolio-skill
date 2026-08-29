# Self-Driving Portfolio

Claude Code and Codex plugin for governed Strategic Asset Allocation (SAA)
research. It implements the six-stage agentic workflow described by
[Ang, Azimbayev, and Kim (2026)](https://arxiv.org/abs/2604.02279), while
keeping arithmetic and control decisions in deterministic Python.

```text
IPS snapshot -> macro regime -> CMAs -> PSD covariance
             -> 10 portfolio methods -> Borda review -> CIO ensemble
             -> board memo + manifest + hash-chained audit log
```

The repository is intentionally research-only. It has no brokerage
integration, order placement, or claim of guaranteed performance.

## What v0.2 Adds

- **Executable contracts:** enforce strict JSON Schemas and semantic invariants
  between all six stages.
- **Fail-closed finite-state orchestration:** prevent skipped, repeated, or
  out-of-order stage commits.
- **Point-in-time controls:** propagate one as-of date through macro and market
  data; use true FRED vintage retrieval when `FRED_API_KEY` is available.
- **No silent universe shrinkage:** stop when any IPS asset lacks required data.
- **Numerical safety:** use exact Euclidean box projection, reject infeasible
  IPS bounds, and repair covariance eigenvalues with explicit diagnostics.
- **Tamper evidence:** snapshot the IPS and raw macro/price inputs, freeze schema
  contracts, hash every artifact, chain audit events, and ship a standalone
  verification command.
- **Atomic outputs:** expose only complete artifact writes and preserve failed
  runs for diagnosis.
- **Agent-native packaging:** install as a Claude Code or Codex plugin with a
  canonical meta-skill, six stage skills, six least-privilege specialist
  agents, and four workflow commands.
- **Automated quality gates:** run network-free tests and lint across Python
  3.10-3.13 in CI.

See [the evidence-based comparison](docs/COMPARISON.md) and
[governance architecture](docs/ARCHITECTURE.md).

## Install in Codex or ChatGPT

A workspace administrator can import this GitHub repository from **Workspace
settings > Plugins > Marketplaces**. The importer discovers
`.agents/plugins/marketplace.json`; after import, make the plugin available and
install it from the Plugins directory. See OpenAI's
[GitHub marketplace import guide](https://help.openai.com/en/articles/20001504).

## Install in Claude Code

```text
/plugin marketplace add nutdnuy/self-driving-portfolio-skill
/plugin install self-driving-portfolio-skill@self-driving-portfolio-skill
```

These commands follow the Claude Code
[marketplace workflow](https://code.claude.com/docs/en/discover-plugins).

## Local Setup

```bash
git clone https://github.com/nutdnuy/self-driving-portfolio-skill.git
cd self-driving-portfolio-skill
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
```

No key is required for the public FRED CSV fallback. Set `FRED_API_KEY` when a
historical FRED vintage is required; the fallback is latest-revised history
with a correct observation-date cutoff, not a vintage-clean backtest.

## Run

Edit `ips/ips_template.md`, then create a unique run:

```bash
python pipeline/orchestrator.py \
  --ips ips/ips_template.md \
  --run-id policy-2026-05-08 \
  --as-of 2026-05-08 \
  --lookback-years 10 \
  --cov-method ledoit_wolf \
  --top-k 5
```

Omit `--as-of` to use the IPS `As-of date`. Omit `--run-id` to generate a UTC
timestamped ID. Existing run directories are never overwritten.

## Verify Before Use

```bash
python pipeline/verify.py outputs/policy-2026-05-08
```

A valid result reports:

```json
{
  "ok": true,
  "run_id": "policy-2026-05-08",
  "status": "complete",
  "events_verified": 11,
  "inputs_verified": 3,
  "artifacts_verified": 7,
  "contracts_verified": 6,
  "cross_artifact_verified": true
}
```

Treat any verification failure or incomplete status as unusable research.

## Governed Outputs

Every run is self-contained:

```text
outputs/<run-id>/
├── inputs/
│   ├── ips.md                 # immutable IPS snapshot
│   ├── macro.csv              # exact macro frame consumed by the classifier
│   └── prices.csv             # exact price frame shared by CMA/covariance
├── contracts/                 # immutable schema snapshots
├── regime.json               # regime scores + vintage policy
├── cmas.json                 # per-asset assumptions
├── covariance.json           # PSD risk matrix + diagnostics
├── pc_proposals.json         # 10 deterministic proposals
├── peer_review.json          # filters + Borda ranking
├── final_portfolio.json      # ensemble recommendation + escalation
├── board_memo.md             # human-review memo
├── run_manifest.json         # parameters + source/schema/artifact hashes
└── audit.jsonl               # hash-chained state transitions
```

The hash chain is tamper-evident within the run directory; it is not an
external signature. Add immutable storage or independent signing for legal
non-repudiation requirements.

## Portfolio Methods

The deterministic engine compares:

1. Equal Weight
2. Inverse Volatility
3. Minimum Variance
4. Maximum Sharpe
5. Risk Parity
6. Hierarchical Risk Parity
7. Maximum Diversification
8. Black-Litterman
9. Constrained Mean-Variance
10. Total Portfolio Allocation

Peer review drops IPS/risk failures, scores risk-adjusted return,
diversification, and robustness, then aggregates ranks with Borda points. The
CIO stage evaluates seven ensemble methods and retains a dissenting view.

## Plugin Skill and Commands

The canonical skill is `skills/self-driving-portfolio/SKILL.md`.

Example prompts:

```text
Build an IPS-governed strategic asset allocation from this mandate.
Compare portfolio construction methods as of 2026-05-08.
Verify this self-driving portfolio run and explain every escalation.
```

Workflow commands:

- `/self-driving-setup`
- `/self-driving-run`
- `/self-driving-verify`
- `/self-driving-explain-limits`

## Development

```bash
ruff check .
pytest -q
python -m compileall -q pipeline skills examples tests
```

The test suite does not require FRED or yfinance access. Network calls remain
outside acceptance tests so governance failures are reproducible.

## Scope and Limitations

This prototype does not fully encode liabilities, taxes, liquidity, turnover,
market impact, currency hedging, derivatives, legal constraints, operational
risk, or trade execution. Historical means are noisy; correlations change;
regime tilts are heuristic; and yfinance is not an institutional market-data
system. Read
[`references/limitations.md`](skills/self-driving-portfolio/references/limitations.md)
before interpreting a result.

Human portfolio-manager review remains mandatory. Generated weights are a
research starting point, not investment advice or implementation approval.

## Related Implementation

[chirindaopensource/agentic_architecture_for_institutional_asset_management](https://github.com/chirindaopensource/agentic_architecture_for_institutional_asset_management)
is an MIT-licensed independent implementation of the same paper and documents
important ideas including deterministic arithmetic, schema gating, state
control, covariance repair, and cryptographic provenance. This repository uses
an independently implemented, modular plugin architecture and adds a
standalone verifier, immutable run contract, agent discovery manifests,
network-free acceptance tests, and CI. No source file from that implementation
is vendored here.

## License

MIT. See [LICENSE](LICENSE).
