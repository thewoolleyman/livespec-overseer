---
topic: foreman-blocking-picker-removal
author: claude-fable-5
created_at: 2026-08-21T23:36:32Z
---

## Proposal: Remove the foreman's blocking-picker escape hatch

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

The foreman operator contract should no longer permit a blocking question for
the foreman's own unresolved human decisions, even as a last resort with a
bounded timeout. A foreman tick that needs such a decision should surface it
through the daemon's existing mechanical attention surface and return idle.

### Motivation

Measured on 2026-08-21 under work-item `overseer-lixhd3.1`, an open
`AskUserQuestion` picker suppresses scheduled fires for the session that raised
it, and missed occurrences are dropped rather than backfilled. That means the
ratified bounded-timeout escape cannot be implemented by the foreman session
itself: enforcing the timeout would require the very scheduled tick that the
open picker suppresses.

The current clause is therefore worse than merely permissive. It can read as
satisfied by an unbounded picker called "last resort", while removing the only
in-session clock that could make the bound real. The implementation now uses
the already-shipped foreman escalation file path and daemon attention surface
for these decisions, so the specification should forbid the blocking shape
instead of licensing an impossible bounded variant.

This proposal does not alter restart authority. The cardinal rule remains
unchanged: a tracked session may be restarted only after its own current-round
filesystem `ready` declaration. Nothing here authorizes the daemon, foreman, a
timer, or a heuristic to restart a session or to answer a picker on a human's
behalf.

### Proposed Changes

In `SPECIFICATION/spec.md`, replace the foreman human-decision escalation
paragraph's blocking-question permission:

```text
A blocking question MAY be used only as a last resort and only for a bounded
wait with a defined timeout, after which the escalation reverts to the
non-blocking form.
```

with a prohibition:

```text
The foreman MUST NOT use a blocking question to surface its own unresolved
human decision. It MUST surface that decision through the non-blocking
mechanical attention path and return idle with any required recurring schedule
still armed.
```

The surrounding restart-authority constraint should remain in place, preserving
the cardinal rule unchanged.

In `SPECIFICATION/scenarios.md`, add or revise the foreman scenario for human
decision escalation so it proves both sides of the rule:

- a foreman tick that needs a human decision records a non-blocking foreman
  escalation, returns idle, and still receives a later scheduled tick; and
- a foreman tick that ends with its own blocking prompt outstanding is a
  reportable violation rather than a permitted bounded wait.
