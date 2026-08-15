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

The restart interlock has a fifth, undocumented gate for SUPERVISOR topics only -- a bounded plan-tree read/existence check (_supervisor_resume_artifact_certifies / _migrated_supervisor_epic_certifies in overseer/_supervisor_restart.py) -- that contradicts SIX current ratified absolute claims: spec.md's 'the restart interlock deliberately inspects nothing beyond the state-file token' (§"Non-interference with tracked work"), THREE further daemon-wide absolute claims in spec.md §"Track discovery and the mapping store" ('the daemon never reads inside a plan directory', 'the daemon never reads one [a file inside a plan directory]', and 'the daemon consumes the recorded value and never reads the anchor itself' -- the last of these only became contradictory after overseer/_registry_epic.py commit e0f1100 made plan/<topic>/epic.md the anchor file itself for the migrated shape), constraints.md's 'The daemon NEVER reads, writes, or hashes files under a repository's plan tree', and contracts.md's closed four-item restart-interlock checklist ('A restart fires ONLY when every one of these deterministic checks passes'). Amend all six passages (three files) to document this bounded, supervisor-topic-only, two-shape resume-artifact certification as a named, explicit exception rather than leaving shipped behavior silently contradict ratified prose.

### Motivation

Discovered via a focused capture-spec-drift review of the planning-lane-redesign plan's (epic livespec-zsn2xh) own code changes across repos, scoped ONLY to this plan's changes per maintainer instruction. PR #913 in this repo (livespec-overseer, merged 2026-08-14T12:24:16Z, work-item overseer-i3o2jr) added _migrated_supervisor_epic_certifies(), which reads the full text content of plan/<topic>/epic.md and pattern-matches it (epic id, 'ledger', 'comment'/'entry' substrings) as a restart-authorization condition for supervisor topics, as part of realizing this plan's ratified Planning Lane redesign (the daemon must recognize the migrated ledger-held plan shape to restart a certified-ready supervisor entity). This function, and its older sibling that checks plan/<topic>/supervisor-handoff.md's existence, are both real, live, verified-working code paths -- not a mistake to be reverted -- but neither is documented anywhere in the current SPECIFICATION, which instead makes unqualified absolute claims that the daemon never touches plan-tree files at all. A future agent reading only the spec would reasonably conclude the daemon never touches plan-tree files, and could regress by 'fixing' this code to match the (currently overstated) absolute claim, breaking supervisor restart for both the legacy and migrated plan shapes.

### Proposed Changes

Five coordinated edits (across three files, fixing six passages -- edit 4 alone fixes two passages, edits 1/2/3/5 each fix one), each narrowing an absolute claim into an absolute claim WITH ONE NAMED, BOUNDED EXCEPTION -- topic-scoped (SUPERVISOR topics only, per signals.topic_reserved_for_supervisor), fixed-shape (exactly the legacy supervisor-handoff.md existence check OR the migrated epic.md content check -- no other plan-tree path or content is read), read-only (never opens for write, never hashes), and restart-gating only (it can only BLOCK a restart pending certification, never trigger one, authorize a kill, or substitute for the session's own fresh `ready` declaration).

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
READ exception (per contracts.md §"The restart interlock", resume-artifact
certification; existence-only STAT probes elsewhere, e.g. the supervision-offer
surface's check of the same two artifact names, are unchanged by this
exception and were never covered by the "opens, writes, or hashes" verb
list the next sentence uses). The plan state and everything beside it are the
supervised session's own workflow: the overseer enumerates plan DIRECTORIES
to discover tracks and points sessions at ledger-held plan state, and for
every topic other than a SUPERVISOR topic the daemon never opens, writes, or
hashes plan-tree files and never reads plan-state text as restart
authorization — the restart interlock inspects nothing beyond the
state-file token for those tracks. For a SUPERVISOR topic only, the restart
interlock ADDITIONALLY certifies that either the legacy
plan/<topic>/supervisor-handoff.md exists, or the migrated
plan/<topic>/epic.md names the track's recorded ledger epic and references
the ledger-comment binder medium, before restarting — a bounded, read-only,
restart-gating-only check that can never trigger a restart, authorize a
kill, or substitute for the entity's own fresh `ready` declaration. The
discovery path still performs no file-level probe inside a plan
directory — the one named read exception sits on the restart interlock,
never on discovery.
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

4. SPECIFICATION/spec.md, section '## Track discovery and the mapping
store'. This section carries two FURTHER daemon-wide absolute claims
(distinct from the discovery-scoped sentence a few lines earlier, "The
discovery path performs no file-level probe inside a plan directory.",
which stays true and is untouched) that edits 1-3 do not reach and that
would otherwise be left silently contradicted after ratification. Replace:

```
Because the daemon never reads
inside a plan directory, it can never re-derive that id for itself:
```

with:

```
Because the daemon never reads
inside a plan directory on the discovery or consumption path — the sole
exception being the supervisor resume-artifact certification per
contracts.md §"The restart interlock" — it can never re-derive that id
for itself on any other path:
```

Separately, replace:

```
The epic id
qualifies because its source is the plan's write-once metadata anchor, a
file inside a plan directory, and the daemon never reads one — which is why
the id is recorded at track assignment by a surface that MAY read plan-tree
text as evidence, and merely consumed by the daemon thereafter.
```

with:

```
The epic id qualifies because its source is the plan's write-once metadata anchor, a
file inside a plan directory, and the daemon never reads one for THIS
purpose (id re-derivation) — the supervisor resume-artifact certification
per contracts.md §"The restart interlock" MAY read the SAME anchor file
(plan/<topic>/epic.md, in the migrated shape -- since overseer/_registry_epic.py
commit e0f1100, epic.md is the FIRST-read write-once anchor, not a
distinct file) for a DIFFERENT, narrower purpose:
certifying a supervisor's resume artifact, never re-deriving an id — which
is why the id is recorded at track assignment by a surface that MAY read
plan-tree text as evidence, and merely consumed by the daemon thereafter.
```

5. SPECIFICATION/spec.md, same section ('## Track discovery and the
mapping store'). A fifth, closely-related passage in this same section
also needs amending, and edit 4b's earlier drafts (this proposal's first
two rounds) instead left it as an unamended Note claiming it "stays
literally true" -- that claim depended on the anchor file being distinct
from epic.md, which commit e0f1100 (above) made false for the migrated
shape: the anchor and the certification's target are now the SAME file.
Replace:

```
The
daemon consumes the recorded value and never reads the anchor itself.
```

with:

```
The
daemon consumes the recorded value and never reads the anchor itself to
re-derive it — the sole exception is the supervisor resume-artifact
certification per contracts.md §"The restart interlock", which MAY read
the SAME anchor file for that narrower, unrelated purpose.
```
