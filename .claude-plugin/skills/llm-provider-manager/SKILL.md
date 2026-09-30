---
name: llm-provider-manager
description: >-
  Acquire, validate, store, select, provision, revalidate and replace LLM
  provider credentials. Invoke as `/livespec-overseer:llm-provider-manager` to
  list what needs operator attention, or as
  `/livespec-overseer:llm-provider-manager --provider <v> --account-id <v>
  --kind <v> --purpose <v>` to acquire one credential identity.
allowed-tools: Bash, Read
---

# llm-provider-manager - Claude Code binding

This file is the thin Claude Code binding for the `llm-provider-manager`
operation of the **livespec-overseer** plugin. The complete operator contract is
the plugin-owned prose artifact at
`${CLAUDE_PLUGIN_ROOT}/prose/llm-provider-manager.md`. Read that prose file in
full, then execute it end-to-end.

```bash
cat "${CLAUDE_PLUGIN_ROOT}/prose/llm-provider-manager.md"
```

This binding adds NO operation behavior of its own. Root validation, argument
validation and the manager launch all live in the shared importable entrypoint
the prose invokes; do not reimplement any of them here.
