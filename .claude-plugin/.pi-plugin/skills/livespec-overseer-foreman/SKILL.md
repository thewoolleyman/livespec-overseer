---
name: livespec-overseer-foreman
description: Run the bounded livespec foreman operator loop for the current repository.
allowed-tools: bash read
---

# livespec-overseer-foreman - pi binding

This file is the thin pi binding of the `foreman` operation of the
**livespec-overseer** plugin. It carries pi-runtime mechanics ONLY. The
complete operator contract is the plugin's shared artifact at
`prose/foreman.md`, the same artifact the Claude and Codex bindings read.

Order of work, every time:

1. Resolve `$PLUGIN_ROOT` (next section).
2. Read `$PLUGIN_ROOT/prose/foreman.md` **completely** with the `read` tool.
3. Execute that prose end-to-end, binding its harness-neutral vocabulary to
   this runtime via the Runtime bindings section below.

Never paraphrase, summarize, or act on a partial read of the prose, and never
restate its steps here - the prose owns the behavior, this file owns the
wiring.

pi's skill namespace is flat - a skill name admits no colon - so this plugin's
namespace is carried by the unabbreviated `livespec-overseer-` name prefix
rather than by the `/livespec-overseer:foreman` form the Claude and Codex
surfaces use.

## Resolving the plugin root (`$PLUGIN_ROOT`)

The ordered algorithm is realized ONCE, by this package's
`lib/resolve-plugin-root.sh`, and MUST NOT be restated inline here.

`<skill-dir>` below is the directory holding THIS `SKILL.md` - you read this
file from disk, so you know its absolute path; the resolver sits two levels up,
beside the bindings tree.

```bash
PLUGIN_ROOT="$(bash "<skill-dir>/../../lib/resolve-plugin-root.sh" .)" || exit 1
echo "$PLUGIN_ROOT"
```

The resolver searches, in order: the `LIVESPEC_OVERSEER_PLUGIN_ROOT` override;
the governed project's own plugin directory when that checkout IS this plugin
(dogfooding); the project-scope pi package clone under
`.pi/git/github.com/thewoolleyman/livespec-overseer/`; and the user-scope clone
under `~/.pi/agent/git/github.com/thewoolleyman/livespec-overseer/`.

On failure the resolver writes its own diagnostic to stderr and exits 1. STOP
and surface that diagnostic verbatim. Do not improvise a path, and do not run an
install command the diagnostic did not ask for.

## Runtime bindings

- **"ask the user" / "confirm with the user" / "obtain consent"** -
  conversational turns in this pi session. Ask in plain prose, state the
  options explicitly, and WAIT for the user's reply before proceeding.
- **"read `<file>`" / "list `<dir>`"** - the `read` tool, or the `bash` tool
  for shell work.
- **"invoke a wrapper" / "run a command"** - the `bash` tool, with explicit
  argv. Surface usage errors and precondition failures verbatim rather than
  retrying with guessed arguments.
- **"invoke the sibling `<operation>` skill"** - this runtime exposes it as the
  pi skill `livespec-overseer-<operation>`; drive that skill rather than
  reimplementing its behavior.
