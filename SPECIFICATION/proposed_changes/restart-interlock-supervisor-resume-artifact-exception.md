---
topic: restart-interlock-supervisor-resume-artifact-exception
author: claude-code
created_at: 2026-08-14T20:56:38Z
---

## Proposal: restart-interlock-supervisor-resume-artifact-exception

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/constraints.md
- SPECIFICATION/contracts.md

### Summary

The restart interlock has a fifth, undocumented gate for SUPERVISOR topics only -- a bounded plan-tree read/existence check (_supervisor_resume_artifact_certifies / _migrated_supervisor_epic_certifies in overseer/_supervisor_restart.py) -- that contradicts three current ratified absolute claims: spec.md's 'the restart interlock deliberately inspects nothing beyond the state-file token', constraints.md's 'The daemon NEVER reads, writes, or hashes files under a repository's plan tree', and contracts.md's closed four-item restart-interlock checklist ('A restart fires ONLY when every one of these deterministic checks passes'). Amend all three to document this bounded, supervisor-topic-only, two-shape resume-artifact certification as a named, explicit exception rather than leaving shipped behavior silently contradict ratified prose.

### Motivation

Discovered via a focused capture-spec-drift review of the planning-lane-redesign plan's (epic livespec-zsn2xh) own code changes across repos, scoped ONLY to this plan's changes per maintainer instruction. PR #913 in this repo (livespec-overseer, merged 2026-08-14T12:24:16Z, work-item overseer-i3o2jr) added _migrated_supervisor_epic_certifies(), which reads the full text content of plan/<topic>/epic.md and pattern-matches it (epic id, 'ledger', 'comment'/'entry' substrings) as a restart-authorization condition for supervisor topics, as part of realizing this plan's ratified Planning Lane redesign (the daemon must recognize the migrated ledger-held plan shape to restart a certified-ready supervisor entity). This function, and its older sibling that checks plan/<topic>/supervisor-handoff.md's existence, are both real, live, verified-working code paths -- not a mistake to be reverted -- but neither is documented anywhere in the current SPECIFICATION, which instead makes unqualified absolute claims that the daemon never touches plan-tree files at all. A future agent reading only the spec would reasonably conclude the daemon never touches plan-tree files, and could regress by 'fixing' this code to match the (currently overstated) absolute claim, breaking supervisor restart for both the legacy and migrated plan shapes.

### Proposed Changes

Three coordinated edits, each narrowing an absolute claim into an absolute claim WITH ONE NAMED, BOUNDED EXCEPTION -- topic-scoped (SUPERVISOR topics only, per signals.topic_reserved_for_supervisor), fixed-shape (exactly the legacy supervisor-handoff.md existence check OR the migrated epic.md content check -- no other plan-tree path or content is read), read-only (never opens for write, never hashes), and restart-gating only (it can only BLOCK a restart pending certification, never trigger one, authorize a kill, or substitute for the session's own fresh `ready` declaration).

1. SPECIFICATION/spec.md, section '## Non-interference with tracked work'. Replace:

```
The overseer's DAEMON — the unattended observation and restart loop — NEVER
touches files under any repository's plan tree. The plan state and
everything beside it are the supervised session's own workflow: the overseer
enumerates plan DIRECTORIES to discover tracks and points sessions at
ledger-held plan state, but the daemon never opens, writes, or hashes
plan-tree files and never reads plan-state text as restart authorization —
the restart interlock deliberately inspects nothing beyond the state-file
token for the same reason. The discovery path performs no file-level probe
inside a plan directory.
```

with:

```
The overseer's DAEMON — the unattended observation and restart loop — NEVER
touches files under any repository's plan tree, with exactly ONE bounded
exception (per contracts.md §"The restart interlock", resume-artifact
certification). The plan state and everything beside it are the supervised
session's own workflow: the overseer enumerates plan DIRECTORIES to discover
tracks and points sessions at ledger-held plan state, and for every topic
other than a SUPERVISOR topic the daemon never opens, writes, or hashes
plan-tree files and never reads plan-state text as restart authorization —
the restart interlock inspects nothing beyond the state-file token for those
tracks. For a SUPERVISOR topic only, the restart interlock ADDITIONALLY
certifies that either the legacy plan/<topic>/supervisor-handoff.md exists,
or the migrated plan/<topic>/epic.md names the track's recorded ledger epic
and references the ledger-comment binder medium, before restarting — a
bounded, read-only, restart-gating-only check that can never trigger a
restart, authorize a kill, or substitute for the entity's own fresh `ready`
declaration. The discovery path still performs no file-level probe inside a
plan directory outside that one named exception.
```

2. SPECIFICATION/constraints.md, section '## Filesystem boundaries'. Replace:

```
The daemon NEVER reads, writes, or
hashes files under a repository's plan tree.
```

with:

```
The daemon NEVER reads, writes, or
hashes files under a repository's plan tree, EXCEPT for the one named,
bounded resume-artifact certification described in contracts.md §"The
restart interlock": for a SUPERVISOR topic only, a read-only, restart-gating
check of either plan/<topic>/supervisor-handoff.md's existence or
plan/<topic>/epic.md's content, and no other plan-tree path or content.
```

3. SPECIFICATION/contracts.md, section '## The restart interlock'. After the
existing four-item numbered list and before the sentence 'Any absent,
unreadable, or other-valued file fails the check.', insert a fifth
conditional item documenting the supervisor-topic resume-artifact
certification exactly as items 1-4 document their own checks, and amend the
list's own framing sentence from an unconditional 'ONLY when every one of
these deterministic checks passes' to name that a fifth, topic-conditional
check applies for supervisor topics. Cite the two accepted artifact shapes
(legacy supervisor-handoff.md existence; migrated epic.md naming the
recorded epic id and referencing the ledger-comment binder medium) and state
that this check is read-only and can only BLOCK, never authorize, a
restart.
