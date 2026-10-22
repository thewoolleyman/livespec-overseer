---
topic: live-exercise-agent-client-isolation
author: claude-opus-5-5
created_at: 2026-10-22T04:54:22Z
---

## Proposal: The isolated live exercise runs the installed agent client or refuses before starting

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add a new spec.md section, `## The isolated live exercise`, that states the agent-client contract of the released live-exercise runner (`scripts/overseer-live-exercise.sh`). The namespace replaces the operator home with a scratch home and binds no writable operator-home path. An agent client installed under the operator home is made runnable inside the namespace by binding, read-only, what it actually executes. This includes a script launcher whose real executable or install tree lives under that home. When the client cannot be made runnable, the runner refuses before any terminal backend starts and names the unresolvable client path. Add the matching scenario `## Scenario: The isolated live exercise runs the installed agent client or refuses before starting`.

### Motivation

The specification states nothing about the live-exercise runner, yet it is the only sanctioned way to produce the authenticated Claude and Codex host-captured release proof (overseer/live-exercise.md: 'Authenticated real-client evidence remains a release-host obligation'). Measured 2026-10-22 on the release host: the authenticated Codex host proof for overseer-uzvcbn.4 failed bootstrap with 'no idle Codex TUI in pane w1:p1 within 60s', after plan-only and the isolation check had both passed. The host's `~/.local/bin/codex` is a 368-byte bash shim that runs `exec ~/.bun/bin/bun ~/.bun/bin/codex`. The runner bound only that shim file at its own path, and the scratch home hid `~/.bun`, so Codex never started. The failure surfaced only after the backend, the namespace and a 60-second wait, as a bootstrap failure that names neither the client nor the missing install. The work item overseer-fr8f fixes the runner, and its Definition of Done needs a governing scenario to grade against (DoD preflight finding, coordinator rulings R559/R202).

### Proposed Changes

In SPECIFICATION/spec.md, insert a new H2 section immediately after `## Non-interference with tracked work` and before `## Notify, never block`:

```
## The isolated live exercise

The released live-exercise runner (`scripts/overseer-live-exercise.sh`) runs one
supported terminal backend and one authenticated agent client (Claude Code or
Codex) inside a private namespace. It is the sanctioned surface for the
host-captured lifecycle proof of a release, and it MUST NOT touch the operator's
real fleet.

The namespace MUST replace the operator home with a scratch home, and it MUST NOT
bind any operator-home path writable. The agent client's credential is the only
operator-home content copied in.

An agent client installed under the operator home MUST be made runnable inside the
namespace by binding, read-only, what that client actually executes — the
executable itself, or the install tree a script launcher runs from. Binding only
the launcher file is insufficient when that launcher executes content elsewhere
under the operator home, because the scratch home hides that content.

When the runner cannot make the selected agent client runnable inside the
namespace, it MUST refuse BEFORE it starts any terminal backend. The refusal MUST
name the client path it could not resolve. It MUST NOT report the condition later
as a lifecycle-stage failure.
```

In SPECIFICATION/scenarios.md, append:

```
## Scenario: The isolated live exercise runs the installed agent client or refuses before starting

Given an operator host whose agent client on PATH is a script launcher that executes an install tree under the operator home

When the released live-exercise runner starts a lifecycle run for that agent client

Then the client inside the namespace reaches its idle input prompt

And no operator-home path is bound writable inside the namespace

And when the client cannot be made runnable inside the namespace, the runner refuses before any terminal backend starts, naming the unresolvable client path
```

Both new headings MUST be registered in tests/heading-coverage.json as `"test": "TODO"` rows owned by work item overseer-fr8f, with matching tests/heading-coverage-debt.json entries, co-edited in the same change.
