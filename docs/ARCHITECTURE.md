# Governance Architecture

## Design Goal

Make every portfolio recommendation reproducible, fail closed, and
independently verifiable without trusting an agent narrative.

## Control Flow

```text
new safe run ID
  -> snapshot and hash IPS
  -> fetch macro/prices once and snapshot exact consumed frames
  -> run one deterministic stage
  -> JSON Schema gate
  -> semantic invariant gate
  -> atomic artifact commit
  -> append hash-chained event
  -> advance finite-state machine
  -> repeat through final portfolio
  -> commit board memo
  -> mark complete
  -> verify all evidence from disk
```

The orchestrator never writes a stage artifact before validation. A failure
records `run_failed`, preserves prior valid evidence, and blocks downstream
stages.

## Structural Contracts

Draft 7 schemas under `schemas/` reject unknown fields and constrain types,
formats, enumerations, ranges, and required properties.

## Semantic Contracts

`pipeline/governance.py` checks relationships that are awkward in JSON Schema:

- regime probabilities sum to one and the selected label is the argmax;
- top-1 confidence fields agree with the committed probability vector;
- tickers and portfolio methods are unique;
- successful portfolios are long-only, fully invested, and inside IPS bounds;
- covariance dimensions match tickers, the matrix is symmetric PSD, and its
  condition diagnostic is reproducible;
- raw CSV columns, row counts, dates, universe, and metadata agree;
- CMA, covariance, proposal, review, dissent, and ensemble lineage agrees
  across artifacts;
- every reported proposal/final metric recomputes from the frozen CMA and
  covariance artifacts; and
- escalation and ensemble-selection flags agree with the governed policy.

## State Machine

Only this sequence can commit:

```text
regime -> cmas -> covariance -> pc_proposals -> peer_review -> final_portfolio
```

Attach `board_memo.md` only after all JSON stages. Mark the run complete only
after the memo commits.

## Provenance Model

Store source-independent metadata only: the IPS source filename, immutable
snapshot, hashes, byte counts, parameters, timestamps, and stage state. Avoid
recording credentials or authenticated request URLs.

Snapshot the IPS, macro frame, price frame, and all six JSON Schemas. Anchor
their hashes in the audit chain. Reuse one immutable price frame for CMA and
covariance stages so two network calls cannot observe different histories.

Store all six JSON Schemas under `contracts/` and anchor their hashes in the
first audit event. Record a deterministic hash of the Python engine source in
the run parameters so code drift remains visible even when a run moves away
from its originating Git checkout. Record Python, NumPy, pandas, SciPy,
yfinance, and jsonschema versions alongside the engine hash.

Each event hashes canonical JSON containing its sequence, timestamp, type,
details, and previous hash. Verification recomputes the entire chain and
cross-checks input and artifact hashes against both the manifest and commit
events. It then replays cross-artifact contracts from the immutable IPS and
consumed data snapshots, rather than trusting hashes alone.

## Threat Model

Detect accidental corruption, partial writes, casual artifact editing,
manifest drift, stage reordering, path traversal in run IDs/manifests, and
schema-compatible weight tampering.

Do not claim protection against an attacker who can rewrite the complete run
directory and regenerate the chain. Anchor `audit_head` externally when that
threat matters.
