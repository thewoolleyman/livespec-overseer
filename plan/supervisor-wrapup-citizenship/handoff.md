# supervisor-wrapup-citizenship — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path in §5.
> Do not treat chat history as a source of truth.

## 1. The primary goal — the maintainer's ruling this thread exists to ratify

The maintainer's words (2026-08-02), the bar every step is judged against:

> Supervisors will ALWAYS have a shell going if they are monitoring their
> worker, that shouldn't be a reason not to tell them to restart on low
> context.

Today the opposite is RATIFIED SPEC: `SPECIFICATION/spec.md`
§"Fail-soft posture" makes busy-suppression "unbounded for ACTION" and
forbids injecting a wrap-up on shell-busy evidence — so a supervisor
session, whose steady state is a live monitor shell, can never be told to
wind down and ride its context to the floor unwarned. The daemon currently
CONFORMS to that contract; nothing is "broken" in the implementation. This
thread changes the contract first, then the daemon.

## 2. Where this thread stands

Created 2026-08-02. The epic anchor is **`overseer-blccme`**. Read live
status from the ledger —
`list-work-items` / `bd show overseer-blccme` — never from this file; this
handoff cites ids read-only and carries no work queue.

Done so far: the reasoning note (§5, read it first) is complete and
ratification-ready. NOT done: the spec proposed change, its review, the
ratification, the daemon implementation, and the re-derivation of
`overseer-vyjkzw` acceptance criterion 3. No code may change before the
spec does.

## 3. The contract delta in one screen

Narrow unbounded wrap-up-injection ACTION suppression from "any busy
evidence" to "generating". The daemon MAY inject the escalating wrap-up
when ALL hold:

- remaining context at/below the wind-down threshold (band machinery,
  coalescing, and the durable injection-stamp sidecar unchanged);
- no fresh `winding-down` ACK stands (unchanged);
- the input prompt is verifiably idle AND settled (the existing
  two-capture settle check — never into a changing pane);
- every piece of busy evidence is background-shell evidence (Claude
  registry `status=shell` / Codex descendant-shell fallback) — the session
  is NOT generating and carries no sub-agent-busy evidence.

Generating/changing panes keep unbounded action suppression, with the
bounded attention floors (`winddown-starved`, `shell-prolonged`) as their
fallback surface. UNCHANGED: THE CARDINAL RULE (restart only on a
session-written `ready`), no auto-spawn, no force-kill, `danger` stays
report-only.

## 4. The next action (exactly one)

Author the spec proposed change realizing §3 via the `/livespec:propose-change`
operation against THIS repo's `SPECIFICATION/`, sweeping every statement of
the old letter (the sweep list is the reasoning note's §"Consequences for
existing records"). Then: independent adversarial review by a
separately-spawned Fable-model agent, then `/livespec:revise` with the
maintainer. At ratification, also re-derive `overseer-vyjkzw` acceptance
criterion 3 (its letter encodes the old contract; its intent — protect
genuine background work — survives).

AFTER ratification: file the daemon-implementation item as a CHILD of
`overseer-blccme` via the `capture-work-item` operation (`depends_on` the
epic; autonomy tier T2), and implement it through the FACTORY path — the
`drive` operation (`impl:<id>`) or the Dispatcher drain under the janitor
gate — never the in-session `implement` operation.

Every repo artifact of this thread (the proposed change, the ratified
snapshot, the eventual implementation) rides this repo's normal
worktree → PR → rebase-merge discipline, as the thread's own opening did.

## 5. Read-first chain (all committed in this repo, livespec-overseer)

1. `plan/supervisor-wrapup-citizenship/contract-narrowing.md` — the whole
   argument: ruling, evidence, current-contract citations, delta, safety
   case, drift-sweep list.
2. `SPECIFICATION/spec.md` §"Fail-soft posture" AND §"The keep-going
   nudge" — the ratified old contract being narrowed, plus the
   pair-nudge clause ("This nudge is the ONE bounded exception to busy
   classification suppressing acts … and only then") that the proposed
   change MUST re-derive so the spec never declares one exception while
   carrying two; that same clause is the ratified precedent the safety
   case cites.
3. `plan/archive/background-shell-supervision-liveness/handoff.md` — the
   settled predecessor thread (epic `overseer-4xfmez`, closed) this thread
   deliberately reopens on new evidence.
4. `overseer/_supervisor_evaluate.py`, `overseer/_supervisor_threshold.py`,
   `overseer/_supervisor_attention.py` — the conforming implementation the
   ratified change will alter.

Ledger ids to read live (never stored here): `overseer-blccme` (this
thread's epic), `overseer-vyjkzw`, `overseer-x6d`, `overseer-4xfmez`.
