---
description: Verify a Self-Driving Portfolio run's contracts, hashes, and audit chain
argument-hint: "<run folder>"
allowed-tools: Bash(cd:*), Bash(python:*), Bash(python3:*)
---

Verify an existing governed run before interpreting it.
Resolve the run folder to an absolute path before changing directories.

Run:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 pipeline/verify.py "<absolute run folder>"
```

Report `ok`, status, artifact count, event count, and audit head. Treat any
failure as disqualifying. Use `--allow-incomplete` only for diagnosis and never
to approve a partial recommendation.
