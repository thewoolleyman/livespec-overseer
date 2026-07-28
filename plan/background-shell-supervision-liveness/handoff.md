# Control-plane supervision liveness — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path named in
> §5. Do not treat chat history as a source of truth.

## 1. The primary goal — read this first, it reframes everything else

The maintainer's words, and the bar every proposed behavior is judged
against:

> The overseer and the supervisor exist to surface ONLY what genuinely needs
> human attention, to keep everything else running autonomously, and to NEVER
> stall without a legitimate blocking human decision — and when there is one,
> it is presented as an `AskUserQuestion`, not as prose.

Two failure modes are SYMMETRIC, and a design that commits either is wrong:
**stalling silently**, and **surfacing noise** a human cannot act on. Judge
every candidate against both directions. How that reconciles with the
daemon's notify-never-block invariant is settled in the research note's
cross-cutting section: the daemon owns no decisions and never prompts;
attended seats do.

## 2. Where this thread stands — READ BEFORE DOING ANYTHING

**The gate is discharged, the maintainer has ruled, and steps a–c are
LANDED.** The thread is parked at exactly one place: ratification.

| Step | State |
|---|---|
| §9 adversarial gate | **DISCHARGED** — 8 reviews, two waves, both model families, all verified and folded, zero refutations in the final round |
| Maintainer's batched decisions | **ALL RULED 2026-07-28** — see §3 |
| a. Research note landed | **DONE** — PR #219 merged. `research/control-plane-liveness.md` is the design source of truth, on master |
| b. Widened proposal landed | **DONE** — PR #226 merged. `SPECIFICATION/proposed_changes/background-shell-liveness-attention.md` carries nine edits (six spec.md, three contracts.md), UNRATIFIED |
| c. Ledger filed | **DONE** — six children under `overseer-4xfmez` (`.1`–`.6`), epic retitled and its scope description widened |
| d. `/livespec:revise` | **NOT RUN, AND NOT YOURS TO RUN** — ratification is the maintainer's valve; the revise session gets scheduled with the maintainer from the supervisor seat |
| e. Implementation | **BLOCKED on ratification.** No product code may land before `/livespec:revise` completes |

**So: if you are cold-opening into this thread with nothing new in hand, you
are waiting on the maintainer's ratification session. Do not run
`/livespec:revise` yourself, and do not start implementing.** Check the
ledger and the forge first (§6) in case ratification already happened.

## 3. The rulings — binding, do not relitigate

Maintainer, 2026-07-28, via `AskUserQuestion`:

1. **Widening approved** — one ratification cycle for the whole reviewed
   contract.
2. **The inherited restart defect is consented for ledger filing** — filed as
   `overseer-4xfmez.1`.
3. **All nine recommended defaults accepted verbatim**: starvation floor
   **7200 s** (the one shared 2 h value); token **`winddown-starved`**;
   blocked bands **{4 h, 24 h, then daily}**; supervisor entity on the
   **daemon-wide 50** with **no** per-track override propagation;
   above-threshold arm **8 h** reusing **`shell-prolonged`**; continuity gap
   by the **formula** (`gap ≥ 2 × worst-case tick under full pair load`) with
   **900 s interim**; nudge escalation **N = 2** then the operator line,
   **Claude-only v1**; daemon self-liveness recorded as a **future separate
   thread**; dead-supervisor visibility per the side picked in the note.
4. **The attended-takeover identity-hold guard SHIPS** as a designed guard,
   not an accepted residual.

Earlier and still binding: the narrow predicate's **2-hour episode floor**
and **`shell-prolonged`** token; supervisor sessions are **FULL CITIZENS**
(the monitor-and-surface-only stance is overruled and survives only as a
rejected alternative).

## 4. What is TRUE about the code, and must stay true

Worker-side action is exactly as suppressed as it is today. Every new
worker-side obligation in this contract is **report-only**: no shell age,
prompt shape, timer, declaration age, or context percentage may EVER
authorize a paste, Enter, respawn, kill, or declaration write against a
worker. A fresh session-written `ready` remains the SOLE restart
authorization, restated **per supervised entity** — a worker's `ready` can
never restart its supervisor, or the reverse.

The acts this contract DOES add are the maintainer-ruled supervisor paths,
each reusing an already-ratified act shape under its full guard set: the
supervisor wrap-up and restart are the worker's own machinery under a
different key, and the pair nudge is the keep-going nudge's act discipline
under strictly narrower conditions — with its one posture exception (a paste
may land while the supervisor's only busy evidence is a background command)
stated in governed prose rather than hidden in implementation.

## 5. Read-first chain

1. This file.
2. `research/control-plane-liveness.md` (on master) — the design source of
   truth: four lanes, every rejected alternative with its failure mode, the
   clearing/re-arm/daemon-restart table, the owed-tests list, and the
   rulings table.
3. `SPECIFICATION/proposed_changes/background-shell-liveness-attention.md`
   (on master) — the widened, UNRATIFIED proposal. Its nine edits are what
   `/livespec:revise` will accept or reject.
4. `tmp/overseer/background-shell-supervision-liveness/reviews/` — the raw
   review relays, `wave1-verification.md`, and `wave3-worker-verification.md`
   (scratch, UNTRACKED; durable conclusions are already folded into the note).
5. `research/root-cause.md`, `research/policy-options.md` — the narrow
   predicate only.
6. `SPECIFICATION/spec.md` + `contracts.md`, `overseer/marker-protocol.md`,
   `overseer/AGENTS.md`.
7. Code, cascade order: `_supervisor_observe.py`, `_supervisor_evaluate.py`
   (resume-retry leg FIRST at `:165-167`, busy `:198`, `void_stale_blocked`
   `:206`, gate/blocked `:241`, ready `:283`, threshold `:296`, offer
   else-leaf `:326`, re-arm `:385-391`), `_supervisor_state.py`
   (`void_if_stale`'s only two call sites are `evaluate:237` and `:244`),
   `_supervisor_restart.py` (`:135-154`, the filed defect),
   `_supervisor_launch.py` (`session_of` returns `track.tmux` first, `:52` —
   the pair-naming trap), `_supervisor_prompts.py` (`_WRAPUP_BODY`'s
   hardcoded copy DESTINATION), `signals.py` (`ready_valid`'s `mtime > stamp`
   `:423`; whole-capture `is_busy` `:152-155`; `state_path` plain join
   `:339-341`), `_supervisor_core.py` (`alert` dedups on full line text),
   `_supervisor_view.py`, `_supervisor_config.py`, `_supervisor_records.py`,
   `_supervisor_offer.py`.

All `file:line` citations above were re-verified against source on
2026-07-28.

## 6. Ledger anchors — ids only, never copied status

- Epic **`overseer-4xfmez`** — retitled and scope-widened to control-plane
  supervision liveness. Children:
  - **`.1`** the inherited restart defect (P1 bug; independent of the
    widening — it is a shipped worker-path defect today)
  - **`.2`** lane A foundations — **blocks `.3`–`.6`**
  - **`.3`** the general round-starvation clause + above-threshold arm +
    cascade amendment
  - **`.4`** blocked age-band escalation
  - **`.5`** lane C supervisor full citizenship
  - **`.6`** lane D pair-stall + guarded nudge (depends on `.5`)
- **`overseer-vyjkzw`** — stays the NARROW instance (`shell-prolonged`).
- **`overseer-5jttov`** (`supervisor-scratch-discipline`) — adjacent,
  non-blocking. It edits the same generated supervisor charter that lane C's
  teach-the-protocol obligation touches; sequence those edits, do not gate.

Reach `bd` through the fleet wrapper — `with-livespec-env.sh bd show <id>`;
a bare `bd` is refused by the tenant. Beads refuses task→epic `blocks` edges;
do not manufacture one. The `auto-backup failed … command denied` warning on
every write is a known tenant defect tracked as `overseer-n04`, not a
failure of your command.

## 7. Known-good verification results, so they are not re-derived

Measured 2026-07-28; re-measure rather than trusting these if they matter to
a decision, but do not assume they are stale.

- `uv run pytest overseer -q` — **487 passed** on master.
- **Lane C is a coverage problem, not a detection problem.** Feeding live
  `-supervisor` pane captures to the daemon's OWN unmodified detectors: five
  of nine were `is_structured_gate == True` (they would render
  `blocked:human`), three were cleanly idle with parsed ctx, one had exited
  to a bare `zsh` (it would render `session-gone`). The same-tick render
  showed 33 tracks, `NEEDS YOU (5)`, and **zero supervisor rows** — none of
  the five gated supervisors among them.
- **A gate hides the statusline**, so all five gated panes parsed
  `ctx = None`. Expect the ctx-staleness clock to start routinely on gated
  entities.
- **The heading-coverage registry has 23 stale module qualifiers** (not 2, as
  an earlier revision of the note said), and **nothing validates them**:
  directions 1–3 of the check never resolve a node id, and the
  `scenarios.md`-only tier direction accepts one on a **string prefix**
  without resolving it. So "no new `## Scenario` heading ahead of its test"
  is a discipline this thread honors deliberately — **not** something the
  gate would catch. The 23 rows want their own hygiene work-item; it is
  **not filed** (it is neither a widened lane nor the consented defect, so it
  was outside the filing authorization). The prefix-acceptance gap is in the
  pinned `livespec-dev-tooling` check, so it belongs in THAT tenant if it is
  filed at all.

## 8. Repository discipline

Worktree → PR → **rebase**-merge for every tracked change; create worktrees
ONLY with `just worktree-create <branch> [base_ref]`; `mise exec -- git …` so
hooks fire; **never** `--no-verify`; halt and report on any hook failure;
never commit on the primary checkout; check **`git status`, not `git log`**,
after a hook-gated commit; verify against the forge after a fetch; never
touch another session's worktrees or branches; **never kill the acting
overseer daemon** (tmux `livespec-overseer:1.1`). Gate: `uv run pytest
overseer -q`, then `just check` where hooks demand it. No existing check may
be weakened, removed, skipped, or exempted.

One practical note from landing PR #219: a branch carrying its own copy of
this handoff will conflict with master's. Resolve to **master's** copy
(`git checkout --ours <path>` during a rebase) — it is the landed one.

## 9. Handoff refresh rule

Keep this file self-sufficient and cold-open sufficient. Durable design
reasoning lives in `research/`; per-finding review verdicts live in the
scratch verification logs AND, where durable, in the note; status lives in
the ledger and on the forge; keep exactly ONE next execution path. Refresh §2
whenever a step changes state, and before declaring `ready`.
