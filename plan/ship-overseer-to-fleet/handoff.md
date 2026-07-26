# Plan — ship-overseer-to-fleet

**Owning repo:** `livespec-overseer`. **Status:** **ALL SIX GOALS MET.** The
plugin is RELEASED (through v0.12.3), REGISTERED in all twelve consuming repos,
and INSTALLED on the host for **all twelve** — nine fleet members plus all three
adopters — with `supervise-plan` proven to RESOLVE by live exercise in eleven
sessions that are not this repo's. **All 23 children of `overseer-hbr` are
closed.** Whether to close the epic is the maintainer's call. Read §"NEXT
ACTION" — it was rewritten 2026-07-26 (third wrap-up) and SUPERSEDES every
earlier status statement in this file.

<!-- Superseded headers, kept so a reader arriving from an older revision lands
somewhere real. This has read, in order: "OPEN — WAITING ON MAINTAINER VALVES",
then "OPEN — SHIPPING", now "OPEN — ONE ITEM LEFT". Goal 2's arming (`.20`),
which an earlier version of this paragraph named as the remaining work, is
DONE. --> Goal 2 is **COMPLETE, both halves**: all **54** registry rows map to a
test, **0 TODO**, 21 of 21 `scenarios.md` rows are pinned at integration tier,
and the lever fired green on the release path. Goals 1, 3 and 5 are met for the
fleet. **The one buildable row is `.23`** (goal 4's adopter arm), and it needs
the maintainer's `approve:` valve first. Created 2026-07-25 (maintainer
supervisor brief 22) as the LIVING successor of
`plan/archive/cutover-and-shipping/` (archived 2026-07-25). Groomed 2026-07-26
into 13 filed slices; **all 13, plus all nine pre-existing children, are now
DONE** — see §"NEXT ACTION", which is the only section you must read before
starting.

**Ledger anchor:** epic **`overseer-hbr`** (this repo's beads tenant). Children
and lanes are READ from the ledger (`list-work-items` / `next`), never stored
here. It SUPERSEDES `overseer-19s` (the Phase-2-only epic, closed as superseded
— absorbed here as goal 6) so there is exactly ONE anchor. **That anchor is why
groom Step 3 was not run** — it would have closed this epic; see §"NEXT ACTION".

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
   `research/operator-surface.md:27` records that exemption as a settled ruling
   — that file is at `plan/archive/cutover-and-shipping/research/`.** Goal 1 does
   NOT silently reopen Codex scope;
   <!-- operator-surface.md placement: SETTLED 2026-07-26 — it STAYS in the
   archive and is cited by its post-archive path. That was overseer-hbr.3's open
   question ("git mv it into the successor research tree, or leave it and cite
   the archive path?"), and it is settled by observation rather than by a new
   decision: it was never moved, and every surviving citation now carries the
   archive path. HAZARD THIS LEAVES: a LIVE ruling now lives under plan/archive/.
   If that archive is ever pruned, carry this ruling forward FIRST — the Codex
   exemption and the livespec-b1uo.4/.5 "unnecessary" ruling both rest on it. -->

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

> **SUPERSEDED 2026-07-26 (second wrap-up). This heading is now BACKWARDS for the
> fleet.** The plugin is registered in all twelve consuming repos and INSTALLED
> for the nine fleet members; `known_marketplaces.json` carries it, the cache
> carries both skills, and `installed_plugins.json` has nine project entries.
> `supervise-plan` RESOLVES in sessions that are not this repo's. The subsection
> is kept because the *diagnosis* below — registration, not packaging — was
> correct and is what got acted on, and because the "treat 'shipped' with
> suspicion" instruction earned its keep twice more today (see §"NEXT ACTION" on
> registration-is-not-installation, and on the release ref predating the fix).
> **Still true:** the three ADOPTERS are registered but not installed — `.23`.

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

**The blocker is REGISTRATION, not packaging — and it already has an owner.**
Verified 2026-07-25: the plugin ships both skills
(`.claude-plugin/skills/overseer/SKILL.md` and `…/supervise-plan/SKILL.md`), and
its `marketplace.json` declares `"source": "./.claude-plugin"` — **identical to
all four working fleet peers** (`livespec`, `livespec-driver-claude`,
`livespec-orchestrator-beads-fabro`, `livespec-orchestrator-git-jsonl`). Nothing
is malformed. What is missing is that `livespec-overseer` is absent from
`~/.claude/plugins/known_marketplaces.json`, which lists 10 marketplaces.

> **CORRECTION (2026-07-26, measured).** "Absent from `known_marketplaces.json`"
> is true but **incomplete**, and taking it as the whole blocker would send the
> next reader at an impossible task. Registering in the peers' observed shape is
> **currently impossible**: all four peer registrations pin **`ref: "release"`**,
> that branch is produced by `fast-forward-release-branch.yml` on
> `release: published`, and this repo has **no such workflow, no `release`
> branch, and zero releases**. See the **HARD `3a → 4`** edge in §"NEXT ACTION".
> Registration itself is a *tracked-file* change — `.claude/settings.json` →
> `extraKnownMarketplaces` + `enabledPlugins`, checked in per consuming repo (six
> fleet repos carry the identical 3-entry shape today; no copier template exists,
> so it is an explicit per-repo sweep).

That registration step is **`livespec-cbmw`** — an item in the livespec CORE
tenant ("Wire livespec-overseer into the fleet: wire-fleet-member + GitHub App
install"), the direct mirror of the closed precedent `livespec-inxg`. **No goal
references it**, which is a goal-4 scope leak; tracked as **`overseer-hbr.8`**.

> **CORRECTION (2026-07-26, re-measured). `livespec-cbmw` is FULLY stale — all
> three legs, not two — and should CLOSE.** An earlier draft called it "partially
> stale" with `app-installation` possibly remaining. Measured:
>
> - `merge-settings` and `delete-branch-on-merge` — **RESOLVED.**
>   `check-fleet-conformance` reports **"fleet conformance passed", 9 members, 0
>   blind rows**. **Run it from `/data/projects/livespec-dev-tooling`, NOT from
>   here** — see the correction below.
> - `app-installation` — **also discharged, and re-confirmed 2026-07-26.** The
>   fleet GitHub App IS installed on this repo: PR #52 is authored by
>   **`app/livespec-pr-bot`**, and `release-please.yml:58-61` mints the App token
>   from `secrets.APP_ID` / `APP_PRIVATE_KEY` via
>   `actions/create-github-app-token@v1`.
>
> **Precision worth keeping:** the conformance run itself declares
> `app-installation` **out-of-vantage** for the local lane (it is owned by the
> lane running under the App installation token), so *the pass does not prove
> that leg*. The App-bot authorship does, independently — and that is the leg
> you can verify from here without any conformance run at all. Disposition
> tracked on **`overseer-hbr.21`** (S12).

> **CORRECTION (2026-07-26, measured). The re-run instruction above was
> UNFOLLOWABLE AS WRITTEN, and this is the `overseer-hbr.4` defect class again —
> a durable record shipping an instruction that reads runnable and is not.** An
> earlier revision said "**Re-run `check-fleet-conformance` before acting on that
> item**" with a `LIVESPEC_RUN_FLEET_CONFORMANCE=true` lever, as though it were a
> recipe here. It is not:
>
> - absent from THIS repo's justfile (the only "fleet" match is
>   `check-fleet-marketplace-relative-sources`);
> - absent from livespec core's **96** recipes (zero matches for "conform");
> - absent from the pinned dev-tooling's `checks/` package (only
>   `fleet_marketplace_relative_sources`).
>
> It exists **only in `livespec-dev-tooling`'s own justfile**, whose comments
> call it a *repo-private extra*, beside `check-fleet-conformance-admin` — the
> ADMIN-vantage lane running the rows that need admin scope "which no App-token
> context can read", under the operator's own `gh` credentials at pre-push, and
> deliberately absent from CI.
>
> **So: `cd /data/projects/livespec-dev-tooling && just check-fleet-conformance`,
> plus the `-admin` lane for the admin-scope rows.** That also explains the
> out-of-vantage note above — it is the check's design, not a caveat about this
> repo.

### Goal 2 — 21 scenarios, ZERO top-of-pyramid tests, and the rule is UNARMED

> **SUPERSEDED IN PART (2026-07-26).** This subsection is the 2026-07-25 baseline
> and is kept because the *analysis* below (the three buckets, the two-gate
> distinction, core as the worked example) is still the right map. But every
> NUMBER in it has moved, and its "ZERO top-of-pyramid tests" heading is now
> exactly backwards:
>
> - **All 54 registry rows are mapped. `0` TODO.** `.17` retired the 26 cheap
>   rows (PR #93), `.18` the 7 awkward ones (PR #96), and `.19` all 21
>   `scenarios.md` rows across four slices (PRs #97, #100, #102, #103) — each
>   sabotage-verified.
> - **A `tests/integration/` tree now exists** carrying 4 modules and 22 tests,
>   this repo's first evidence above the unit tier.
> - The lever is still **UNARMED** — that part holds, and `.20` is still last.
>   But it now has **nothing left to fail on**, so the `2 → 3b` edge is
>   discharged from goal 2's side.
>
> Re-measure before relying on any count here.

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

### Goal 2's real size — three buckets, and the awkward one is the trap

All 54 rows must leave `TODO` before the lever can be armed, but they are **not
the same kind of work**, and sizing them as one lump will overestimate goal 2
badly. Direction 4's docstring is explicit: *"This direction applies ONLY to
`scenarios.md`; headings in `spec.md`, `contracts.md`, and `constraints.md` MAY
be exercised by unit-tier tests."*

All 54 rows were audited individually on 2026-07-25 against the **445**
beside-test functions this repo carries. They settle at **21 expensive / 26
cheap / 1 removal candidate / 6 gate-backed**:

| bucket | rows | what it costs |
|---|---|---|
| **Expensive** | 21 — all of `scenarios.md` | genuinely new integration-tier-or-above tests |
| **Cheap** | 26 — 14 `spec.md`, 8 `contracts.md`, 3 `constraints.md`, 1 NFR | MAP an existing node id; no new test |
| **Removal candidate** | 1 — NFR §`Boundary` | a registry row over a document preamble |
| **Gate-backed** | 6 — 3 `constraints.md`, 3 NFR | evidence is a `just check` target, not a pytest node |

Only the 21 are real construction. The 26 are bookkeeping. The 7 in the last two
buckets need a DECISION (thin pytest wrapper over the gate, or governed removal
with a recorded reason) — cheap in effort, but they will silently block arming
the lever if nobody makes that call.

### DO NOT DESIGN THIS FROM SCRATCH — livespec core is a finished worked example

Goal 2 is not bespoke work; it is this repo's leg of a **fleet-wide** program,
and exactly one member has completed it. Measured across the fleet 2026-07-25:

| repo | registry rows | TODO | top-of-pyramid trees | lever armed |
|---|---|---|---|---|
| **livespec (core)** | 68 | **0** | 2 | **yes — 2 workflows** |
| livespec-dev-tooling | 43 | 36 | 1 | no |
| livespec-runtime | 43 | 29 | 1 | no |
| livespec-orchestrator-beads-fabro | 86 | 63 | 1 | no |
| livespec-driver-claude | 36 | 36 | **0** | no |
| **livespec-overseer (this)** | **54** | **54** | **0** | no |

Two things follow. First, this repo is **not an outlier in debt** — four of six
carry heavy TODO debt — but it IS tied for furthest behind, with zero
top-of-pyramid trees. Second, and more useful: **core has already solved every
problem listed above**, including the gate-backed NFR rows.

Copy its shape rather than reinventing:

- It has the `tests/e2e` and `tests/prompts` trees this repo lacks entirely.
- Its 68 rows map to **39 distinct tests** — mostly 1:1, with a few broad
  top-of-pyramid tests carrying the meta/architectural headings **many-to-one**
  (16 rows → one `test_phase3_round_trip`; 8 → `tests.prompts.livespec.test_seed`;
  6 → `test_happy_path_minimal`). Many-to-one is explicitly permitted by the
  direction-4 docstring.
- **All five of its NFR rows** — the same `Boundary`/`Spec`/`Contracts`/
  `Constraints`/`Scenarios` set that is awkward here — map to a single
  prompts-tier test. That is the precedent for this repo's 7 undecided rows.

> **Adopt the shape, not the concentration.** Sixteen headings resting on one
> test is a lot of weight for a single verifier, and this thread's own standard
> (Corrections: *"a verifier must be able to fail"*) says to ask what injected
> defect would redden it. Core's mapping is rule-legal and green; that is not the
> same as each of those 16 rules being independently pinned. Use the template,
> then apply this thread's stricter evidence bar to what you map.

- **21 `scenarios.md` rows — EXPENSIVE.** They require integration-tier-or-above
  tests. The 445 existing unit-tier tests **cannot** satisfy them, however
  thorough. This is genuinely new construction, and it is the part needing the
  `tests/e2e` (or `integration`/`consumer`/`prompts`) tree that does not exist.
- **22 `spec.md` + `contracts.md` rows — CHEAP.** These state POSITIVE,
  behavioral rules and the suite already pins them. Aptness spot-checked, not
  just keyword-matched: `The cardinal rule` →
  `test_restart_fires_only_on_a_declared_ready`; `The restart interlock` → the
  stamp/mtime/void family (`test_warned_writes_stamp_before_pasting`,
  `test_stale_marker_voided_when_busy_past_grace`); `Notify, never block` →
  `test_every_track_alert_names_the_tmux_session_and_pane`; `The escalating
  wrap-up` → `test_wrapup_message_names_the_one_state_file_and_all_three_values`.
  Expect *mapping node ids into the registry*, not writing tests.
- **6 `constraints.md` rows — MIXED. Three cheap, three not.** Confirmed by
  reading each rule and its candidate tests:
  - `Acting safety` — **CHEAP**, near-perfect 1:1 mapping. The rule's four
    suppression cases each have a test: busy → `test_busy_suppresses_injection`;
    structured gate → `test_structured_gate_suppresses_injection`; bare shell →
    `test_shell_pane_never_pastes`; foreign program →
    `test_a_foreign_pane_is_session_gone_not_a_status_of_its_own`.
  - `Atomicity and single instance` — **CHEAP.** Atomic whole-file replace is
    pinned by `test_write_rows_is_atomic_and_skips_when_unchanged` and
    `test_atomic_write_fail_soft_leaves_the_store_intact_and_removes_the_temp`;
    the `flock(LOCK_EX)` singleton (`registry.py:78-89`) by
    `test_singleton_lock_is_treated_as_contended_when_the_lockfile_cannot_be_created`
    and `test_releasing_the_singleton_lock_frees_it_and_releasing_none_is_a_no_op`.
  - `Runtime requirements` — **CHEAP for its behavioral half, but SPLIT.** The
    `/proc` readers (which `claude_sessions.py:75` calls *"the ONE host
    coupling"*) are covered by the `test_pane_pid_*` family. But its
    "**DECLARED** requirement" half is decision **D4**, implemented by core item
    **`livespec-b1uo.2`** — still `backlog`. Mapping the row is cheap; claiming
    the constraint fully ENFORCED is not, and rides on a core item.

  The remaining three express **NEGATIVE architectural properties**, which unit
  tests do not naturally assert:
  - `Language and dependencies` ("no third-party imports anywhere") — **NO test
    asserts this at all.** NFR §"Constraints" says outright it is *"enforced at
    review and by the executables' isolated launch mode"*. There is no pytest
    node to map.
  - `Determinism boundary` ("holds NO semantic judgment and makes no model
    calls") and `Filesystem boundaries` ("NEVER reads, writes, or hashes files
    under any repository's plan tree") — same shape. The nearest evidence for
    the latter is a **prose substring assertion** in `test_plugin_structure.py`,
    which is not behavioral.
  - `Runtime requirements`, `Atomicity and single instance` and `Acting safety`
    do look genuinely testable and likely map.

  > **This corrects an earlier over-claim in this file.** A keyword probe found
  > "candidates for every heading", but two of the weakest were **not apt** on
  > inspection — the `atomic` hits for `The restart interlock` were registry
  > file-write tests, unrelated to the interlock. The interlock turned out fine
  > under a better probe; `Language and dependencies` did not. **Confirm aptness
  > per row before budgeting.** Keyword presence is not evidence.
- **5 `non-functional-requirements.md` rows — LESS awkward than first assessed.**
  These are CONTRIBUTOR-facing meta-requirements, so their evidence tends to be
  `just check` TARGETS while the registry maps headings to **pytest node ids**.
  But auditing them individually, only three are genuinely stuck:
  - `Contracts` — **CHEAP, mappable TODAY.** Its "the invocation surface stays
    knob-free" rule is already pinned verbatim by
    `test_cli_surface_has_no_config_knobs` and
    `test_build_supervisor_has_no_knobs_and_badges_its_own_tmux_pane`, and its
    "single-sourced constants" rule by the `_WRAPUP_SUGGEST_HEAD` /
    `_WRAPUP_INSIST_HEAD` / `_WRAPUP_BODY` constants in `supervisor.py`.
  - `Boundary` — **REMOVAL CANDIDATE.** Read it: it is pure document framing
    ("This file carries the contributor-facing invariants… The decision rule:
    if an operator could observe a violation, it belongs in spec.md…"). It
    states no requirement of its own. **Exactly the same category as
    `gap-jqszyzae`** — a registry row over a preamble. Retire by governed
    co-edit with that reason.
  - `Spec`, `Constraints`, `Scenarios` — gate-backed. Their evidence really is
    check targets (100% coverage, stdlib-only, the red-green lefthook, and —
    for `Scenarios` — `check-heading-coverage` direction 4 itself, which is
    pleasingly circular). Wrap each in a thin pytest assertion over the gate, or
    retire by governed co-edit. **Do not let these silently block arming the
    lever.**

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

**This is a hard dependency, not a preference — and it is confirmed by
OBSERVATION, not just by reading a docstring.** `no_todo_registry.py` says CI
sets `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST=true` for the release
context. Checking livespec core, which is the only fleet repo that has actually
armed it, that is exactly where it lives:

- `.github/workflows/release-readiness.yml:37` — `…TODOS_EXIST: "true"`
- `.github/workflows/release-tag.yml:48` — same, with the in-file comment
  *"Ensures every release ships with full rule-test coverage."*

**This repo has NEITHER workflow.** It carries 5 workflows (`ci`,
`release-please`, `release-dispatch`, `bump-pin-from-dispatch`, `pin-freshness`)
against core's 12+. So goal 3 is not merely "wire release-please for the plugin
half" — **it means ADDING `release-readiness.yml` and `release-tag.yml`, and
those are precisely the files that arm the lever.** The dependency is mechanical:
the moment goal 3 lands on core's template, all outstanding registry TODOs turn
the release path red.

**A SECOND release-armed lever comes with them.** `release-tag.yml` also sets
`LIVESPEC_RUN_MUTATION: "true"`. **This repo has never run mutation testing** —
the variable appears only in a `justfile` comment here.

> **MEASURED 2026-07-26, and the conclusion is the opposite of what this
> paragraph originally drew.** The sentence above is still true, but the
> inference from it — that adopting core's release template "switches on
> mutation testing for the first time" and so goal 3 "gates on a mutation pass"
> — is **FALSE for this repo as it stands.** `check_mutation` gates on the
> `pure_trees` role key, which `pyproject.toml` declares EXPLICITLY EMPTY; with
> the lever armed the check logs a sanctioned opt-out and exits 0 in about a
> second, without invoking mutmut (which is not even installed here). Setting
> the variable inspects nothing.
>
> This does NOT retire the concern, it RELOCATES it. The fleet's mutation gate
> really is the mechanical form of this thread's own "a verifier must be able to
> fail" rule, and this repo really has never been subject to it — but it becomes
> subject to it when **`overseer-hbr.22`** arms the ROP role keys, not when goal
> 3 lands the workflows. Full measurement is recorded on `.22`.

So goal 3 = release-readiness + release-tag workflows, and it gates on goal 2's
registry. It does **not** gate on a mutation pass today; that edge activates with
`.22`'s Gate E work. Sequence accordingly.

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

> **SUPERSEDED 2026-07-26 (second wrap-up).** Release automation is COMPLETE:
> three published releases, `plugin.json` in release-please `extra-files` (it
> bumped to 0.12.2 automatically), the `source_repo` misnaming fixed,
> `fast-forward-release-branch.yml` advancing `refs/heads/release`, and
> `release-readiness.yml` + `release-tag.yml` in place with goal 2's lever armed.
> The open release PRs and the "zero tags, zero releases" measurements below are
> HISTORY. Kept for the root-cause trace of the scaffold copy-paste, which is
> still the best record of how a component came to be misnamed.

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

**A release lane is ALREADY IN FLIGHT — and the bug above ALREADY FIRED.** ONE
release PR is open, titled `chore(master): release 0.12.0`:

| PR | branch component | state |
|---|---|---|
| **#52** | `…--components--livespec-overseer` | **OPEN**, MERGEABLE, green |
| **#21** | `…--components--livespec-runtime` | **CLOSED** 2026-07-25T20:08:55Z — never merged; branch deleted |

The root cause is a **scaffold copy-paste that was only PARTIALLY fixed**:
`ceaca74` scaffolded this repo with `package-name: "livespec-runtime"`, and
`6421590` corrected it — **in `release-please-config.json` only**. PR #21 is the
artifact release-please opened while the component was still misnamed; #52 is
its correct successor from the day after the fix. The repo has **zero** tags and
**zero** releases.

> **CORRECTION (2026-07-25, re-measured against the forge).** An earlier draft
> of this section recorded **TWO open** release PRs and recommended that #21 "can
> never merge and should be **closed as orphaned**". **That recommendation is
> already DISCHARGED** — do not re-do it. Measured against the forge, not a
> working tree: `gh pr list --state open` returns **only #52**; `gh pr view 21`
> reports `state: CLOSED`, `closedAt: 2026-07-25T20:08:55Z`, `mergedAt: null`;
> and `git fetch --prune` confirms
> `refs/heads/release-please--branches--master--components--livespec-runtime`
> is **deleted** on the remote. `overseer-hbr.9` already records the same
> outcome. Everything else in this section re-verified and still holds: #52 is
> OPEN and MERGEABLE, and the repo still has zero tags and zero releases
> (`gh release list` is empty).

The same scaffold residue also survives in two header comments that name the
wrong repo — `.mise.toml:1` and `lefthook.yml:1`. Cosmetic, but sweep them with
the `source_repo` fix. Full trace on **`overseer-hbr.1`**.

> **CORRECTION (2026-07-25, Codex adversarial review of PR #78).** The
> §"NEXT ACTION" claim "Nothing is started. Nothing is in flight." is FALSE as
> written — PR #52 is in flight. The accurate statement is that **no successor
> slice** has started. See that section.

## NEXT ACTION — the thread is DONE; all six goals are met

**Rewritten 2026-07-26 at the THIRD wrap-up. Every earlier status line in this
file — "waiting on maintainer valves", "`.16` is in flight", "`.13` is next",
"goal 4's adopter clause is not met" — is SUPERSEDED. All 23 children are
closed.**

### What changed, in one paragraph

The plugin went from installed-in-zero-projects to **installed in all twelve** —
nine fleet members and all three adopters — and `supervise-plan` now RESOLVES in
sessions that are not this repo's, proven by live exercise rather than by a
settings file. Releases are published through **v0.12.3**, `refs/heads/release`
tracks the latest, the registration is merged in all twelve consuming repos, and
goal 2's lever fired green on the release path. **All six goals are met.** All
23 children of `overseer-hbr` are closed.

### THE BOARD IS CLEAR — nothing of this thread's is open

`overseer-hbr` itself is still `backlog`; whether to close the epic is the
maintainer's call. Two items exist outside it and are NOT this thread's work:

- **`overseer-l0f`** (`pending-approval`, P2) — `uv.lock` trails
  `pyproject.toml` after every release; any `uv run` dirties a tracked file and
  no gate catches it. Found while wrapping up; filed rather than tolerated
  because it trains agents to `git checkout --` things they have not diagnosed.
- **`overseer-byvxlp`** (`backlog`) — the generated-prompt quality bar beyond
  both stall modes. Untouched and still owned by
  `plan/supervisor-prompt-quality/`.

### Goal 4's ADOPTER arm — how it was closed (`overseer-hbr.23`)

**The filed diagnosis was incomplete, and acting on it as written would have
shipped a still-broken mechanism.** The item said the adopters "do not run the
provisioner", which is true but missed that homelab's loop **ran `claude plugin
update` only** — and `update` on a plugin that was never installed does
NOTHING. So the obvious remedy (add a fourth entry to homelab's literal list)
would have changed nothing observable.

The load-bearing fact, established by a NEGATIVE test rather than assumed:
**Claude Code does NOT natively auto-install from checked-in project
`extraKnownMarketplaces` + `enabledPlugins`.** A full session in
`/data/projects/resume` with the registration present installed nothing. There
is no passive path; a provisioning hook is required.

Each adopter now has one, in its own stack, all deriving their commands from
that repo's own committed `.claude/settings.json` — so enabling another plugin
needs no hook edit anywhere:

| adopter | what landed | how it lands |
|---|---|---|
| `homelab` | `.claude/hooks/ensure_plugins.py`, stdlib-only, replacing the inline loop | PR #67, squash-merge |
| `openbrain` | `scripts/ensure-plugins.ts`, tsx, typechecked | direct push (its protocol: no PR, pre-push hooks are the gate) |
| `resume` | `.claude/hooks/ensure-plugins.ts`, Bun/TS, standalone per its own boundary clause | fast-forward push |

**Acceptance was real sessions, not hand-run hooks.** Each adopter was reset to
declared-but-not-installed, then ONE ordinary `claude` session provisioned it
unaided, and a SECOND session resolved both skills. `installed_plugins.json`
carries twelve project entries. Every adopter tree is clean afterwards.

**D5 held throughout:** each provisioner reads only its OWN repo's settings.
None reads a fleet manifest; none is a discovery input for any plugin's runtime.

### Two `claude plugin` CLI hazards — read before touching any provisioner

Both cost a debugging pass, both are now pinned by tests and written into the
adopters' own docs.

**1. `-s project` resolves the project from the PROCESS CWD** and ignores
`CLAUDE_PROJECT_DIR` entirely. The first implementation inherited cwd, ran from
elsewhere, **exited 0 and provisioned nothing** — a silent success. Pass the
project directory as each command's cwd explicitly.

**2. `install` and `uninstall` REWRITE `.claude/settings.json`** — a tracked
file. `install` adds the `enabledPlugins` key, `uninstall` REMOVES it, and both
re-serialize the whole file in the CLI's own canonical formatting. Two
consequences:

- Each adopter's committed file was in a different key order, so every run
  dirtied a tracked file with a cosmetic reformat (homelab 40 lines, openbrain
  12, resume 36). All three are now committed in the CLI's canonical shape,
  which is a **fixed point** — verified by re-running install/update and
  diffing. Prettier accepts either order, so no formatting gate would catch a
  regression.
- **`claude plugin uninstall` alone is not a valid reset.** It deletes the
  DECLARATION along with the install, so the next hook run has nothing to act on
  and looks broken. That mis-reset consumed the first debugging pass. Correct
  reset: uninstall, then `git checkout -- .claude/settings.json`.

### The two postures, demonstrated live and unplanned

Mid-verification another track published **v0.12.3** and `refs/heads/release`
fast-forwarded. The postures then diverged correctly with nobody touching them:

| repo | posture / pin | resolved to |
|---|---|---|
| `homelab` + the 9 fleet members | `released` / `ref: "release"` | followed to `13bb0b94` |
| `openbrain`, `resume` | `pinned` / `v0.12.2` | stayed at `74bbe7e8` |

That is goal 5's branch-ref auto-follow **observed across a real release
boundary**, and simultaneously the evidence that concrete pins do not drift.
**The two pinned adopters still have no bump lane** — provisioning is fixed;
advancing a concrete pin is a separate question no lane covers.

### THE TWO LESSONS THIS THREAD PAID FOR TODAY — read before touching goal 4

**1. REGISTRATION IS NOT INSTALLATION.** A merged `.claude/settings.json` entry
is a DECLARATION. After all twelve PRs merged, the host still showed 10 known
marketplaces with `livespec-overseer` absent, no cache directory, and zero
`installed_plugins.json` keys. Never record goal 1 or goal 4 as met on the
settings files; the maintainer caught exactly that attempt.

**2. THE PROVISIONER READS THE LOCAL WORKING TREE, NOT THE FORGE.** The first
live-exercise session installed nothing because that checkout was two commits
behind origin/master. Eleven of twelve primary checkouts were behind after the
sweep. **"Merged" and "available" are different facts, and only one of them is
visible at the forge.** All were fast-forwarded (`livespec-dev-tooling` skipped
— dirty tree, another track's — and it already carried the entry).

A third, smaller one worth keeping: **first exposure in a repo takes TWO
sessions.** Plugins load at startup, so a plugin installed BY SessionStart
cannot appear in that same session's skill list.

### How goal 1 was actually proven — the bar for any re-verification

Three fresh short-lived non-interactive sessions, owned by this track. **No live
track session was hijacked or restarted** — `worktree-location-enforcement` and
every other attached session was left alone. Run 1 (stale checkout): nothing.
Run 2 (after pull): the hook installed the plugin, skills not yet visible. Run 3:

```text
livespec-overseer:overseer
livespec-overseer:supervise-plan
```

Reproduced identically in `/data/projects/livespec`, so run 3 is not an artifact
of one repo. The skill was then INVOKED there and loaded correctly, naming its
own thin-binding → prose contract. And the payload was checked at the byte
level: the cached prose is `diff`-identical to
`origin/release:.claude-plugin/prose/supervise-plan.md`.

### The blocker that nearly shipped the defect anyway — a keeper

`refs/heads/release` was **v0.12.1, which PREDATES PR #120**. The prose served at
that ref was the 158-line UNCORRECTED generator. Registering pinned to
`ref: "release"` at that moment would have installed fleet-wide exactly the
generator the `.16 blocks .13` edge existed to prevent — **the edge satisfied on
paper and defeated in fact.**

Root cause: #120's commits were typed `test:` and `docs:`, and neither bumps
under this repo's release-please config. **`.claude-plugin/prose/supervise-plan.md`
is a SHIPPED artifact** — the skill `cat`s it at run time — so a change to it is
a `fix`, never `docs`. Cleared by PR #123, which also added the last missing
prohibition ("never kill the acting overseer daemon") and published v0.12.2.

**Generalise it:** landing a fix on `master` does not ship it. Anything a
consumer resolves through `ref: "release"` reaches them only via a version-
bumping commit type.

### Goal scorecard, measured 2026-07-26

| goal | state |
|---|---|
| 1 — `supervise-plan` works fleet-wide | **MET** — resolves in all 12 consuming repos, proven by live exercise in each |
| 2 — top-of-pyramid tests, present AND enforced | **MET** — 54/54 rows mapped, lever armed, fired green on the release path |
| 3 — auto-released | **MET** — three releases; `release-readiness.yml` + `release-tag.yml` in place |
| 4 — auto-installed, fleet AND adopters | **MET** — 12 install records; each adopter provisions itself from an ordinary session (`.23`) |
| 5 — release pin auto-bumped | **MET** — observed across a real release boundary: `ref: "release"` consumers followed v0.12.2 → v0.12.3 unattended while the two `posture: pinned` adopters correctly held. Those two still have no bump lane |
| 6 — phase-2 adopter shipping folds in | **MET** — dispositions on `.21`/`.22`, and its shipping arm landed as `.23` |

### Five core-tenant closes are justified and are NOT ours to make

Recorded with evidence on `.21`: `livespec-b1uo.1` and `.3` (close as
delivered), `.4`/`.5` (close as unnecessary), and `livespec-cbmw` (fully stale,
all three legs). Whoever holds the core tenant can act on facts.

### The valve lesson — READ BEFORE USING `drive`

`approve:` moves `pending-approval → ready`; `accept:` moves `acceptance →
done`; **there is no non-dispatching valve from `ready` to `acceptance`.** Work
built outside the dispatch path therefore cannot walk the normal path, and
`accept:` refuses with `invalid-source-state`. Worse, approving a COMPLETED item
makes `next` rank it `implement` — pointing the next worker at rebuilding merged
work. That happened to `.19` and had to be undone.

**The established remedy, maintainer-approved:** close directly with
`bd close --reason-file`, and make the reason self-justifying — quote the
refusal, say why no valve reaches `acceptance`, and record the evidence.
`overseer-hbr.19`'s close reason is the template. Use `--reason-file`, never
`-r`: the reasons contain backticks and command substitution has eaten them
before.


### The method `.19` established — carry it into `.20` and any later test work

**Name the injected defect BEFORE writing the assertion, then actually run it.**
In slice 1, **two of five** tests initially passed for the wrong reason:

- A sabotage set exactly at a boundary (`_ACK_STALE_AFTER = 0.0` against an ack
  of age `0.0`, compared with `<=`) silently no-ops. That is indistinguishable
  from a test with no teeth.
- One test asserted "staleness authorizes nothing" but was really pinning "no
  stamp, no restart" — the interlock short-circuited before the token was ever
  examined, so sabotaging `ready_valid` left it GREEN. It had to be restructured
  to open the round first.

That rate did **not** recur across slices 2–4 (31 named sabotages run, 31 red),
and the reasons are reusable:

- **DIFFERENTIAL setup.** Satisfy every precondition except the one under test,
  so the assertion is about that one thing. The malformed-state test is the
  fresh-`ready` test with one token changed; written on an already-ineligible
  track it would pass however the token were handled.
- **A control for every "the daemon did nothing" claim.** The three refusal tests
  assert no wrap-up was pasted, which is worth exactly as much as the proof the
  same fixture DOES paste one when nothing is refused. That control ships beside
  them and is deliberately not mapped to a row.
- **Test ORDERING by failing every gate at once.** An isolated gate test cannot
  distinguish "checked first" from "the only one failing".
- **Re-run the sabotages after any refactor.** Twice in this slice a mid-review
  refactor could have defanged a verifier; both times the re-run was the right
  call and both times it still bit.
- **A sabotage that aborts the run early does not prove the LATER assertion.**
  Verify that one separately rather than assuming it.

### State on the forge (re-measured 2026-07-26 at the second wrap-up)

- **Registry: `0` TODO of 54.** Re-derive with
  `jq '[.[] | select(.test == "TODO")] | length' tests/heading-coverage.json`.
- **`tests/integration/` carries 4 modules, 22 tests**; `tests/prompts/` carries
  the generated-charter contract, **12 tests**.
- **`just check` on master: 61 targets, green, 100% statement+branch.**
- **Three releases published** — v0.12.0, v0.12.1, **v0.12.2** — and
  `refs/heads/release` = `74bbe7e84d02cec9423c9ad83cc65aad22e01f5e` = the v0.12.2
  tag. PR #52 is long since merged; the "do not merge it" instruction that used
  to live here is spent.
- **NOTHING of this thread's is in flight.** Its worktrees were removed and its
  branches deleted after merge.
- **Host plugin state** (the numbers goal 4 moves — re-derive against
  `~/.claude/plugins/`, not against any settings file):
  - `known_marketplaces.json` — **11** entries, `livespec-overseer` PRESENT,
    `{source: github, repo: thewoolleyman/livespec-overseer, ref: release}`.
  - `cache/livespec-overseer/` — present, carrying BOTH skills.
  - `installed_plugins.json` — `livespec-overseer@livespec-overseer` with **nine**
    project entries, all at `74bbe7e84d02`. **No adopter path appears** — that is
    `.23`.
- **A known, benign lag:** release-please does not update `uv.lock`, so the lock
  trails `pyproject.toml` by one version after each release and any `uv run`
  dirties it. No gate covers it; do not mistake it for a stray edit.

### DONE — do not redo

| item | what landed |
|---|---|
| `.17` (S8) | all 26 cheap rows mapped — PR #93 |
| `.18` (S9) | all 7 awkward rows, sabotage-verified — PR #96 |
| `.10` (S1) | `plugin.json` in release-please `extra-files`, version synced, two headers — PR #92 |
| `.5` | `registry.py` docstring no longer cites the removed `watch_set` — PR #94 |
| `.7` | the stale CAUTION block — PR #95 |
| `.19` (S10) | **all 21 scenarios**, 4 slices — PRs #97, #100, #102, #103 |
| `.16` (S7) | the generated-charter contract + generator fix — PR #120 |
| `.13` (S4) | the marketplace registered in **all 12** consuming repos — livespec #1769, dev-tooling #684, driver-claude #294, driver-codex #277, orchestrator-beads-fabro #989, orchestrator-git-jsonl #416, runtime #343, console-beads-fabro #445, overseer #127, homelab #66, openbrain #7, resume #7 |
| `.15` (S6) | goal 1 accepted by live exercise outside this repo |
| `.14` (S5) | goal 5 accepted: `gitCommitSha` == `refs/heads/release` |
| `.3` `.4` `.8` | disposed with evidence at the second wrap-up |
| — | **PR #123** — `fix(supervise-plan)`: the acting-daemon prohibition, and the release that carried #120 to consumers |

`.21` (S12) and `.22` (S13) carry full written dispositions in their ledger notes
— including that **`overseer-3wt` may now close** (both items 3 and 5 disposed)
and that **`livespec-cbmw` is fully stale and should close**. Neither has been
closed; both are core-tenant or maintainer calls.

### `.16`/S7 — the stand-down was WITHDRAWN, and `.16` is DONE

**This section is kept as a record of how the conflicting-lane rule was resolved
here; it is no longer a live constraint.** This thread previously stood down on
`.16` because `plan/supervisor-prompt-quality/` (epic `overseer-byvxlp`, PR #90)
sequences it as that thread's step 2. The stand-down was **withdrawn at
maintainer direction** on the reasoning that `.16` is a CHILD of `overseer-hbr`,
this thread's own epic — the sibling thread SEQUENCES it, it does not OWN it.
**Coordination is by RECORDING, not by stopping**, and the record was written
onto `.16`'s notes before the work started.

`overseer-byvxlp` is **NOT superseded.** `.16` was the FLOOR — both stall modes
plus fixtures that tell them apart, asserted over generated output. That epic's
broader bar is untouched and still open: iteration-stable generic form,
anti-drift layering, the cold-open generation gate, classified-remedy
preconditions, wait-channel bootstrap, adopter parameterization.

`overseer-fitvmo` is CLOSED and properly disposed — a maintainer-directed
supersession into `.16` and `overseer-byvxlp`, with an explicit no-content-dropped
clause. **The disposition is in the `close_reason` field**, which is distinct from
`resolution` and `reason` (neither of which exists as a key on that record). An
earlier pass queried the wrong fields and wrongly reported it as an undisposed
burial. When checking whether something was disposed, read the whole record's
keys.

### Ledger lifecycle — repaired, and the repair held

Every child sat at beads' native `open`, which is **not** a livespec
`WorkItemStatus`. Effect: `is_item_ready` never fired, `next` ranked zero
candidates, and `drive --action approve` refused — dispatch was silently disabled
for the whole epic. All were repaired to real statuses and read back.

**All 22 original children are now `closed`.** `.16` — the last one still at
beads-native `open` — was repaired to `ready` before it was executed, and is
closed on PR #120's merge evidence.

**The `bd create --parent` defect was avoided when filing `.23`**, which is the
first hierarchical child filed since it was documented. That command defaults
status to beads' foreign `open` AND inherits parent labels, which is how
`.10`–`.22` acquired a misleading `intake:triaged` marker the DoR router never
earned. `.23` was created with `--no-inherit-labels`, then explicitly set to
`pending-approval` and read back: **status `pending-approval`, zero labels.**
Any future hierarchical filing must correct both the same way.

**`overseer-xbxkrv` is an ORPHANED DUPLICATE of `overseer-byvxlp` and should
CLOSE.** Found 2026-07-26 (second sweep). The two epics carry **byte-identical
titles** and both sit at `backlog`, so a `bd list` reader cannot tell which is
the anchor. Measured:

- Created **23 seconds apart** — `xbxkrv` at `01:30:49Z`, `byvxlp` at
  `01:31:12Z`. `xbxkrv` was updated once at `01:30:50Z` and never again;
  `byvxlp` was updated at `01:32:47Z`.
- `xbxkrv` carries **only** `origin:freeform`; `byvxlp` also carries
  `intake:triaged`. The router finished on one of them.
- Their descriptions differ in **exactly one paragraph**: `xbxkrv` claims
  `depends_on overseer-hbr.16` and `overseer-hbr.4`. `byvxlp` replaces that with
  *"beads forbids task-blocks-epic edges, so these are NOT encodable as
  depends_on and readiness must be re-checked manually."* So `xbxkrv` is the
  stillborn first filing, and the live record it preserves is **factually
  wrong** — it asserts the very edge `byvxlp` exists to correct.
- **Zero** references to `xbxkrv` anywhere in the fleet's markdown or JSON;
  `byvxlp` is named by three plan documents, including this file and
  `plan/supervisor-prompt-quality/`, which declares it that thread's anchor.
- Both have 0 dependencies, 0 dependents, 0 comments — closing `xbxkrv` strands
  nothing.

**RESOLVED — `overseer-xbxkrv` is now `closed`** (re-measured 2026-07-26 at the
second wrap-up). The disposition above was recorded and a human acted on it,
which is the precedent working as intended: record the disposition, let a human
flip the valve. `overseer-byvxlp` is the surviving anchor and remains `backlog`.

**Do not trust `intake:triaged` on `.10`–`.22`.** That marker means "the DoR gate
saw this item". On `.1`–`.9` it is genuine (they also carry `origin:freeform`, so
they came through `capture-work-item`). On `.10`–`.22` it was **inherited from the
epic's own labels** by `bd create --parent`; the router never ran. Root cause:
`bd create --parent` is the only way to get hierarchical `.N` children — the
`WorkItem` model has no parent field at all — but it defaults status to `open` and
inherits parent labels. Any future hierarchical filing must correct both.

### What was filed, and the two decisions behind it

**Maintainer decision 1 — marketplace hosting: PUBLISH ITS OWN.** Open question 1
below is **CLOSED**, and it was settled by measurement rather than argument: all
four peers (`livespec`, `livespec-driver-claude`,
`livespec-orchestrator-beads-fabro`, `livespec-orchestrator-git-jsonl`) each
register their **own** marketplace in `~/.claude/plugins/known_marketplaces.json`,
one per repo. **There is no family marketplace to join.** Do not re-litigate it.

**Maintainer decision 2 — MINIMAL RELEASE FIRST.** Land a narrow goal-3 slice
(`fast-forward-release-branch.yml`, the `source_repo` fix, `plugin.json` into
release-please `extra-files`), merge PR #52 to cut v0.12.0, then register pinned
to `ref: "release"` — **deliberately WITHOUT `release-readiness.yml` /
`release-tag.yml`**, so `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST` stays
unarmed and the 54 registry TODOs do not block goals 4/5/1.

**Groom Step 3 was deliberately NOT run.** `file_approved_slices` ends with
`close_regroomed_out(item_id=…)` (`groom.py:223`), and `close_regroomed_out`
calls `require_backlog_target`, which raises unless status is exactly `backlog`
— `overseer-hbr` **is** `backlog`, so the close would have SUCCEEDED. Running it
would have closed the thread's declared single ledger anchor and left `.1`–`.9`
and `overseer-fitvmo` parented to a closed epic. The maintainer chose **keep the
epic, file as children**; the cost accepted is that the groom's automatic
dependency linking and drain-order ranking were forgone, so **every edge below
was set by hand and then read back from the ledger to verify.**

### The filed graph

| slice | id | goal | blocked by | state |
|---|---|---|---|---|
| S1 residue, non-workflow | `.10` | 3a | — | **DONE** (PR #92) |
| S2 workflow landing | `.11` | 3a | `.10` | **DONE** (PR #115) |
| S3 cut v0.12.0 → `release` branch | `.12` | 3a | `.11` | **DONE** (PR #52; v0.12.0, then v0.12.1) |
| S4 register marketplace fleet-wide | `.13` | 4 | `.12`, **`.16`** | **DONE** — 12 repos, 12 PRs, all merged |
| S5 consumer pin path observed | `.14` | 5 | `.12`, **`.13`** | **DONE** under the RESTATED acceptance |
| S6 goal-1 acceptance, live | `.15` | 1 | `.13`, `.16` | **DONE** — live exercise, 2 repos |
| S7 template: BOTH stall modes | `.16` | 1 | — | **DONE** (PR #120) |
| S8 map the 26 cheap rows | `.17` | 2 | — | **DONE** (PR #93) |
| S9 decide the 7 awkward rows | `.18` | 2 | — | **DONE** (PR #96) |
| S10 21 scenario tests | `.19` | 2 | `.17`, `.18` | **DONE** — 21/21, PRs #97/#100/#102/#103 |
| S11 arm the lever, LAST | `.20` | 3b | `.19` | **DONE** — fired green on the release path |
| S12 goal-6 dispositions | `.21` | 6 | — | **DONE** |
| S13 `overseer-3wt` items 3 + 5 | `.22` | 6 | — | **DONE** — item 5 satisfied, item 3 sized |
| — goal-4 ADOPTER arm | **`.23`** | 4 | — | **DONE** — homelab PR #67, openbrain + resume direct push |

Plus `.1`–`.9`, all closed: `.1`/`.9` (the `source_repo` misnaming), `.2` (the
goal-6 anchor), `.5`/`.7` (stale docs), `.6` (`overseer-3wt` items 3+5), and
`.3`/`.4`/`.8` disposed at the second wrap-up.

**`.23` went through the `approve:` valve** (pending-approval → ready, green) —
the one item in this epic that did, since the maintainer declined to scope goal
4's adopter clause out. Every other close in this epic is a raw
`bd close --reason-file`, for the lifecycle reason recorded on `.19`.

### Ordering — THREE MEASURED HARD CONSTRAINTS, all now FILED

- **HARD — `2 → 3b`. DISCHARGED 2026-07-26.** Auto-release arms
  `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST` in the release context, which
  fails on every registry TODO. See §"Ordering constraint: goal 2 BEFORE goal 3".
  It was never the maintainer's to accept or replace — it falls out of
  `no_todo_registry.py`'s source. It bound `.19 → .20`, and `.19` has now landed
  all 54 rows, so the constraint is satisfied rather than waived. **The
  `LIVESPEC_RUN_MUTATION` lever that arrives in the same workflow is a NO-OP on
  this repo today** (`pure_trees` is declared empty, so `check_mutation` takes a
  sanctioned opt-out) — measured 2026-07-26; it does not gate `.20`. Its real
  cost lands with `overseer-hbr.22`'s Gate E work. See §"NEXT ACTION".
- **HARD — `3a → 4`.** **PROMOTED FROM "Hypothesis" 2026-07-26 — this doc
  previously recorded it as a starting guess, and that was wrong.** Every peer
  marketplace registration pins **`ref: "release"`**; that branch exists only
  because each peer carries `fast-forward-release-branch.yml`, which
  fast-forwards `refs/heads/release` to each published release tag. The
  correlation is exact — all four registered peers carry the workflow, have the
  branch, and are registered; `livespec-overseer` publishes a catalog but has
  **none** of the three (`git ls-remote --heads origin` shows no `release`;
  `gh release list` is empty). So goal 4 cannot be reached until a release is
  published. Binds `.12 → .13`.
- **HARD — `generator quality → 4`. FOUND AND FILED 2026-07-26 (second sweep).**
  Found unfiled, owned by neither thread; the maintainer's answer was **add the
  edge**, and `overseer-hbr.16 blocks overseer-hbr.13` is now on the ledger
  (read back; `bd dep cycles` reports none). It reproduced this thread's own
  signature failure at a new location. Measured, three facts:
  - **`.13` installs the generator.** Its scope is a checked-in
    `extraKnownMarketplaces` + `enabledPlugins` entry in each consuming repo's
    `.claude/settings.json`, and the plugin ships **both** skills — so
    registering the marketplace puts `supervise-plan` into every consuming repo
    at once.
  - **The ledger did not gate that on the generator being correct — now it
    does.** As found: `.13` was blocked by **`.12` only**; `.16` blocked
    **`.15` only**; and `overseer-byvxlp`'s dependency on `.16`/`.4` is
    **prose-only** (beads forbids task-blocks-epic edges — the sibling thread's
    handoff says so outright). So the filed graph permitted `.12 → .13` to land
    with the generator untouched, and only *acceptance* (`.15`) waited. The new
    edge closes that; `.13` is now blocked by `.12` **and** `.16`.
  - **The generator has never been corrected.**
    `.claude-plugin/prose/supervise-plan.md` has **exactly ONE commit**
    (`d126ccf`, its creation), while the hand-written exemplar it is supposed to
    mirror has **SEVEN**. Every correction this thread produced — `.4`'s
    executable commands, both stall-mode procedures, the busy-detect-by-change
    fix — landed in the exemplar and **none** of it reached the generator.
    Re-derive with `git log --oneline -- <each path>`.

  Probed against the shipped prose, these are ABSENT from what it tells the
  generator to emit: `capture-pane`, `-S -40`, `pane_pid`, `readlink`, the
  no-idle rule, the armed-re-entry rule, any watcher, any forge-verification
  clause, and — notably for this product — *"never kill the acting overseer
  daemon"*. Its `picker` mention is only the `---` presentation rule, not the
  fact that an open picker **suppresses the daemon's own wrap-up injection**.
  Two of `.4`'s named defects are live in it verbatim: HALT precondition 2 (live
  agent driver) supplies **no command at all**, and precondition 4 is a bare
  CWD-relative `test -d "plan/<topic>"` while the skill never establishes a
  working directory anywhere (grep: zero hits for `cd`/`cwd`/`absolute` in the
  prose or its binding) — so it can pass in the wrong repo.

  **This is not new scope for the sibling thread** — `overseer-byvxlp` and `.16`
  already own the generator's CONTENT, and this thread stands down on that. What
  was unowned was the **EDGE**. Without it, goal 4 would have landed structurally
  true (installed everywhere) and functionally false (generating stall-prone,
  non-executable charters) — the exact pairing this thread was created to
  prevent.

  **The maintainer's decision, 2026-07-26: block `.13` on `.16`.** The two
  alternatives were declined and are recorded so they are not silently
  re-litigated: a *minimal port* of `.4`'s commands plus both stall-mode
  sections into the prose, without waiting for fixtures — declined because it
  ships prose no fixture has ever reddened, the same unverified-verifier class
  this repo was already bitten by in PR #75; and *ship `.13` first knowingly*,
  whose honest mitigations were that `supervise-plan` is ATTENDED (a defective
  generator only fires when a human invokes it; it auto-runs nowhere) and that
  the registration is a checked-in `settings.json` entry and therefore
  reversible per repo.

  **Consequence for `.16`.** It is now on the critical path to goal 4, which
  makes it materially more urgent than its P1 label conveyed. Two things about
  it are unchanged: its status is still beads-native `open` — **not** a livespec
  `WorkItemStatus`, so `is_item_ready` will not fire and `next` will not rank it
  until that is repaired the same way the rest of the epic was — and **this
  thread still stands down on executing it**. The edge stops goal 4 overtaking
  `.16`; it does not transfer ownership from `plan/supervisor-prompt-quality/`.

**The chosen path threads BETWEEN the two edges**, which is the whole point: they
bind *different halves* of goal 3. `2 → 3` binds only the two lever-setting
workflows (`release-readiness.yml`, `release-tag.yml` — verified by grep to be
the only places the fleet sets that variable); `3 → 4` needs only a published
release. Splitting goal 3 into **3a (minimal, lever-free)** and **3b (full
template, arms the lever)** frees goals 4, 5 and 1 from the 54-row cleanup.

Goal 2 is **NOT** independent and must not be planned as a parallel lane; it
gates 3b.

**Goal 1 = availability ∧ behavior.** `.15` depends on BOTH `.13` (the plugin is
actually installed elsewhere) and `.16` (the generated template is not
stall-prone). Availability alone does not close goal 1.

**Since 2026-07-26 that conjunction is also SEQUENCED, not merely required.**
`.16` now blocks `.13` as well as `.15`, so behavior comes before availability
rather than beside it. The distinction matters: previously both legs could land
in either order and only the final acceptance noticed; now the defective leg
cannot ship at all. See §"Ordering", third edge.

### The remaining open questions

`research/phase-2-adopter-shipping.md` is a **DRAFT SHAPE**, not a slice list.
Question 1 (marketplace hosting) is **CLOSED** — see above. Two remain:

1. **Is the Codex arm in scope for first ship?** `.livespec.jsonc` declares
   `codex: exempt` today, though the daemon half is already harness-neutral.
2. **Does "shipped" warrant a SPECIFICATION scenario?** That would route through
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

Full evidence: the predecessor thread, archived 2026-07-25 at
`plan/archive/cutover-and-shipping/` — and the comments on epic
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
   exactly **seven**. **At audit time — BEFORE this thread's own ledger children
   existed — a `bd list --all --json` sweep of the then-22-item tenant found ZERO
   references to any gap and zero items carrying a `gap_id`.** That is the
   condition that motivated filing an anchor. It is deliberately no longer true:
   **`overseer-hbr.2` is now that anchor** and references all seven, and the
   tenant has grown past 22. Re-measuring will therefore NOT reproduce "zero
   references" — check instead that every gap is anchored:

   | gap id | location |
   |---|---|
   | `gap-jqszyzae` | `constraints.md` › livespec-overseer — constraints |
   | `gap-lqxagafn` | `spec.md` › Non-interference with tracked work |
   | `gap-mgjjuo3n` | `spec.md` › Notify, never block |
   | `gap-pd54ut36` | `spec.md` › Supervised runtimes |
   | `gap-h5sj7scj` | `spec.md` › The cardinal rule |
   | `gap-opeyzo5y` | `spec.md` › The escalating wrap-up |
   | `gap-4vy63slp` | `spec.md` › The escalating wrap-up |

   **ALL SEVEN WERE AUDITED 2026-07-25. NONE needs new implementation work.**
   This is no longer a hypothesis — each was traced to its rule text, its
   implementing code, and its pinning test:

   | gap | disposition | evidence |
   |---|---|---|
   | `gap-pd54ut36` | **SATISFIED (proven)** | "restart MUST resume the SAME runtime" — **sabotage-verified**: re-pointing the codex restart at the claude command turned **3** tests red |
   | `gap-h5sj7scj` | **SATISFIED** | cardinal rule; `supervisor.py` states *"`ready` is the SOLE authorization"*; 35 ready/restart tests incl. `test_idle_at_danger_with_no_declaration_is_never_restarted` |
   | `gap-mgjjuo3n` | **SATISFIED** | alert self-sufficiency; pinned by `test_every_track_alert_names_the_tmux_session_and_pane` |
   | `gap-opeyzo5y` | **SATISFIED** | "MUST escalate rather than repeat"; `test_escalates_one_paste_per_band_as_ctx_drops`, `test_wrapup_escalates_from_suggestion_to_insistence`, plus band-durability tests |
   | `gap-4vy63slp` | **SATISFIED** | "MUST tell the session concretely"; pinned almost verbatim by `test_wrapup_message_names_the_one_state_file_and_all_three_values` |
   | `gap-lqxagafn` | **SHALLOW — read the caveat** | supervise-plan's worktree→PR write discipline. `test_supervise_plan_prose_pins_reviewed_target_repo_write_discipline` pins it — but by **substring presence in static prose** |
   | `gap-jqszyzae` | **NOT A GAP** | it is `constraints.md`'s own PREAMBLE — *"Each one is a boundary the implementation MUST hold, stated without prescribing…"*. A detector artifact on document framing, not an implementable rule |

   **The `gap-lqxagafn` caveat matters beyond this table.** A substring test on
   prose proves the INSTRUCTION EXISTS; it cannot prove the skill OBEYS it. That
   is exactly the gap between unit-tier and scenario-tier evidence that direction
   4 exists to enforce, and exactly what `overseer-fitvmo` demands for the
   generated prompt text ("tests must FAIL on wording equivalent to…"). Goal 1
   needs behavioral evidence over GENERATED output, which no static-prose
   assertion can supply.

   > **NEW MISREADING HAZARD (2026-07-26) — `.19` did NOT fix this.** This repo
   > now advertises 22 integration-tier tests, and a reader could reasonably
   > assume the shallow pin was swept up with them. **It was not.** Re-measured:
   > nothing under `tests/integration/` references `supervise-plan` at all, and
   > `gap-lqxagafn`'s only evidence is still
   > `test_plugin_structure.py:71`. That absence is CORRECT — `supervise-plan` is
   > not a `scenarios.md` scenario, so `.19` rightly did not cover it — but it
   > means the caveat is exactly as live as it was on 2026-07-25. The behavioral
   > evidence over generated output is owed by **goal 1 / `overseer-byvxlp`**,
   > not by anything `.19` shipped.

   So the disposition for six of seven is *record as satisfied*, and for
   `gap-jqszyzae` *record as a detector artifact*. **Do not manufacture seven
   slices.** Re-run the detector before disposing — the set is a pure function of
   spec text and moves when the spec is revised.

   > **RE-RUN DONE 2026-07-26 (`--since-version v001`): the set reproduces
   > EXACTLY** — same seven ids, same headings, spec unmoved. The core-tenant
   > statuses are unchanged too (`livespec-b1uo` backlog, `.1`/`.2`/`.3` backlog,
   > `.4`/`.5` blocked), and `.1`'s and `.3`'s dispositions were re-verified at
   > code level rather than re-read: `watch_set()` is defined nowhere, the only
   > `.livespec-fleet-manifest.jsonc` mentions in `registry.py` are comments
   > explaining D5, and the acting daemon is still pid 2954933 running this
   > repo's own `.venv/bin/overseerd`. Full record on **`overseer-hbr.21`**.

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
   - **`.4`/`.5`** driver bindings —
     `plan/archive/cutover-and-shipping/research/operator-surface.md:27` already
     rules them **unnecessary**. Close as such. They still read `blocked` only
     because that ruling lives in this repo's archived research file and was
     never reflected in core. **(Path corrected 2026-07-26: this read a bare
     `operator-surface.md:27`, which resolves to nothing from this file's own
     directory — `plan/ship-overseer-to-fleet/research/operator-surface.md` does
     not exist. It is the last unresolvable instance of that reference.)**
   - **`.2`** Linux+tmux precondition (D4) — genuinely core-side work on core's
     own spec and gates. No disposition available from here; leave with core.
3. **`check-no-workflow-edits` copy-drift** across the 4 carrying fleet repos.
   Single-sourcing into `livespec-dev-tooling` is dev-tooling's call, **not this
   thread's** — so this is EXPLICITLY OUT OF SCOPE here, owned by
   `livespec-dev-tooling`. Goal 6 is discharged for this item by naming that
   owner, which this line does. Do not silently re-absorb it.
4. **`overseer-3wt`'s OWN un-migrated payload — a HARD PRECONDITION on Phase 3.**
   Tracked as **`overseer-hbr.6`**. The predecessor epic lists **SIX** numbered
   items in its description, and the predecessor plan's Phase 3 **closes that
   epic**. Verified 2026-07-25: items 1, 2 and 4 are genuinely done (4's PRs
   #6/#8/#10 are all closed); **item 6** ("Phase 2 adopter-family shipping per
   D7/D8/D9") IS covered — it is **goal 6** of this thread, via `overseer-19s`
   closed as superseded. But **items 3 and 5 are not, and no goal covers them**:

   - **Item 3 — "Gate E: arm the Result-railway role keys."** This is a
     **latent CI failure of several hundred findings**, not a config line.
     `just check` emits Phase-0 WARN diagnostics each stamped *"hard-fails once
     this repo is flipped to the hard gate in Phase 2"*. **Same pattern as goal
     2's lever** — a rule that runs and reports but cannot fail, so debt accrues
     invisibly. Worse: the flip is driven by the FLEET ROP program (core
     `livespec-gcsn`, `livespec-h2hs`, `livespec-qgp2jt`), so an upstream
     decision this repo does not make can turn it red.

     > **DO NOT QUOTE A FIXED COUNT HERE — measured 2026-07-26, it is a MOVING
     > TARGET.** This passage used to assert "a **705**-finding latent CI
     > failure ... across 23 files", with a fixed category breakdown. Re-measured
     > a week later: **712**, and — the part that matters — **not one
     > `overseer/*.py` had changed.** `git diff --stat ec1a638..HEAD -- overseer/`
     > is empty; the only non-docs commit in the range is a routine
     > `chore(deps)` bump of the dev-tooling pin (v0.54.17 → v0.54.18). The
     > entire +7 came from upstream.
     >
     > That turns the "upstream decision" warning above from a hypothesis into a
     > measurement, and makes it sharper: the number drifts **on an ordinary
     > dependency bump**, not merely on a deliberate ROP phase flip — and
     > `pin-freshness.yml` exists precisely to keep that pin moving. Every delta
     > in that pass was an increase.
     >
     > **So budget Gate E by CATEGORY and CONCENTRATION, never by a total.**
     > Current shape: ~603 missing `*` keyword-only separators, 45 banned
     > cross-module `_`-prefixed calls, 25 files with no declared semantic role,
     > 23 modules missing `__all__`, 7 over the LLOC ceiling, 7 banned process
     > terminations outside `bin/`, 2 misc. **`overseer/test_supervisor.py`
     > alone carries 311 of them (44%)**, then `test_registry.py` 59,
     > `supervisor.py` 56, `test_codex_sessions.py` 44, `registry.py` 43,
     > `tmuxio.py` 40. "Retire the keyword-only separators in
     > `test_supervisor.py`" is a stable unit of work; "retire 705 findings" was
     > wrong within a week of being written.
     >
     > **`.19` contributed ZERO of these**, and the scan is why: it does not
     > reach `tests/`. All 25 semantic-role rows are `overseer/*` plus the
     > footgun hook; none of the four new integration modules appear. Do not
     > attribute the move to the new test tier. Full record on
     > **`overseer-hbr.22`**.
   - **Item 5 — the deferred public entry-point surface** for the two
     executables (the demoted `reportPrivateUsage` findings). Anchored on
     **`overseer-hbr.22`**.

     > **MEASURED FOR THE FIRST TIME 2026-07-26 — it looks SATISFIED, and the
     > evidence is sabotage-verified.** This item had a description but no
     > measurement, unlike item 3. It has one now.
     >
     > Both executables are **12-line thin trampolines** (`from overseer.start
     > import main` / `from overseer.daemon import main`) with **no dotted
     > private access and no pyright suppressions** in either — the public
     > surface those findings were deferred pending was evidently delivered by
     > `overseer-m5dtmj` and `overseer-dmtv6w`, both closed. Both executables ARE
     > in pyright's scope: `[tool.pyright] include` names them individually,
     > precisely because `include` resolves by extension and `overseer` alone
     > would not reach them.
     >
     > **`just check-types` reports 0 errors — and the rule can actually fire.**
     > "Strict mode implies `reportPrivateUsage`" is a documentation claim, so it
     > was tested rather than trusted: injecting a cross-module private access
     > into a pyright-included product module produced
     > `error: "_key" is private and used outside of the module in which it is
     > declared (reportPrivateUsage)` and failed `check-types`. Reverted; the
     > throwaway worktree was destroyed. So the clean result is a real negative,
     > not a silent skip.
     >
     > **The caveat that keeps this honest:** pyright EXCLUDES the beside-tests,
     > so this says nothing about private usage in tests — and there is plenty.
     > All **45** Phase-0 "banned cross-module `_`-prefixed call" findings live in
     > `test_supervisor.py` (39) and `test_registry.py` (6), **zero** in the
     > executables. Those are a DIFFERENT rule and remain **item 3's** debt.
     > Conflating them is the easy mistake: closing item 5 does not reduce that
     > 45 by one. (Those 45 were checked FIRST as candidates for item 5's
     > "demoted findings" and are not them.)

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
