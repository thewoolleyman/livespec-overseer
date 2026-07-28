# Control-plane supervision liveness — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing, and
> that you may be a different model than the session that wrote it. Everything
> load-bearing is either stated here or cited by a path verified to exist on the
> merged default branch.

## 1. The primary goal — read this first, it reframes everything else

The maintainer's words, and the bar every proposed behavior is judged against:

> The overseer and the supervisor exist to surface ONLY what genuinely needs
> human attention, to keep everything else running autonomously, and to NEVER
> stall without a legitimate blocking human decision — and when there is one, it
> is presented as an `AskUserQuestion`, not as prose.

Two failure modes are therefore SYMMETRIC, and a design that commits either one
is wrong:

- **Stalling silently.** A track that cannot proceed and says nothing.
- **Surfacing noise.** An operator line no human can act on. Adding a row to
  `NEEDS YOU` that a person reads and can do nothing about FAILS this goal just
  as surely as a silent stall.

When you evaluate any candidate in this thread, ask both questions, not one.

## 2. What this thread is now — the WIDENED scope

This thread is no longer "a stale background shell". It is **control-plane
supervision liveness**. `shell-prolonged` (the ratified narrow predicate, §5) is
an INSTANCE of a general rule, not the deliverable.

The general rule must cover four lanes:

| Lane | What it must settle |
|---|---|
| **A. Duration as a first-class primitive** | Every state carries a duration, via ONE mechanism — not a second bespoke clock per signal |
| **B. `blocked:` liveness** | Declaration age, voiding on IDLE ticks, and an escalation path |
| **C. The supervisor as a TRACKED entity** | Its context, its state, and its attention — today it has none of the three |
| **D. Track-level PROGRESS** | A signal that makes a mutual worker/supervisor wait visible from OUTSIDE both sessions |

The unifying observation, measured (§6): **no signal but `idle` carries a
duration, and no signal at all carries progress.** A `shell` 3 seconds old and
one 39 hours old are indistinguishable to the daemon; so are a `blocked:` 5
minutes old and one 22 hours old; so are a supervisor at 80% context and one at
2%; and a pair of sessions waiting on each other looks healthy from BOTH
single-session vantages.

## 3. Read-first chain

Every path below was verified present on `origin/master` when this file was
written.

1. This file.
2. `plan/background-shell-supervision-liveness/research/root-cause.md` — the
   first incident (the 39-hour poller) and its causal chain.
3. `plan/background-shell-supervision-liveness/research/policy-options.md` — the
   completed comparison for the NARROW predicate: evidence inventory, eight-row
   behavior matrix, four candidates with verdicts, and the selected contract.
   Its rejected-alternative discipline is the bar for the note you must write.
4. `SPECIFICATION/proposed_changes/background-shell-liveness-attention.md` — the
   FILED, UNRATIFIED proposal you must widen before anyone reviews it.
5. `SPECIFICATION/spec.md` — especially "The cardinal rule", "The supervision
   round", "The escalating wrap-up", "The keep-going nudge" (its in-memory
   continuous-idle clock is the only existing duration precedent), "Notify,
   never block", and "Fail-soft posture" (the clause incident 1 falsified).
6. `SPECIFICATION/contracts.md` — "The state file", "The restart interlock",
   "The wrap-up injection", "Attention surface".
7. `overseer/marker-protocol.md`, then `overseer/AGENTS.md` (busy detection,
   Claude registry status, state precedence, attention).
8. Code, in cascade order: `overseer/_supervisor_observe.py`,
   `overseer/_supervisor_evaluate.py`, `overseer/_supervisor_state.py`,
   `overseer/_supervisor_view.py`, `overseer/_supervisor_config.py`,
   `overseer/_supervisor_records.py`, `overseer/_supervisor_offer.py`.

Do not treat chat history as a source of truth. It does not survive the restart.

## 4. Artifact state — precise

| Artifact | State |
|---|---|
| `research/root-cause.md` | Merged, current |
| `research/policy-options.md` | Merged, current — covers the NARROW predicate only |
| `SPECIFICATION/proposed_changes/background-shell-liveness-attention.md` | **FILED and merged as `316d69d`, NOT RATIFIED** |
| `research/control-plane-liveness.md` | **DOES NOT EXIST.** Not started |

**`/livespec:revise` has deliberately NOT run.** The proposal must be WIDENED
first so this stays ONE ratification cycle. Running revise against the narrow
proposal as filed would ratify the instance and strand the class.

What `research/control-plane-liveness.md` still owes — all of it, nothing is
drafted: the four lanes of §2 generalized from BOTH measured incidents; the
rejected alternatives for each lane with their failure modes; the exact
clearing/re-arm rule for anything time-based; and the argument that the result
satisfies §1 in both directions (no stall, no unactionable noise).

## 5. What is already RATIFIED — do not relitigate

The maintainer confirmed both values for the narrow predicate. Keep them exactly
as they stand, and land them as an instance of the general rule:

- Episode floor: **2 hours**.
- Row status token: **`shell-prolonged`** (yellow; `ATTENTION_STATUSES`
  membership; alert condition key `prolonged-background-shell`).

The predicate itself, from `policy-options.md`:

```text
shell_episode_now = not is_busy(capture) and (claude_status == "shell" or codex_fallback)
attention         = shell_episode_now and episode >= 2h and eff_ctx <= threshold
```

## 6. Measured evidence, and where the supervisor's own measurements were WRONG

Supervisor brief 1 supplied five measurements. I re-ran all five. **Three
CONFIRMED exactly; two need correction.** The corrections are recorded rather
than smoothed, because one of them changes the mechanism.

### CONFIRMED as stated

**M1 — `blocked` outranks both `ready` and the threshold branch.**
`overseer/_supervisor_evaluate.py`: `elif gate or blocked is not None:` is line
**241**; `elif ready:` is line **283**; `elif eff_ctx is not None and eff_ctx <=
threshold:` is line **296**. So a blocked track can neither restart nor open a
wind-down round. `~/.livespec-overseer-stamps.json` held exactly **2** keys
(`/data/projects/livespec` × `cloud-local-memory-cleanup`, `codex-acp-auto-bump`)
— neither for `console-happy-path-mvp`. It has never been warned.

**M4 — nothing tracks supervisor sessions.** The read-only render
(`supervisor.py list`, `act=False`) showed **33 tracks, zero** of them a
`-supervisor`. tmux held **11** `-supervisor` sessions; the Claude registry held
**10** live supervisor sessions at 57–80% context, one of them status `shell`.
`_supervisor_offer.surface_supervision_offer` reduces a supervisor to two
booleans and returns. Confirmed: no context monitoring, no wrap-up, no restart,
no `NEEDS YOU`, no state file, for any supervisor in the fleet.

**M5 — the daemon times exactly one thing.** The brief's exact grep over
`_supervisor_config.py` and `registry.py` returns a single hit — and it is
**weaker than the brief claimed**: the hit is a *comment* mentioning
`InjectState.idle_since`, not the field. Widening the grep to the whole package
confirms `idle_since` (declared in `_supervisor_records.py:43`) is the ONLY
`_since` anywhere. One clock, one signal, for the keep-going nudge.

### CORRECTION 1 — M2's mechanism is an OSCILLATION, not a permanent state

The brief said the terminal blocked state is "permanent by construction" because
an idle session's stale `blocked:` is never voided.

The CODE claim is true. `void_stale_blocked` is called from exactly one site,
`_supervisor_evaluate.py:206`, inside `if busy:` → `if act:`, and it early-returns
unless `generating`. Its own docstring says: *"An idle blocked session is never
touched: it keeps its declaration and keeps alerting, forever."*

But that is **not what trapped this track**. The daemon log holds **31** void
lines for `console-happy-path-mvp` (the brief said "20+"), running from
**2026-07-25T21:28:38Z** (the brief said "since 2026-07-26" — a day late), with
declaration ages of exactly **121s … 80728s** (the brief's range, exact). The
declaration IS voided — 31 times — each time the session resumed generating, and
then re-declared.

So the real trap is a CYCLE, and it is worse than the brief's version because it
needs no permanence at all:

- while `blocked:` stands → the blocked branch (241) preempts the threshold
  branch (296) → no round;
- while the session generates → the busy branch (198) preempts it → no round;
- the track is never in any third state, so **no round can ever open in either
  phase.**

The idle-never-voided property is real and did bite — one declaration survived
80728s ≈ **22.4 hours** — but the unrestartability is caused by the precedence
of TWO branches over the threshold branch, not by voiding behavior. Any fix
aimed only at voiding will miss this.

### CORRECTION 2 — the track was NOT blocked at verification time

The brief describes the track as currently sitting blocked. When I measured it,
`console-happy-path-mvp` had **no `.overseer-state` file at all** — voided at
`2026-07-28T03:15:26Z` and not re-declared. The render showed it as plain
`working` at **22%**, not `blocked:human`. The trap is intermittent by nature
(Correction 1), so a single-moment observation can miss it entirely. Do not
expect to reproduce it by looking once.

**M3 — CONFIRMED with a rounding note.** `console-happy-path-mvp-supervisor` was
live at **64%** (brief said 65%), registry status `shell`, statusline reading
`2 monitors`. Its armed monitor (`b4oslj62u`) is described in its own pane as
*"worker executes dry-run — ledger change, PR, or report"* — a wake condition
strictly downstream of the worker executing. The structural point stands. One
nuance worth carrying: by the time I looked, that supervisor had already NAMED
the stall in its own pane and authorized the worker to proceed, so the pair was
not frozen at that instant — but nothing OUTSIDE either session could have told
you that, which is exactly lane D.

### Corroborating debris (not in the brief, low weight)

Two state files under `/data/projects/livespec/tmp/overseer/` hold bare `ready`
(`fleet-pin-propagation`, `ledger-status-conformance`) while the stamp sidecar
has no key for either, so `ready_valid` can never certify them. Both plans are
undiscovered (they are absent from the 33-row render), so these are **inert
debris, not live traps** — but they are the same shape: a declaration with no
duration, no round, and nothing that ever reconciles it.

## 7. Design direction — UNRATIFIED, and the reason it is here

This section is one session's analysis. It has NOT been reviewed, NOT been
ratified, and MUST NOT be implemented from. It is recorded only so the successor
starts from an argument rather than a blank page. **Your first act is to test
it, not to adopt it.** If you disagree, write the disagreement into
`research/control-plane-liveness.md` and follow your own reasoning.

- **Lane A.** Duration splits honestly into two mechanisms, not one clock per
  signal. (i) **On-disk, already available and daemon-restart-proof**: every
  declaration's age is its state-file mtime, which `signals.read_state` already
  returns and which the code today uses for only two purposes (the 900s ACK
  staleness, the 120s void grace). (ii) **In-memory**, needed only for signals
  with no on-disk footprint (busy/shell, gate, idle): one clock keyed on a
  deterministic condition SIGNATURE derived in `observe`, reset on signature
  change or on an observation gap. Keying the clock to the signature rather than
  to the rendered status matters, because the status changes at the floor and a
  naive status clock would reset itself at the moment it fires.
- **Lane B.** Voiding an idle `blocked:` **on age alone is unsafe** and I would
  reject it: a session legitimately waiting on a human while idle is the normal
  case, and a timer that discards its declaration is the daemon overruling a
  session's own semantic assertion — the exact thing the cardinal rule forbids
  everywhere else. Two safer routes, both evidence-based: (i) **escalate by age**
  instead of voiding — the current alert is edge-triggered, so a 22-hour block
  emits ONE line and then is silent forever; re-arming on age-band crossings
  fixes the surfacing without touching the declaration; (ii) void an idle
  `blocked:` only on PROOF it belongs to a dead predecessor — the declaration's
  mtime predating the live session's own process start. The daemon already reads
  that start time (`procStart`, used for PID-reuse defence in
  `claude_sessions.read_live_sessions`), so this is exact, durable, and needs no
  timer. Note this contradicts brief 1's prescription of "voiding on IDLE ticks";
  the disagreement is deliberate and is flagged for the maintainer.
- **Lane C.** A supervisor has no `plan/<topic>/` of its own, so discovery cannot
  see it — discovery keys on plan directories. The candidate worth comparing
  first is treating a track as a PAIR: an optional `<topic>-supervisor` session
  discovered by the SAME name derivation and containment check that already
  exists, with its own context reading and its own state file. Minimum viable is
  **monitor and surface only** — no injection and no restart for supervisors,
  because a supervisor holds the brief and restarting it is strictly more
  dangerous than restarting a worker.
- **Lane D.** The daemon may not read anything under `plan/` (invariant 1) and
  must stay orchestrator-agnostic (so the ledger is off-limits too). That leaves
  one universal signal it ALREADY parses every tick: **remaining context**. A
  session that is classified busy but whose `eff_ctx` has not moved across a
  bounded window is not spending tokens, therefore not working — runtime-agnostic,
  already read, and needing no new evidence source. `InjectState.last_ctx` is
  already the storage. A PAIR both stalled by that measure is the mutual wait,
  visible from outside both sessions. Rejected alternatives to record: reading
  `plan/` or git history (violates non-interference outright), reading the ledger
  (couples the daemon to one orchestrator), and pane-text diffing (already exists
  as the 0.6s `pane_settled` check, and pane text churns for cosmetic reasons).
- **Attention-surface shape.** The general rule genuinely CHANGES the shape and
  the proposal must say so rather than bolting on a sixth member: membership
  becomes the five enumerated instant conditions PLUS one general clause — a
  track whose observable condition has persisted past a bounded floor without
  progress while its remaining context is at or below its wind-down threshold.
  `shell-prolonged` is then an instance of that clause.
- **The §1 test, applied honestly.** Lanes A–D all ADD operator lines. Each one
  must be justified against §1's second failure mode, and at least one deserves
  real scrutiny: an alert that says "this pair is mutually waiting" is only
  actionable if the operator is told WHICH session to go to and what decision is
  owed. If a lane cannot produce an actionable line, it belongs in the ledger as
  a defect report, not in `NEEDS YOU`.

## 8. Overlap check — RESOLVED

I read it. Commit `faeaeba` opened `plan/supervisor-scratch-discipline/`,
anchored by epic **`overseer-5jttov`**.

**It owns NONE of the four lanes. Stand down on nothing; drive all four.**

Its subject is the DURABILITY of what a supervisor WRITES into a gitignored
scratch directory: the rule that only JSON may live in `tmp/supervisor/` with
prose confined to `tmp/supervisor/briefs/`, a fixture over the generated
supervisor charter, and a local-only enforcement check. Its three goals are file
hygiene, charter content, and brief-mirroring. That is orthogonal to supervision
COVERAGE, which is lane C.

One genuine adjacency, a coordination note and **not** a block: its goal 1 edits
`.claude-plugin/prose/supervise-plan.md` (the generated supervisor charter). If
lane C requires a supervisor to write its own state file, that touches the same
FILE. Shared file, different lane — sequence the edits, do not gate on it.

Also worth knowing: that thread's own handoff draws an explicit scope boundary —
the same hazard applies to anything an agent writes outside SCM and the ledger,
but it declares that generalization a different, larger thread it must not
absorb. So it will not grow into these lanes on its own.

## 9. The adversarial review gate — HARD precondition, entirely UNDISCHARGED

**No product code, and no `/livespec:revise`, until the plan has been
adversarially reviewed by sub-agents on at least three distinct lenses:**

1. **Safety and predicate refutation** — find ANY path from the new behavior to
   a paste, Enter, respawn, kill, or declaration write. Construct inputs where
   the predicate fires wrongly, and inputs where it never fires at all.
2. **Autonomy and stall** — does the design ever stall? Does it surface anything
   a human cannot act on? Does it satisfy §1 in BOTH directions?
3. **Code-truth** — verify EVERY code and spec claim in the plan against the
   actual source, by `file:line`. This handoff's own §6 line numbers are in
   scope; re-verify them rather than trusting them.

Use **Fable and GPT-Codex sub-agents**, not one model's opinion. **A review that
finds nothing is a FAILED review** unless it also reports what it tried and could
not break.

The supervisor launched one such reviewer from its own seat before this restart.
**It did not survive the restart.** Treat the gate as entirely undischarged and
run it from scratch.

## 10. Ledger anchors — ids only, never copied status

- Planning epic: **`overseer-4xfmez`** — its scope is now control-plane
  liveness, not one stale shell. Widening its description is part of the work.
- Narrow implementation bug: **`overseer-vyjkzw`** — stays narrow
  (`shell-prolonged`).
- Adjacent, non-blocking: **`overseer-5jttov`** (`supervisor-scratch-discipline`).

Read current state from the ledger; never copy it into this file as a shadow
queue. **Reach `bd` through the fleet credential wrapper** —
`with-livespec-env.sh bd show <id>` — a bare `bd` is refused by the tenant
database with an access-denied error.

**Do NOT invent a task-to-epic `blocks` edge.** Beads refuses it
(`tasks can only block other tasks, not epics`). That finding stands; do not
bypass the store to manufacture one.

New work for the widened lanes must be filed as SIBLINGS under the epic. That
filing has NOT been done.

## 11. Next action — exactly one path

1. **Write `plan/background-shell-supervision-liveness/research/control-plane-liveness.md`.**
   Generalize from BOTH measured incidents (§6). Cover all four lanes of §2 with
   the same rejected-alternative discipline `policy-options.md` uses. Test §7
   rather than adopting it. Judge every candidate against §1 in both directions.
2. **Run the §9 adversarial review gate** over that note. Fable + GPT-Codex
   sub-agents, three lenses, and make each reviewer report what it tried and
   could not break.
3. **Widen the filed proposal** (`SPECIFICATION/proposed_changes/background-shell-liveness-attention.md`)
   to carry the general rule, keeping `shell-prolonged` exactly as ratified (§5)
   but landing it as an INSTANCE. If the general rule changes the shape of the
   attention surface — it does, see §7 — say so plainly in the proposal rather
   than appending a sixth member to a closed list.
4. **File the widened lanes as sibling work-items** under `overseer-4xfmez`, and
   update that epic's scope.
5. **Only then** run `/livespec:revise` — one ratification cycle for the whole
   contract.
6. **Only after ratification**, dispatch implementation via the factory route:
   `drive` action `impl:overseer-vyjkzw`, or the Dispatcher drain. Never
   implement inline from a planning session.

## 12. Outcome constraints — binding on every lane

- No shell age, prompt shape, timer, declaration age, or context percentage may
  EVER authorize a paste, Enter, respawn, kill, or declaration write.
- A fresh session-written `ready` remains the SOLE restart authorization.
- Genuine background work and a genuine human wait both stay protected.
- Every alert is coordinate-rich and edge-triggered, and every condition clears
  and can re-arm.
- Daemon-restart behavior is explicit for anything time-based, and fails in the
  safe direction (delay, never a false alarm).
- Claude and Codex are each addressed explicitly, with parity justified by
  common evidence or divergence justified by measured evidence.
- Spec, contracts, scenarios, protocol docs, maintenance guide, status coloring,
  attention membership, and tests all agree.
- Any new `## Scenario` in `SPECIFICATION/scenarios.md` MUST land atomically with
  a real integration test under `tests/integration/` and its
  `tests/heading-coverage.json` row — every scenario heading in this tree is
  mechanically required to name one, which is why the filed proposal
  deliberately adds no scenario ahead of the code.
- Two existing heading-coverage tests pin the clauses being amended and MUST be
  grown by the implementing slice:
  `overseer.test_supervisor.test_needs_attention_predicate_covers_every_attention_status`
  (pins `contracts.md` §"Attention surface") and
  `overseer.test_supervisor.test_ctx_unknown_never_injects` (pins `spec.md`
  §"Fail-soft posture").

## 13. Repository discipline

Every tracked-file change goes worktree → PR → **rebase**-merge. Create
worktrees with `just worktree-create <branch> [base_ref]` — never raw
`git worktree add`, which omits the discipline pack and makes the worktree
unable to commit a `.py` change or push at all.

Use `mise exec -- git …` so hooks fire. **Never pass `--no-verify`**; halt and
report on any hook failure rather than bypassing it. Never commit on the primary
checkout. Product `.py` changes follow the red-green-replay commit ritual.

**Check `git status`, not `git log`, after a hook-gated commit** — a rejected
commit leaves the change STAGED, and a following `git log` shows some other
track's commit at HEAD and reads as success.

Verify against the forge after a `git fetch`, never against a possibly stale
working tree. Note that `just worktree-reap` cannot prove ancestry for
rebase-merged branches and will skip them; remove only your OWN worktree
explicitly rather than passing `--force`, which would touch other sessions'.

Never touch another session's worktree or branch. **Never kill the acting
overseer daemon in tmux `livespec-overseer:1.1`.**

Gate: `uv run pytest overseer -q`, then `just check`. No existing check may be
weakened, removed, skipped, or exempted.

## 14. Handoff refresh rule

Keep this file self-sufficient and cold-open sufficient. Put durable reasoning in
`research/`, keep status in the ledger, cite live ledger ids rather than copying
their state, and keep exactly ONE next execution path. Before declaring this
handoff ready, verify every path in §3 exists and is tracked on the merged
default branch.
