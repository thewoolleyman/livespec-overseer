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
   in EVERY fleet and adopter session, not just this repo. "Works" includes the
   PROMPT TEXT it generates: `overseer-fitvmo` (a CHILD of `overseer-hbr`) carries
   required anti-stall guidance for the generated supervisor-handoff — see
   §"Prompt-text guidance goal 1 must incorporate".
2. **TOP-OF-PYRAMID e2e TESTS EXIST FOR ALL SCENARIOS** in
   `SPECIFICATION/scenarios.md`, **and** the rule that they must exist is present
   AND **enforced**.
3. **The plugin is AUTO-RELEASED** like the other fleet plugins.
4. **The plugin is AUTO-INSTALLED** for the other fleet AND adopter members.
5. **The release pin is AUTO-BUMPED** for consumers.
6. **Phase-2 adopter-family shipping FOLDS INTO the above** — see
   `research/phase-2-adopter-shipping.md` beside this file.

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
- All **21/21** scenario entries in `tests/heading-coverage.json` are
  `test: "TODO"`.

**The "and enforced" clause is the subtle half.** The fleet RULE does exist here:
`just check` wires `check-heading-coverage`, whose direction 4 requires a
`scenarios.md` entry to map to an integration-tier-or-above test. But it accepts
`test: "TODO"` plus a tier-acknowledging reason as compliant — which is exactly
what all 21 entries are. The companion gate `check-no-todo-registry` is
severity-levered by `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST`, and **that
variable is set nowhere in this repo** — it appears only in a `justfile` COMMENT,
never in a workflow. So today the 21 TODOs **warn and can never fail CI**.

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

## NEXT ACTION — groom the six goals into slices

**Nothing is started. Nothing is in flight.**

1. **GROOM** the six goals into dependency-layered, buildable slices under
   `overseer-hbr`, via `/livespec-orchestrator-beads-fabro:groom` — a read-only
   drafting conversation; **the maintainer OWNS every cut and every acceptance**,
   and the front-end files nothing until approval.
2. **Then build** through the normal machinery (`drive --action approve:<id>`
   then `impl:<id>` for factory-tier work).

Likely ordering constraint worth putting to the maintainer during the groom:
goals 3 → 4 → 1 are plausibly a chain (a plugin must be releasable before it can
be auto-installed, and auto-install is what makes `supervise-plan` actually
available), while goal 2 is largely independent and can run in parallel. Goal 5
follows 3. Do not treat that as the cut — it is a starting hypothesis for the
maintainer to accept or replace.

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

## Also open, tracked elsewhere

- **7 untied spec→impl gaps** from the v002 delta
  (`detect-impl-gaps --since-version v001`), no work-item tied to any.
- **`check-no-workflow-edits` copy-drift** across the 4 carrying fleet repos —
  single-sourcing into `livespec-dev-tooling` is dev-tooling's call.

## Operational map

Supervision runs against the live fleet: daemon in tmux `livespec-overseer:1.1`,
stderr log `tmp/overseer/daemon.log` (appends — `overseer-2boaoy`). Protocol:
`overseer/marker-protocol.md`. Invariants a change must not regress:
`overseer/AGENTS.md`. Operator surface contract: `overseer/SKILL.md`. Cross-track
coordination log (shared, still active — append only, never rewrite): livespec
core `tmp/fleet-pin-propagation-supervisor/status.log`. This thread's supervisor
charter: `supervisor-handoff.md` beside this file.
