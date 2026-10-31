---
topic: declaration-command
author: claude-opus-5-5
created_at: 2026-10-31T14:50:51Z
---

## Proposal: The declaration command is the session's sanctioned declaration channel

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Ratify `overseer-declare` as the one sanctioned way a session declares its state: one validated form per session-writable value plus a clear, refusing any value that would be malformed, and require every daemon-authored declaration instruction to name that command (resolvable on both runtimes) instead of a hand write. Hand-written files stay readable; the v075 rejection remains the backstop.

### Motivation

Incident 2026-10-26..30 (plan overseer-malformed-state-recovery): a coordinator hand-wrote `working: ...` into its state file and went four days without restart. v075 made the daemon reject and name such a value; this closes the cause. Today every daemon prompt except the final `overseer-declare ready` tells sessions to `echo` into or `rm` the file by hand, so nothing validates what they write. Maintainer direction 2026-10-31 (plan overseer-validated-state-command, epic overseer-kwkx74): use the existing command for everything, update all prompts to enforce it, and do whatever we can to discourage or prevent unvalidated direct writes.

### Proposed Changes

In `SPECIFICATION/contracts.md` §"The state file", insert the following paragraph immediately after the paragraph beginning "The normal sequence is two writes:" and before "Contract rules:":

```
THE DECLARATION COMMAND. The overseer ships one command, `overseer-declare`,
as the session's declaration channel. It MUST offer one form per
session-writable value — `winding-down`, `ready`, `blocked <reason>`, and
`done [<summary>]` — plus `clear`, which deletes the entity's own state file
when it holds a session-written value (the session-side clears this section
and spec.md permit: a recovered wind-down, or new work after `done`). It
MUST accept an explicit repository and entity topic, so a worker and a
supervisor pair member each address their OWN state file. It MUST validate
before it writes: a `blocked` reason MUST be non-empty, and a reason or
summary MUST be a single line free of control characters and at most 200
characters. A refused value MUST exit non-zero, name the accepted forms, and
leave any existing state file untouched, so the command can never write a
malformed value. Every write MUST be atomic. A hand-written state file
remains READ exactly as before — a valid value is honored and a malformed one
is rejected per the rules below — but it is not a sanctioned channel, and no
daemon-authored text may instruct one.
```

In the same section's Contract rules, append this bullet at the end of the list:

```
- Every daemon-authored message that asks a session to declare or to clear a
  declaration — the wrap-up of §"The wrap-up injection" for a worker or a
  supervisor pair member, the keep-going nudge, the ready-expiry notice, and
  the rejected-value line — MUST name the `overseer-declare` invocation for
  each value it asks for, carrying that entity's repository and topic, through
  a path that resolves for every supported runtime without relying on a
  harness-provided command search path. It MUST NOT instruct the session to
  write, echo into, redirect into, or delete the state file by hand, and it
  MUST state that the command is the only sanctioned way to declare.
```

In `SPECIFICATION/contracts.md` §"The wrap-up injection", in the "Message obligations" bullet replace "the state-file path with the four writable values (naming `done` as the declaration for finished work)," with "the four writable values, each as its `overseer-declare` invocation per §\"The state file\" (naming `done` as the declaration for finished work), together with the state-file path the command writes,".

In `SPECIFICATION/scenarios.md`, insert immediately after `## Scenario: A malformed state value is moved aside and named in the next wrap-up` (that is, before `## Scenario: A blocked declaration is relayed, not answered`) two new scenarios:

```
## Scenario: The declaration command refuses a value the daemon would reject

Given a tracked session whose state file holds a valid declaration

When the session runs overseer-declare blocked with an empty or multi-line reason

Then the command exits non-zero and names the accepted forms

And the state file still holds the earlier declaration

But overseer-declare blocked with a one-line reason writes that blocked declaration

## Scenario: Every declaration instruction names the declaration command

Given a tracked worker or supervisor pair member

When the daemon composes a wrap-up, a keep-going nudge, a ready-expiry notice, or a rejected-value line for it

Then each value it asks for is named as an overseer-declare invocation carrying that entity's repository and topic

And the text never instructs writing, echoing into, or deleting the state file by hand
```

The implementation MUST add both scenario headings to `tests/heading-coverage.json` (TODO entries with matching `tests/heading-coverage-debt.json` rows owned by an open work item) in the same revision, and the implementation children MUST replace them with tests.
