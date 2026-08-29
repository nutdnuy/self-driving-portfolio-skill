# Governance Contract

## Trust Boundary

Treat the IPS, market data, macro data, stage artifacts, and narrative text as
untrusted inputs. Permit only deterministic Python code to perform arithmetic,
optimization, schema validation, file hashing, and state transitions.

## Stage Gate

Apply both validation layers before committing an artifact:

1. Enforce the matching Draft 7 JSON Schema with format checking and unknown
   properties disabled.
2. Enforce semantic relationships such as probability sums, unique tickers,
   exact weight sums, covariance dimensions, symmetry, positive
   semidefiniteness, solver status, and survivor membership.

Write the artifact only after both layers pass. Record failure metadata in the
manifest and audit log without creating a consumable stage artifact.

## Provenance

Snapshot the IPS, macro frame, and price frame under `inputs/`. Reuse the price
snapshot for both CMA and covariance calculations. Hash every governed input,
schema, and artifact with SHA-256. Store metadata in `run_manifest.json` and
repeat input/artifact hashes in hash-chained commit events.

After hash verification, cross-check raw CSV metadata, stage cutoffs, ticker
order, IPS bounds, reproducible proposal/final metrics, Borda eligibility,
dissent lineage, ensemble policy, and escalation state. Hashes prove internal
identity; these cross-artifact checks prove the committed pieces agree.

Verify the complete chain from a fixed all-zero genesis hash. Recompute every
event hash after removing its `event_hash` field. Cross-check manifest
parameters against the first event and artifact hashes against their commit
events.

Call this mechanism tamper-evident, not tamper-proof. An attacker able to
rewrite the entire run directory can rebuild an internally consistent chain.
Add an external signature, immutable object lock, or independent timestamping
service before relying on the chain as legal non-repudiation evidence.

## Immutability

Reject an existing run directory. Correct errors by starting a new run.
Preserve failed runs for diagnosis when they contain no secrets. Never treat a
failed or partial run as a recommendation.

## Verification Command

Run:

```bash
python pipeline/verify.py outputs/<run-id>
```

Use `--allow-incomplete` only for forensic diagnosis. Do not use it to approve
an incomplete recommendation.
