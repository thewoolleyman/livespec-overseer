# Control-plane supervision liveness — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path named in
> §6. Do not treat chat history as a source of truth.

## 1. The primary goal — read this first, it reframes everything else

The maintainer's words, and the bar every proposed behavior is judged
against:

> The overseer and the supervisor exist to surface ONLY what genuinely needs
> human attention, to keep everything else running autonomously, and to NEVER
> stall without a legitimate blocking human decision — and when there is one,
> it is presented as an `AskUserQuestion`, not as prose.

Two failure modes are SYMMETRIC, and a design that commits either is wrong:
**stalling silently**, and **surfacing noise** a human cannot act on. Judge
every candidate against both directions. How the AskUserQuestion clause
reconciles with the daemon's notify-never-block invariant is settled in the
research note's cross-cutting section: the daemon owns no decisions and
never prompts; attended seats do.

## 2. What this thread is — scope, and the binding ruling

Control-plane supervision liveness, four lanes: **A** duration as a
first-class primitive; **B** `blocked:` liveness; **C** the supervisor as a
tracked entity; **D** track-level progress. `shell-prolonged` (§5) is a
ratified INSTANCE, not the deliverable.

**Maintainer ruling, 2026-07-28, BINDING:** supervisor sessions are FULL
CITIZENS — wrap-up at worker thresholds/bands, ready-gated restart
preserving the `-supervisor` session name, resume pointer
`plan/<topic>/supervisor-handoff.md`; and a both-stalled pair triggers a
guarded supervisor NUDGE (a presented human question suppresses the nudge
and is surfaced instead). The earlier monitor-and-surface-only stance is
OVERRULED and survives only as a rejected alternative. The ruling's one
posture exception — the nudge may paste into a shell-classified supervisor
under strict guards — must be stated in governed prose at the widening
step, never hidden in implementation.

## 3. Where the work stands NOW

| Artifact | State |
|---|---|
| `research/control-plane-liveness.md` | **The design source of truth. On branch `control-plane-liveness-plan` — PR #219, DRAFT, deliberately HELD unmerged.** Investigation complete; ALL relayed §9 gate reviews verified and folded (wave 1: Fable autonomy/safety, Codex autonomy, two independently-convergent code-truth claim tables; wave 2: Fable and Codex act-path safety over lanes C/D). Its status header lists what each wave changed |
| `tmp/overseer/background-shell-supervision-liveness/reviews/` | The raw review relays + `wave1-verification.md`, the per-finding verification log (scratch, UNTRACKED — its durable conclusions live in the note) |
| `tmp/overseer/background-shell-supervision-liveness/drafts/` | UNFILED prep, staged while awaiting the gate judgment: `widened-proposal-draft.md` (the full step-7.2 text, decision-sensitive spots marked against the note's open-decisions numbering) and `sibling-work-items-draft.md` (the step-7.3 `bd` filings, dependency-ordered). Verify against the maintainer's batched decisions before filing either — they are prep, not decisions |
| `research/root-cause.md`, `research/policy-options.md` | Merged, current (policy-options covers the narrow predicate only) |
| `SPECIFICATION/proposed_changes/background-shell-liveness-attention.md` | FILED narrow (`316d69d`), NOT ratified, NOT yet widened. Wording fixes owed at widening, recorded in the note's governed-clauses section: the falsifiable "never reported" MUST; the status-vs-COMMAND-vocabulary misquote; the "Two edits"/three-labels miscount |
| This handoff | Landed on master via the wrap-up flow; an identical copy rides PR #219's branch (the rebase-merge will reconcile them cleanly) |

**Gate state:** the §9 adversarial gate was run by the SUPERVISOR seat
(never this seat). All relayed reviews are verified and folded; the worker
report is on PR #219's comment trail. As of this writing the supervisor
seat was about to judge the gate discharged and take the BATCHED maintainer
decisions (the note's "Open maintainer decisions", nine items) to the
maintainer. One item was flagged for ledger-filing CONSENT beyond the plan
docs: the inherited restart defect (§5 below).

**Restart context:** the previous worker session was wound down by the
overseer at the 50% line while those decisions were pending. FIRST ACTION
on cold open: check for anything that arrived after this handoff was
written — PR #219's comment trail, new files under
`tmp/overseer/background-shell-supervision-liveness/reviews/`, and the
ledger anchors (§9) — before doing anything else. If a supervisor relay is
waiting, it defines your next step; if nothing new exists, you are in §7
step 1 (awaiting the judgment) and the drafts row above is your prepared
runway.

## 4. Standing HOLDS from the supervisor seat — do not jump them

1. **PR #219 stays HELD** until the supervisor seat discharges the gate.
2. **Do NOT widen the filed proposal** until told.
3. **Do NOT file ledger work-items or touch the epic's scope** until told.
4. **Do NOT run `/livespec:revise`** — one ratification cycle for the whole
   widened contract, after the gate and the maintainer's batched decisions.
5. **Do NOT launch your own §9 reviewers** — the gate runs from the
   supervisor seat.

The supervisor establishes your state from artifacts (forge, ledger), not
pane prose. The held PR and its comment trail ARE the report.

## 5. Decisions and findings that BIND the next steps

- **Ratified narrow predicate (do not relitigate):** 2-hour episode floor;
  `shell-prolonged` (yellow, `ATTENTION_STATUSES`, alert key
  `prolonged-background-shell`); keep the `eff_ctx is not None` conjunct
  EXPLICIT in every restatement.
- **The §2 ruling** (full citizenship + nudge), as elaborated by the note:
  entity substitution table with the offer leaf excluded; supervisor
  wrap-up VARIANT (the worker template's commit ritual corrupts pair state
  under either parameterization — wave-2 blocker); topic-derived pair
  naming; derivation-level `-supervisor` reservation; canonical-path rule
  against state-file symlink aliasing; content-immune progress under the
  directional-evidence principle; Claude-only nudge v1 with
  consecutive-episode escalation; in-memory nudge bookkeeping (no
  state-file grammar change); per-track ctx-staleness surface; continuity
  gap as a formula (900 s interim).
- **An inherited SHIPPED defect, verified against code** and flagged to the
  supervisor seat for ledger-filing consent: `_supervisor_restart.py:135-154`
  — a successful respawn whose recognition poll times out retains
  declaration+stamp, so one `ready` can authorize a SECOND kill against a
  successor that never declared. Worker-path today; would extend to
  supervisors. Fix shape in the note (convert to `resume_pending`,
  consuming the kill authorization). Track its ledger state — do not
  re-flag if already filed.
- **Recorded rejections stand** unless the maintainer reopens them: B3
  dead-predecessor voiding (withdrawn — `--resume` false-void +  `/clear`
  blindness); idle-tick blocked voiding; per-session frozen-ctx detection;
  handoff-mtime freshness ordering (violates non-interference's
  mtime-independence); the pair-nudge marker token (one-file contention).

## 6. Read-first chain

1. This file.
2. The research note (PR #219 branch) — including its status header, §1
   tables, clearing table, governed-clauses list, owed tests, and the
   nine open maintainer decisions.
3. `reviews/wave1-verification.md` beside the raw relays — the per-finding
   verdicts, including the findings REFUTED with evidence (keep that
   discipline: reviews are input-to-verify; your verification wins and the
   contradiction is recorded).
4. `research/policy-options.md`, `research/root-cause.md`.
5. The filed proposal, then `SPECIFICATION/spec.md` + `contracts.md`
   (especially "Fail-soft posture", "Notify, never block", "The restart
   interlock" — its item 3 is the mtime>stamp ordering lane A's
   read-only-age argument protects — and the three sections lane C
   contradicts as written: restart-interlock naming, wrap-up injection,
   session-name derivation), `overseer/marker-protocol.md`,
   `overseer/AGENTS.md`.
6. Code, cascade order: `_supervisor_observe.py`, `_supervisor_evaluate.py`
   (resume-retry leg FIRST at :165-167, busy :198, gate/blocked :241,
   ready :283, threshold :296, offer else-leaf :326, re-arm :385-391),
   `_supervisor_state.py`, `_supervisor_view.py`, `_supervisor_config.py`
   (`MARKER_VOID_GRACE` residual :109-111), `_supervisor_records.py`,
   `_supervisor_offer.py`, `_supervisor_launch.py` (`session_of` returns
   `track.tmux` first, :52 — the pair-naming trap), `_supervisor_restart.py`
   (:135-154, the inherited defect), `_supervisor_prompts.py`
   (`_WRAPUP_BODY`'s hardcoded commit ritual); `signals.py` (`ready_valid`
   mtime>stamp :423; whole-capture `is_busy` :152-155; `state_path` plain
   join :339-341); `_supervisor_core.py` (`alert` line-text dedup
   :281-284); `claude_sessions.py` (`procStart` ticks-since-boot :116,
   byte-compared :232); `_supervisor_lifecycle.py` (`run_loop` propagates
   tick exceptions while assuming a nonexistent process supervisor).

## 7. Next actions — exactly one path, gated left to right

1. **Await/receive the supervisor seat's gate-discharge judgment and the
   maintainer's batched decisions** on the note's nine open items (+ the
   ledger consent for the inherited defect). Fold any decision that
   changes the design into the note first.
2. **Widen the filed proposal** — the note's "Governed clauses this
   changes" section IS the widening spec (bounded attention + instances;
   band escalation amending the edge-trigger sentence; full-citizen
   supervisor entities; the pair nudge + posture exception + residuals;
   the canonical-path rule; the derivation-level reservation; the three
   contradicted sections; the three wording fixes). Amend EXISTING `## `
   sections only — heading-coverage mechanically pins every spec.md
   heading to a real test, so no new heading before the implementing
   slice's tests.
3. **File the widened lanes as SIBLING work-items under `overseer-4xfmez`**
   (+ the inherited-defect item if consented) and widen the epic's
   description. `overseer-vyjkzw` stays the narrow instance. Reach `bd`
   via `with-livespec-env.sh bd …`; task→epic `blocks` edges are refused
   by beads — do not manufacture one.
4. **Run `/livespec:revise`** — one cycle, with the maintainer.
5. **Dispatch implementation via the factory route** (`drive` action
   `impl:overseer-vyjkzw` + the new siblings) — never implement inline
   from a planning session.

## 8. Outcome constraints — the original §12, amended by the ruling

Worker-side: UNCHANGED and absolute — no shell age, prompt shape, timer,
declaration age, or context percentage may EVER authorize a paste, Enter,
respawn, kill, or declaration write against a WORKER; a fresh
session-written `ready` remains the sole restart authorization; genuine
background work and genuine human waits stay protected; every alert is
coordinate-rich and edge-triggered under the note's alert-identity rule;
every condition clears and re-arms per-condition; daemon-restart behavior
is explicit and delay-only; Claude and Codex are each addressed
explicitly, parity or divergence justified by evidence; docs, coloring,
attention membership, and tests all agree; any new scenario lands
atomically with its integration test and heading-coverage row.

Supervisor-side, PER THE RULING: wrap-up/restart run the IDENTICAL
interlock under the `(repo, <topic>-supervisor)` key — only the
supervisor's own fresh `ready` restarts a supervisor, and the crossed-file
and symlink-alias sabotage tests are owed; the pair nudge is the ONE
bounded exception to shell-classified busy suppressing acts, under the
full guard set (verified empty settled prompt; never generating; never
over a gate / `waiting` / `blocked:`; never with an open round or fresh
ACK; once per episode with counted escalation; Claude supervisors only);
supervisor sabotage tests INVERT — prove every act fires ONLY under its
guards, and prove the non-acts as thoroughly as the acts.

## 9. Ledger anchors — ids only, never copied status

Planning epic **`overseer-4xfmez`** (scope-widening owed at step 7.3);
narrow bug **`overseer-vyjkzw`** (stays narrow); adjacent non-blocking
**`overseer-5jttov`** (`supervisor-scratch-discipline` — shares the
generated charter file lane C's teach-the-protocol obligation touches;
sequence edits, do not gate). The inherited restart defect may gain its
own id — check the ledger before filing anything.

## 10. Repository discipline

Worktree → PR → rebase-merge for every tracked change; create worktrees
ONLY with `just worktree-create <branch> [base_ref]`; `mise exec -- git …`
so hooks fire; never `--no-verify`; halt and report on hook failure; never
commit on the primary checkout; check `git status`, not `git log`, after a
hook-gated commit; verify against the forge after a fetch; never touch
another session's worktrees or branches; never kill the acting overseer
daemon (tmux `livespec-overseer:1.1`). Gate: `uv run pytest overseer -q`,
then `just check`; no existing check may be weakened, removed, skipped, or
exempted. This thread's branch is `control-plane-liveness-plan`
(worktree `~/.worktrees/livespec-overseer/control-plane-liveness-plan`).

## 11. Handoff refresh rule

Keep this file self-sufficient and cold-open sufficient. Durable design
reasoning lives in `research/`; per-finding review verdicts live in the
scratch verification log AND, where durable, in the note; status lives on
the PR and in the ledger; keep exactly ONE next execution path. Refresh §3
and §7 whenever the held PR's state changes, and before declaring `ready`.
