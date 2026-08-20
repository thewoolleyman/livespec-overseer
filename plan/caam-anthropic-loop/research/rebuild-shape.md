# Rebuild shape — how the skill becomes a livespec-overseer plugin skill

**Ledger anchor:** epic `overseer-54k2za`. Mutable plan state — status, next
action, handoff entries — lives on that epic and its children. This note is
write-once research and is never authoritative about what remains.

Companion to `feature-inventory.md`, which enumerates **what** must be
reproduced. This note is **where it goes, how it is tested, and in what order** —
measured against this repo's tree on 2026-08-20. Re-measure before trusting any
path or count.

## The mandate, stated precisely

The maintainer owns and wrote the current implementation. This thread does not
redesign it and does not improve it. It **re-implements the same behavior** in
this repo, under this repo's discipline, and then **proves the reproduction is
complete** with an independent review.

Three properties, and they constrain each other:

1. **Feature-identical.** Every carrier in `feature-inventory.md` (A1–U9) is
   reproduced, including the constants, the exact log strings, the sleep
   durations, the column widths, and the failure texts. Where a behavior is
   deliberately absent (P18 "no retry, no recovery"), the absence is the feature.
2. **Red-green-refactor.** Every product `.py` commit lands as a Red→Green pair
   under this repo's `check-red-green-replay` gate. The current implementation has
   **zero tests**; the rebuild's value is that its behavior is pinned.
3. **Spec-driven.** The supervision contract in `SPECIFICATION/` governs. The
   thread opens with a `/livespec:propose-change` so the operation is specified
   before it is built, not narrated afterwards.

The tension worth naming up front: (1) and (2) pull against each other. Red-green
tempts you to test the behavior you find easy to reach and quietly drop the rest;
feature-identity demands the awkward ones — the wrapping picker, the display-width
padding, the two-pass label match. **The inventory is the arbiter, and the exit
gate checks the inventory, not the test count.**

## Target surfaces in this repo

Measured from `6833264` ("bind the grooming operation into all three harnesses"),
the most recent skill addition, plus `4ac61b0` which added its prose.

### The operation contract (harness-neutral)

| path | role |
|---|---|
| `.claude-plugin/prose/caam-anthropic-loop.md` | the complete operator contract — the LLM-facing half (inventory sections **A**, **B**) |

Peers: `foreman.md` (16 KB), `grooming.md` (21 KB), `overseer.md` (39 KB),
`supervise-plan.md` (47 KB). This is where the schedule-installation dialogue, the
mode resolution, and the reporting contract live.

### The three harness bindings (thin; no behavior)

| path | harness |
|---|---|
| `.claude-plugin/skills/caam-anthropic-loop/SKILL.md` | Claude Code — frontmatter `name`/`description`/`allowed-tools`, resolves `${CLAUDE_PLUGIN_ROOT}/prose/…` |
| `.claude-plugin/.codex-plugin/skills/caam-anthropic-loop/SKILL.md` | Codex — frontmatter `name` + `description` only, `$PLUGIN_ROOT` resolved **explicitly** in the body |
| `.claude-plugin/.pi-plugin/skills/livespec-overseer-caam-anthropic-loop/SKILL.md` | pi — note the flattened `livespec-overseer-<op>` directory name |

Each binding adds **no** operation behavior. `tests/test_bindings_reference_their_prose.py`
already gates that they point at their prose.

### Manifests, in lockstep

`.claude-plugin/plugin.json`, `.claude-plugin/.codex-plugin/plugin.json` and
`.claude-plugin/marketplace.json` each carry a version bumped together;
`tests/test_plugin_manifest_lockstep.py` gates it. The grooming commit touched all
three.

### The implementation

The Python goes in the `overseer/` package with **beside-tests** (68 `test_*.py`
files there today), not in a markdown fence. Module naming follows the existing
convention — `foreman_*.py` for the foreman operation's collaborators, `_supervisor_*.py`
for the daemon's. This operation is a peer, so `caam_*.py` (public entry points) and
`_caam_*.py` (private collaborators).

`.claude-plugin/overseer/` is a **tracked, byte-identical materialized copy** of
`overseer/` (verified: `diff -q` is silent for a sampled module). Whatever
re-materializes it must run, or the plugin ships a package that does not match the
repo.

### Repo-level gates already in the aggregate

`just check` invokes, among others: `check-plugin-resolution`,
`check-skill-invocation-paths`, `check-plugin-manifest-lockstep`,
`check-codex-plugin-runnable-launcher`, `check-codex-skill-picker`,
`check-red-green-replay`, `check-no-workflow-edits`. A new skill must satisfy all
of them; several will fail on a partially-bound operation, which is useful — they
are the mechanical half of "is it really a first-class skill".

`tests/prompts/` additionally holds prose-quality gates
(`test_charters_carry_no_known_defects.py`, `test_generator_prose_is_defect_free.py`,
`test_module_docs_carry_no_known_defects.py`). The new prose file is scored by
whichever of those claim it. **Note the fenced-block hazard** recorded in
`CLAUDE.md`: those detectors read **fenced** bodies only, so a prose file that must
*show* a defective form as evidence uses an indented literal block instead. This
operation's prose has to quote tmux key sequences and a `/model` invocation, so
this is live, not theoretical.

## Testability — the actual engineering problem

The current program is untestable by construction: module-level constants read
`os.environ` at import, and every effect goes straight to `subprocess.run`,
`urllib.request.urlopen`, or an absolute path under `$HOME`. Reproducing it
faithfully **and** testing it means introducing seams without changing behavior.

This repo already has the conventions and, in two cases, the code.

### What already exists and should be reused

- **`overseer/tmuxio.py`** (519 lines) — `TmuxIO` plus `PaneDriver`,
  `SessionNameDriver`, `WindowLayoutDriver` Protocols. This is the established
  send-keys / capture-pane seam. Inventory **P1–P20** and **O1–O3** should drive
  tmux through it rather than shelling out to `/usr/bin/tmux` directly.
  Note **P19**: the absolute path is itself a requirement (`AGENTS.md` tmux-config),
  so verify `TmuxIO` already honours it rather than assuming.
- **`overseer/claude_sessions.py`** — `proc_ppid`, `proc_children`, `proc_environ`,
  `proc_comm`, `proc_starttime`, all already seam-injected via
  `_seams.PidToOptionalStr` / `PidToIntList` and already tested, including a
  corrupt-`/proc` suite (`test_claude_sessions_corrupt_proc.py`). Inventory
  **M3–M5** is a thin walk on top of these.
  **But**: `CLAUDE_CODE_SESSION_ID` appears **nowhere** in the package today
  (grepped 2026-08-20). The environ-scan for that key is genuinely new code, even
  though its primitives are not.
- **`overseer/_seams.py`** (138 lines) — the Protocol convention, with its rationale
  written down: seams *this repo declares* take keyword-only parameters and are
  `Protocol`s, not `Callable`s; seams declared **elsewhere** (`subprocess.run`,
  `time.sleep`, `shutil.which`) stay positional because they are invoked by code we
  do not own. New seams here follow that split — which matters immediately, because
  `time.sleep` (P1, P12, P13, P15) and `urllib.request.urlopen` (C7) are both
  foreign shapes.

### What must be newly seamed

| effect | inventory | note |
|---|---|---|
| HTTP GET to the usage endpoint | C1–C9 | must be fakeable to return 200/401/429/malformed bodies — C11's three-way control is a *test*, not just a comment |
| the clock | C6, D6, N2, R12, H4 | expiry skew, cache age, memo window, timestamp, `+inf` sort |
| `caam` subprocess | E1, I5, I7 | `status --json` and `activate`, with return codes |
| filesystem paths (`$HOME`) | C4, D1, D8, E3, K5 | vault, live creds, `~/.claude.json`, settings, state |
| `flock` | I1 | contended vs uncontended |
| `time.sleep` | P1, P12, P13, P15 | otherwise every picker test costs 3.4s |
| environment-read tunables | F1–F3, K2, N1, D6 | must be read at *call* time, not import time, or no test can vary them |

That last row is the one that silently defeats a naive port: `THRESHOLD =
float(os.environ.get(...))` at module scope is fixed for the life of the process,
so a test that sets the env var changes nothing. Converting these to
call-time-resolved configuration is a **refactor with no behavioral change** — it
belongs in the rebuild and must be pinned as such.

### The parts that are pure and should be tested hardest

These carry the algorithm and need no seams at all. They are where feature-identity
is won or lost, and they are cheap to cover exhaustively:

`weekly_left` · `binding` · `is_eligible` · the reserve-release retry · the
candidate sort key · `resets_at` · `fmt_duration` · `until` · `picker_rows` ·
`row_for_model` · the modular cursor arithmetic · `current_cell` · the effort-floor
comparison · the table row formatter.

Table-driven tests over these cover **F, G, H, K3–K4, P3, P6–P8, P10–P11, R2, R6,
R10** — the majority of the nuance — without touching a socket, a pane, or a clock.

## Proposed decomposition

Ordered so each slice is independently landable and independently reviewable. Each
becomes a child work-item of `overseer-54k2za` **after** the scope event and the
propose-change land.

| # | slice | carriers |
|---|---|---|
| 0 | **Spec first** — `/livespec:propose-change` specifying the operation, then `/livespec:revise` to ratify | governs all |
| 1 | **Pure decision core** — usage record, `weekly_left`, `binding`, `is_eligible`, reserve release, ranking, `resets_at` | F, G, H |
| 2 | **Rendering** — `fmt_duration`, `until`, `current_cell`, the table, the trigger header, every decision line | R, S1–S5 |
| 3 | **Credential + usage I/O** — `read_creds`, `live_token`, `fetch_usage`, Fable extraction, the expired-token skip | C |
| 4 | **Profiles, cache, state** — vault enumeration, `_`-exclusion, live/cached/dark sourcing, atomic state | D |
| 5 | **Active-profile identity** — `caam status --json` with the UUID fallback | E |
| 6 | **The switch** — flock, under-lock re-read, under-lock re-probe, activate, stick verification, exit codes | I, J1, S6–S9, T |
| 7 | **Effort floor** — settings.json single-key rewrite | K |
| 8 | **Session discovery** — pane → `CLAUDE_CODE_SESSION_ID` → transcript → model | M, N |
| 9 | **Picker driving** — idle guard, menu scoping, name matching, wrap arithmetic, second dialog, the no-horizontal-arrows invariant | O, P |
| 10 | **Enforcement orchestration** — the 1a/1b/2a/2b rules, per-session and whole-pass isolation, `--no-models` | L, Q |
| 11 | **Operation prose + three bindings + manifest lockstep** | A, B |
| 12 | **Exit gate** — independent feature-completeness review | all |

Slices 1–2 have no external dependencies and should go first: they are the highest
nuance-per-test-line in the set, and getting them landed proves the red-green ritual
is working before the awkward I/O slices arrive.

**Dispatch-safety, per `CLAUDE.md`.** Most of these are ordinary repository
changes and are dispatch-safe. Two cautions specific to this thread: the item text
must not carry a doubled-left-brace token (the prose quotes tmux format strings
like the pane-pid specifier — **describe them, do not paste them**, into ledger
records), and slice 12's deliverable is a review recorded on the ledger, which is
supervisor/host tier, not factory work.

## The exit gate

The user's stated exit condition, and the plan's archive gate, are the same thing:
**an independent review that the rebuild is feature-complete, especially the
nuances of the algorithm.**

Concretely, `archive_thread(...)` refuses until both legs pass — every child
disposed, and durable independent completeness-review evidence on the epic. For
this thread the reviewer's charge is narrower and stricter than the generic one:

1. Walk **every** carrier A1–U9 in `feature-inventory.md` against the rebuilt
   implementation and record a per-carrier verdict. Not a sample.
2. Treat the **vps-info program** as the oracle — read it, do not rely on this
   inventory alone. The inventory is a reading of the source and could have missed
   something; the review is the second reading that catches it.
3. Explicitly confirm the **stale-prose trap** was not re-implemented: no Fable
   tier, no Fable disqualification, no Fable-based trigger (F7, F8, G4, H1).
4. Confirm the deliberate **absences** survived: no retry/verification/recovery in
   picker driving (P18), no OAuth refresh anywhere (C10), no dependence on
   `caam status` alone (E2), no status-line model reads (M6), no horizontal arrows
   in any emitted key sequence (P16).
5. Confirm the **exact strings and constants** match — thresholds, defaults, sleep
   durations, format specifiers, `FAIL` texts, exit codes.
6. Have had **no role** in the implementation, and record the result through
   `record_completeness_review_evidence(...)`.

A self-review, an unrecorded result, or a sampled walk is not evidence.

Requirement 4 deserves its own line because it is the one a reviewer naturally gets
wrong: **absences do not appear in a diff.** A reviewer checking "is everything
present" scores 100% on an implementation that helpfully added retry logic to the
picker — and that addition is a regression against a maintainer decision, not a
bonus.

## Deliberate deferrals

Recorded here and on the scope event so the review can tell "missed" from "out of
scope".

- **Retiring the vps-info copy.** Cross-repo sequencing (delete, or leave a pointer
  to the new home) is not this thread's work. Deferred to a named follow-up once
  the rebuild is shipped and exercised.
- **Generalizing the `-foreman` suffix and the account set.** The suffix coupling is
  precisely why the skill belongs here (`AGENTS.md` says so). Making it configurable
  is a change in behavior and is out of scope for a feature-identical rebuild.
- **The `settings.json` `model`-key drift** (K11) — the maintainer left it alone
  deliberately. Reproduce that decision; do not fix it.
- **Cross-session cron deduplication** (T4) — `CronList` is per-session and
  in-memory. Not solvable from inside the skill.
- **Host provisioning of `caam` itself** (U1–U3) — stays vps-info's concern. This
  repo consumes the binary; it does not install or version it.
- **Upstream `caam` cosmetic bugs** (U8) — not ours.
- **Making the vault restore-safe** (U9) — an explicit non-goal upstream.
