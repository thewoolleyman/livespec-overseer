# Scope and inventory

Created 2026-08-19T05:16:23Z by the grooming pass that bucketed every non-done
`livespec-overseer` work-item into a plan. This note is the write-once
research artifact required by the `plan` operation; the durable coordination
record is this thread's plan epic in the beads ledger, and every handoff is a
comment on that epic. Do not author a `handoff.md` here.

## Why this thread exists

Sixteen open work-items describe defects in the SUPERVISED-SESSION BEHAVIOR of
the `overseerd` daemon itself -- what it is allowed to type into a pane, which
tracks it can see, when it stops nagging, and whether the charter it emits can
be trusted. They were filed independently over several weeks, they were never
grouped, and none of them carried a plan. Read together they are one story:
**the running daemon and the ratified letter have drifted apart in both
directions**, and several of the mechanisms meant to detect that drift are
themselves inert.

Grouping them matters because they interact. The acting-safety divergence
(`overseer-um53`) and the v020 tightening (`overseer-g6sy`) contend for the same
paragraphs of `SPECIFICATION/constraints.md` and `spec.md`; the two attention
blind spots (`overseer-x6d`, `overseer-6eo`) both add members to the same NEEDS
YOU surface; and the charter-provenance tautology (`overseer-u63`) and the
topic-locked cold-open stub (`overseer-94p`) are the two reasons the charter
gates cannot currently catch either.

## The three strands

**Strand 1 -- acting safety and the ratified letter.** `constraints.md`
"Acting safety" names exactly two keystroke-bearing acts that may coexist with
the suppression rule. A third exists in the implementation
(`_supervisor_picker_stall.apply_picker_stall` -> `_supervisor_nudge`), and it
fires precisely on the two pane classes the constraint says MUST never be pasted
into: a structured gate (`picker_open` is `obs.gate`) and a human wait
(`status == "blocked:human"`). Either the letter admits a third act under its own
complete predicate, or the implementation retreats. That decision is the spine of
this strand and it blocks the well-formed completion of `overseer-g6sy` item (c).

**Strand 2 -- attention coverage.** Two classes of track are invisible to the
NEEDS YOU surface while in real trouble. A BUSY track below the danger floor is
outranked by `working` and excluded from both busy-time conditions
(`overseer-x6d`; rides to 15% and 7% context were observed). A live codex track
whose rollout has not yet landed in the session index reports `session-gone` and
is left entirely unsupervised -- no wrap-up, no restart (`overseer-6eo`).
Alongside these sit the unbounded `winddown-starved` suppression
(`overseer-t6m`), the stale-background-shell shield (`overseer-vyjkzw`), and the
mapping-store row loss that silently dropped supervision for eight of nine live
sessions including three `blocked:human` ones (`overseer-2ifwfq`).

**Strand 3 -- charter and letter hygiene.** The charter provenance check is a
tautology -- it digests a file against itself, so a stale generator is
undetectable (`overseer-u63`) -- and the cold-open gate's tmux stub is
topic-locked to the exemplar, so it false-positives on every real emitted charter
(`overseer-94p`). The supervisor send idiom is Claude-Code-specific but stated as
harness-neutral in both the generator and the shared protocol, so every future
charter reproduces the error (`overseer-816`). Three smaller spec residuals
(`overseer-9569`, `overseer-y8n6`) and one open maintainer question about whether
a newer ruling supersedes the CLAUDE.md never-kill clause (`overseer-7jrk`) belong
with them, as does the `tmp/overseer/` scratch-discipline hazard
(`overseer-yqza`) and the per-track supervision opt-out (`overseer-cid32m`).

## Requirement carriers admitted to this thread

`overseer-um53`, `overseer-g6sy`, `overseer-x6d`, `overseer-6eo`,
`overseer-t6m`, `overseer-vyjkzw`, `overseer-2ifwfq`, `overseer-cid32m`,
`overseer-u63`, `overseer-94p`, `overseer-816`, `overseer-9569`,
`overseer-y8n6`, `overseer-7jrk`, `overseer-yqza`.

The authoritative member list is the ledger -- the parent-child children of this
thread's plan epic -- never this file. This inventory records the cut that was
made and why; status is composed from the ledger via `list-work-items` and
`next`.

## Deliberate non-membership

Model/wrapper/provider preservation across restart is the separate live thread
`plan/model-preserving-restarts` and stays there. Foreman operator discipline and
plan-thread record integrity are `plan/foreman-improvements`. Test-rig hermeticity
and enforcement-gate defects are `plan/test-and-gate-integrity` even where they
touch supervision code, because their "done" is a green, honest gate rather than a
behavior change in the daemon.

## Ordering note for the first implementer

Take the letter decision in Strand 1 FIRST. `overseer-um53` is a divergence
between `constraints.md` and shipped code, so it is a spec question before it is
an implementation question, and `overseer-g6sy` is already blocked behind it.
Route it through `/livespec:propose-change` -> independent review -> `/livespec:revise`;
do not amend ratified spec text by any other path.
