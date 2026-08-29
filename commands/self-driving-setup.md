---
description: Check the Self-Driving Portfolio runtime, schemas, and test suite
argument-hint: ""
allowed-tools: Bash(cd:*), Bash(python:*), Bash(python3:*), Bash(pytest:*), Bash(ruff:*)
---

Check the plugin-local runtime without fetching market data.

Run:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 pipeline/orchestrator.py --help
cd "${CLAUDE_PLUGIN_ROOT}" && python3 pipeline/verify.py --help
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m pytest -q
```

Report Python compatibility, missing dependencies, test results, and whether
the verifier CLI loads. State that the plugin performs research only and does
not place trades.
