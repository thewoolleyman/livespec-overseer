---
name: overseer
description: >-
  Start and operate the livespec two-pane overseer: a deterministic top-pane
  overseerd daemon plus a thin bottom-pane operator surface. Invoke as
  `/livespec-overseer:overseer`.
allowed-tools: Bash, Read
---

# overseer - Claude Code binding

This file is the thin Claude Code binding for the `overseer` operation of
the **livespec-overseer** plugin. The complete operator contract is the
plugin-owned prose artifact at `${CLAUDE_PLUGIN_ROOT}/prose/overseer.md`.
Read that prose file in full, then execute it end-to-end.

```bash
cat "${CLAUDE_PLUGIN_ROOT}/prose/overseer.md"
```

This binding adds NO operation behavior of its own; the operator contract
lives in the prose.
