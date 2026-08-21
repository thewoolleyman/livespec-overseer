# The hourly plan roster: a per-tick table of every active plan, with a column for the foreman's own inaction

Opened 2026-08-21 (UTC) at maintainer direction. Every measurement below was
taken from `/data/projects/livespec-overseer` on that date against a healthy
daemon (`~/.livespec-overseer-status.json`, `written_at
2026-08-21T23:17:33Z`, `daemon_package.version 1.21.0`, matching master's
released tag — so nothing here is an artifact of a stale daemon).

## What was asked for

After every hourly tick of `/foreman`, print a table of every active plan in
this repo, one row per plan, with these columns:

1. plan / tmux / session name — all three should be identical; print a
   descriptive error when they are not
2. brief status, one sentence, at most 10 words
3. action needed, when the plan is not actively working OR is done and ready
   to archive — one sentence, at most 20 words
4. why the foreman is not taking that action to unblock — one sentence, at
   most 20 words — **especially** when the foreman has been directed to take
   full autonomy and a `full_autonomy` mode is set in the livespec config
5. a status emoji

An emoji legend follows the table on one line. The skill must also carry
guidance telling the foreman to reflect carefully on column 4 and confirm it
is not dropping the ball on its foreman duties.

**The request says "four columns" and then enumerates five.** This thread
carries five; the enumeration is explicit and the word count is not. Recorded
here so the discrepancy is not silently resolved twice in opposite directions.

## Why this is worth building — the roster the foreman is not printing today

At the single healthy tick measured above, this repo had **twelve** active
plans. Joining `plan/*/` against the daemon snapshot:

| plan | daemon status | picker_open | stall |
|---|---|---|---|
| `fix-restart-problem` | `working` | no | 0 |
| `foreman-improvements` | `working` | no | 0 |
| `model-preserving-restarts` | `working` | no | 0 |
| `supervision-safety-and-attention-truth` | `working` | no | 0 |
| `foreman-picker-mutes-its-own-loop` | `idle-with-context-left` | no | 0 |
| `fleet-plumbing-and-dispatch-reliability` | `parked-delivery` | **yes** | 3786s |
| `grooming-skill` | `parked-delivery` | **yes** | 3787s |
| `test-and-gate-integrity` | `parked-delivery` | **yes** | — |
| `track-record-type-safety` | `picker-stalled` | **yes** | 3786s |
| `caam-anthropic-loop` | `session-gone` | no | 0 |
| `overseerd-observability` | `session-gone` | no | 0 |
| `overseerd-release-currency` | `session-gone` | no | 0 |

**Seven of twelve were not working**, four of them sitting on pickers stalled
for about an hour, and three with no live session at all. The daemon detected
every one of these correctly and published them. Nothing was broken. What was
missing was a surface that puts all twelve in front of the foreman in one
place, every tick, with a column the foreman has to fill in explaining itself
for each of the seven.

That is the whole argument for this thread: the evidence already exists and is
already correct; the accountability does not.

It is the same failure `AGENTS.md` records under §"Decision authority" — a
foreman track here sat roughly sixteen hours parked on a picker whose option 1
was its own recorded next action, and escalated five self-decidable calls as
maintainer questions. A roster with column 4 makes that state cost the foreman
a written, per-tick justification instead of silence.

## Finding 1 — `full_autonomy` does not exist yet, anywhere in the fleet

Measured across all four repo checkouts, excluding `.git`, `.venv`,
`worktrees`, and `node_modules`:

| repo | files containing `full_autonomy` |
|---|---|
| `livespec-overseer` | 0 |
| `livespec` | 0 |
| `livespec-dev-tooling` | 0 |
| `livespec-orchestrator-beads-fabro` | 0 |

Zero, fleet-wide. There is no such key in `.livespec.jsonc`, in
`SPECIFICATION/`, in `overseer/`, or in the shipped plugin surface.

The nearest existing lever is **`foreman_valve_disposition`**, set in this
repo's `.livespec.jsonc` to `consensus`, and resolved — never assumed — by

    "$PLUGIN_ROOT/bin/foreman-valve-disposition" --repo "$PWD"

which reports an `effective` value of exactly `report-only` (the fail-closed
default, and what an unset or unrecognized value resolves to) or `consensus`.

A sibling tmux session `foreman-full-autonomy-option` was created
2026-08-22T00:50 local, so the key is being designed on its own thread right
now.

**Consequence for this thread, and it is the load-bearing one: this plan MUST
NOT define `full_autonomy`.** It consumes the setting and must behave
correctly for four states — key absent (today's reality), `report-only`,
`consensus`, and a future `full_autonomy` — resolving through the existing
resolver and degrading fail-closed when the value is unrecognized, exactly as
`foreman.md` already requires. Defining the key here would collide with the
sibling thread and would put a governance decision in a reporting change.

## Finding 2 — the roster must be driven from `plan/`, not from the daemon snapshot

The daemon snapshot is **fleet-wide**: 69 rows at the measured tick, carrying
topics belonging to other repos (`05-hetzner-fleet-member`,
`07-build-substrate`, `09-tailscale-admin-uplift`, and so on). Only twelve of
those rows correspond to this repo's plans.

So the authoritative row set is the direct child directories of `plan/`,
excluding `plan/archive/`, **left-joined** onto the daemon rows by topic. Two
failure modes follow directly, and they are opposite:

- Filtering the daemon snapshot instead would emit rows for other repos'
  topics — noise the foreman has no authority over.
- It would also **drop a plan that has no daemon row at all** — and that is
  precisely the row most in need of attention, because it means nothing is
  watching that plan.

A left join from `plan/` makes the second case render as a row with an
explicit "no daemon row" status rather than as an absence.

## Finding 3 — the name-identity check currently cannot fail, so it needs a negative control

Column 1 asks for a descriptive error when the plan, tmux, and session names
disagree. Measured today: **12 of 12 live plans have an exactly-matching tmux
session; 0 mismatches.**

That is a healthy invariant and a hazard. A check written against today's tree
passes every row and has never been observed rejecting anything — the
"check that cannot fail" shape `AGENTS.md` warns about. Acceptance for this
work must therefore include a **discriminating negative control**: a fixture
with a plan directory having no same-named session, and a fixture with a
session having no same-named plan, each producing its own distinctly-named
error. Without that, a green check is not evidence the check works.

There is also a subtlety the naive check would miss. Three plans above read
`session-gone` in the daemon while a tmux session of that name still exists —
`caam-anthropic-loop` is one. **A tmux session existing is not the same as the
daemon tracking a live session for that topic**, so "the three names agree" and
"there is a live tracked session" are two different questions and column 1
answers only the first. Column 2 answers the second.

## Finding 4 — the roster must be printed BEFORE any picker is raised in the tick

The sibling thread `plan/foreman-picker-mutes-its-own-loop` measured that a
Claude Code session parked on an open `AskUserQuestion` receives **no**
scheduled-task fires, and the missed occurrences are dropped rather than
backfilled — corroborated across 20-plus sessions in 6 repos.

Applied here: a roster emitted *after* a picker in the tick sequence never
prints at all, and it stops printing permanently from the first tick that ends
on a picker. The roster would go silent at exactly the moment its column 4
becomes most valuable.

So placement is part of the contract, not a stylistic choice: **the roster is
emitted before any `AskUserQuestion`, and before `overseer-declare ready` in
the §"Self-initiated wind-down floor" sequence.** The wind-down tick is the one
whose roster the successor session most needs.

## Finding 5 — the roster must be reconciled with §"Tick reporting discipline", which reads as forbidding it

`foreman.md` §"Tick reporting discipline" currently says, emphatically:

> LIST A STANDING ITEM ONCE, BY ID, AND DO NOT RE-ARGUE IT. An item that was
> reported on an earlier tick and has not moved is named by its work-item or
> session id and nothing more.

Read literally, a table that restates all twelve plans every hour is the thing
that rule was written to stop. An implementer will hit this contradiction and
must not be left to resolve it alone.

**The reconciliation, which this thread adopts and which the prose change must
state outright:** the rule targets *re-argument* — history, rationale, and the
case for an item — and its stated harm is a report that "grows monotonically
while the thread stands still". The roster is a **bounded mechanical roster**,
not a narrative: fixed columns, one row per plan, and hard budgets of 10 / 20 /
20 words. Those budgets make re-argument impossible by construction, and the
roster's whole value is the completeness the list-once rule gives up. A stalled
plan that goes unmentioned is the failure being fixed.

So: the roster is exempt from list-once. **The prose half of the tick report is
not, and must not repeat what the roster already carries.** Stating the exemption
narrowly is what keeps the original rule intact.

## Finding 6 — the roster must not be written into the handoff entry

Step 4 of the plan operation requires that a handoff entry "does not embed a
parallel checklist or status queue. Status is composed from the ledger via
`list-work-items` and `next`." The roster is exactly such a status queue, and
persisting it into a handoff is the natural thing an implementer would reach
for.

Durable roster state belongs under `tmp/overseer/foreman/`, per One Tick step 6
("Leave durable state only under `tmp/overseer/foreman/`"), and nowhere else.

## Finding 7 — column 4 needs a closed admissible set, or it becomes a rationalization field

Column 4 is the only column that cannot be derived mechanically, and it is the
only one whose failure mode is that it gets filled in fluently and wrongly. A
free-text "why I did not act" field invites exactly the sentence `foreman.md`
already bans:

> NAME WHO CAN ACT INSTEAD OF QUOTING YOUR OWN CONTRACT. A sentence of the form
> "I cannot do X, my contract does not permit it" tells the reader nothing they
> can use.

This thread proposes that the prose define column 4 as a **closed set of
admissible answers**, so that "I could not think of a reason" resolves to
acting rather than to writing.

**Admissible**, each of which names an actor, a route, or a checkable fact:

- **a. one-action budget spent** — the foreman may propose exactly one
  `foreman-act` proposal per tick (One Tick step 3), so with N stalled plans
  N-1 rows legitimately went unactioned. The answer must **name which plan got
  the action**, so the reader can see a busy foreman rather than an idle one.
- **b. routed** — names the actor and when: the grooming skill, a worker
  session, the review panel, or a ledger action, per §"ROUTE BEFORE YOU
  ESCALATE", and names the specific response being awaited.
- **c. human-gated by design** — permitted only for the §"The floors" cases no
  configuration may relax, and must name the decision being asked for.
- **d. hard external precondition** — a named, re-checkable fact (a red master
  CI, an exhausted credential window, an unlanded sibling PR).
- **e. acting now** — this row is the one action of this tick.

**Inadmissible**, each of which must be rewritten or the foreman must act:

- any restatement of the foreman's own contract as the reason
- "waiting for the maintainer" without naming the decision asked for
- "not yet investigated" or "unclear" — per §"Research before gating", that is
  the action, not a reason to skip it
- "waiting for the next tick"
- re-presenting a plan's single recorded next action as a menu — the exact
  sixteen-hour shape recorded in `AGENTS.md`
- answer (a) repeated for the same plan on consecutive ticks past the
  starvation bound below

### The starvation bound is the part that does the work

Answer (a) is individually valid and collectively lethal: with a one-action
budget and seven stalled plans, "another plan got the action" can be true for
the same row every hour indefinitely. The roster must therefore carry the
**number of consecutive ticks each row has gone unactioned**, and a row past
the bound must escalate rather than repeat (a).

Proposed bound: **2 consecutive ticks** under `report-only` / `consensus`, and
**1** under a future `full_autonomy`. Both are proposals for the maintainer to
set, not measurements. The mechanism — a per-row consecutive-unactioned counter
persisted under `tmp/overseer/foreman/` — is what matters and is what makes
column 4 falsifiable rather than rhetorical.

### How the tiers change column 4

| effective disposition | column 4 obligation |
|---|---|
| key absent | fail closed to `report-only` |
| `report-only` | (c) is broadly available; surface and exit cleanly |
| `consensus` | (c) narrows: a blocked session that the panel could take is not "human-gated" |
| `full_autonomy` (future) | (c) shrinks to §"The floors" only; starvation bound tightens to 1 |

The floors never move. No setting — `consensus` or any successor — authorizes
disposing of a truly unresolvable or by-design human-gated decision.

## Finding 8 — the spam question, answered

The maintainer asked for confirmation that this will not be printed constantly.
It will not, and the reason is structural rather than a matter of care.

A tick is armed by `CronCreate` with an hourly expression avoiding the `:00`
and `:30` marks (`foreman.md` §"Loop Carrier"), and one tick is exactly one
pass through `foreman-runtime`, the gather document, the one-action decision,
and any `foreman-act` revalidation. One roster per tick, hourly, bounded at
twelve rows and roughly 50 words per row — about 600 words per hour at today's
plan count, and the row count is bounded by the number of active plans, which
the archive gates keep from growing without limit.

Every other path moves the frequency **down**, not up:

| path | effect on roster frequency |
|---|---|
| `hard-tick-budget` auto-resume | re-arms at a **doubled** interval — rarer |
| `converged` | schedule cancelled until the maintainer resumes — none at all |
| open picker (Finding 4) | fires dropped, not backfilled — none at all |

**There is exactly one spam vector, and it must be closed explicitly.**
`foreman-runtime` can legitimately be invoked more than once inside a single
tick — §"Arming the loop" requires that on `loop_lapsed: true` the foreman
re-arm and then re-evaluate every `human_wait: true` row **in that same tick**
from a fresh gather. A roster keyed to "each `foreman-runtime` invocation"
would print twice for one tick.

**The guard: emit at most one roster per tick, keyed on the runtime's tick
identity, not on the invocation count.** That is the single mechanical
requirement behind the confirmation above.

## Proposed shape

Split along the line this repo already uses everywhere else — deterministic
wrapper for what must not be forgotten, LLM for what requires judgment:

- **A deterministic helper** (`bin/foreman-plan-roster`, JSON out) owns the
  authoritative row set from `plan/`, the left join onto the daemon snapshot,
  the three-way name-identity verdict, columns 2 and 5, the per-row
  consecutive-unactioned counter, and the once-per-tick guard. These are the
  parts that fail silently when left to memory, and the name-mismatch error is
  a check the foreman must not be able to skip.
- **The prose** (`.claude-plugin/prose/foreman.md`, harness-neutral and shared
  by both harnesses) owns the table's placement in the tick, the word budgets,
  the legend, columns 3 and 4, the closed admissible set, the starvation bound,
  and the list-once exemption of Finding 5.

Proposed legend, one line under the table:

    🟢 working · 🟡 winding down or awaiting restart · 🔴 blocked, action needed · 🔵 done, ready to archive · ⚪ no live session · ❗ name mismatch or unjustified foreman inaction

Columns 3 and 4 are `—` for a 🟢 row. `❗` is reserved for the two conditions
the roster exists to make visible: a name disagreement, and a column-4 answer
that fell outside the admissible set or past the starvation bound.

## Requirement carriers and deferrals

Carried by this thread:

1. The deterministic roster helper, with the left join and the once-per-tick
   guard (Findings 2 and 8).
2. The name-identity verdict **with its discriminating negative control**
   (Finding 3).
3. The prose contract: placement before any picker and before `ready`
   (Finding 4), the columns and budgets, the legend.
4. The column-4 closed admissible set, tier table, and starvation bound
   (Finding 7).
5. The narrow list-once exemption, written into §"Tick reporting discipline"
   itself so the two rules are read together (Finding 5).

Explicitly deferred:

- **Defining `full_autonomy`.** Not part of this thread; it is a governance
  decision being designed on the `foreman-full-autonomy-option` thread. This
  work consumes the resolver and behaves correctly for all four states,
  including the key's absence today. Reconsidered when that thread lands a
  ratified key.
- **Fixing the picker-mute defect.** Owned by
  `plan/foreman-picker-mutes-its-own-loop`. This thread only orders its own
  output so as not to be swallowed by it. Reconsidered if that thread's fix
  changes tick re-entry semantics.
- **Propagating the roster to other foreman-carrying repos.** This thread
  changes this repo's prose only. Reconsidered once the roster has run here
  for enough ticks to show whether column 4 changes foreman behaviour.
- **The exact starvation bound and its per-tier values.** Proposed as 2 and 1;
  these are maintainer settings, not measurements, and are to be ratified
  rather than assumed.

## Read first

- `.claude-plugin/prose/foreman.md` — §"Tick reporting discipline", §"One
  Tick", §"Self-initiated wind-down floor", §"Loop Carrier", §"The floors",
  and §"Human valves and blocked sessions are CONFIG-GATED".
- `plan/foreman-picker-mutes-its-own-loop/research/picker-suppresses-scheduled-ticks.md`
  — why placement is load-bearing.
- `AGENTS.md` §"Decision authority — when to ask, proceed, or self-resolve" —
  the sixteen-hour stall this roster is aimed at.
- `overseer/foreman_gather_collect.py` and `overseer/foreman_gather_render.py`
  — the existing document shape the roster joins against.
