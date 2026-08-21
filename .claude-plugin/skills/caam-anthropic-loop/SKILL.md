---
name: caam-anthropic-loop
description: >-
  Watch caam-managed Claude Max account usage and rotate safely.
  Invoke as /livespec-overseer:caam-anthropic-loop.
allowed-tools: Bash, Read
---

# caam-anthropic-loop - Claude Code binding

This file is the thin Claude Code binding for the `caam-anthropic-loop`
operation of the **livespec-overseer** plugin. The complete operator contract is
the plugin-owned prose artifact at
`${CLAUDE_PLUGIN_ROOT}/prose/caam-anthropic-loop.md`. Read that prose file in
full, then execute it end-to-end.

```bash
cat "${CLAUDE_PLUGIN_ROOT}/prose/caam-anthropic-loop.md"
```

This binding adds NO operation behavior of its own; the operator contract lives
in the prose.
