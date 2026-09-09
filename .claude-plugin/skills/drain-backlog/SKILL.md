---
name: drain-backlog
description: >-
  Drain a livespec repository's open backlog through the factory: freeze the
  scope, triage it in ruled batches, dispatch through detached probe-gated
  engines, and loop on outcomes until every item is closed or dispositioned.
  Invoke as `/livespec-overseer:drain-backlog [--update-snapshot]
  [--repo <path>]`.
allowed-tools: Bash, Read
---

# drain-backlog - Claude Code binding

This file is the thin Claude Code binding for the `drain-backlog` operation of
the **livespec-overseer** plugin. The complete operator contract is the
plugin-owned prose artifact at `${CLAUDE_PLUGIN_ROOT}/prose/drain-backlog.md`.
Read that prose file in full, then execute it end-to-end.

```bash
cat "${CLAUDE_PLUGIN_ROOT}/prose/drain-backlog.md"
```

This binding adds NO operation behavior of its own; the operator contract lives
in the prose.
