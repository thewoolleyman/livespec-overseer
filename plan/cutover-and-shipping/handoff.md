# Plan — cutover-and-shipping

**Owning repo:** `livespec-overseer`. **Status:** WRAPPING UP — being archived,
but **NOT YET**, and **NOT BY YOU UNTIL A GATE CLEARS**. Read §BLOCKED first.

**Ledger anchor:** epic `overseer-3wt` (still OPEN, not closed). Its COMMENTS
carry this thread's full evidence journal. The core-tenant epic `livespec-b1uo`
stays in core per its do-not-move ruling.

---

## 🛑 BLOCKED — read this before doing anything

**There is a maintainer decision outstanding. Do not route around it.**

The maintainer (supervisor brief 22) ordered the remaining overseer work SPLIT
into a new plan thread FIRST, then this thread archived. Phase 1 is done and
pushed. **Phase 2 — a required DUAL adversarial review — FAILED on both legs:**

- **Fable reviewer: FAILED.** Verbatim error:
  `You've reached your Fable 5 limit. Run /usage-credits to continue or switch models with /model.`
- **Codex GPT-5.6/"sol" reviewer: INTERRUPTED** before returning any verdict.

Neither produced findings, so **the review gate is UNSATISFIED**.

I asked the maintainer how to proceed (add Fable credits and retry / substitute a
different fresh-context model / proceed on one reviewer). **The maintainer
interrupted that question without answering.** The decision is still open.

**DO NOT:**

- Do NOT merge PR #78 — the gate the maintainer specified has not been met.
- Do NOT archive this thread — brief 22 puts the archive strictly AFTER #78 merges.
- Do NOT close epic `overseer-3wt`.
- Do NOT run `/usage-credits`, `/model`, or any spend/account action. Billing is
  the maintainer's alone (this thread's `supervisor-handoff.md` §Corrections).
- Do NOT silently substitute a different reviewer model. Brief 22 named
  `model=fable` explicitly; swapping it quietly downgrades a gate the maintainer
  chose — exactly the class of erosion this whole body of work exists to prevent.

**DO:** put the open question to the maintainer in ONE turn, recommended option
first, then wait. Suggested framing:

> The Fable reviewer hit its usage limit and the Codex reviewer was interrupted,
> so PR #78's required dual adversarial review is unsatisfied. How do you want the
> second review obtained? (a) substitute a fresh-context Opus/Sonnet reviewer with
> the identical adversarial brief, recorded as a substitution; (b) you add Fable
> credits and I re-spawn the identical Fable reviewer; (c) proceed on Codex sol
> alone — not recommended, since brief 22 required two precisely because a single
> pass previously missed a false "shipped" claim.

The adversarial brief to reuse is in PR #78's description plus §"What it did NOT
do" below: hunt missing definition-of-done goals, false "done"/"works" claims,
contradictions with measured state, dangling references, and cold-open
executability of both new handoffs.

---

## Where everything actually is

### Phase 1 — DONE and pushed, NOT merged

New living successor thread: **`plan/ship-overseer-to-fleet/`**, anchored by new
epic **`overseer-hbr`** (P2, open). It holds ALL remaining overseer work.

- **PR #78** — branch `docs/thread-ship-overseer-to-fleet`, commit `1f25b7e`.
  **OPEN, MERGEABLE, deliberately unmerged.** `just check` green (60 targets).
- Contains the new thread's `handoff.md` (six-goal definition of done, each
  grounded in measured state), a **hand-written** `supervisor-handoff.md`, and
  `research/phase-2-adopter-shipping.md` moved in by `git mv` as a LIVING ref.
- `overseer-19s` (the earlier Phase-2-only epic) is CLOSED as **superseded** by
  `overseer-hbr`, so there is exactly one anchor. Caveat: the plugin's
  `superseded_by` field is plugin-owned and rejected a metadata write, so it still
  reads `resolution: completed`; the close reason and its comment both state
  plainly that it was superseded, not delivered.

The worktrees `.claude/worktrees/new-thread` and `.claude/worktrees/wrapup` may
still be on disk. Both branches are pushed, so removing them loses nothing.

### PR #78 CONFLICTS WITH THIS FILE

PR #78 also edits `plan/cutover-and-shipping/handoff.md` (it repointed the stale
Phase-2 references). This wrap-up rewrite lands on master first, so **#78 will
need a rebase**. Resolution: **keep THIS file's content** — it is strictly newer
and already accounts for the split. Take #78's `plan/ship-overseer-to-fleet/**`
and its `git mv` unchanged; discard its older version of this file.

### Phase 3 — NOT STARTED (blocked behind #78)

Honestly wrap up and archive this thread:

1. Rewrite this handoff to reflect ONLY what this thread genuinely completed (see
   below), stating explicitly that the plugin is **BUILT-BUT-NOT-FLEET-RELEASED /
   NOT-INSTALLED / NOT-E2E-TESTED**, with those plus Phase 2 handed to
   `plan/ship-overseer-to-fleet/`. **Do NOT claim `supervise-plan` "works."**
   Scope Phase-2/productization OUT of this thread.
2. Close epic `overseer-3wt`.
3. `git mv plan/cutover-and-shipping/ plan/archive/cutover-and-shipping/` via
   worktree → PR → rebase-merge.
4. Verify on origin/master: archive path present, active path gone, epic closed.

### Phase 4 — NOT STARTED

Wind down and print the safe-to-exit message. **Never kill the acting overseer
daemon** (pid was 2954933, tmux `livespec-overseer:1.1`) — it is the shipped
product supervising the whole live fleet, not part of any session.

---

## What THIS thread genuinely completed (for the Phase-3 honest rewrite)

- **Daemon cutover PROVEN** — Stage-4 twice (declare-ready → atomic restart; and
  daemon-injected wrap-up → ready → restart, on two separate tracks).
- **`SPECIFICATION/history/v002` ratified** (PR #73) — the attended-skill
  carve-out plus the bounded existence-only probe allowance. doctor-static 21/21.
- **Supervision surfaces A+B shipped** (`overseer-6uobos`, PR #74 + review fix
  PR #75) and live-exercised: `02-parameter-store-bootstrap` hit the fourth
  truth-table cell (live supervisor session, no `supervisor-handoff.md`) and
  correctly surfaced the capture offer. PR #75 fixed a sabotage test that could
  not fail — proven toothless by mutation, then red-then-green.
- **Acting daemon restarted onto latest master** — single instance, 12/12
  watch-set, header now `0.11.0`. `overseer-2boaoy`'s append live-exercised
  mechanically: fd2 flags `0100001` → `0102001` (O_APPEND set), prior 80 log lines
  byte-identical underneath.
- **Accepted items:** `overseer-m5dtmj`, `overseer-tn3hmi`, `overseer-myjovi`
  (`supervise-plan` **BUILT — not fleet-available**), `overseer-vlu5cd`,
  `overseer-kfbcv4`, `overseer-2boaoy`, `overseer-5aaeyd`, `overseer-6uobos`,
  `overseer-3o9`, `overseer-y8o`, `overseer-4dr`, `overseer-zvo`,
  `overseer-tvko3z`.
- **Slice 4 needed NO filing** — verified both upstream targets already carry the
  ratified "hosted supervision artifact" declaration (livespec core **v175**,
  livespec-orchestrator-beads-fabro **v048**). Filing the prepped packets would
  have duplicated ratified content.

### What it did NOT do — why the successor thread exists

The plugin is **BUILT but FUNCTIONALLY UNSHIPPED**: installed in **zero**
projects, **no** marketplace cache entry (every other fleet plugin has one), and
`supervise-plan` is **absent** in another live fleet session. There are **21**
scenarios in `SPECIFICATION/scenarios.md` and **zero** top-of-pyramid tests; all
21 `tests/heading-coverage.json` entries are `TODO`, and the rule is **UNARMED**
(`LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST` is set nowhere but a `justfile`
comment, so the TODOs warn and can never fail CI). Release automation is partial:
release-please versions the package, but the plugin half is unwired.

Those gaps are the successor thread's six-goal definition of done: fleet-wide
`supervise-plan` availability; top-of-pyramid e2e tests for every scenario WITH
the rule enforced; auto-release; auto-install; auto-pin-bump; and Phase-2
adopter-family shipping absorbed into those.

---

## Also open, tracked in the ledger

- **`overseer-fitvmo`** (P2 bug, pending-approval) — `supervise-plan` prompts must
  not stall on conflict boundaries. Standalone; relevant to the successor's goal 1.
- **7 untied spec→impl gaps** from the v002 delta (`detect-impl-gaps
  --since-version v001`); `capture-impl-gaps` deliberately not run to filing, since
  it would file 7 auto-derived items across the groomed queue without consent.
- **`check-no-workflow-edits` copy-drift** across the 4 carrying fleet repos.

## Operational map

Daemon: tmux `livespec-overseer:1.1`, stderr log `tmp/overseer/daemon.log`
(appends). Protocol: `overseer/marker-protocol.md`. Invariants:
`overseer/AGENTS.md`. Operator contract: `overseer/SKILL.md`. This thread's
supervisor charter: `supervisor-handoff.md` beside this file. Cross-track
coordination log (shared, still active — append only, never rewrite): livespec
core `tmp/fleet-pin-propagation-supervisor/status.log`. Research beside this file:
`research/operator-surface.md` and
`research/slice4-upstream-one-liners-and-unit3-home.md` (its Packet A/B sections
are SUPERSEDED — slice 4 needs no filing).
