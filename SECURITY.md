# Security Policy

## Scope

Report path traversal, unsafe file writes, secret leakage, schema bypass,
artifact-verification bypass, dependency confusion, or any behavior that could
turn research output into unauthorized trading activity.

## Safe Operation

- Keep API keys in environment variables; never add them to the IPS, manifest,
  logs, or repository.
- Use a new run ID for every execution.
- Run `pipeline/verify.py` before interpreting artifacts.
- Treat downloaded market and macro data as untrusted.
- Keep brokerage credentials and order APIs outside this project.

## Reporting

Open a GitHub security advisory for the repository owner instead of a public
issue when the report includes an exploitable vulnerability or sensitive
details.

## Cryptographic Boundary

The local hash chain detects modification relative to the recorded chain. It
is not a digital signature and does not protect against full-directory rewrite
by an attacker with write access. Use externally anchored immutable storage for
regulated evidence retention.
