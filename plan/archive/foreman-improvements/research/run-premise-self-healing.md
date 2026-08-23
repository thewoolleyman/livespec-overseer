# Run-premise self-healing — adopted research note

Adopted 2026-08-19 into the `foreman-improvements` plan (epic
`overseer-au3pt3`) from the plan draft authored by
`livespec-overseer-foreman` on maintainer directive; the corrected draft
(post the orchestrator foreman's forge-proof premise correction) is
reproduced verbatim below the adoption record.

## Adoption record

- Scope-extension event recorded on epic `overseer-au3pt3` (2026-08-19),
  naming the five children as requirement carriers and the xyoj / v7io /
  containment-closed deferrals.
- Children filed as individual ledger work-items under the epic, each with
  the maintainer-directed GATING LIVE-VERIFICATION EXIT CRITERION (close
  only after an end-to-end demonstration against a real tracked session
  under the running daemon, evidence recorded verbatim in a ledger comment)
  and the `acceptance:ai-then-human` parking label:
  - Child A -> `overseer-au3pt3.5` (typed wait-premise records)
  - Child B -> `overseer-au3pt3.6` (`wait-target-missing` daemon condition;
    remote-aware authoritative-source set is MANDATORY — local `fabro ps -a`
    is never sufficient for HP-remote runs, in either direction)
  - Child C -> `overseer-au3pt3.7` (self-healing evidence-carrying relay;
    text-dependency on `overseer-v7io`, never a dependency edge)
  - Child D -> `overseer-au3pt3.8` (aggregate `dispatch-quiet-with-waiters`,
    keyed on failed remote-aware premise verification, NOT local process
    quiet; text-link `bd-ib-xyoj`)
  - Child E -> `overseer-au3pt3.9` (picker-premise hygiene at raise time;
    spec-bearing routing check recorded before implementation)
- Local dependency edges: `.6` depends on `.5`; `.8` depends on `.6`
  (genuine sibling deps — distinct from the forbidden anchor-as-dependency
  shape).
- Dedupe against this plan's earlier items, per the draft's map: A/B extend
  the shipped stall/dead-watch mechanism family (`overseer-h4ziqc`, closed)
  rather than duplicating it; C/D are concrete instances of the ratified
  v017 non-blocking-escalation and evidence-carrying-relay floors
  (`overseer-z63rh3`/`overseer-dz2skw`, closed; daemon membership condition
  `overseer-au3pt3.1`, closed).

## Adopted draft (verbatim)

# Plan draft: mechanical, self-healing handling of false wait-premises and dispatch outages

Drafted by `livespec-overseer-foreman` on maintainer directive, 2026-08-19.
Motivating incident (2026-08-19 ~23:00Z–02:00Z), **premise CORRECTED
post-draft by the orchestrator foreman with forge proof, re-verified here**:
this was NOT a full outage. 7c4c's factory dispatch DELIVERED —
livespec-dev-tooling PR #1525 verified MERGED at 2026-08-18T23:41:26Z (`gh pr
view 1525 --json state,mergedAt`), inside the claimed window. The real
defects are (a) a **local-vs-remote fabro visibility gap**: local `fabro ps
-a` proves nothing in either direction for HP-remote runs, and two foremen
were burned by that trap tonight; and (b) a pre-flight wedge (the wnsq2d
evidence). Two console-foreman workers still waited on runs (`-ivem`,
`llioxx`) invisible locally, and the aggregate state went unnoticed for over
an hour. Root-cause item for the dispatch surface: `bd-ib-xyoj` —
**re-scoped P2** (not P0), orchestrator tenant, driven as an ordinary item
there. This correction SHARPENS Child B: "absent from local `fabro ps -a`"
must never be a sufficient re-verification for a remote run — the forge /
publish branch / dispatch-journal `outcome` legs are mandatory, and the
authoritative-source set must be keyed by where the run executes. Picker-answer path defect:
`overseer-v7io` (carried by plan `foreman-fixes-to-blocking-pickers`,
recompute-at-act-time design ratified, in implementation).

## The three failure classes, and the mechanical principle

1. **False wait-premise** — a session (picker or prose) waits on a fabro run
   that does not exist. Today nothing re-verifies the premise; the wait is
   trusted indefinitely.
2. **Undeliverable answer** — even a correct mechanical answer cannot reach a
   picker-parked pane (`overseer-v7io`, double-broken: vocabulary skew +
   unpublished `question_fingerprint`).
3. **Invisible systemic outage** — zero running fabro processes while
   multiple tracked sessions hold dispatch-shaped waits; no attention
   condition exists for the AGGREGATE state.

Principle (same throughline as `foreman-improvements` brainstorm items 2/5):
**a wait is a claim, and every claim a session parks on must be keyed to a
re-verifiable identity plus a liveness leg, checked by the daemon's existing
`evaluate()`/attention machinery — never by standing operator explanations.**
This is the armed-mechanism-validity rule (pane title + daemon_instance_id)
generalized from watches to WAITS.

## Proposed children (new, under the foreman-improvements plan epic)

### Child A — typed wait-premise records ("wait-target ledger")

When a tracked session enters a dispatch-shaped wait (foreman relay, picker
raise, or supersede-order), the actor records a typed premise under
`tmp/overseer/<topic>/`: `{kind: fabro-run|pr|ci-run|work-item-close, target
id, evidence source to re-query, recorded_at, recheck_by}`. Untyped prose
waits remain legal but are second-class: they inherit the existing 30-minute
re-read rule. Acceptance: a premise file schema + writer helper shipped in
`overseer/`, and `foreman-gather` surfacing premises per row.

### Child B — daemon attention condition `wait-target-missing`

A NEW membership condition inside the existing `evaluate()` machinery (per
invariant 1/2 in `overseer/AGENTS.md`, NOT a second daemon): for each typed
premise, re-verify the target against its authoritative source (`fabro ps
-a` presence/state, dispatch-journal `outcome`, `gh pr view`/`gh run view`)
on the daemon's poll cadence with caching. A missing or terminal target
raises `wait-target-missing` on the row — report-only, exactly like
`pane-still`. This makes "waiting on a run that evaporated" a NEEDS-YOU
condition within one poll interval instead of an hours-later human catch.
Detection must distinguish the six dispatch-trap shapes already tabled in
CLAUDE.md (evicted vs succeeded-untransitioned vs blocked, etc.) at least to
the level of "absent from ps -a" vs "present, terminal state X".

### Child C — self-healing relay: auto-answer/auto-wake on a dead premise

The foreman's tick, on seeing `wait-target-missing`: compose the evidence
record (the re-query output verbatim + on-disk path, per the
evidence-carrying relay rule) and deliver it mechanically —
`blocked_session_answer` for picker panes (DEPENDS ON `overseer-v7io`
landing in foreman-fixes-to-blocking-pickers; do not duplicate that fix),
ordinary verified paste for prose-waiting panes. Floors unchanged: this
delivers FACTS to the session; it never chooses the session's next action,
never restarts anything without a `ready`, and stays report-only where the
valve disposition says so.

### Child D — aggregate condition `dispatch-quiet-with-waiters`

The overseer-side slice of `bd-ib-xyoj`'s detection leg (the pipeline itself
is the orchestrator repo's to fix — link, don't absorb): when >=N tracked
rows across the daemon's snapshot hold dispatch-shaped waits AND the fabro
process set has been empty for the whole recheck window, raise ONE
fleet-level attention row. Self-healing side: the foreman may issue the
containment supersede-order mechanically (hold re-dispatch, verify forge
landings, continue non-dispatch work) as a typed relay template, and an
all-clear relay when the condition clears — so tonight's hand-written
containment becomes a shipped playbook.

### Child E — picker-premise hygiene at raise time

Prevention twin of B: any picker whose text embeds a wait-premise must embed
the typed premise (Child A) at raise time, so its options can be
mechanically invalidated ("option 2's run no longer exists") instead of
trusted as written. Overlaps the routing-instruction-in-picker rule already
in the prose contract; likely lands as a prose-contract amendment plus a
lint in the picker-raising helper. Shares foreman-improvements item 3's
spec-bearing-ness question — check `/livespec:propose-change` routing before
assuming a plain PR.

## Relation to existing work (dedupe map)

- `foreman-improvements` item 2 (durable stall + dead-watch detection):
  Children A/B are the same mechanism-family — ADOPT into that plan as
  siblings; consider one shared "typed watch/wait registry" design note so
  watches and waits use one identity+liveness schema.
- `foreman-improvements` item 5 (non-blocking escalation): Child C/D's relay
  templates are the concrete instances of that pattern.
- `foreman-fixes-to-blocking-pickers` / `overseer-v7io`: Child C DEPENDS on
  it (thread membership in text, NOT a cross-repo depends_on edge).
- `bd-ib-xyoj` (orchestrator, P0): owns pipeline root cause + factory-side
  detection. Child D is the consumer-side mirror; cross-reference by id in
  item text only.
- Non-goals: no Phase E federation; no weakening of the cardinal rule; no
  duplication of xyoj's dispatcher-release/credential hypotheses here.

## Sequencing

1. Land `overseer-v7io` (already in flight) — unblocks Child C's picker leg.
2. Child A (schema) → B (daemon condition) as one red-green track; D reuses
   B's re-query helpers.
3. C and E after B, in either order; E carries the spec-routing check.
