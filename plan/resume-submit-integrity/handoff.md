# resume-submit-integrity — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path in §5.
> Do not treat chat history as a source of truth.

## 1. The primary goal

Make the restart leg's resume delivery trustworthy end-to-end. Today a
daemon restart (or one-shot `start`) can log a clean success while the
pasted resume line sits UNSUBMITTED in the fresh session's composer: the
submit confirm fires on the never-typed empty box during TUI startup
(the paste is queued unrendered; the startup TUI drops the Enter but
keeps the paste), the `ready` marker and stamps are cleared, the
`resume_pending` retry never arms (it gates on the confirm returning
False), and the lane sits dead with zero surfacing. Worst observed:
**32 hours** of silent outage on a supervisor lane. The defect record is
**`overseer-mgg`**; its comments carry all three confirmed instances.

Three work fronts: (1) a two-phase submit confirm (box-empty proves
submission only after the paste was SEEN rendered, or on a
busy-transition), (2) an any-tick stranded-resume self-heal (composer
holds exactly the expected resume text → re-send Enter; NEVER a
respawn), (3) a restarted-but-never-worked attention condition
(report-only, edge-triggered, `NEEDS YOU` + badge). THE CARDINAL RULE is
untouched throughout: only a fresh session-written `ready` ever
authorizes a respawn.

## 2. Where this thread stands

Created 2026-08-05. The epic anchor is **`overseer-xkrwm3`**. Read live
status from the ledger — `list-work-items` / `bd show overseer-xkrwm3` —
never from this file; this handoff cites ids read-only and carries no
work queue.

Done so far: the reasoning note (§5 item 1) fixes the scope, the
constraints, and the spec-bearing analysis. NOT done: the spec sweep and
its routing, any proposed change, and all three fronts' implementation.

## 3. The next action (exactly one), then the follow-on sequence

THE next action: run the spec-bearing sweep and record its verdict.
Read `SPECIFICATION/spec.md` §"The restart" and §"The supervision
round", the dropped-resume scenario in `SPECIFICATION/scenarios.md`
("A dropped resume submission is retried without a second kill"), any
parallel clauses in `SPECIFICATION/contracts.md`, and the shipped prose
(`.claude-plugin/prose/overseer.md`, `overseer/marker-protocol.md`);
write the per-front verdict (ratified-letter vs implementation-only) as
a research note in this thread, beside the existing note.

The follow-on sequence, in order, after that verdict exists:

1. Author the proposed change via the `/livespec:propose-change`
   operation — for front 3 REGARDLESS (a new attention condition is
   contract-bearing: the `NEEDS YOU` membership set is ratified
   surface), and for whatever of fronts 1-2 the sweep showed touches
   ratified letter. Then independent adversarial review by a
   separately-spawned Fable-model agent, then `/livespec:revise` with
   the maintainer.
2. File the implementation slices as CHILDREN of `overseer-xkrwm3` via
   the `capture-work-item` operation (`depends_on` the epic, plus the
   ratification where contract-bearing; autonomy tier T2), implemented
   through the FACTORY path — the `drive` operation (`impl:<id>`) or
   the Dispatcher drain — never the in-session `implement` operation.
3. Fold `overseer-mgg` under the epic as its slices are cut rather
   than leaving it a floating P1.

Every repo artifact of this thread rides this repo's normal
worktree → PR → rebase-merge discipline.

## 4. The regression boundary

- The genuine submit sequence (paste rendered → Enter → box clears /
  session goes busy) must still confirm on the first pass.
- The self-heal re-sends Enter ONLY, only when the composer holds
  EXACTLY the track's expected resume text, and never escalates to a
  kill or respawn; a composer holding ANY other text is a human's
  draft and must never be submitted by the daemon.
- The Codex `expect_codex` confirm keeps its existing guard (payloads
  free of busy-marker substrings) and gets the startup-race analysis
  (covered or explicitly ruled out).
- The attention condition is report-only, edge-triggered, clears when
  the session works or the composer changes, and never fires on a
  session that simply has not been kicked yet by design (an
  `unassigned` plan is not a stranding).
- A failed paste stays a hard False (never counted as sent).

## 5. Read-first chain (all committed in this repo, livespec-overseer)

1. `plan/resume-submit-integrity/confirm-race-and-remedies.md` — scope,
   evidence, constraints, spec-bearing analysis, code anchors.
2. `overseer/_supervisor_launch.py` (`submit_prompt` — the confirm
   under change) and `overseer/signals.py` (`input_box_ready` /
   `_input_box_present` — the empty-box predicate it trusts).
3. `overseer/_supervisor_restart.py` (the restart caller; it arms the
   `resume_pending` retry on a False confirm — and on
   recognition-timeout and structured-gate — but NEVER on a
   falsely-True confirm, which is the gap) and
   `overseer/_supervisor_recovery.py` (`do_launch` — the `start` /
   recovery path a live reproduction exercised).
4. `SPECIFICATION/spec.md` §"The restart" and §"The supervision round",
   plus the dropped-resume scenario in `SPECIFICATION/scenarios.md` —
   the ratified letter the sweep must clear (alongside
   `SPECIFICATION/contracts.md`, `.claude-plugin/prose/overseer.md`,
   `overseer/marker-protocol.md`).

Ledger ids to read live (never stored here): `overseer-xkrwm3` (this
thread's epic), `overseer-mgg` (the defect record and its three
instance comments), `overseer-er6ikw` (the sibling
authorization-side thread), `overseer-daj` (the Codex-adoptability
restart defect, out of scope here).
