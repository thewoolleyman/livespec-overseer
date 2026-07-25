# Plan — ship-overseer-to-fleet

**Owning repo:** `livespec-overseer`. **Status:** **OPEN — nothing started.**
Created 2026-07-25 (maintainer supervisor brief 22) as the LIVING successor of
`plan/cutover-and-shipping/`, which archives once this thread exists.

**Ledger anchor:** epic **`overseer-hbr`** (this repo's beads tenant). Children
and lanes are READ from the ledger (`list-work-items` / `next`), never stored
here. It SUPERSEDES `overseer-19s` (the Phase-2-only epic, closed as superseded
— absorbed here as goal 6) so there is exactly ONE anchor.

> **Read this first:** the predecessor thread PROVED the daemon cutover and
> BUILT the operator surface. It did NOT get that surface into anyone's hands,
> and it did NOT test the specification at the top of the pyramid. Everything
> below is that gap. Treat every "shipped" claim you inherit with suspicion —
> the whole reason this thread exists is that "shipped" was structurally true
> and functionally false.

## Definition of done — the maintainer's six goals

The thread is NOT done until all six hold. Goal 6 is ABSORBED into 1–5, not run
beside them.

1. **`supervise-plan` ACTUALLY WORKS FLEET-WIDE** — auto-installed and available
   in EVERY fleet and adopter session, not just this repo. **"EVERY" means every
   CLAUDE-harness session: `.livespec.jsonc` declares Codex EXEMPT and
   `plan/cutover-and-shipping/research/operator-surface.md:27` records that
   exemption as a settled ruling.** Goal 1 does NOT silently reopen Codex scope;
   doing so needs an explicit superseding maintainer decision. "Works" includes the
   PROMPT TEXT it generates: `overseer-fitvmo` (a CHILD of `overseer-hbr`) carries
   required anti-stall guidance for the generated supervisor-handoff — see
   §"Prompt-text guidance goal 1 must incorporate".
2. **TOP-OF-PYRAMID e2e TESTS EXIST FOR ALL SCENARIOS** in
   `SPECIFICATION/scenarios.md`, **and** the rule that they must exist is present
   AND **enforced**. Arming that rule retires **the whole 54-entry
   `tests/heading-coverage.json` registry**, not just the 21 scenario rows — see
   §"Goal 2" for why the gate is registry-wide.
3. **The plugin is AUTO-RELEASED** like the other fleet plugins. **Goal 3 is
   ordered AFTER goal 2** — releasing arms goal 2's gate. See §"Ordering
   constraint: goal 2 BEFORE goal 3".
4. **The plugin is AUTO-INSTALLED** for the other fleet AND adopter members.
5. **The release pin is AUTO-BUMPED** for consumers.
6. **Phase-2 adopter-family shipping FOLDS INTO the above** — see
   `research/phase-2-adopter-shipping.md` beside this file. Goal 6 also carries
   the **residue-disposition conditions** in §"Goal 6 completion conditions",
   which exist so this thread cannot repeat the predecessor's burial failure.

## Ground truth — measured 2026-07-25 against origin/master

These are the numbers the goals move. Do not re-derive them to start work, but DO
re-measure before closing any goal.

### Goals 1 + 4 — the plugin is BUILT but FUNCTIONALLY UNSHIPPED

`.claude-plugin/` carries `marketplace.json`, `plugin.json`, `prose/` and
`skills/`, and `.livespec.jsonc` declares
`harnesses.claude.canonical_command = livespec-overseer:overseer`. So the plugin
EXISTS. But:

- It is installed in **ZERO** projects — `~/.claude/plugins/installed_plugins.json`
  carries no `overseer` key at all.
- It has **NO marketplace cache entry**, while every other fleet plugin does
  (`livespec`, `livespec-driver-claude`, `livespec-orchestrator-beads-fabro`,
  `livespec-orchestrator-git-jsonl` all have one under
  `~/.claude/plugins/cache/`).
- Independently corroborated by the maintainer: `supervise-plan` is **ABSENT** in
  another live fleet session (`worktree-location-enforcement`).

**Do not write or trust any claim that the skill "works" until goal 1 is
demonstrated in a session that is not this repo's.**

### Goal 2 — 21 scenarios, ZERO top-of-pyramid tests, and the rule is UNARMED

- `SPECIFICATION/scenarios.md` is 236 lines carrying **21** `## Scenario:`
  headings.
- There are **no** top-of-pyramid tests. The only tests are unit-tier
  beside-tests under `overseer/` (`test_supervisor.py`, `test_signals.py`, …).
  There is no `tests/e2e`, `tests/integration`, `tests/consumer`, or
  `tests/prompts` tree.
- `tests/heading-coverage.json` holds **54 entries, and ALL 54 are
  `test: "TODO"`** — 21 from `scenarios.md`, 14 `spec.md`, 8 `contracts.md`,
  6 `constraints.md`, 5 `non-functional-requirements.md`.

> **CORRECTION (2026-07-25, Codex adversarial review of PR #78).** An earlier
> draft of this file said "all **21/21** scenario entries". That number is the
> `scenarios.md` SUBSET, not the registry. Scoping goal 2 to 21 rows understated
> the arming debt by **33 entries**. The measurement below is the corrected one:
> `jq 'group_by(.spec_file)' tests/heading-coverage.json`.

**The "and enforced" clause is the subtle half, and it is registry-wide.** Two
DIFFERENT gates are in play, and conflating them is what produced the 21-vs-54
error:

- `check-heading-coverage` **direction 4** (the tier rule) applies **ONLY to
  `scenarios.md`** — it requires a scenario entry to map to an
  integration-tier-or-above test. It accepts `test: "TODO"` plus a
  tier-acknowledging reason as compliant, which is exactly what those 21 rows are.
- `check-no-todo-registry` (`livespec_dev_tooling/checks/no_todo_registry.py`) is
  the gate the severity lever `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST`
  controls, and it is **NOT scoped by `spec_file`**. Read the source: it walks the
  entire array and flags *every* entry whose `test == "TODO"`. Arming the lever
  therefore fails on **all 54**, not 21.

That variable is **set nowhere in this repo** — it appears only in a `justfile`
COMMENT, never in a workflow. So today all 54 TODOs **warn and can never fail
CI**.

### Goal 2's real size — the 21 are expensive, the 33 are probably cheap

All 54 rows must leave `TODO` before the lever can be armed, but they are **not
the same kind of work**, and sizing them as one lump will overestimate goal 2
badly. Direction 4's docstring is explicit: *"This direction applies ONLY to
`scenarios.md`; headings in `spec.md`, `contracts.md`, and `constraints.md` MAY
be exercised by unit-tier tests."*

The 54 rows fall into **three** buckets, not two. Audited 2026-07-25 against the
**445** beside-test functions this repo carries:

- **21 `scenarios.md` rows — EXPENSIVE.** They require integration-tier-or-above
  tests. The 445 existing unit-tier tests **cannot** satisfy them, however
  thorough. This is genuinely new construction, and it is the part needing the
  `tests/e2e` (or `integration`/`consumer`/`prompts`) tree that does not exist.
- **28 `spec.md` / `contracts.md` / `constraints.md` rows — PROBABLY CHEAP.**
  These accept unit-tier evidence. A keyword audit of all 27 behavioral headings
  found **candidate tests for every single one**, from 2 (`The restart
  interlock`, `Language and dependencies`) to 67 (`Supervised runtimes`). Median
  is around 20. Keyword matching proves candidates EXIST, not that they are apt —
  so confirm aptness per row — but do **not** budget these as new construction.
  The likely work is *mapping node ids into the registry*, not writing tests.
- **5 `non-functional-requirements.md` rows — AWKWARD, and the real snag.**
  These are `Boundary`, `Spec`, `Contracts`, `Constraints`, `Scenarios`:
  CONTRIBUTOR-facing meta-requirements about how the repo is developed and
  gated, not operator-observable behavior. Their evidence is mostly `just check`
  TARGETS (100% coverage, stdlib-only, pin-consuming gates, the red-green
  ritual), whereas the registry maps headings to **pytest node ids**. So they do
  not map cleanly in either direction. Decide deliberately: wrap each gate in a
  thin pytest assertion, or retire the rows by governed registry co-edit with a
  recorded reason. Do not let these five silently block arming the lever.

**The "map existing tests" strategy is only sound if those tests can FAIL — so
that was checked, not assumed.** `non-functional-requirements.md` §"Contracts"
requires safety-routing tests to be sabotage-verified, and this repo has already
shipped one toothless verifier (PR #75). So the routing guard was mutation-tested
on 2026-07-25: `_do_codex_restart`'s launch-command selection was deliberately
re-pointed at the CLAUDE command — the exact violation
`test_a_codex_ready_restart_never_issues_the_claude_command` exists to catch.

Result: **three independent tests went red**, not one —
`…_never_issues_the_claude_command`,
`test_an_adopted_codex_track_declaring_ready_is_restarted_with_the_codex_command`,
and `test_two_codex_tracks_sharing_a_tmux_session_each_restart_their_own_session`
— with a precise assertion. The sabotage was reverted immediately and the suite
restored to green with a zero diff.

So the existing unit-tier suite has real teeth on at least this safety-critical
path, and mapping it into the registry buys genuine evidence rather than laundering
a green tick. Re-verify per safety routing when touched, as the NFR requires.

> **Goal 2 is not merely a maintainer preference — the SPEC ALREADY REQUIRES IT,
> and the repo is currently NON-CONFORMANT.** `non-functional-requirements.md`
> §"Scenarios" states: *"Every scenario heading in `scenarios.md` maps to test
> evidence through the repository's heading-coverage registry; a scenario's
> evidence is integration-tier or better, never a unit-tier test."* That is
> ratified content, and 21/21 scenario rows are `TODO`. Goal 2 closes a live
> conformance violation against this repo's own specification.

### Ordering constraint: goal 2 BEFORE goal 3

**This is a hard dependency, not a preference.** `no_todo_registry.py` documents
that CI sets `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST=true` **for the
release context**. So goal 3 (auto-release) is precisely what ARMS goal 2's gate.

Wiring auto-release while any of the 54 TODOs remain means **the first release
run fails CI on all outstanding rows**. Sequence accordingly:

1. Retire the registry TODOs (goal 2) — or land the release wiring with the lever
   demonstrably not yet set in the release job, and arm it as the LAST step of
   goal 2.
2. Then wire auto-release (goal 3), and confirm the first release run is green.

An earlier draft of this file called goal 2 "largely independent, can run in
parallel" with 3/4/5. **That was wrong** — 2 and 3 are coupled through this lever.
The groom must treat 2→3 as an ordering edge.

This repo also does **not** declare `scenario_tiers` in `pyproject.toml`, so the
documented defaults apply (`tests.e2e`, `tests.integration`, `tests.consumer`,
`tests.prompts`) — whichever tree the tests land in must match one of those
prefixes, or the declaration must be added.

Goal 2 therefore has TWO halves: **write the tests**, AND **arm the gate** so the
rule is enforced rather than merely documented.

### Goals 3 + 5 — release automation is PARTIAL

`.github/workflows/` carries `release-please.yml`, `release-dispatch.yml`,
`bump-pin-from-dispatch.yml`, `pin-freshness.yml` and `ci.yml`. release-please
already versions the PACKAGE — the daemon render header shows `0.11.0`, wired by
`overseer-vlu5cd`. What is missing is the **plugin** half: it is not wired into
the fleet marketplace / auto-install / auto-bump path the other plugins use.
`.claude-plugin/plugin.json` still reads version **`0.1.0`** against the package's
`0.11.0`, because `plugin.json` is absent from release-please's `extra-files`.

**`release-dispatch.yml` announces this repo under the WRONG NAME.** Line 27 says:

```yaml
source_repo: livespec-runtime
```

Every peer names ITSELF (`livespec`, `livespec-dev-tooling`,
`livespec-driver-claude`, `livespec-orchestrator-beads-fabro`,
`livespec-runtime` all self-name); `livespec-overseer` is the **sole mismatch** —
an uncorrected copy-paste. A published overseer release would be announced to
consumers as a `livespec-runtime` release, so this breaks **goal 5**'s pin path
as well as goal 3. Fixing it is goal-5 work that already exists; it is not new
scope.

**A release lane is ALREADY IN FLIGHT — and the bug above ALREADY FIRED.** There
are **TWO** open release PRs, both titled `chore(master): release 0.12.0`:

| PR | branch component | state |
|---|---|---|
| **#21** | `…--components--livespec-runtime` | CONFLICTING — orphaned debris |
| **#52** | `…--components--livespec-overseer` | MERGEABLE, green |

The root cause is a **scaffold copy-paste that was only PARTIALLY fixed**:
`ceaca74` scaffolded this repo with `package-name: "livespec-runtime"`, and
`6421590` corrected it — **in `release-please-config.json` only**. PR #21 is the
artifact release-please opened while the component was still misnamed; #52 is
its correct successor from the day after the fix. #21 can never merge and should
be **closed as orphaned**. The repo has **zero** tags and **zero** releases.

The same scaffold residue also survives in two header comments that name the
wrong repo — `.mise.toml:1` and `lefthook.yml:1`. Cosmetic, but sweep them with
the `source_repo` fix. Full trace on **`overseer-hbr.1`**.

> **CORRECTION (2026-07-25, Codex adversarial review of PR #78).** The
> §"NEXT ACTION" claim "Nothing is started. Nothing is in flight." is FALSE as
> written — PR #52 is in flight. The accurate statement is that **no successor
> slice** has started. See that section.

## NEXT ACTION — groom the six goals into slices

**No successor SLICE has started.** That is not the same as "nothing is in
flight": release PR **#52** (`chore(master): release 0.12.0`) is open and
mergeable right now — see §"Goals 3 + 5". Check it before grooming goal 3, and
decide deliberately whether it merges before or after the `source_repo` fix,
since merging it as-is publishes under the wrong `source_repo`.

1. **GROOM** the six goals into dependency-layered, buildable slices under
   `overseer-hbr`, via `/livespec-orchestrator-beads-fabro:groom` — a read-only
   drafting conversation; **the maintainer OWNS every cut and every acceptance**,
   and the front-end files nothing until approval.
2. **Then build** through the normal machinery (`drive --action approve:<id>`
   then `impl:<id>` for factory-tier work).

Ordering for the groom. One edge is a MEASURED HARD CONSTRAINT, the rest is
hypothesis:

- **HARD — `2 → 3`.** Auto-release arms `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST`
  in the release context, which fails on all 54 registry TODOs. See
  §"Ordering constraint: goal 2 BEFORE goal 3". This one is not the maintainer's
  to accept or replace — it falls out of `no_todo_registry.py`'s source.
- **Hypothesis — `3 → 4 → 1`** (a plugin must be releasable before it can be
  auto-installed, and auto-install is what makes `supervise-plan` actually
  available), with **5 following 3**. Starting hypothesis only; the maintainer
  owns this cut.

Goal 2 is **NOT** independent and must not be planned as a parallel lane.

`research/phase-2-adopter-shipping.md` is a **DRAFT SHAPE**, not a slice list —
its own text reserves every cut to the maintainer. It carries three open
questions that likely gate the cut:

1. **Marketplace hosting** — does this repo publish its own plugin marketplace
   (as livespec core does), or join an existing family marketplace? This one
   probably has to be answered FIRST, because goals 3/4 depend on the answer.
2. **Is the Codex arm in scope for first ship?** `.livespec.jsonc` declares
   `codex: exempt` today, though the daemon half is already harness-neutral.
3. **Does "shipped" warrant a SPECIFICATION scenario?** That would route through
   `/livespec:propose-change` — spec-side and human-gated. Note the interaction
   with goal 2: a new scenario adds a 22nd heading that itself needs a
   top-of-pyramid test and a `tests/heading-coverage.json` co-edit.

## What the predecessor already landed — do NOT redo

Daemon cutover **PROVEN** (Stage-4 twice); the acting daemon runs this repo's code
on latest master; `SPECIFICATION/history/v002` ratified. Accepted items:
`overseer-m5dtmj` (entry points), `overseer-tn3hmi` (plugin scaffold),
`overseer-myjovi` (`supervise-plan` **BUILT** — not fleet-available),
`overseer-vlu5cd` (version-in-header), `overseer-kfbcv4` (telemetry argv),
`overseer-2boaoy` (daemon-log append), `overseer-5aaeyd` (canonical command +
adopter install story, D5 boundary documented in the README), `overseer-6uobos`
(supervision surfaces A+B, live-exercised), plus `overseer-3o9`, `overseer-y8o`,
`overseer-4dr`, `overseer-zvo`, `overseer-tvko3z`.

Full evidence: the predecessor thread — at `plan/cutover-and-shipping/` until it
archives, then `plan/archive/cutover-and-shipping/` (the archive move lands in
its own PR right after this thread merges) — and the comments on epic
`overseer-3wt`.

## Standing bounds

From the D-codes on core-tenant epic `livespec-b1uo` (which stays in livespec
core per its own do-not-move ruling):

- **D5** — never read the fleet manifest. A family's own
  `~/.livespec-overseer-repos.json` is the ONLY discovery input. This is the
  boundary `overseer-5aaeyd` already documented in the README, and goal 4 must not
  quietly breach it: auto-installing the plugin is a HARNESS concern, never a new
  discovery input for the daemon.
- **D7** — Control Plane, peer of the console; never a console component.
- **D8 / D9** — repo class is `control-plane-tool`, which is why this repo is an
  ordinary pin-consuming fleet member.
- No new ledger state; no new store paths.

## Prompt-text guidance goal 1 must incorporate

**`overseer-fitvmo`** (P2 bug, `pending-approval`) is a **CHILD of `overseer-hbr`**
— a hard ledger edge, since it lives in this same tenant. It is not a generic bug:
it carries GUIDANCE FOR THE SUPERVISOR-HANDOFF PROMPT TEXT, which is precisely what
goal 1 must get right. Filed 2026-07-25 by the now-archived `supervisor-skill`
session, after that supervisor treated another track's ownership of a lane as
permission to STOP while non-conflicting work still existed.

What the GENERATED prompt text must contain:

- A conflicting lane is **NOT** a blocked state — say so explicitly.
- A **No Idle / No Silent Block** decision procedure: (1) stand down ONLY on the
  conflicting action owned by another track; (2) enumerate the remaining
  non-conflicting work; (3) drive the next concrete safe action immediately;
  (4) only if no legitimate non-conflicting action exists, ask exactly ONE
  maintainer-facing blocking question, recommended answer FIRST.
- Stale queued input: **IDLE with queued input means STUCK** — it needs a safe
  nudge/clear/ask, not passive waiting.
- The anti-stall rule must be PROMINENT in the generated markdown, not buried.
- Regression fixtures must FAIL on wording equivalent to "all remaining action
  belongs elsewhere, stand down" that lacks next-action enumeration or a
  maintainer question.

**Consequence:** goal 1 is NOT satisfied by mere availability. A skill that is
installed everywhere but generates stall-prone prompts has shipped a behavioral
defect fleet-wide. The groom decides whether this is its own slice or folded into
the goal-1 slice — either way it is a PRECONDITION of goal 1's acceptance.

Convenient reference: this thread's own `supervisor-handoff.md` already implements
the procedure (its §"No idle, no silent block"), so it doubles as candidate
wording for the generated template.

## Goal 6 completion conditions — the residue this thread must DISPOSE OF

> **ADDED 2026-07-25 (Codex adversarial review of PR #78 — BLOCKER finding).**
> The six goals as originally written covered the predecessor's "What it did NOT
> do" section cleanly, but did **not** cover the residue the predecessor
> acknowledged as "tracked elsewhere". "Elsewhere" had no anchor — which is
> exactly the burial this thread was created to prevent. These items are now
> completion conditions of goal 6.

**A disposition is not the same as implementation work.** Each item below is
discharged by a DURABLE, recorded decision — proving a gap is already
implemented, or a child unnecessary, is a perfectly good disposition. What is
NOT acceptable is leaving any of them in an unanchored "tracked elsewhere"
state.

1. **The 7 untied spec→impl gaps** from the v002 delta. Reproduce with
   `/livespec-orchestrator-beads-fabro:detect-impl-gaps --since-version v001 --json`
   (read-only; never mutates the store). Run first-hand 2026-07-25 — it returns
   exactly **seven**, and a `bd list --all --json` sweep of all 22 tenant items
   finds **zero** references to any of them and zero items carrying a `gap_id`:

   | gap id | location |
   |---|---|
   | `gap-jqszyzae` | `constraints.md` › livespec-overseer — constraints |
   | `gap-lqxagafn` | `spec.md` › Non-interference with tracked work |
   | `gap-mgjjuo3n` | `spec.md` › Notify, never block |
   | `gap-pd54ut36` | `spec.md` › Supervised runtimes |
   | `gap-h5sj7scj` | `spec.md` › The cardinal rule |
   | `gap-opeyzo5y` | `spec.md` › The escalating wrap-up |
   | `gap-4vy63slp` | `spec.md` › The escalating wrap-up |

   **Read this set correctly before slicing it.** All seven are MUST clauses in
   the CORE supervision contract, and the daemon already carries 100%
   statement+branch coverage across all 12 modules, with the cardinal rule and
   the wrap-up escalation both live-exercised (Stage-4, twice). The LIKELY
   disposition for most is *"already implemented, recorded as satisfied"* — do
   **not** manufacture seven slices. Re-run the detector before disposing; the
   set is a pure function of spec text and moves when the spec is revised.

   **Connection to goal 2 — related, but NOT the same question.** Be precise
   here, because conflating them mis-sizes both:

   - A **gap** asks *"is this MUST clause IMPLEMENTED?"* Spot-checked
     `gap-h5sj7scj` (cardinal rule, "the daemon MUST NOT infer readiness"):
     `supervisor.py` encodes it explicitly (*"`ready` is the SOLE authorization
     for a restart"*) and 35 of the 445 beside-tests exercise ready/restart,
     including `test_idle_at_danger_with_no_declaration_is_never_restarted` —
     the cardinal rule almost verbatim. So this gap's disposition is
     **"implemented, record it"**, not build work. That is evidence FOR the
     "don't manufacture seven slices" warning above, not merely a hope.
   - A **registry row** asks *"is there a test AT THE REQUIRED TIER mapped to
     this heading?"* For `scenarios.md` rows the answer is no and unit tests
     cannot help (see §"Goal 2's real size").

   So an implemented-and-unit-tested rule can be a satisfied GAP and still a
   `TODO` REGISTRY ROW at the same time, with no contradiction. Six of the seven
   gaps sit in `spec.md`, whose 14 registry rows DO accept unit-tier tests — so
   for those, one audit pass can plausibly settle both ledgers at once. That
   convenience does **not** extend to the 21 scenario rows.
2. **Core epic `livespec-b1uo` and children `.1`–`.5`.** Re-verified first-hand
   2026-07-25 against the CORE tenant: `livespec-b1uo` `backlog`; `.1/.2/.3`
   `backlog`; `.4/.5` `blocked`. The epic STAYS in core per its own do-not-move
   ruling — disposition means RECORDING the outcome, not migrating items.
   **Four of the six already have determinable dispositions, none needing build
   work** (full evidence on `overseer-hbr.2`):

   - **`.1`** "move the overseer to the new livespec-overseer repo" — **DONE.**
     This repo carries the full `overseer/` package (12 modules — the 8
     substantive ones plus `__init__`/`daemon`/`streams`/`version` — all at 100%
     statement+branch coverage, beside 10 test modules) and the acting daemon
     (pid 2954933) runs from it. Close as delivered.
   - **`.3`** "decouple the shipped overseer from the fleet manifest (D5)" —
     **DONE, verified at code level.** The shipped path
     (`supervisor.py:2810`/`:2824`) calls only `watch_set_from_config` reading
     `$HOME/.livespec-overseer-repos.json`; the manifest-seeded `watch_set()` is
     **not defined anywhere** any more, and no non-test code reads
     `.livespec-fleet-manifest.jsonc`. Close as delivered.
   - **`.4`/`.5`** driver bindings — `operator-surface.md:27` already rules them
     **unnecessary**. Close as such. They still read `blocked` only because that
     ruling lives in this repo's research file and was never reflected in core.
   - **`.2`** Linux+tmux precondition (D4) — genuinely core-side work on core's
     own spec and gates. No disposition available from here; leave with core.
3. **`check-no-workflow-edits` copy-drift** across the 4 carrying fleet repos.
   Single-sourcing into `livespec-dev-tooling` is dev-tooling's call, **not this
   thread's** — so this is EXPLICITLY OUT OF SCOPE here, owned by
   `livespec-dev-tooling`. Goal 6 is discharged for this item by naming that
   owner, which this line does. Do not silently re-absorb it.
4. **`overseer-3wt`'s OWN un-migrated payload — a HARD PRECONDITION on Phase 3.**
   Tracked as **`overseer-hbr.6`**. The predecessor epic lists five numbered
   items in its description, and the predecessor plan's Phase 3 **closes that
   epic**. Verified 2026-07-25: items 1, 2 and 4 are genuinely done (4's PRs
   #6/#8/#10 are all closed), but **items 3 and 5 are not, and no goal covers
   them**:

   - **Item 3 — "Gate E: arm the Result-railway role keys."** This is a
     **705-finding latent CI failure**, not a config line. `just check` emits 705
     Phase-0 WARN diagnostics across 23 files, each stamped *"hard-fails once
     this repo is flipped to the hard gate in Phase 2"*: 600 missing `*`
     keyword-only separators, 45 banned cross-module `_`-prefixed calls, 23 files
     with no declared semantic role, 21 modules missing `__all__`, 7 over the
     LLOC ceiling, 7 banned process terminations outside `bin/`, 2 misc. **Same
     pattern as goal 2's lever** — a rule that runs and reports but cannot fail,
     so debt accrues invisibly. Worse: the flip is driven by the FLEET ROP
     program (core `livespec-gcsn`, `livespec-h2hs`, `livespec-qgp2jt`), so an
     upstream decision this repo does not make can turn it red.
   - **Item 5 — the deferred public entry-point surface** for the two
     executables (the demoted `reportPrivateUsage` findings). No successor
     anchor.

   **`overseer-3wt` MUST NOT CLOSE until 3 and 5 each have a durable
   disposition.** Also check what the release context sets before goal 3 lands —
   if the ROP phase flip is release-scoped like goal 2's lever, the first
   auto-release surfaces both debts at once.

## Also open, tracked elsewhere

Everything formerly listed here is now a goal-6 completion condition above — the
section is kept only so a reader arriving from the predecessor thread's wording
lands somewhere real instead of on a removed heading.

## Operational map

Supervision runs against the live fleet: daemon in tmux `livespec-overseer:1.1`,
stderr log `tmp/overseer/daemon.log` (appends — `overseer-2boaoy`). Protocol:
`overseer/marker-protocol.md`. Invariants a change must not regress:
`overseer/AGENTS.md`. Operator surface contract: `overseer/SKILL.md`. Cross-track
coordination log (shared, still active — append only, never rewrite): livespec
core `tmp/fleet-pin-propagation-supervisor/status.log`. This thread's supervisor
charter: `supervisor-handoff.md` beside this file.
