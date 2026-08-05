# winddown-rationale-expiry — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path in §5.
> Do not treat chat history as a source of truth.

## 1. The primary goal

Make a wind-down intent EXPIRE when its rationale does. A wind-down is a
response to low remaining context; the runtime's auto-compaction can
restore context at any moment after the intent forms, and today no
protocol artifact tells the session what to do then — so the observed
default is the worst behavior: hold the intent and wait for a restart
that can never come. Codify the rule the failing session itself
articulated only after a human intervened: after auto-compaction (or
any recovery above the wind-down threshold), CLEAR the intent —
including any written `.overseer-state` declaration — and RESUME from
the checkpoint, waiting for nobody. The refreshed handoff is not
wasted; it is simply a better checkpoint.

**The detection anchor (load-bearing for the drafter):** auto-compaction
is precisely the event that can erase the session's own MEMORY of being
mid-wind-down, so the rule must not be phrased on recollection. The
evidence that survives compaction is on disk: the session's own
`tmp/overseer/<topic>/.overseer-state` (if it declared) and its
freshly-updated handoff/checkpoint. Anchor the drafted rule on READING
those — a post-compaction session that finds a wind-down declaration or
a just-written restart checkpoint under its own topic, while its
context is comfortably recovered, is in the expiry case. Relatedly, the
wind-down threshold is daemon-side configuration the wrap-up text does
not interpolate (it carries only the current remaining percent), so the
session-observable trigger is the compaction event plus the disk
evidence — not a number the session was never told; whether the wrap-up
text should also carry the threshold is a drafting decision.

Two companion repairs ride along: generated charters must state that a
declaration IS the state file and never pane text (the observed session
announced "Ready for restart" in pane prose and never declared), and
the daemon's `idle-with-context-left` keep-going nudge must be verified
against the stalled end-state — including the latent sibling where a
STALE `winding-down`/`ready` survives compaction and, being "declared",
suppresses the very nudge that should fire.

## 2. Where this thread stands

Created 2026-08-06. The epic anchor is **`overseer-5gl4em`**. Read live
status from the ledger — `list-work-items` / `bd show overseer-5gl4em` —
never from this file; this handoff cites ids read-only and carries no
work queue.

Done so far: the reasoning note (§5 item 1) carries the observed
timeline, the three-front decomposition, and the sweep surfaces. NOT
done: everything else — the proposed change, the charter amendment, the
nudge verification.

## 3. The next action (exactly one), then the follow-on sequence

THE next action: author the marker-protocol expiry rule as a spec
proposed change via the `/livespec:propose-change` operation against
THIS repo's `SPECIFICATION/`, sweeping every ratified statement of the
wind-down/declaration letter that the new rule touches — start from the
sweep list in the reasoning note's §"Relations" (marker-protocol prose,
`.claude-plugin/prose/overseer.md`, the wrap-up/round/keep-going-nudge
sections of `SPECIFICATION/spec.md`, `SPECIFICATION/contracts.md`,
`SPECIFICATION/scenarios.md`, and the charter/supervisor-handoff
generator surfaces). The expiry rule is contract-bearing on
its face (it changes what a compliant session MUST do), so no
spec-bearing-or-not sweep verdict is needed first — the sweep is part
of drafting.

The follow-on sequence, in order:

1. Independent adversarial review by a separately-spawned Fable-model
   agent, then `/livespec:revise` with the maintainer.
2. File the implementation/charter slices as CHILDREN of
   `overseer-5gl4em` via the `capture-work-item` operation
   (`depends_on` the epic + the ratification; autonomy tier T2): the
   charter/generator amendment (declaration mechanics + expiry leg),
   and the daemon-side nudge verification with its
   stale-declaration-suppression case. FACTORY path only — the `drive`
   operation (`impl:<id>`) or the Dispatcher drain (the
   `livespec-orchestrator-beads-fabro` dispatcher polling the ledger's
   ready set into sandboxed janitor-gated runs) — never the in-session
   `implement` operation. ("Autonomy tier T2" is the fleet's
   dispatch-after-ratification tier: autonomous implementation once the
   contract it depends on is accepted.)
3. Live-exercise evidence per fleet discipline: a real session driven
   through wind-down → auto-compaction → self-resume without human
   touch, journaled on the accepting item.

Every repo artifact of this thread rides this repo's normal
worktree → PR → rebase-merge discipline.

## 4. The regression boundary

- No new restart path: expiry means the session RESUMES; it never
  makes the daemon kill or respawn anything. THE CARDINAL RULE is
  untouched.
- The daemon's void machinery (a `ready` followed by resumed work is
  voided after the grace) stays; the expiry rule is the session-side
  complement.
- A session that is GENUINELY low (no compaction; context still under
  threshold) keeps winding down exactly as today — expiry triggers
  only on recovery above the wind-down threshold.
- The keep-going nudge stays once-per-episode and edge-triggered; any
  nudge-text change must not re-introduce per-tick spam.
- The charter amendment must not weaken the declaration contract: the
  state file remains the ONLY declaration channel; the amendment adds
  clarity, never an alternative channel.

## 5. Read-first chain (all committed in this repo, livespec-overseer)

1. `plan/winddown-rationale-expiry/expiry-mechanism.md` — the observed
   timeline, the three fronts, what does not change, the sweep list.
2. `overseer/marker-protocol.md` — the wind-down/declaration contract
   the expiry rule amends.
3. `SPECIFICATION/spec.md` §"The escalating wrap-up", §"The supervision
   round", and §"The keep-going nudge" — the ratified letter adjacent
   to the new rule (sweep alongside `SPECIFICATION/contracts.md`,
   `SPECIFICATION/scenarios.md`, `.claude-plugin/prose/overseer.md`).
4. `overseer/_supervisor_nudge.py`, `overseer/_supervisor_evaluate.py`,
   and `overseer/_supervisor_evaluate_idle.py` — the keep-going nudge
   implementation, the precedence cascade, and the idle-leg delegation
   that actually carries the `idle-with-context-left` guard (including
   the no-declaration-of-its-own condition — the suppression case the
   verification front must cover), for the verification front.

Ledger ids to read live (never stored here): `overseer-5gl4em` (this
thread's epic), `overseer-er6ikw` (closed authorization-side sibling),
`overseer-xkrwm3` (delivery-side sibling), `overseer-daj` (charter
under-specification family).
