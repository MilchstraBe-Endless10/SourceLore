---
name: sourcelore-probe
description: >
  SourceLore F2-P0 runtime probe. Use ONLY when explicitly asked to run
  "sourcelore probe" or to verify SourceLore runtime integration capabilities.
  Test asset — NOT a product skill. Excludes all real knowledge-base work.
---

# SourceLore Probe (test asset)

This skill exists only to verify DeepSeek Harness runtime integration.
It performs deterministic local checks and writes nothing outside the
controlled probe directory.

## Deterministic checks

Run exactly one of these and report the raw JSON back verbatim:

1. Echo/hash check:
   `python3 {{PROBE_DIR}}/scripts/echo_tool.py sourcelore-probe-token`

2. Read-only listing:
   `python3 -c "import os;print(sorted(os.listdir('{{PROBE_DIR}}/scripts')))"`

Do not interpret or summarize the output; report it as-is.
