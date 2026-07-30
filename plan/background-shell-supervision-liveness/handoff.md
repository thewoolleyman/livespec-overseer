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

**RATIFIED THROUGH v004. Steps a–d are LANDED and step e is FIVE-SEVENTHS
DONE: `.1`, `.2`, `.4`, `.5`, `.7` are merged on master and CLOSED. `.3` is
stored `ready`, awaiting ONE dispatch from a fresh-bound session — gate 1
fired mid-tail on 2026-07-30 ~06:2xZ (release `67081674b0f3`; the
pre-stage update was run, so the NEXT session binds current). `.6` has a
run in flight under its pre-release dispatcher. The factory-outage story
below is history, not the present.**

| Step | State |
|---|---|
| §9 adversarial gate | **DISCHARGED** — 8 reviews, two waves, both model families, all verified and folded, zero refutations in the final round |
| Maintainer's batched decisions | **ALL RULED 2026-07-28** — see §3 |
| a. Research note landed | **DONE** — PR #219 merged. `research/control-plane-liveness.md` is the design source of truth, on master |
| b. Widened proposal landed | **DONE** — PR #226 merged |
| c. Ledger filed | **DONE** — six children under `overseer-4xfmez` (`.1`–`.6`), epic retitled and scope-widened |
| d. `/livespec:revise` | **DONE — v003 RATIFIED**, PR #232, commit `ed55630` on master. `proposed_changes/` is empty; `history/v003/` holds the proposal and its decision. Decision was `modify`: the nine edits verbatim plus one counsel co-edit aligning spec.md §"The restart" with contracts.md §"The restart interlock" |
| e. Implementation | **FIVE OF SEVEN CLOSED (2026-07-30)** — `.1` (PR #243, `86cb0b6`); `.2` (PR #313, `427ea8ee`, seventh dispatch); `.4` (PR #324, `fa05c58`); `.5` (PR #321 + ruled direct close, §3 ruling 10); `.7` (PR #322, `e4315acc`, built against v004, §3 ruling 9). REMAINING: `.3` stored `ready` — its first run's review-accepted fix was destroyed by the review_fix checkpoint timeout (third occurrence, `bd-ib-g56f` addendum 6) and its redispatch was refused by gate 1; `.6` run `01KYRTKFT7K8PTHN…` in flight since 06:15:55Z under the superseded-build dispatcher — see cold-open |

### Step e state, and the FOUR gates a dispatch can hit

**`.1` (the P1 restart defect) is DONE:** PR #243, rebase-merged as
`86cb0b6`, Fabro run `01KYNDKJH0RHJZAMHAY9JYWW98`; the maintainer accepted
2026-07-29 and the ledger row is CLOSED. One review note that stands for
later slices: the owed fixture landed as
`tests/integration/test_ready_declaration_restart.py`, a NEW directory —
this repo's convention had been beside-tests in `overseer/`; the full
`just check` aggregate accepted it.

**`.2` IS DONE — PR #313, rebase-merged `427ea8ee`, run
`01KYRJMD7DXFSNZG9F4NX5RNDT`, post-merge janitor green, ai-only accepted,
ledger CLOSED — on the SEVENTH dispatch, 2026-07-30 ~04:2xZ.** The six
dispatches before it all died in factory infrastructure, never on the code;
the full post-mortem is bug **`bd-ib-g56f`** in the ORCHESTRATOR tenant
(READ IT before reasoning about the factory — addenda 6–7 add the
checkpoint-timeout mechanism and its third occurrence, the fork-salvage
NEGATIVE, the stranded-item reconciliation gap, and the publish
self-collision). The outage history in brief, kept for instinct:

- Run `01KYP350T3PEMKYX87QND2WFPW` (04:47Z): implement + `just check` green
  (commits `554b5d2`, then `a70807a` after one retry). At 05:11Z the org's
  Anthropic MONTHLY SPEND LIMIT was crossed mid-review-turn; from then on
  every Claude ACP launch fleet-wide fast-died in 5–8 s while codex stages
  kept working (different billing). The R/I/A escalate interview showed only
  "ACP turn failed" — the actionable spend-limit error sat unexposed in the
  `stage.failed` event properties. Abandoned (supervisor-seat ruling); green
  work discarded with the sandbox.
- Run `01KYP8NDW1NF6D87XMXCFET3SE` (06:23Z, fresh dispatch): green again
  (commit `fddfd48`), review fast-died identically — falsifying the
  credential-TTL hypothesis and pinning the spend limit. It was PARKED
  blocked on its interview awaiting the maintainer, and at EXACTLY 240m00s
  wall the run ceiling / stall watchdog finalized it `workflow_error`,
  destroying the sandbox and the green work. **Parked interviews do not
  survive; answer promptly or lose the run.** (`fabro attach` exited 0 while
  answering the dying run — verify `fabro ps` status after every answer.)
- The maintainer ruled **"Raise the limit now"** (2026-07-29, identically
  through both seats' pickers); capacity re-verified by probe at 15:00Z
  (HTTP 200). The next dispatch then refused PRE-launch at
  `run-config-overlay`: **the host codex credential was too short-lived for
  the 4 h run budget** (gate 4 below). **Both of those are RESOLVED as of
  2026-07-30** — see the step-e row in §2 and gate 4 below; step e is held
  only by its own review-pass rule now.
- **The 15:00Z "capacity re-verified (HTTP 200)" above is a KNOWN FALSE
  POSITIVE.** That probe used `ANTHROPIC_API_KEY_LIVESPEC_E2E`, not the
  credential the review adapter bills. It is left in the record because the
  wrong conclusion it produced is the point; gate 4 and the probe block
  below carry the corrected form.

Four DISTINCT gates refused dispatches in this thread. Know all four; only
one is a human VALVE (gate 2). Gate 4 was described here as a human ACT —
that is no longer accurate (see gate 4).

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
moves). **`.3`–`.6` are STILL `backlog`, and their consent is PRE-GIVEN**
(§3 ruling 5): once `.2` closes and their edges clear, admit via the same
valve WITHOUT surfacing pickers. The valve also serves as recovery: a dead
dispatcher strands its item ACTIVE with no live run, and
`move:<id>:ready` restores it — journaled, exercised three times 2026-07-29
on `.2`.

**Gate 3 — the host dispatch cap (exit 3, "admission cap refused"). This
repo's cap is 4 as of 2026-07-30 (was 2). TRANSIENT; wait and retry.** Two
INDEPENDENT gauges, each capped at the committed value, and
BOTH need headroom: (i) non-terminal runs in `fabro ps -a --json` (terminal
kinds: succeeded/failed/cancelled/canceled/blocked), and (ii) the slot files
`tmp/fabro-dispatch-admission.slot{0,1}.lock` in this repo — a slot is held
iff its recorded pid is alive (the dispatcher self-reclaims dead-pid slots).
Other seats actively dispatch this tenant, so contention is normal; a
refusal names the holders.

**The cap was raised 2 → 4 for THIS REPO ONLY on 2026-07-30 (PR #305,
`2c7465b`), maintainer-directed.** Rationale, and the honest limit of the
evidence, are in the `.livespec.jsonc` comment; the unexercised layer
(same-repo collision at 4x) is filed as `bd-ib-rhap`. Two things that did NOT
change: **the standing rule still stands — do not raise the cap to jump the
queue.** The raise was a deliberate capacity decision, and it does not
prioritize any track: the key is per-repo with `per_item_override: false`, so
all tracks dispatching from this repo share it. Ordering is still the
admission valve's job (gate 2). And **never parallel-dispatch slices that
share files** — work partitioning, independent of host capacity.

**Gate 4 — host codex credential TTL (`run-config-overlay` refusal: "Host
Codex credential is too short-lived for the run budget"). CLEAR as of
2026-07-30 — this is NOT what blocks step e, and it is NOT necessarily a
human act.** The dispatcher requires the codex ACCESS token to outlive the
4 h run budget. Three corrections to what this section said before, each
measured 2026-07-30 ~03:57Z:

- **The gate reads `tokens.access_token`, NOT `tokens.id_token`**
  (`_dispatcher_projection.decode_codex_access_token_exp`). In the current
  `~/.codex/auth.json` the `id_token` IS expired (−9.3 h) while the
  access token runs to 2026-08-08T17:37:28Z. **Do not conclude "the codex
  credential is expired" from the `id_token`** — that is a false positive
  waiting to happen, the same shape as the E2E-key probe below.
- **Measured state: remaining 229.6 h, `alarm` False, `refresh_due`
  False** — via the build's own pure assessor
  (`_dispatcher_codex_refresh.assess_host_codex_credential`), which is the
  authoritative check; prefer it over hand-decoding claims.
- **"`codex login` has NO non-interactive form" is STALE.** The current
  build (`856d699b5f7d`) ships `dispatcher.py codex-cred-status [--json]`
  and `dispatcher.py codex-cred-refresh [--dry-run] [--json]`
  (`commands/dispatcher.py:20-21`, dispatch table at `:267-268`), with
  thresholds `CODEX_ALARM_THRESHOLD_SECONDS` 48 h and
  `CODEX_REFRESH_GUARD_SECONDS` 360 s. An interactive `codex login` is the
  fallback, not the only remedy. (Gate 1's "do not hand-invoke a newer
  build's `dispatcher.py`" caution still applies to anything that
  DISPATCHES; a read-only `codex-cred-status` is not that.)

The Anthropic side now has a REAL pre-flight gate, shipped 2026-07-30 as
`bd-ib-3mbj` (orchestrator PR #1156, rebase-merged at `37f028c`): the
Dispatcher live-probes `CLAUDE_CODE_OAUTH_TOKEN` USABILITY at
`run-config-overlay` BEFORE the sandbox launches — a bounded Messages call
(max 1 output token, 20 s timeout, ~$0.000013 API-price-equivalent per
probe) — and refuses with a per-condition remedy that distinguishes absent /
exhausted / revoked / permission-denied / unavailable. The operator check
(the `codex-cred-status` analogue, gate 4 above) is
`dispatcher.py claude-cred-status [--json]`; read-only, so gate 1's
"do not hand-invoke a newer build's `dispatcher.py`" caution does not apply.
Shipped on orchestrator master at `37f028c`; until a plugin release binds
it, invoke from the orchestrator repo checkout. Verified on this host
2026-07-30 ~07:25Z: `condition: "usable"`, HTTP 200, 8 input + 1 output
tokens, against the exact wrapper credential.

The hand-written curl probe that previously lived here is RETIRED in favor
of that tool-backed check (acceptance criterion 5 of `bd-ib-3mbj` — the
probe's whole story is preserved in that item and in `bd-ib-g56f` addenda
3–5). What stays true and load-bearing: the review adapter bills the org of
**`CLAUDE_CODE_OAUTH_TOKEN`** (the wrapper secret the workflow env hands
it); probes on `ANTHROPIC_API_KEY_LIVESPEC_E2E` (different org) and
interactive `claude -p` (different credential) both returned OK while the
adapter was hard-blocked — BOTH are documented false positives, do not
trust them; and when the token's org exhausts, the maintainer act is
re-minting the wrapper secret from a healthy org (`claude setup-token`),
holding dispatches until the check reports usable. The companion prose-gate
backstop is `bd-ib-p0g6` (P3): the plan skill's Step 4 self-sufficiency
gate checks that cited paths EXIST but never that an embedded operational
command exercises the mechanism it claims to — which is exactly how the
E2E-key probe passed review and was believed.

### So, on cold open

Run the staleness pre-flight (gate 1) FIRST. If it is stale, you are waiting
on another restart, not on a human — say so and stop; do not burn the session
re-deriving this. If it is clean:

1. **Probe both credentials** — `dispatcher.py codex-cred-status [--json]`
   (gate 4) AND `dispatcher.py claude-cred-status [--json]` (the tool-backed
   Anthropic check above; E2E-key and `claude -p` probes are false
   positives). Both measured CLEAR on 2026-07-30 (~229.6 h codex headroom;
   claude-cred-status `usable`/200 after the maintainer's rotation), so
   expect to CONFIRM rather than to unblock — but re-measure, do not
   assume, since both are time-dependent. If the codex token is short of
   the 4 h budget, try the non-interactive `codex-cred-refresh` FIRST and
   fall back to an interactive `codex login` (surface it — attended:
   `AskUserQuestion`; the `!`-prefix runs it in-session). If
   claude-cred-status reports exhausted, the maintainer act is re-minting
   the wrapper token from a healthy org (`claude setup-token`); hold
   dispatches until it reports usable. Do the rest of this list while
   waiting.
2. **Dispatch `.3`** — stored `ready`; `drive --action impl:overseer-4xfmez.3`.
   Context the fresh run's reviewer will likely re-derive: its first run's
   review ACCEPTED a real finding — `_supervisor_shielded_attention.py:163`
   hardcodes "preventing evidence: background shell", so the
   `winddown-starved` alert can fire on a shell-less tick, violating the
   evidence-enumeration rule — and the fix was applied, then destroyed by
   the review_fix checkpoint timeout (that timeout has killed 2 of 2 runs
   whose review accepted a finding; `bd-ib-g56f` addendum 6). On a gate-3
   cap refusal, wait and retry — do not raise the cap further.
3. **Watch every run; never park an interview.** If the R/I/A interview
   fires, read the REAL error from `fabro events <run>` `stage.failed`
   properties (the interview text hides it), answer promptly — a parked run
   dies at 240 m and takes its green work along — and verify the run status
   flipped after answering (`fabro attach` exit 0 proves nothing).
4. **See `.6` through** — run `01KYRTKFT7K8PTHN…` (started 2026-07-30
   06:15:55Z) was launched by a dispatcher on the superseded build
   `856d699b5f7d`; the run itself is unaffected. If its dispatcher reports
   green, verify the ledger row closed. If the dispatcher dies and the run
   completes out-of-band, the item strands ACTIVE with NO sanctioned valve
   (measured on `.5`: `impl:` refuses not-ready, `accept:` refuses
   invalid-source-state) — the `.5` precedent (§3 ruling 10) is the shape of
   the remedy, and each recurrence needs its own consent.
5. **Epic close-out once `.3` and `.6` are CLOSED:** verify each slice by
   its OWED TESTS per
   `plan/background-shell-supervision-liveness/research/untracked-obligation-closure.md`
   (`.4`/`.5`/`.6` closure is by owed tests, NOT the gap-id check), refresh
   this §2 to the completed state, and surface the two §7 PENDING remedies
   (the epic-comment sentence and the future MUST-form propose-change) for
   a consent batch — they remain NON-blocking.

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

Maintainer, 2026-07-29:

5. **Admissions for this epic's remaining slices are PRE-APPROVED**
   (verbatim: "I pre-approve all of the admissions") — the `move:<id>:ready`
   valve for `.3`–`.6`, including any re-admission the flow needs; do NOT
   surface admission pickers. NOT covered: NEW item filings. (An earlier
   revision of this line also excluded acceptances as `ai-then-human`
   maintainer valves — superseded by ruling 7 below.)
6. **"Raise the limit now"** — the org Anthropic spend limit is raised
   (ruled identically through both seats' pickers); `.2` recovery proceeds
   by redispatch.
7. **Acceptance is fleet-standard `ai-only` — there is NO human acceptance
   valve in this repo.** Maintainer-directed 2026-07-29: commit `2ec4b99`
   sets `dispatcher.acceptance_mode: "ai-only"` explicitly in
   `.livespec.jsonc` (the vendored default `ai-then-human` at
   `_dispatcher_policy_settings.py:50` is the NON-fleet-standard value this
   repo had silently inherited; `.1`'s human accept predates the switch).
   Slices accept on the AI verdict post-merge. If a slice parks at
   `acceptance` anyway, suspect a stale plugin/config binding FIRST — do
   not manufacture a maintainer valve and do not route acceptance pickers
   to the supervisor. Edit `.livespec.jsonc` BY HAND only: the
   `set-config` drive surface strips its comments while reporting green
   (tracked `bd-ib-lmi5`).

ATTRIBUTION NOTE (supervisor correction, 2026-07-29): the `.2`
abandon-and-redispatch decision and the `bd-ib-g56f` filing were the
SUPERVISOR seat's decisions under its vetting rubric, NOT maintainer
rulings. Never record the maintainer ruling on something they have not seen.

Maintainer, 2026-07-30:

8. **The WIP cap is 4 for this repo** (PR #305, `2c7465b`) **and the epic
   tail parallelizes**: `.3` + `.4` + `.5` dispatched simultaneously rather
   than `.5`-first-serially, `.6` immediately after `.5` lands; sequence
   only around real shared-file conflicts. Executed 2026-07-30. The cap
   raise was a capacity decision — the do-not-raise-to-jump-the-queue rule
   still stands.
9. **`.7` is ratified and authorized**: the uncertifiable-declaration
   proposal's ratification was delegated, cut as **v004** (PR #309,
   `SPECIFICATION/history/v004/`), and the ~04:05Z `AskUserQuestion` ruling
   approved dispatching `.7` immediately — that ruling IS `.7`'s admission
   consent (it was never in ruling 5's batch; the citation lives on the
   item's notes). Landed same-day as PR #322.
10. **`.5`'s stranded ledger row was ruled directly closeable** (~06:1xZ
    `AskUserQuestion`): its run completed out-of-band after its dispatcher
    died at the publish interview (PR #321 merged 05:56:51Z, exit stage
    succeeded) and NO sanctioned valve covers that state, so a ONE-TIME
    direct `bd close` carrying the full authority chain in its reason was
    authorized. Systemic gap: `bd-ib-g56f` addendum 7 / remedy 5. This is
    precedent-SHAPED, not a general license — each recurrence needs fresh
    consent.

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
  - **`.7`** attention for standing un-certifiable declarations (filed
    2026-07-29 from a live incident; ratified basis v004; admission via §3
    ruling 9; CLOSED via PR #322)
- **`overseer-vyjkzw`** — stays the NARROW instance (`shell-prolonged`).
- **`overseer-5jttov`** (`supervisor-scratch-discipline`) — adjacent,
  non-blocking. It edits the same generated supervisor charter that lane C's
  teach-the-protocol obligation touches; sequence those edits, do not gate.
- **`bd-ib-g56f`** — the ORCHESTRATOR tenant (`livespec-orchestrator-beads-fabro`),
  P1 bug: the 2026-07-29 factory-outage post-mortem (spend-limit hard-fail
  swallowed by "ACP turn failed", `transient_infra` misclassification with a
  per-run human interview, and the 240 m ceiling destroying parked green
  work). Filed and twice-amended by the supervisor seat's decision. Reach it
  by running the `bd` wrapper FROM that repo's checkout.

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

- **The 2026-07-29 factory-outage findings live in `bd-ib-g56f`; do not
  re-derive them.** The short form: an org Anthropic spend limit fails every
  Claude ACP turn hard while codex turns keep working; the workflow surfaces
  only "ACP turn failed" (the real cause is in `stage.failed`
  `properties.failure.causes`); parked interviews die at exactly 240m00s
  with their sandbox; `fabro attach` exit 0 proves nothing against a dying
  run. Three `.2` implementations went green in sandboxes that day and none
  landed — **the code side of `.2` is derisked; the factory side was the
  entire story.**

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
