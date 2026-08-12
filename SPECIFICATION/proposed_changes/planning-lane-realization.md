---
topic: planning-lane-realization
author: claude-fable-5
created_at: 2026-08-12T00:07:35Z
---

## Proposal: Realize the ratified Planning Lane contract in the overseer spec

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

### Summary

Replace the overseer's file-handoff vocabulary with the ratified Planning Lane
contract from livespec v197/v198. The governed plan's epic ledger is the durable
plan-state surface: supervisor handoffs are appended there as ledger entries,
and worker and supervisor respawns are prompted to read ledger-held plan state.
The PR-authored `plan/<topic>/supervisor-handoff.md` path is retired from the
specification surface, and `plan/<topic>/handoff.md` is no longer named as the
worker resume source.

This proposal also updates the four current `spec.md` prose lines that still
use old plan-thread vocabulary (re-enumerated in this tree as lines 369, 397,
400, and 439) to Planning Lane terms. No `## ` heading is added, removed, or
renamed in any target file, so no `tests/heading-coverage.json` co-edit is
required. Ratification is deliberately out of scope for this slice.

### Motivation

livespec v197/v198 ratified the Planning Lane realization: plan state is held on
the governed plan's epic, not in a plan-tree handoff file. livespec-overseer's
own spec still predates that contract in the wrap-up obligation, restart prompt,
supervisor-pair brief, non-interference carve-out, contracts, constraints, and
operator-observable scenarios. That leaves the control-plane spec instructing
sessions and pair members to use artifacts that the fleet contract has retired.

The protected properties do not change. The daemon still never writes tracked
plan-tree files, still never reads handoff payloads as authorization, and still
restarts only after a fresh `ready` declaration passes the interlock. What
changes is the durable read-first target: it is the plan's epic-held ledger
state, including supervisor handoff ledger entries, rather than
`plan/<topic>/handoff.md` or `plan/<topic>/supervisor-handoff.md`.

### Proposed Changes

Seven edits. Anchors re-enumerated against the working tree at proposal time.

EDIT 1 (spec.md §"The supervision round"). Replace the stale example in the
undelivered-wrap-up paragraph:

> `ready` written afterwards — a handoff convention, a state file inherited from
> a predecessor, an unprompted write by a session that was never told to declare
> — would otherwise certify against it and authorize a kill.

with:

> `ready` written afterwards — a stale resume convention, a state file inherited
> from a predecessor, an unprompted write by a session that was never told to
> declare — would otherwise certify against it and authorize a kill.

EDIT 2 (spec.md §"The escalating wrap-up" and §"The restart"). Replace the
wrap-up message obligation:

> its current remaining-context percentage; the exact state-file path and the
> three values it may write; that its handoff file is the ONLY artifact the
> successor session inherits, so drifted resume state belongs in a rewritten
> handoff, never withheld; and the truth that it will be restarted ONLY when it
> declares `ready`.

with:

> its current remaining-context percentage; the exact state-file path and the
> three values it may write; that the plan's epic-held ledger state is the
> successor session's durable read-first source, so drifted resume state belongs
> in an appended ledger entry, never withheld; and the truth that it will be
> restarted ONLY when it declares `ready`.

In the restart paragraph, replace:

> read your track's handoff file and follow it.

with:

> read your track's ledger-held plan state and follow it.

EDIT 3 (spec.md §"Track discovery and the mapping store"). Replace the discovery
paragraph's file-handoff tail and the bounded file probe:

> Discovery keys on the DIRECTORY existing — it never reads, stats, or hashes
> any file inside a plan directory (per §"Non-interference with tracked work");
> the conventional handoff path it derives is a pointer handed to sessions,
> never opened by the overseer. One bounded exception: for a track with a
> CURRENTLY MATCHING live session (the liveness gate), the daemon MAY test the
> EXISTENCE of exactly one named artifact, plan/<topic>/supervisor-handoff.md —
> no open, no read, no hash, no content or mtime dependence, and no probe of any
> kind for tracks without a live session. This is the ONLY file-level probe the
> discovery path may ever perform.

with:

> Discovery keys on the DIRECTORY existing — it never reads, stats, or hashes
> any file inside a plan directory (per §"Non-interference with tracked work").
> The read-first target it hands to sessions is the plan's epic-held ledger
> state, not a plan-tree file, and the daemon does not inspect that ledger state
> as restart authorization. The discovery path performs no file-level probe
> inside a plan directory.

EDIT 4 (spec.md §"Track discovery and the mapping store" and §"Session-name
derivation"). Apply the Planning Lane vocabulary to the four term-bearing prose
lines called out by this work item:

- Replace "Whoever archives a plan thread MUST leave NOTHING at its live path"
  with "Whoever archives a Planning Lane topic MUST leave NOTHING at its live
  path".
- Replace "When a plan thread would close with anything unresolved" with "When
  a Planning Lane would close with anything unresolved".
- Replace "TRANSFERRED to a different or new NON-ARCHIVED plan thread and/or
  work-item" with "TRANSFERRED to a different or new NON-ARCHIVED Planning Lane
  and/or work-item".
- Replace "a plan-thread worker, wrapped up, nudged, or respawned into a plan
  handoff" with "a Planning Lane worker, wrapped up, nudged, or respawned into
  ledger-held plan state".

EDIT 5 (spec.md §"Supervised runtimes" and §"Non-interference with tracked
work"). Replace the supervisor-pair artifact contract with the ledger-held
Planning Lane contract.

In the pair identity paragraph, replace:

> its wrap-up and keep-going messages are entity VARIANTS whose paths, session
> name, and commit ritual refer to the supervisor's own artifacts —
> `plan/<topic>/supervisor-handoff.md`, committed through the repository's own
> discipline — and never to the worker's handoff; and its restart preserves the
> suffixed session name and hands the fresh session exactly one prompt: read the
> supervisor handoff and follow it. The respawn is additionally gated on that
> artifact EXISTING, re-checked immediately before the act, so a `ready` with no
> artifact preserves the declaration and surfaces the existing capture offer
> instead of resuming onto a dead pointer; the daemon takes no content or
> modification-time dependence on the artifact, so brief freshness remains the
> supervisor's own protocol obligation, discharged by committing the brief before
> declaring `ready`.

with:

> its wrap-up and keep-going messages are entity VARIANTS whose paths and
> session name refer to the supervisor entity while its read-first obligation
> points at supervisor handoff ledger entries on the governed plan's epic, never
> at the worker's own read-first state; and its restart preserves the suffixed
> session name and hands the fresh session exactly one prompt: read the
> supervisor entries in the track's ledger-held plan state and follow them. The
> respawn is not gated on any plan-tree artifact existing. Brief freshness
> remains the supervisor's own protocol obligation, discharged by appending the
> brief to the governed plan's epic before declaring `ready`.

Replace the attention sentence:

> supervision died mid-handoff and the brief is at risk

with:

> supervision died mid-brief and the ledger entry is at risk

Replace the non-interference paragraph beginning "The overseer's DAEMON" and
the attended artifact paragraph with:

> The overseer's DAEMON — the unattended observation and restart loop — NEVER
> touches files under any repository's plan tree. The plan state and everything
> beside it are the supervised session's own workflow: the overseer enumerates
> plan DIRECTORIES to discover tracks and points sessions at ledger-held plan
> state, but the daemon never opens, writes, or hashes plan-tree files and never
> reads plan-state text as restart authorization — the restart interlock
> deliberately inspects nothing beyond the state-file token for the same reason.
>
> An ATTENDED Control-Plane operator skill (supervise-plan) MAY append
> supervisor handoff entries to the governed plan's epic ledger. It MUST do so
> through the repository's ratified Planning Lane ledger discipline, never by
> creating or updating `plan/<topic>/supervisor-handoff.md` through the pull
> request path. A supervisor handoff entry is NOT overseer runtime state: the
> "exactly two places" sentence below and the startup gitignore refusal continue
> to bind the daemon's runtime state verbatim.

EDIT 6 (contracts.md §"The restart interlock", §"The wrap-up injection",
§"The keep-going nudge", and §"Durable stores"). Replace the restart guarantee:

> handed exactly one prompt: read that entity's resume artifact —
> `<repo>/plan/<topic>/handoff.md` for a worker,
> `<repo>/plan/<topic>/supervisor-handoff.md` for a supervisor pair member —
> and follow it.

with:

> handed exactly one prompt: read that entity's ledger-held plan state — the
> governed plan's epic ledger for a worker, or the supervisor handoff entries on
> that same epic for a supervisor pair member — and follow it.

Replace the wrap-up message obligation:

> the handoff path as the sole artifact the successor inherits (with the
> instruction to REWRITE it on drift, never withhold the declaration)

with:

> the ledger-held plan state as the successor's durable read-first source (with
> the instruction to APPEND a ledger entry on drift, never withhold the
> declaration)

Replace the keep-going sentence:

> The message points the session back at its handoff

with:

> The message points the session back at its ledger-held plan state

Replace the mapping-store durable-key sentence:

> Durable keys: `topic`, `repo`, `tmux`, `handoff`, `resume`, `epic`,
> `pinned_session_id`, plus `ctx_threshold` ONLY when a per-track override is
> set

with:

> Durable keys: `topic`, `repo`, `tmux`, `epic`, `pinned_session_id`, plus
> `ctx_threshold` ONLY when a per-track override is set. The `epic` value is the
> plan-state locator for the read-first chain; retired `handoff` and `resume`
> keys are legacy input only and MUST NOT be emitted by rewrites.

EDIT 7 (constraints.md §"Filesystem boundaries" and scenarios.md). Replace the
constraints paragraph's attended authoring sentence:

> The attended Control-Plane authoring exception permits supervise-plan to
> create exactly two reviewed artifacts, `.ai/supervisor-protocol.md` and
> `plan/<topic>/supervisor-handoff.md`.

with:

> The attended Control-Plane authoring exception permits supervise-plan to
> append supervisor handoff entries to the governed plan's epic ledger; it MUST
> NOT create or update plan-tree handoff files through the pull request path.

In scenarios.md, replace:

> And the message names the state-file path, the three writable values, and the
> handoff path

with:

> And the message names the state-file path, the three writable values, and the
> ledger-held plan state

Replace:

> And hands the fresh session exactly one prompt pointing at the track's handoff

with:

> And hands the fresh session exactly one prompt pointing at the track's
> ledger-held plan state

Replace the body of the existing supervision-artifact probe scenario without
renaming its `## ` heading:

> Then it MAY test whether plan/<topic>/supervisor-handoff.md exists
>
> And it never opens, reads, or hashes that file and never depends on its content
> or mtime
>
> And for a track without a live matching session it performs no file-level
> probe at all

with:

> Then it performs no file-level probe inside the plan directory
>
> And it never opens, reads, or hashes plan-tree handoff files as authorization
>
> And it points the session at ledger-held plan state instead

No target-file `## ` heading is added, removed, or renamed by these edits, so
ratification owes no `tests/heading-coverage.json` co-edit.
