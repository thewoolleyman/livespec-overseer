# Plan — cutover-and-shipping

**Owning repo:** `livespec-overseer`. **Status:** OPEN — created 2026-07-23 as
the SUCCESSOR of livespec core's `plan/archive/overseer-productization/`
(archived the same day). This repo now drives its own overseer work; the core
thread is reference-only history.

**Ledger anchor:** epic `overseer-3wt` (this repo's beads tenant), children
`overseer-y8o` and `overseer-zvo`. Status is READ from the ledger, never
stored here. The CORE-tenant epic `livespec-b1uo` stays in livespec core per
its own do-not-move ruling; its `.1`/`.2`/`.3` closes are evidence-staged
there for the maintainer, and `.4`/`.5` carry a recommended
close-as-unnecessary disposition (D7/D9).

## THE ONE STANDING RULE — no daemon cutover until the staged protocol passes

**Maintainer-declared 2026-07-23: do not cut the fleet's supervision over to
this repo's code until it is proven stable, in parallel, with its behavior
COMPARED against the old daemon's.** The OLD daemon (pid 1570280, started
2026-07-20 05:13:03 UTC, running livespec core's deleted-path code from
memory) remains the ACTING supervisor until stage 4 below completes. Leave it
running.

Two facts that make an eager relaunch wrong, both verified 2026-07-23:

1. **The running daemon is NOT equivalent to this repo's code.** It started
   ~18 hours before core's `d1b4428c` (watch-set → `$HOME`) landed, so its
   in-memory watch-set is still FLEET-MANIFEST-derived, while this repo's
   code reads `~/.livespec-overseer-repos.json`. Byte-identical files do not
   make the running PROCESS equivalent, and this code has never run as a
   long-lived daemon.
2. **This repo's two-pane bootstrap is broken** (`overseer-y8o`): stale
   `.claude/skills/overseer/` daemon path + `parents[3]` core-root traversal.
   Only the bare `overseer/overseerd` launch works from here today.

**Rollback exists in BOTH directions.** The pre-relocation tree is
byte-identical to this repo's pre-seed state and recoverable from core git
history (`git -C /data/projects/livespec archive f9664481~1
.claude/skills/overseer | tar -x -C <rescue-dir>`); this repo pins the same
bytes at `6425828` and earlier. If the old daemon dies before the protocol
completes, an emergency relaunch from EITHER copy is legitimate — the bytes
are proven identical; the protocol exists to prove RUNTIME equivalence.

## The staged cutover protocol

Literal dual-ACTING operation on the real fleet is DESIGNED OUT — the
singleton lock refuses a second daemon on the same mapping store, and all
durable state (mapping, round stamps, per-track state files) is shared, so
two actors would double-inject wrap-ups and race restarts. Hence the split:

- **Stage 0 — land `overseer-y8o`** under the ratified spec, so the
  sanctioned launch path exists in this repo.
- **Stage 1 — read-only parallel soak.** Run this repo's `supervisor.py list`
  (`act=False`) beside the live daemon against the real fleet, repeatedly
  across a soak window, and diff its table against the old daemon's render.
  Zero mutation risk. PASSING = zero unexplained row deltas. The ONE expected
  delta class is the watch-set source (manifest-derived in the old process vs
  `$HOME`-declared here); every observed delta is either explained to that or
  ruled a defect.
- **Stage 2 — isolated acting proof.** Using the scratch-`HOME` recipe in
  `overseer/AGENTS.md` §"How to exercise it live", run a full second daemon
  against a disposable demo repo + demo session and drive the complete
  inject → declare → restart cycle on THIS code. The real fleet is never
  touched.
- **Stage 3 — cutover, MAINTAINER-EXECUTED, at a quiet window.** Stop the old
  daemon, launch this repo's. Durable round state (stamps, notified bands,
  mapping rows) carries over by design; the only in-memory loss is the
  continuous-idle clocks, which merely DELAYS nudges — the safe direction.
  Immediately compare the first new ticks' table and `NEEDS YOU` block
  against the old daemon's last render; watch `tmp/overseer/daemon.log`.
- **Stage 4 — rollback stays pinned until proven.** The cutover is "proven"
  only once the new daemon has supervised a REAL wrap-up → `ready` → restart
  round on a live track. Until then, rollback = kill the new daemon and
  relaunch the byte-identical pre-seed state (either recovery command above).

**Wiring already done (2026-07-23):** `/data/projects/livespec-overseer` is
in `~/.livespec-overseer-repos.json`, so post-cutover the new daemon
supervises this repo's own plan threads. The OLD daemon needs no edit — its
manifest-derived watch-set admits any member checkout with a `plan/` dir, so
it picks this thread up automatically now that `plan/` exists.

## The rest of the scope, in rough order

1. **`overseer-zvo`** — module-doc staleness sweep (SKILL.md's
   `.claude/skills/overseer/` paths and "local-only" framing, its retired
   `not-claude` status row, marker-protocol.md's "fleet manifest" phrase).
   The seeded `SPECIFICATION/` already follows the CODE where those docs are
   stale; this brings the docs back in line. Doc-only, dispatchable anytime.
2. **`/overseer` operator surface from this repo** — after the cutover: how
   the interactive pane's skill ships (plugin install path). The core-tenant
   items `livespec-b1uo.4`/`.5` (per-Driver thin bindings) are recommended
   closed-unnecessary; whatever replaces them is THIS thread's design call.
3. **Gate E** — arm the Result-railway role keys in `pyproject.toml` once
   livespec core's `rop-sweep-fleet-policy` thread lands `cvz`. Blocked
   until then; do not pre-arm (enforcement-before-adoption is the recorded
   hazard).
4. **Pin-queue hygiene** — PRs #6/#8 (duplicate livespec-v0.20.1 bumps) and
   #10 (dev-tooling v0.51.8) predate the seed and cannot merge as-is; the
   freshness sweep regenerates them now that master is green. Close the
   leftovers when the sweep replaces them.
5. **Public entry-point surface for the two executables** — the deferred
   change behind the two demoted `reportPrivateUsage` warnings; pairs
   naturally with `overseer-y8o`.
6. **Phase 2 — ship to adopter families** (D7/D8/D9, recorded on core epic
   `livespec-b1uo`): the overseer is Control Plane; ship it as a tool an
   adopter FAMILY may run against its own declarations — never reading
   `.livespec-fleet-manifest.jsonc` (D5). This is the thread's eventual
   payload; everything above clears the runway.

## Where the history lives

The full Phase-1/Phase-2 record — gate-by-gate reasoning, the relocation, the
seed scoping and framing decision, the birth-procedure gotchas
(`CI_RUNNER_LABELS`, explicit-empty role trees, the export-telemetry scaffold
gap), and the staleness post-mortems — is livespec core's
`plan/archive/overseer-productization/handoff.md`. Read it for reasoning;
nothing there is actionable anymore.
