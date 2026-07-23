# Plan — cutover-and-shipping

**Owning repo:** `livespec-overseer`. **Status:** OPEN — created 2026-07-23 as
the SUCCESSOR of livespec core's `plan/archive/overseer-productization/`
(archived the same day). This repo drives its own overseer work; the core
thread is reference-only history.

**Ledger anchor:** epic `overseer-3wt` (this repo's beads tenant); its
children and every lane are READ from the ledger (`list-work-items` /
`next`), never stored here. The CORE-tenant epic
`livespec-b1uo` stays in livespec core per its own do-not-move ruling; its
`.1`/`.2`/`.3` closes are evidence-staged there for the maintainer, and
`.4`/`.5` carry a recommended close-as-unnecessary disposition (D7/D9).

## The cutover HAPPENED — 2026-07-23, via the emergency contingency

The staged old-vs-new protocol this handoff used to carry was OVERTAKEN BY
EVENTS on cutover day; the full original text is in this file's git history
(the "docs(plan): open cutover-and-shipping" revision). What happened:

- **Stage 0 landed first.** `overseer-y8o` (bootstrap re-point) went through
  the factory: PR #19, merge `f13be76`, post-merge janitor green, accepted.
  `overseer-start` now launches `overseer/overseerd` and derives the checkout
  root from the module file's parent directory; beside-tests pin both.
- **The old daemon (pid 1570280, livespec core's deleted-path code) DIED**
  before the read-only soak could run. The original handoff's contingency —
  "if the old daemon dies before the protocol completes, an emergency
  relaunch from EITHER copy is legitimate; the bytes are proven identical" —
  was exercised at ~00:04 UTC by an operator session: THIS repo's daemon was
  launched bare (`./.venv/bin/python3 overseer/overseerd` from
  `/data/projects/livespec-overseer`, two-pane layout in tmux session
  `livespec-overseer`, real `$HOME` watch-set). **It is the ACTING supervisor
  of the real fleet now.**
- **Stages 1–2 (soak + isolated acting proof) are RETIRED as unexecutable:**
  the old daemon's render was the comparison baseline, and it died with the
  process. The one still-meaningful read-only check — a fresh
  `overseer/supervisor.py list` render diffed against the acting daemon's
  live pane — PASSED row-for-row on 2026-07-23 (single delta: one Ctx% cell
  read at a different instant; a timing artifact, not a classification
  difference).
- **First production evidence, day one:** the daemon correctly treated a
  malformed state-file token (`working: <prose>` written by another session)
  as no-declaration and surfaced it; that exposed `overseer-4dr` (the
  malformed-state alert re-fires every tick instead of edge-triggering —
  latent in the old code too); and it properly voided a ~23h-stale blocked
  declaration when its session resumed generating.

## THE ONE REMAINING GATE — Stage-4: PARTIALLY proven; rollback stays pinned

The gate is a REAL wrap-up → `ready` → restart round supervised by THIS
repo's daemon on a live track. As of 2026-07-23 the round is PARTIALLY
proven (evidence also recorded as a comment on epic `overseer-3wt`):

- **PROVEN — the declare-ready → atomic-restart interlock.** The acting
  daemon (restarted 22:29:38Z onto post-`overseer-4dr` master `73015e1`)
  logged `2026-07-23T22:49:57Z overseer: restarted
  /data/projects/livespec::fleet-pin-propagation (pane %21)`; the track's
  `ready` declaration was consumed at the same second (state dir emptied,
  mtime 22:49:57Z) and the pane came back as a fresh session with full
  context. Restart mechanics, state consumption, and no-double-restart all
  behaved.
- **UNPROVEN — the daemon-INJECTED wrap-up leg.** The observable log window
  (22:29:38Z onward) contains zero `injected wrap-up into` lines
  (`overseer/supervisor.py` `_log` format), and the restarted track's own
  record shows a SELF-initiated wind-down ("WINDING DOWN (context limit)",
  22:34Z). Pre-22:29Z daemon history is unrecoverable: the launch line's
  truncating `2>` redirect wiped it at restart — filed as
  `overseer-2boaoy`.

### Stage-4 self-completion — capture instructions for the post-restart session

The gate is expected to close ON THIS TRACK in the ordinary course: this
repo is in the daemon's watch-set, the default injection threshold is 50%
remaining (`registry.DEFAULT_CTX_THRESHOLD`), and the planning session runs
below it as it winds down. When the daemon injects the escalating wrap-up,
COMPLY with it (wind down, declare `ready` per
`overseer/marker-protocol.md`) — the compliance IS the evidence. The
POST-RESTART session must then promptly collect from
`tmp/overseer/daemon.log`:

1. the injection line — `injected wrap-up into
   /data/projects/livespec-overseer::cutover-and-shipping (ctx N%, bands
   [...])`;
2. the restart line — `restarted
   /data/projects/livespec-overseer::cutover-and-shipping (pane %N)`;
3. the ABSENCE of `tmp/overseer/cutover-and-shipping/.overseer-state`
   after that logged restart — the `ready` declaration is CONSUMED at
   restart, so absence-after-a-logged-restart is the EXPECTED evidence
   shape, not a missing artifact.

ACCEPTANCE BAR — do not weaken it: all three, from ONE round on THIS
track, with the injection line timestamped BEFORE the restart line. Then
record the lines verbatim as a comment on epic `overseer-3wt`, flip this
section from PARTIALLY proven to PROVEN, and ask the maintainer to unpin
the rollback. Working copies under `tmp/` (e.g.
`tmp/cutover-and-shipping-supervisor/`) are snapshots only; the DURABLE
record is this handoff plus the ledger.

The gate CLOSES when a daemon-injected wrap-up → `ready` → restart round is
observed end-to-end, or the maintainer rules the partial proof sufficient.
Until then, keep the rollback pinned: kill the daemon and relaunch the
byte-identical pre-seed state, recoverable from EITHER copy —

- core git history: `git -C /data/projects/livespec archive f9664481~1
  .claude/skills/overseer | tar -x -C <rescue-dir>`, or
- this repo at pin `6425828` and earlier.

Operationally: the daemon's stderr log is `tmp/overseer/daemon.log` in this
checkout (gitignored, runtime-only; truncated only when the DAEMON
restarts — supervised-session restarts do NOT touch it — until
`overseer-2boaoy` lands, so snapshot before any daemon restart);
the protocol contract is `overseer/marker-protocol.md`; the maintenance
invariants are `overseer/AGENTS.md`. This repo is in
`~/.livespec-overseer-repos.json`, so the daemon supervises this repo's own
plan threads — including this one.

Cross-track FACTORY turn-taking, coordinated in livespec core's
`tmp/fleet-pin-propagation-supervisor/status.log` until the orchestrator
exclusivity item `bd-ib-sd8o` lands (this track also has a dedicated
supervisor in tmux `cutover-and-shipping-supervisor` watching the slot):

- Agreed dispatch order as of 2026-07-23 ~23:00Z: x9o (running) →
  `overseer-m5dtmj` (OURS) → factory-success-rate-remediation drain a3–a8
  uninterrupted → `overseer-vlu5cd` (our re-queue).
- ONE dispatch host-wide at a time; launch only after the prior track's
  done-or-passing line AND a zero-foreign-`fabro-run-*` container check.
- Before killing ANY fabro container: verify ownership by its run-config
  argv (the config toml names the work item) — never by image shape,
  timing, or assumption; `exit 137` is AMBIGUOUS between a kill and normal
  teardown, never kill-proof.

## The rest of the scope, in rough order

Ledger-backed implementation goes through the factory dispatch route — the
`drive` operation (`--action impl:<id>`, after intake triage and the
admission valve) or the Dispatcher drain — never hand-coded in a planning
session.

1. **The groomed implementation queue** — the operator-surface slices
   `overseer-m5dtmj` (entry points) → `overseer-tn3hmi` (plugin + skill) →
   `overseer-5aaeyd` (canonical-command + install story), dependency-linked
   in that order, plus the independent `overseer-vlu5cd` (render header
   shows the pinned release semver) and `overseer-2boaoy` (daemon log must
   survive restarts). Compose current lanes from `list-work-items`; respect
   the cross-track factory turn-taking above when dispatching.
2. **`/overseer` operator surface from this repo** — DECIDED 2026-07-23
   (maintainer): ships as a fleet-standard plugin plus public entry points;
   reasoning and boundaries in `research/operator-surface.md` beside this
   handoff. The decision confirms the core-tenant items `livespec-b1uo.4`/
   `.5` (per-Driver thin bindings) unnecessary — their close stays staged
   in livespec core. Implementation is ledger work under `overseer-3wt`;
   groom before dispatch.
3. **Gate E** — arm the Result-railway role keys in `pyproject.toml` once
   livespec core's `rop-sweep-fleet-policy` thread lands `cvz`. Blocked
   until then; do not pre-arm (enforcement-before-adoption is the recorded
   hazard).
4. **Pin-queue hygiene** — #6 CLOSED 2026-07-23 as the sweep-replaced
   duplicate; #8 (freshness-sweep livespec-v0.20.1, still the latest
   livespec release) remains the live candidate for the bootstrap
   placeholder rewrite. Dev-tooling bumps flow normally through the pin
   queue; release-please #21 (livespec-runtime 0.11.1) awaits its cadence.
5. **Phase 2 — ship to adopter families** (D7/D8/D9, recorded on core epic
   `livespec-b1uo`): the overseer is Control Plane; ship it as a tool an
   adopter FAMILY may run against its own declarations — never reading
   `.livespec-fleet-manifest.jsonc` (D5). This is the thread's eventual
   payload; everything above clears the runway.

## Where the history lives

Reasoning behind the relocation, the seed, and the original staged protocol:
livespec core's `plan/archive/overseer-productization/handoff.md` plus this
file's own git history (the cutover-day sequence — the Stage-0 factory run,
the old daemon's death, the emergency relaunch — is recorded across this
repo's 2026-07-23 commits and the ledger records under `overseer-3wt`).
Nothing there is actionable anymore; this handoff is the single resumption
point.
