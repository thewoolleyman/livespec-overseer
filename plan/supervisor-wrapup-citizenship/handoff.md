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

Created 2026-08-02. **Ledger anchor:** epic **`overseer-blccme`**. Read live
status from the ledger —
`list-work-items` / `bd show overseer-blccme` — never from this file; this
handoff cites ids read-only and carries no work queue.

That anchor is spelled `Ledger anchor:` deliberately. The gate in
`tests/test_plan_thread_records_agree.py` extracts a handoff's declaration
with a pattern keyed on those words, and an unreadable declaration is scored
as an OFFENCE rather than a skip once the thread has a charter — so the
earlier "The epic anchor is" wording would have turned master RED the moment
`supervise-plan` ran here, with a message naming the charter while the file
needing the change was this one. Filed as `overseer-jtc`; do not re-word it.

**Re-measured 2026-08-03T00:09Z, and §4 below was rewritten with it.** The
spec phase is DONE: the narrowing ratified as **v005**, merged by PR #522 at
commit `cc90899`, with `SPECIFICATION/history/v005/` holding the revision and
the accepted proposal. The reasoning note (§5, read it first) remains the
argument of record and is unchanged by ratification. STILL OPEN: the daemon
implementation and, inside it, the re-derivation of `overseer-vyjkzw`
acceptance criterion 3.

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

**Finish `overseer-sfpurg` — the fail-closed evidence-change interlocks — and
verify the result against `origin/master`, not against a PR.** The spec phase,
the filing phase and the bulk of the implementation are discharged.

Measured 2026-08-03T01:00Z:

- `overseer-6mbp2q` (implement v005) produced PR **#536**, which **MERGED** at
  00:39:03Z as `96eb0a2`, and release **0.17.0** (`4b3a300`) shipped it. Its
  documented acceptance is met on master: 12 integration legs in
  `tests/integration/test_shell_wrapup_v005.py`, zero remaining TODO rows in
  `tests/heading-coverage.json`, canonical and mirrored plugin copies both
  updated. `overseer-vyjkzw` acceptance criterion 3 was re-derived at 00:28:23Z
  and now reads from the v005 contract, so that obligation is discharged.
- `overseer-sfpurg` (supersede #536 with complete interlocks) is the OPEN item
  and is in the factory. It exists because PR #536 carried a
  `CHANGES_REQUESTED` review whose BLOCKER is real and is **still true on
  master**: `_fresh_threshold_observation` cancels on a changed `capture` and a
  changed `is_codex`, then re-derives `shell_only`/`blocked`/`ready` from the
  FRESH observation alone — it never compares `claude_status`,
  `codex_fallback` or `declared` against `request.obs`. Independently-safe is
  not unchanged. Separately, its vocabulary guard is skipped when the status is
  `None`, so an ABSENT Claude registry status is not distinguished from an
  affirmative idle one.

Two traps around that item, both recorded as comments on it rather than edited
into it:

1. **Its premise is stale.** It says PR #536 "will be closed unmerged" and that
   the replacement branch must carry the entire implementation. #536 was
   already merged six minutes before the item was filed. Treat it as a FORWARD
   FIX ON TOP OF MASTER; a clean rebase is not evidence that work went missing.
2. **The merge itself was a gate failure**, filed as `overseer-zfq`: the
   blocking review landed at 00:38:24Z and the merge happened 39 seconds later,
   then went out in a release. THE CARDINAL RULE is untouched by any of this —
   restart still requires a fresh session-written `ready` — so this is a defect
   to finish, not an incident to roll back.

Re-measure a factory run with `mise exec -- fabro ps`, never from the ledger's
`active` field — `ACTIVE` is a claim, a running process is evidence, and both
`overseer-6mbp2q` and `overseer-sfpurg` still read `active` here while one of
them is long since merged. Everything that made these T2 factory items still
binds: implement through the `drive` operation (`impl:<id>`) or the Dispatcher
drain under the janitor gate, never the in-session `implement` operation.

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
