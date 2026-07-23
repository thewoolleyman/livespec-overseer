# Plan — cutover-and-shipping

**Owning repo:** `livespec-overseer`. **Status:** OPEN — created 2026-07-23 as
the SUCCESSOR of livespec core's `plan/archive/overseer-productization/`
(archived the same day). This repo drives its own overseer work; the core
thread is reference-only history.

**Ledger anchor:** epic `overseer-3wt` (this repo's beads tenant), children
`overseer-y8o`, `overseer-zvo`, and `overseer-4dr`. Status is READ from the
ledger (`list-work-items` / `next`), never stored here. The CORE-tenant epic
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

## THE ONE REMAINING GATE — Stage-4 proof; rollback stays pinned

The cutover is "proven" only once THIS daemon supervises a REAL
wrap-up → `ready` → restart round on a live track. Until then, keep the
rollback pinned: kill the daemon and relaunch the byte-identical pre-seed
state, recoverable from EITHER copy —

- core git history: `git -C /data/projects/livespec archive f9664481~1
  .claude/skills/overseer | tar -x -C <rescue-dir>`, or
- this repo at pin `6425828` and earlier.

Operationally: the daemon's stderr log is `tmp/overseer/daemon.log` in this
checkout (gitignored, runtime-only); the protocol contract is
`overseer/marker-protocol.md`; the maintenance invariants are
`overseer/AGENTS.md`. This repo is in `~/.livespec-overseer-repos.json`, so
the daemon supervises this repo's own plan threads — including this one.

## The rest of the scope, in rough order

Ledger-backed implementation goes through the factory dispatch route — the
`drive` operation (`--action impl:<id>`, after intake triage and the
admission valve) or the Dispatcher drain — never hand-coded in a planning
session.

1. **`overseer-4dr`** — edge-trigger the malformed-state alert (one SURFACE
   line per malformed episode, not per tick). Small, test-pinnable, and its
   fix directly improves the acting supervisor's signal-to-noise.
2. **`overseer-zvo`** — module-doc staleness sweep (SKILL.md's
   `.claude/skills/overseer/` paths and "local-only" framing, its retired
   `not-claude` status row, marker-protocol.md's "fleet manifest" phrase).
   Doc-only, dispatchable anytime.
3. **`/overseer` operator surface from this repo** — how the interactive
   pane's skill ships (plugin install path). The core-tenant items
   `livespec-b1uo.4`/`.5` (per-Driver thin bindings) are recommended
   closed-unnecessary; whatever replaces them is THIS thread's design call.
4. **Gate E** — arm the Result-railway role keys in `pyproject.toml` once
   livespec core's `rop-sweep-fleet-policy` thread lands `cvz`. Blocked
   until then; do not pre-arm (enforcement-before-adoption is the recorded
   hazard).
5. **Pin-queue hygiene** — PRs #6/#8 (duplicate livespec-v0.20.1 bumps,
   pre-seed) are still open and cannot merge as-is; close them when the
   freshness sweep replaces them. #10 was already superseded (dev-tooling
   bumps have since flowed: v0.51.10 → v0.52.0 landed, #22 carries v0.52.2);
   release-please #21 (livespec-runtime 0.11.1) awaits its normal cadence.
6. **Public entry-point surface for the two executables** — the deferred
   change behind the two demoted `reportPrivateUsage` warnings.
   `overseer-y8o` landed WITHOUT it, so it stands alone now; pairs naturally
   with scope item 3.
7. **Phase 2 — ship to adopter families** (D7/D8/D9, recorded on core epic
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
