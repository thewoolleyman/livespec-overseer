---
name: foreman
description: >-
  Run the bounded livespec foreman operator loop for the current repository.
  Invoke as /livespec-overseer:foreman.
allowed-tools: Bash, Read
---

# foreman - Claude Code binding

This file is the thin Claude Code binding for the `foreman` operation of the
**livespec-overseer** plugin. The complete operator contract is the
plugin-owned prose artifact at `${CLAUDE_PLUGIN_ROOT}/prose/foreman.md`.
Read that prose file in full, then execute it end-to-end.

```bash
cat "${CLAUDE_PLUGIN_ROOT}/prose/foreman.md"
```

This binding adds NO operation behavior of its own; the operator contract
lives in the prose.
