# Evidence-Based Comparison

Comparison date: 2026-08-29.

Reference baseline:
[`chirindaopensource/agentic_architecture_for_institutional_asset_management`](https://github.com/chirindaopensource/agentic_architecture_for_institutional_asset_management)
at public `main` commit `5b5c2bc`.

Both projects are MIT-licensed independent implementations of the
Ang/Azimbayev/Kim (2026) architecture. The reference project is broad and
method-rich. This project optimizes for installability, modularity, automated
verification, and safe agent operation.

| Acceptance criterion | This repository v0.2 | Reference baseline observed |
| --- | --- | --- |
| Claude/Codex plugin manifests | Yes | No plugin manifests in repository tree |
| Canonical triggerable skill | Yes, plus six stage skills | Conventional Python/notebook project |
| Standalone run verifier | Yes | No standalone verifier entry point observed |
| Strict schema + semantic gates | Both layers execute before each commit | Schema gating documented |
| Finite-state stage commits | Enforced by `GovernedRun` | Deterministic FSM documented |
| Existing run overwrite protection | Yes | Not documented as a run contract |
| Immutable consumed inputs | IPS, macro, and price snapshots hashed per run | Configuration provenance documented |
| Artifact hash chain | Manifest and ordered JSONL events | Cryptographic archive documented |
| Manifest/ledger/lineage cross-check | Includes raw metadata, IPS bounds, metrics, review, dissent, and escalation | No standalone cross-check observed |
| Exact bounded-simplex projection | Bisection with infeasible-IPS rejection | Exact projection documented |
| PSD covariance diagnostics | Repair flag, original min eigenvalue, missingness, sample count | PSD repair documented |
| Point-in-time price cutoff | Propagated and tested | Point-in-time truncation documented |
| FRED vintage disclosure | Explicit authenticated/fallback policy | Not observed in public README |
| Network-free automated tests | Pytest governance, math, and plugin contracts | No `tests/` directory observed |
| GitHub CI matrix | Python 3.10-3.13 | No workflow observed in repository tree |

“Observed” means visible in the public repository tree and documentation, not
a claim that an unobserved capability cannot exist elsewhere. Re-run this
comparison when either repository changes.

## Deliberate Non-Goals

Do not compete by adding opaque LLM autonomy, live trading, or more methods
without tests. Prioritize mandate computability, point-in-time correctness,
deterministic math, failure evidence, and human approval.
