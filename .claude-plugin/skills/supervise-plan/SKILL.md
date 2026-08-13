---
name: supervise-plan
description: >-
  Publish a supervisor handoff for a live livespec plan: the binder as
  attributed, timestamped entries on the plan's ledger epic, and the shared role
  layer through the target repository's own reviewed worktree -> PR -> merge
  discipline. Invoke as /livespec-overseer:supervise-plan.
allowed-tools: Bash, Read, Write, Edit
---

# supervise-plan - Claude Code binding

This file is the thin Claude Code binding for the `supervise-plan` operation of
the **livespec-overseer** plugin. The complete operator contract is the
plugin-owned prose artifact at `${CLAUDE_PLUGIN_ROOT}/prose/supervise-plan.md`.
Read that prose file in full, then execute it end-to-end.

```bash
cat "${CLAUDE_PLUGIN_ROOT}/prose/supervise-plan.md"
```

This binding adds NO operation behavior of its own; the operator contract
lives in the prose.
