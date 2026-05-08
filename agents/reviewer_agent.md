# Reviewer Agent (Multi-agent strategy review)

**Position in pipeline**: stage 5 of 6 (paper §3.1, item 5).

## Role
Subject every PC proposal to peer review and aggregate the panel's verdicts
via Borda-count voting. Surface an adversarial-diversifier challenger when
the leading proposal is concentrated.

## Workflow

1. **Hard-constraint filter**: drop proposals that violate any IPS hard
   constraint (sum, long-only, ticker box).
2. **Risk filter**: drop proposals whose ex-ante vol exceeds the IPS hard cap.
3. **Peer review**: each PC agent reviews two other proposals (random pairing,
   no self-review). Each review yields a 1–5 score on three axes:
   *risk-adjusted return*, *diversification*, *robustness to regime change*.
4. **Borda count**: each reviewer ranks the proposals; Borda points are
   summed.
5. **Adversarial diversifier**: if the Borda winner has effective N < 4 or
   max weight > 0.5, an adversarial agent proposes a more-diversified
   challenger and the panel re-votes head-to-head.
6. Surviving proposals (top-K by Borda, K configurable, default 5) are
   passed to the CIO ensemble.

## Output
`schemas/peer_review.schema.json`.
