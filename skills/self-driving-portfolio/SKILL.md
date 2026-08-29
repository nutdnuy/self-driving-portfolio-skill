---
name: self-driving-portfolio
description: This skill should be used when the user asks to "build a strategic asset allocation", "run a self-driving portfolio", "compare portfolio methods", "audit an SAA run", or "produce an IPS-governed policy portfolio".
---

# Self-Driving Portfolio

Run a governed six-stage Strategic Asset Allocation (SAA) research workflow.
Translate a human-authored Investment Policy Statement (IPS) into deterministic
portfolio proposals, structured review, an ensemble recommendation, and a
board memo. Preserve human fiduciary authority; never place trades or present
research output as individualized investment advice.

## Required Inputs

Collect or confirm:

1. An IPS markdown file with a dated asset-universe table and computable
   minimum/maximum weights, an annualized volatility hard cap, and a minimum
   feasible-proposal escalation threshold.
2. An explicit as-of date, or a valid `As-of date` row in the IPS.
3. A historical lookback in years.
4. A covariance method: `sample`, `ewma`, or `ledoit_wolf`.
5. A unique run identifier containing only letters, numbers, `.`, `_`, or `-`.

Stop when the IPS is ambiguous, contradictory, or mathematically infeasible.
Require `sum(min_w) <= 1 <= sum(max_w)`. Refuse future as-of dates and silent
asset-universe shrinkage.

## Run the Governed Pipeline

Execute from the plugin root (the directory containing `.codex-plugin/` and
`.claude-plugin/`). In Claude Code, resolve this directory with
`${CLAUDE_PLUGIN_ROOT}`. In Codex, resolve it from this skill's installed
location.

```bash
python pipeline/orchestrator.py \
  --ips ips/ips_template.md \
  --run-id saa-2026-05-08 \
  --as-of 2026-05-08 \
  --lookback-years 10 \
  --cov-method ledoit_wolf \
  --top-k 5
```

Run the stages only through the governed orchestrator for a final
recommendation. Use individual stage scripts only for isolated research and
clearly label their outputs as ungoverned.

Apply this finite-state order:

1. Classify the macro regime.
2. Build per-asset Capital Market Assumptions (CMAs).
3. Estimate and repair the covariance matrix when necessary.
4. Run ten deterministic portfolio-construction methods.
5. Filter, score, and rank proposals with a deterministic Borda review.
6. Combine survivors, preserve a dissenting view, and render a board memo.

Fetch macro and price data once, snapshot the exact CSV frames, and reuse the
same price frame for CMA and covariance stages. Treat every boundary as fail
closed. Validate each JSON artifact against its
schema and semantic contract before allowing the next stage to read it. Write
artifacts atomically. Snapshot the IPS. Record file hashes in the hash-chained
audit log.

## Verify the Result

Run verification before interpreting weights:

```bash
python pipeline/verify.py outputs/<run-id>
```

Require `ok: true`. Verify:

- the IPS snapshot hash;
- raw macro/price CSV hashes, metadata, columns, row counts, and cutoffs;
- the six-stage finite-state order;
- strict JSON Schemas and semantic invariants;
- cross-artifact lineage, IPS bounds, and reproducible portfolio metrics;
- artifact byte counts and SHA-256 hashes;
- the audit-event hash chain;
- the final board memo attachment; and
- complete run status.

Treat a failed or incomplete verification as unusable evidence. Never repair a
run in place. Correct the input or code, then create a new run identifier.

## Interpret Outputs

Read these governed artifacts in order:

| Artifact | Purpose |
| --- | --- |
| `inputs/ips.md` | Immutable mandate snapshot |
| `inputs/macro.csv` | Exact macro frame consumed by the classifier |
| `inputs/prices.csv` | Exact price frame shared by CMA and covariance |
| `contracts/*.schema.json` | Immutable stage-contract snapshots |
| `regime.json` | Regime probabilities, data cutoff, and FRED vintage policy |
| `cmas.json` | Expected return, volatility, confidence, and data-through date |
| `covariance.json` | PSD covariance, shrinkage, conditioning, and missing-data diagnostics |
| `pc_proposals.json` | Method status, weights, metrics, rationale, and feasibility |
| `peer_review.json` | Hard-filter results, Borda ranking, and adversarial challenger |
| `final_portfolio.json` | Ensemble weights, dissent, metrics, and escalation state |
| `board_memo.md` | Human-review summary |
| `run_manifest.json` | Parameters, engine/input/schema/artifact hashes, and status |
| `audit.jsonl` | Ordered hash-chained provenance events |

Separate three classes of information in the response:

- **Facts:** run parameters, data cutoffs, weights, metrics, verification state.
- **Model judgments:** regime tilts, expected returns, method ranking, ensemble selection.
- **Required decisions:** mandate clarification, escalation review, implementation approval.

Surface `escalate_to_human` and every escalation reason without softening or
omitting them. Present the recommendation as a research starting point, not an
authorization to rebalance.

## Point-in-Time Rules

Propagate one as-of date through macro, price, CMA, covariance, proposal,
review, and ensemble artifacts. Reject observations after that cutoff.

Use `FRED_API_KEY` when true FRED vintage-as-of retrieval is required. Without
the key, label macro data `latest_revision_cutoff`: observation dates are
truncated correctly, but historical values may include later revisions. Do not
describe that fallback as a fully point-in-time macro backtest.

## Safety Boundaries

Keep LLM work limited to mandate clarification, interpretation, and narrative.
Delegate arithmetic, optimization, validation, hashing, and state transitions
to the bundled Python scripts.

Never:

- place orders or connect the workflow to a broker;
- invent missing prices, macro observations, or IPS constraints;
- continue after a schema, hash, stage-order, PSD, or universe check fails;
- overwrite a completed run directory;
- describe the hash chain as an external digital signature; or
- imply guaranteed returns or fiduciary approval.

## Additional Resources

Load only the resource needed for the current task:

- `references/governance.md` — artifact contracts, provenance, and threat model.
- `references/limitations.md` — data, estimation, optimization, and investment limitations.
- `../macro-regime/SKILL.md` — regime methodology.
- `../asset-class-cma/SKILL.md` — CMA methodology.
- `../covariance/SKILL.md` — covariance methodology.
- `../portfolio-construction/SKILL.md` — ten construction methods.
- `../peer-review/SKILL.md` — filtering and Borda review.
- `../cio-ensemble/SKILL.md` — ensemble selection and board memo.
