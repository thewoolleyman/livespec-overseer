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

**RATIFIED. Steps a–d are LANDED. Step e is IN FLIGHT: `.1` is merged and
parked at the human acceptance valve; `.2` is admitted and waits ONLY on a
fresh-session dispatch (a new plugin release re-tripped the staleness gate).**

| Step | State |
|---|---|
| §9 adversarial gate | **DISCHARGED** — 8 reviews, two waves, both model families, all verified and folded, zero refutations in the final round |
| Maintainer's batched decisions | **ALL RULED 2026-07-28** — see §3 |
| a. Research note landed | **DONE** — PR #219 merged. `research/control-plane-liveness.md` is the design source of truth, on master |
| b. Widened proposal landed | **DONE** — PR #226 merged |
| c. Ledger filed | **DONE** — six children under `overseer-4xfmez` (`.1`–`.6`), epic retitled and scope-widened |
| d. `/livespec:revise` | **DONE — v003 RATIFIED**, PR #232, commit `ed55630` on master. `proposed_changes/` is empty; `history/v003/` holds the proposal and its decision. Decision was `modify`: the nine edits verbatim plus one counsel co-edit aligning spec.md §"The restart" with contracts.md §"The restart interlock" |
| e. Implementation | **IN FLIGHT** — `.1` merged (PR #243, `86cb0b6`), parked in `acceptance`; `.2` stored `ready`, dispatch needs a fresh session; `.3`–`.6` still `backlog` behind `.2` — see below |

### Step e state, and the THREE gates a dispatch can hit

**`.1` (the P1 restart defect) went through the factory GREEN on 2026-07-29:**
PR #243, rebase-merged as `86cb0b6`, post-merge janitor green, Fabro run
`01KYNDKJH0RHJZAMHAY9JYWW98`. It is parked in `acceptance` under
`ai-then-human` (the AI pass verdict was PASS); the maintainer chose on
2026-07-29 to hold it for their own review rather than accept immediately.
The pending act is `drive --action accept:overseer-4xfmez.1` (or
`reject:overseer-4xfmez.1:rework`). One review note: the owed fixture landed
as `tests/integration/test_ready_declaration_restart.py`, a NEW directory —
this repo's convention had been beside-tests in `overseer/`; the full
`just check` aggregate accepted it.

**`.2` is admitted (stored `ready`) and is THE next dispatch.** Its dispatch
was refused by the staleness gate (gate 1 below) minutes after `.1` merged:
release `822186e16544` was cut mid-session, so the dispatching session's
`c53fd50e58b6` binding went stale. The project-scope version was re-updated
to `822186e16544` before this handoff landed, so ONE restart should bind
current — verify with the pre-flight, since another release can land anytime.

Three DISTINCT gates refused dispatches in this thread. Know all three; only
one of them is a human valve.

**Gate 1 — dispatcher staleness (exit 3, "plugin build is stale"). NOT a
human valve; remedy is a session restart.** Skill bindings are fixed for a
session's lifetime, so a stale session cannot self-remediate — and the
SessionStart hook's own update does not help the session it runs in (the
hook says so: `Restart to apply changes`; measured 2026-07-28, a hook-updated
session ran the old build for its whole life and only the NEXT session bound
current). Running `claude plugin update --scope project
livespec-orchestrator-beads-fabro@livespec-orchestrator-beads-fabro` from the
stale session DOES pre-stage the next session correctly.

**Pre-flight check — do this BEFORE dispatching, it is free.** Your own
bound hash is the `<hash>` in any loaded skill's base-directory line
(`…/cache/…/<hash>/skills/…`) — invoke any orchestrator skill if you have
not seen one this session. Compare it against the project-scope version
(NOTE: the entry key is `projectPath` — an earlier revision of this snippet
said `scopePath`, which silently prints NOTHING; the `projectPath` is the
PRIMARY checkout `/data/projects/livespec-overseer` regardless of which
worktree you stand in):

```bash
python3 -c "
import json
d=json.load(open('/home/ubuntu/.claude/plugins/installed_plugins.json'))
for e in d['plugins']['livespec-orchestrator-beads-fabro@livespec-orchestrator-beads-fabro']:
    if e.get('projectPath') == '/data/projects/livespec-overseer': print(e['version'])
"
```

If that value is not the build hash in the skill's base-directory path, you
are stale — restart instead of dispatching. The SessionStart banner is the
same signal read live: `already at the latest version` means you are good;
`updated from X to Y … Restart to apply changes` means THIS session is X and
is stale. **Do not route around the gate** by hand-invoking a newer build's
`dispatcher.py` from the plugin cache — the same class of move as
`--no-verify`.

**Gate 2 — admission: `backlog` items are NEVER dispatch candidates. THIS is
the human valve.** The rendered lane IS the stored status (vendored
`livespec_runtime.work_items.lifecycle.lane_of`), and this epic's children
were ALL filed `backlog`, so the dispatcher refused `.1` with "not in the
ready set" even though its dependency edges were clear. (An earlier revision
of this handoff said `.1`/`.2` were "ready with no blockers" — that meant
dependency-clear, NOT stored-`ready`.) The sanctioned admission act is the
guarded queue-control valve `drive --action move:<id>:ready` — the
ORCHESTRATOR plugin's spec (the `livespec-orchestrator-beads-fabro` repo's
`SPECIFICATION/contracts.md` §"Human valve actions", NOT this repo's
`SPECIFICATION/`) lists it for `backlog` items as "move→ready
(admission)", and the explicit action selection IS the consent — so surface
it to the maintainer, never self-admit. The maintainer consented 2026-07-29
and `.1`/`.2` were moved `backlog → ready` (journaled operator human-valve
moves). **`.3`–`.6` are STILL `backlog`** and will need the same valve, with
fresh consent, once `.2` closes and their dependency edges clear.

**Gate 3 — the host dispatch cap (exit 3, "admission cap refused"), cap 2.
TRANSIENT; wait and retry.** Two INDEPENDENT gauges, each capped at 2, and
BOTH need headroom: (i) non-terminal runs in `fabro ps -a --json` (terminal
kinds: succeeded/failed/cancelled/canceled/blocked), and (ii) the slot files
`tmp/fabro-dispatch-admission.slot{0,1}.lock` in this repo — a slot is held
iff its recorded pid is alive (the dispatcher self-reclaims dead-pid slots).
Other seats actively dispatch this tenant, so contention is normal; a
refusal names the holders. Do not raise `dispatcher.host_dispatch_cap` in
`.livespec.jsonc` to jump the queue.

### So, on cold open

Run the staleness pre-flight (gate 1) FIRST. If it is stale, you are waiting
on another restart, not on a human — say so and stop; do not burn the session
re-deriving this. If it is clean:

1. **Dispatch `.2`** — `drive --action impl:overseer-4xfmez.2` (it is
   already admitted; no valve stands between you and dispatch). On a gate-3
   cap refusal, wait for capacity and retry — do not raise the cap.
2. **Surface `.1`'s pending acceptance** if the maintainer has not yet ruled:
   accept, or `reject:…:rework`, on PR #243 (see the review note above).
3. **After `.2` reaches `done`:** the next layer (`.3`, `.4`, `.5` — and `.6`
   behind `.5`) is still `backlog`; surface the gate-2 admission valve for
   fresh consent, then dispatch per the dependency layering — do not
   parallel-dispatch slices that share files. **Read
   `plan/background-shell-supervision-liveness/research/untracked-obligation-closure.md`
   before touching `.4`, `.5`, or `.6`** (their closure is by owed tests,
   not the gap-id check). The two §7 PENDING remedies (the epic-comment
   sentence and the future MUST-form propose-change) are NON-blocking; they
   ride any later consent batch.

**Never implement inline from this planning seat.** If `drive` hits a
genuine human valve, do NOT force it — surface it (an attended seat presents
it as an `AskUserQuestion` per §1; an unattended seat reports it to the
supervisor seat, which batches valves to the maintainer).

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
2. `plan/background-shell-supervision-liveness/research/control-plane-liveness.md`
   (on master) — the design source of
   truth: four lanes, every rejected alternative with its failure mode, the
   clearing/re-arm/daemon-restart table, the owed-tests list, and the
   rulings table.
3. `SPECIFICATION/spec.md` + `contracts.md` — RATIFIED v003, the governing
   prose. The proposal is no longer in `proposed_changes/` (that directory is
   empty); it is snapshotted with its decision record under
   `SPECIFICATION/history/v003/`.
3b. `plan/background-shell-supervision-liveness/research/untracked-obligation-closure.md`
   — REQUIRED before touching
   `.4`, `.5`, or `.6`: the four ratified obligations gap detection cannot
   see, their consolidated owed-test closure criteria, and the drafted
   one-sentence epic-comment fix.
4. `tmp/overseer/background-shell-supervision-liveness/reviews/` — the raw
   review relays, `wave1-verification.md`, and `wave3-worker-verification.md`
   (scratch, UNTRACKED; durable conclusions are already folded into the note).
5. `plan/background-shell-supervision-liveness/research/root-cause.md` and
   `…/research/policy-options.md` — the narrow predicate only.
6. `SPECIFICATION/spec.md` + `contracts.md`, `overseer/marker-protocol.md`,
   `overseer/AGENTS.md`.
7. Code, cascade order: `_supervisor_observe.py`, `_supervisor_evaluate.py`
   (resume-retry leg FIRST at `:165-167`, busy `:198`, `void_stale_blocked`
   `:206`, gate/blocked `:241`, ready `:283`, threshold `:296`, offer
   else-leaf `:326`, re-arm `:385-391`), `_supervisor_state.py`
   (`void_if_stale`'s only two call sites are `evaluate:237` and `:244`),
   `_supervisor_restart.py` (the `.1` defect site — FIXED by PR #243, so its
   coordinates below predate `86cb0b6`),
   `_supervisor_launch.py` (`session_of` returns `track.tmux` first, `:52` —
   the pair-naming trap), `_supervisor_prompts.py` (`_WRAPUP_BODY`'s
   hardcoded copy DESTINATION), `signals.py` (`ready_valid`'s `mtime > stamp`
   `:423`; whole-capture `is_busy` `:152-155`; `state_path` plain join
   `:339-341`), `_supervisor_core.py` (`alert` dedups on full line text),
   `_supervisor_view.py`, `_supervisor_config.py`, `_supervisor_records.py`,
   `_supervisor_offer.py`.

All `file:line` citations above were re-verified against source on
2026-07-28 — at `aa4411d`, BEFORE PR #243 touched `_supervisor_restart.py`;
every other cited module is untouched by that PR.

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

- **The gate is fully green on master, RE-MEASURED after the
  `livespec-dev-tooling` pin went to v1.0.0** (PR #234) — a major bump of the
  enforcement tooling moved nothing. At `aa4411d`: `uv run pytest overseer -q`
  = **487 passed**; `just check` = **all 62 targets passed**, coverage
  **100%** (2724 statements, 608 branches, zero missed), green token written.
  Do not re-run these to satisfy curiosity about the bump; that question is
  answered.
- **v003's ratification is structurally sound**, per the same `just check`
  doctor-static phase: `out-of-band-edits` (HEAD-active matches
  HEAD-history-vN), `version-contiguity`, `revision-to-proposed-change-pairing`
  and `accept-decision-snapshot-consistency` all PASS.
- **Every `file:line` coordinate in §5 was re-verified exact at `aa4411d`** —
  navigate by them without re-deriving. Spot-proofs worth having in hand:
  `_supervisor_evaluate.py` resume-retry leg really is FIRST (`:165-167`),
  then busy `:198`, `void_stale_blocked` `:206`, `void_if_stale` `:237`,
  gate/blocked `:241`, `void_if_stale` `:244`, ready `:283`, threshold
  `:296`, offer else-leaf `:326`, re-arm `:385-391`. `void_if_stale` has
  exactly the two live cascade call sites (`:237`, `:244`); the only other
  reference is the `_supervisor_core.py:341` delegation wrapper, which just
  one test drives. `signals.py`: `ready_valid`'s `state.mtime >
  injection_stamp` at `:423`; `is_busy` searches the WHOLE stripped capture
  (`:152-155`); `state_path` is a plain `marker_dir(...) / ".overseer-state"`
  join with no canonicalization (`:339-341`) — the U4 defect coordinate.
- **`.1`'s defect re-confirmed in source, all three exits — since FIXED by
  PR #243 (`86cb0b6`); this bullet describes the PRE-fix source and is kept
  as review context for the pending acceptance.** The respawn-FAILED
  exit (`_supervisor_restart.py:135-144`) alerts and returns bare — safe,
  nothing was killed. The recognition-timeout exit (`:146-154`) runs AFTER a
  successful `respawn_pane`, alerts "respawned pane never became Claude;
  keeping the ready declaration", and returns bare with **no**
  `set_resume_pending` — the defect. The gate exit (`:166`) and the
  submit-failure exit (`:189`) both DO call it. And the timeout exit precedes
  the resume computation and paste (`:175-176`), which is why the successor is
  a fresh session that was never handed anything to do.
- **`.5` scope item 5's "VERIFIED CAUSE" re-confirmed:**
  `_supervisor_prompts.py:84` is literally
  `cp {handoff} "$W/plan/{topic}/handoff.md"` — the destination basename is
  hardcoded and independent of `{handoff}`, so no choice of
  `{topic}`/`{handoff}` yields `supervisor-handoff.md`. It needs a VARIANT,
  not a parameter substitution, exactly as filed. Useful head start:
  `supervisor_handoff_path` is ALREADY a public builder in that module, so the
  variant has its path function to hand.
- `_supervisor_launch.py:52` — `session_of` returns `track.tmux` first, with
  an in-code comment explaining the mapped/unmapped fallback. The pair-naming
  trap is real and documented at the site.
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
  gate would catch. Two items came out of this, **BOTH now filed** with
  maintainer consent (2026-07-28), and neither belongs to this epic — do not
  re-file them:
  - **`overseer-knm`** (this repo's tenant, standalone task,
    `origin:freeform`) — the 23 stale registry rows. Fixture-data only: it
    rewrites each row's module component to the module that actually defines
    the function, renaming and moving no test. Carries a re-derivation script
    rather than trusting its embedded list.
  - **`livespec-dev-tooling-r3ib`** (the DEV-TOOLING tenant, bug) — the
    checker gap that made the drift invisible, with `file:line` coordinates
    against that repo's master and a minimal repro sketch. Note its rollout
    caveat: consumers are pinned, so a new resolving direction turns existing
    drift red for them, which makes sequencing a real design decision.

- **Gap detection cannot see four of the ratified obligations — so the
  prescribed closure check is incomplete.** The epic's traceability comment
  maps 12 real gaps to slices and its 12/8 split is CORRECT (re-verified: the
  8 unmapped ids are genuinely pre-existing implemented clauses). The hole is
  upstream of classification: `detect_impl_gaps` emits exactly one candidate
  per sentence containing the literal token `MUST`, so an obligation written
  without that token is invisible to it.

  So four obligations ratified in v003 in indicative / RESERVED / only-when
  voice produced NO gap id: EDIT 3's age-band escalation (→ slice **`.4` has
  no gap id at all**); EDIT 6's entire pair nudge including the one bounded
  exception permitting a paste into a busy-classified supervisor (→ **`.6`
  has none either**); EDIT 4's `-supervisor` reservation and EDIT 7's
  canonical-path rule (→ two untracked halves of `.5`).

  **Consequence, WIDENED by measurement 2026-07-29: the gap-id
  set-membership check is not a done-signal for ANY slice.** The detector's
  gap-id set is a pure function of the spec text (its docstring says so) —
  it never consults the code or the ledger, so landing a slice cannot
  shrink it: `.1` merged and its `gap-ekwoq4ey` still emits, along with all
  20 candidates. Verify every slice by its OWED TESTS; the gap-ledger echo,
  where one exists, is a `capture-impl-gaps` DRY-RUN re-classifying the
  slice's mapped ids as implemented. See the research file's §3b for the
  measurement and the corrected §4 draft.

  **All of this is now worked out in full, against the RATIFIED tree, in
  `research/untracked-obligation-closure.md` — read that before touching
  `.4`, `.5`, or `.6`.** It carries the per-heading `MUST` table, the four
  obligations with `file:line` proof, and the consolidated owed-test closure
  criteria for each. Two corrections it lands, both re-measured 2026-07-28:

  - The per-heading arithmetic above was stated as candidates = `MUST`
    tokens. The detector counts SENTENCES, and one sentence
    (`spec.md:416-419`) carries four `MUST`s; Fail-soft posture is **9**
    tokens, not 8. No conclusion changes — U1–U4 are zero-`MUST` under either
    measure.
  - **Remedy (b) is far narrower than stated here.** The explicit closure
    criteria it calls for ALREADY EXIST and are correct on all three slices
    (`.4` "Owed test 3"; `.5` "Owed tests 5 and 13's lane-C arms", naming the
    symlink refusal; `.6` "Owed tests 6 and 13's lane-D arms"). Do not
    re-author them. The ONE defective artifact is the **epic's traceability
    comment**, whose mapping omits `.4` and `.6` entirely and whose final
    sentence then prescribes the gap-id check as *the* closure check — making
    it vacuously green for those two slices with no code written. Remedy (b)
    is therefore ONE sentence on ONE artifact; its replacement text is drafted
    verbatim in §4 of that file, ready to paste.

  Both remedies remain PENDING, not actioned — (b) the epic-comment sentence,
  and (a) later raising those four clauses to `MUST` form in a fresh
  propose-change (identical semantics, fixes detection for every consumer, but
  touches ratified prose so it needs its own cycle). Amending the epic's
  traceability comment was deliberately NOT done by the worker seat: ledger
  writes in this thread are consent-gated. Earlier detail in
  `reviews/wave3-worker-verification.md` §8.

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
