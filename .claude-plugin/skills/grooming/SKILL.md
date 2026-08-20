---
name: grooming
description: >-
  Run the bounded livespec grooming drain pass for the current repository.
  Invoke as /livespec-overseer:grooming.
allowed-tools: Bash, Read
---

# grooming - Claude Code binding

This file is the thin Claude Code binding for the `grooming` operation of the
**livespec-overseer** plugin. The complete drain-pass contract is the
plugin-owned prose artifact at `${CLAUDE_PLUGIN_ROOT}/prose/grooming.md`.
Read that prose file in full, then execute it end-to-end.

```bash
cat "${CLAUDE_PLUGIN_ROOT}/prose/grooming.md"
```

This binding adds NO operation behavior of its own; the drain-pass contract
lives in the prose.
