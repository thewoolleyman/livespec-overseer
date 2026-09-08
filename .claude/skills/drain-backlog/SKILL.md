---
name: drain-backlog
description: Drain a livespec repository's open backlog through the factory without a foreman seat — freeze the scope, triage it in ruled batches, dispatch through detached probe-gated engines, and loop on outcomes until every item is closed or dispositioned. Invoke as `/drain-backlog [--update-snapshot] [--repo <path>]` from any fleet repo, or point a session at this SKILL.md directly.
---

# drain-backlog — own the forest, keep the factory fed

This skill is the operating doctrine that drained `livespec-dev-tooling`'s
258-item backlog on 2026-09-06 (plan `dev-tooling-backlog-drain`, epic
`livespec-dev-tooling-kcoslm`), generalised so any fleet repo can run it.
It is a **discipline over primitives that already exist** — the orchestrator's
`dispatcher.py loop`, `drive`, `needs-attention`, `next`, `groom`, the beads
ledger, `gh`, `fabro ps` — not a new substrate. Nothing here starts a tmux
worker, a foreman seat, or a pane roster.

The single sentence the maintainer wrote that this skill exists to honour:

> Something has to own the forest, because you LLMs ALWAYS lose the forest
> for the trees.

Everything below is one of: a rule that kept the drive moving, or a rule
learned by stalling. Read the whole file once; then execute §2 → §8 in order.

## 0. Invocation and state

```text
/drain-backlog                      # resume (or first run: freeze the snapshot and propose batch 1)
/drain-backlog --update-snapshot    # re-read every open item + plan, re-prioritise, persist a new snapshot
/drain-backlog --repo <path>        # run against another checkout (default: cwd's primary checkout)
```

All durable skill state lives under **`tmp/drain-backlog/`** in the target
repo (`tmp/` is gitignored fleet-wide).

**The skill neither creates nor requires a plan or epic, and never selects
one.** `snapshot.py` issues zero ledger writes (§2), so nothing here files a
plan epic. When a drain runs under a plan epic, that epic was created and bound
EXTERNALLY — by the orchestrator plan skill
(`/livespec-orchestrator-beads-fabro:plan <slug>`), not by drain-backlog — and
WHICH epic a given drain run posts its scope events and handoffs to is
operator/session judgment the skill does not resolve: there is no `--plan`
argument, no metadata match, and no lookup in any shipped script. With no epic,
the drain runs fully in its file-backed mode — dispositions in
`dispositions.jsonl` (§3), the handoff in `handoff.md` (§7) — and
`tmp/drain-backlog/` holds the snapshot and engine artefacts. When the operator
HAS named a plan epic, handoffs and scope events go on that epic instead and
`tmp/drain-backlog/` holds only the snapshot and engine artefacts.

| path | what |
|---|---|
| `tmp/drain-backlog/snapshot.json` | the FROZEN scope: every open id at freeze time, its tier, its order (§2) |
| `tmp/drain-backlog/snapshot-<UTC>.json` | history; one per `--update-snapshot` |
| `tmp/drain-backlog/dispositions.jsonl` | one line per ruled disposition (§3) when there is no plan epic to hold scope events |
| `tmp/drain-backlog/handoff.md` | the handoff + typed next action when there is no plan epic (§7) |
| `tmp/drain-backlog/engine-<label>.log` | one detached engine's journal-shaped log |
| `tmp/drain-backlog/launch-<label>.log` | the launcher's gate trace for that engine |
| `tmp/drain-backlog/last-tick` | ISO instant of the last loop tick (§5) |

Scripts shipped beside this file (`<skill-dir>/scripts/`):

- `snapshot.py` — freeze / `--update-snapshot` / `--status` (§2).
- `plan_completion.py` — `snapshot.py`'s plan half: one record per PLAN, its
  completion state, and the act that would drive it to closed + archived (§2).
- `engine-on-green.sh` — the ONLY way an engine is launched (§4).
- `tick.py` — the §5 tick reader: journal outcomes since the last tick,
  active claims, live runs, open PRs with red checks.

`<skill-dir>` is the directory holding this SKILL.md (the harness prints it as
"Base directory for this skill"). Every ledger call goes through the repo's
credential wrapper: `/usr/local/bin/with-livespec-env.sh -- bd …`. A bare `bd`
that says `Access denied` is a MISSING CREDENTIAL, not an outage.

## 1. Preconditions — measure, never carry a claim

Run these before anything else, every resume, and again before every launch.
A prior session's note about any of them is a claim, not a measurement.

```bash
R=$(ls -td ~/.claude/plugins/cache/livespec-orchestrator-beads-fabro/livespec-orchestrator-beads-fabro/*/scripts/bin/dispatcher.py | head -1 | xargs dirname)
W=/usr/local/bin/with-livespec-env.sh
$W -- python3 "$R/dispatcher.py" claude-cred-status --json | jq .condition     # MUST be "usable"
gh api "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions/workflows/ci.yml/runs?branch=master&per_page=1" \
  --jq '.workflow_runs[0] | "\(.status) \(.conclusion) \(.head_sha[0:8])"'    # master green?
fabro ps --server "$FABRO_SERVER"        # bare `fabro ps` hits the wrong server; the URL is in the run config
$W -- bd list --status active --json | jq length                                # counted claims vs wip_cap
grep -o '"wip_cap": *[0-9]*' .livespec.jsonc                                    # the cap (it counts LEDGER claims)
pgrep -af "dispatcher.py loop --repo $(pwd)" | grep -c python3                  # engines alive?
```

The 2026-09-06 lesson, verbatim in the dev-tooling AGENTS.md: three resumers
slept until a "resets 13:50Z" read from a 429 body while the credential was
usable and the dispatcher held no exhaustion record. **Gate on the probe and
master CI, never on a claimed reset time.** Never write a "sleep until HH:MM"
script. The dispatcher's own exhaustion hold is a bounded 15 minutes and the
orchestrator measured provider-stated instants to be wrong by orders of
magnitude.

## 2. The snapshot — freeze the forest

First run, or `--update-snapshot`:

```bash
$W -- python3 <skill-dir>/scripts/snapshot.py --repo . [--update]
$W -- python3 <skill-dir>/scripts/snapshot.py --repo . --status     # closed-of-frozen, any time
```

`snapshot.py` makes exactly ONE ledger call — `bd list --all --limit 0 --json`
(**`--all`**: the default listing hides closed items and any "no item covers X"
claim without it is unsound) — and issues ZERO ledger writes: it never updates a
status, never comments, and never creates a plan or epic. Every durable write it
makes is to a file under `tmp/drain-backlog/`. From that one read it collects
every open work item as the frozen scope and enumerates the plan-bearing items
into a reported `plans` list.

**The unit of ITEM work is the individual frozen work-item id.** `frozen_ids` is
every open id at freeze time; a plan epic is one ordinary row in that set, not a
container the drain expands into more ready items. Progress is re-read from the
ledger on every `--status` and never stored in `snapshot.json`.

**A PLAN is the drain's SECOND unit, and it is COMPLETABLE.** A plan is finished
when every work item under its subject epic — including a review of the epic
itself — is closed, and a finished plan must reach epic-closed AND
directory-archived. Nothing used to drive that, so finished plans sat open
indefinitely. `plan_completion.py` computes one record per plan and every
`--status` and every Markdown report carries them (§9's exit gate reads the
same records). The drain still never archives on a status flip: the record
NAMES the act; the session runs it through the plan's own gates.

**Plan identification uses BOTH routes, and is deduped by slug.** A slug is a
plan if a `plan/<slug>/` DIRECTORY exists (excluding `plan/archive/`) OR any
ledger row carries `metadata.plan_slug`. Neither key alone is sufficient, and
both failure directions were measured against `livespec-dev-tooling` on
2026-09-08:

- **The metadata key MISSES.** Four of eight plan directories there had no epic
  carrying their slug, so a metadata-only membership key could never reach them.
  The directory route reports them, and the plan's own
  `associated_work_item_id` anchor file resolves the subject epic when no row
  carries the slug.
- **The metadata key also OVER-COUNTS**, because children INHERIT their epic's
  slug: 40 rows came back plan-bearing for 8 directories, and
  `performance-improvements-01` appeared ELEVEN times. Records are keyed by
  SLUG, one per plan, and the subject epic is a ROOT id — never an inheriting
  child.

**The seven plan states, and which four need an act:**

| state | meaning | act |
|---|---|---|
| `finished-unarchived` | epic OPEN, ≥1 child, EVERY child closed, directory live | **drive it: dispose the children, run an independent completeness review of the epic itself, close the epic, archive `plan/<slug>/`** |
| `epic-closed-directory-live` | epic closed, directory still live | archive it through the plan gates, or reopen the epic |
| `epic-open-directory-archived` | directory archived, epic still open | dispose, review, close the epic |
| `unlinked` | directory live, no subject epic reachable by slug OR anchor | link it, then re-read completion |
| `in-progress` | open work remains (or the epic has NO children yet) | none |
| `archived` | directory archived and the epic closed | none |
| `cross-tenant-anchor` | the anchor file carries the `unassigned` sentinel | none HERE |

Two of those rows are load-bearing and were paid for:

- **`finished-unarchived` is the failure that actually occurs, and the
  predecessor detector was pointed at its INVERSE.** `stale_plans()` fired only
  on "epic CLOSED and directory live"; run over that whole tenant it flagged
  NOTHING, while `console-factory-build-cache` (epic `3u3gm2` at `backlog`, both
  children closed, directory live) sat finished-but-unarchived and unseen.
- **`cross-tenant-anchor` is a DECLARATION, not a missing link.** The anchor file
  cannot express a cross-tenant epic, so a plan whose real anchor lives in
  another tenant writes the sentinel `unassigned` rather than a false local id
  (`mutation-testing-keystone`, anchored on `livespec-mutreal` in the livespec
  tenant). It is never reported as `unlinked`: a check that fires permanently on
  a correctly-declared plan is a check that comes to be ignored.

An epic with NO children is `in-progress`, never finished — "every child is
closed" is VACUOUSLY true of an epic nobody has filed work under.

The per-row `plan_slug` / `plan_dir_live` flags remain what they always were: a
`plan:<slug>` annotation in the tier table, surfaced with `(dir missing)`. They
annotate a ROW; they do not decide plan membership.

It writes `snapshot.json` and prints a Markdown proposal grouped by tier:

1. **Factory-path defects** — anything that makes a factory run or a hand
   commit in this repo fail for reasons unrelated to the item it carries:
   commit hooks, the gate runner, the sandbox image, the dispatcher's typed
   inputs, CI lanes that red every PR, pin/lock drift. Worked FIRST, by hand
   where the factory cannot fix the path it runs on.
2. **Enforcement-suite correctness** — checks that pass vacuously, pass on a
   half-pair, or fail on a true positive. A false green poisons every later
   tier's evidence.
3. **P0/P1 epics and their children.**
4. **The long tail**, by priority then age.

The tiering is a HEURISTIC over titles, labels and priority; the printed
proposal says so per item (`tier_reason`). The session reads each tier-1 and
tier-2 candidate's own text before ruling, and moves anything mis-tiered. Items
already `blocked` with `needs-human` are listed apart as **valves** (§3);
titles that name another tenant (`livespec CORE`, a driver, the orchestrator)
are flagged `refer_candidate`.

Rules that make the snapshot a scope and not a status board:

- **The exit gate** is: every id in the snapshot is `closed`, or carries a
  recorded disposition. Progress is read fresh from the ledger, never written
  into the file. A status column in a file is a shadow ledger.
- **Nothing filed after the snapshot extends the plan** unless admitted under
  §6. `--update-snapshot` keeps the original `frozen_ids` and marks later
  arrivals `admitted_after_snapshot`; it never silently widens the exit gate.
- **`--update-snapshot` re-prioritises everything open**, including plans,
  and persists a dated history file. Run it when a tier drains, when a batch
  ruling reshapes the set, or when the maintainer asks for a fresh read.

## 3. Triage — batches, the sorting rule, rulings

Dispositions are proposed **in batches grouped by class**, one tier at a time,
never one item at a time. Each item gets exactly one disposition:

| disposition | meaning |
|---|---|
| `keep` | dispatchable as written; enters the ready set in tier order |
| `re-scope` | the intent survives, the shape does not: rewrite title/acceptance before dispatch, or hand to `groom` |
| `superseded` | exists only to serve a retired mechanism (a transport, a seat, a landed design); close with the reason |
| `consolidate` | duplicates or fragments another; close into the survivor and comment the survivor with what it absorbed |
| `close` | cruft: no longer true, already landed (MEASURE it on master first), or not worth its cost |
| `refer` | cross-tenant: file or link in the owning tenant, record the id here, close here; never work around it locally |
| `hold` | a named cross-tenant or plan-owned condition; comment the hold, leave open |

**Decide, then report for objection.** A disposition the session is confident
about is proposed as DECIDED. A question with a recommendation is a finding.
Only genuine doubt is put as a question — one question per batch, never a
picker per item. When the maintainer says "your plan should be clear unless
there are blockers", that is the standing ruling: decide the batch under the
decision-authority rule, record it, execute it, report.

**Record the ruling before executing it**: a scope event on the drain's plan
epic when the operator has named one (`record_scope_event`, requirement
carriers + explicit deferrals) — the skill does not itself resolve which epic
that is (§0) — or one line per disposition in `dispositions.jsonl` when there is
no epic. Every closure names the ruling in its close reason (`… (drain batch N)`).

**Valves** (`blocked` + `blocked-reason:needs-human`): resolve each as a
finding with the decision written into the acceptance field, then
`drive --action "resolve-blocked:${id}:ready" --answer "<the decision>"`.
Write the action id with **braces**: in zsh, `$id:ready` is eaten by the `:r`
modifier and arrives as `<id>eady` — the 2026-09-06 session lost three calls to
it before reading the error.

**Acceptance criteria are authored at dispatch time**, from the item's own
measured text, and MUST be gradeable: name the behaviour, the test that proves
it (positive and negative control), and `just check green`. The engine refuses
an item without them.

## 4. Execution — everything goes through the factory

The only execution verbs for a work item are `drive --action impl:<id>` and
the dispatcher loop. **Exemption is a closed enum**, carried as a ledger label
because the orchestrator's `factory-bypass-audit --allow-label` reads it:

- `factory-exempt:infra-in-person` — a host, secret, registrar, or billing act
  no sandbox can perform.
- `factory-exempt:factory-path-defect` — the item IS a defect in the path a
  factory run takes (hooks, gate runner, sandbox image, dispatcher inputs, a CI
  lane that reds every PR). The factory cannot fix the thing that blocks it.
- `factory-exempt:workflow-only` — the diff is entirely under
  `.github/workflows/`, which the App token cannot push. Retires when it can.

Classify at triage, record it in the ruling, label the item, and only then
hand-work it through worktree → PR → merge → cleanup. **Hand-fixing a
dispatchable item because "it's quicker" is the leak this rule closes.**

**A failed run is re-dispatched or groomed, never hand-fixed.** On a failed
outcome: read the journal outcome's `detail` (the `✗` node and `Error:` line),
and the run dump when it says nothing (`fabro dump <run> --server … -o <dir>`,
then `stages/*/response.md`). Then exactly one of:

- **re-dispatch once** — the failure is in the run's environment: ACP turn
  timeout, provider 429, sandbox setup, a push refused by fleet state. Return
  the item to `ready` with a comment "RE-DISPATCH 1 of 1 …", and relaunch.
- **groom** — the same node fails twice, or the item is oversized.
- **close as landed** — the implementer found the work already on master and
  verified the criteria (dev-tooling `l5pw`, 2026-09-06: zero-diff run, all
  criteria verified against sibling sources). Close with the run id and the
  landing commit; do not re-dispatch a zero-diff item.
- **file discovered-during** — the failure exposes a factory-path defect:
  `bd create … --deps discovered-from:<snapshot-id>`, labelled exempt if the
  factory cannot land it, then hand-work it.

**The engine.** Launch ONLY through the shipped launcher, DETACHED:

```bash
setsid nohup <skill-dir>/scripts/engine-on-green.sh <label> <parallel> <id>... \
  > tmp/drain-backlog/launch-<label>.log 2>&1 < /dev/null &
```

Its gates are, in order: the credential probe returns `usable` (retrying every
5 minutes, never a clock), the dispatcher's exhaustion record is retired via
the codified `clear-provider-exhaustion` valve when one is held while the
probe is usable, and the newest master CI run is green. Then it starts one
`dispatcher.py loop --budget <n> --parallel <k>` under `setsid nohup` so the
engine outlives the shell and the LLM session. **Never make a run's survival
depend on the chat session being alive.**

`wip_cap` counts LEDGER claims, not live sandboxes: an engine ledger-admits its
whole `--item` list at start. Two engines with 12 items hold 12 claims. A
launcher that reports `capacity-deferred` has exited; relaunch it when the
active count drops below the cap. Keep live sandboxes on the shared factory
host to what its capacity verdict allows; state capacity only from a verdict,
otherwise say "unknown".

## 5. The loop without panes

The session IS the loop. Resume = run this skill, take the typed next action,
and **in the same turn** invoke `/loop` with no interval. A session that has
resumed a drain and is not looping is STALLED BY DEFINITION: it has no watcher,
so nothing it dispatched can reach it.

The `/loop` prompt, verbatim (fill the two placeholders; keep the rest):

```text
/loop drain-backlog tick for <repo> (<plan epic or "no plan epic">): read the three sources —
tmp/fabro-dispatch-journal.jsonl outcome events since the last tick (tick.py), needs-attention,
and the open PRs — plus the engine logs under tmp/drain-backlog/ and live runs via
fabro ps --server <FABRO_SERVER>. Act only on what is ripe: re-dispatch a run-environment
failure once, groom a repeat, close a zero-diff "already landed" run as landed, close merged
items on CI evidence, work the valves as findings, launch the next keeps as claims free
(wip_cap counts ledger claims; engines DETACHED through scripts/engine-on-green.sh, which gates
on the credential probe and master CI, never on a clock), file discovered-during defects with
discovered-from provenance, and propose the next batch when a tier drains. Healthy waits are
silent: write nothing to the ledger when nothing changed. A tick report lists what changed by
id. Verify by the authoritative source (bd show --json, gh pr view, the journal's outcome
event, fabro ps --server), never by a peer's claim.
```

Each `ScheduleWakeup` passes that prompt back verbatim, `noop: true` when the
tick changed nothing, and a 1500–1800 s heartbeat; the Monitor is the wake
signal. Handle a `<task-notification>` in the context of the loop and then
re-schedule the same heartbeat.

Arm ONE persistent Monitor on the dispatch journal that is **replay-safe** —
the dispatcher rewrites the journal file, and a `tail -F` replays it from the
top and floods the session. Poll the line count every 60 s and print only new
outcome lines (`tick.py --follow` does this), plus the open PRs you are
waiting on.

Each tick reads three sources and acts only on what is ripe:

```bash
$W -- python3 <skill-dir>/scripts/tick.py --repo . --server "$FABRO_SERVER"
$W -- python3 "$R/needs_attention.py" --project-root .
gh pr list --state open --json number,title,mergeStateStatus,statusCheckRollup
```

Ripe acts, by outcome:

- `done green` → nothing; the engine closed it. Count it.
- `failed` / `blocked needs-human` → §4's four-way decision.
- a factory PR `BLOCKED` on a red lane → **read the failing job's own finding
  before re-running anything** (`gh run view --job <id> --log-failed`). A
  rerun is only for a failure you have identified as transient; a docs-only
  PR failing a code lane is usually fleet state, and the fix is a tiny PR of
  its own (dev-tooling `cwtk`: one `cross_repo_public_api` entry unblocked
  every PR).
- a PR branch that predates a fleet-state fix on master → `gh api -X PUT
  repos/<owner>/<repo>/pulls/<n>/update-branch`, **one call per PR, never in a
  shell loop** (the rate-limit guard denies looped mutations). The
  fleet-conformance lane reads the self member from the PR checkout, so a
  rerun without the branch update fails identically.
- a stale remote branch after merge → `gh api -X DELETE
  repos/<owner>/<repo>/git/refs/heads/<branch>`; a push from the primary
  checkout, even a deletion, is refused by the hook.
- claims below the cap and keeps still queued → launch the next wave.
- a tier drained → propose the next batch (§3), then `--update-snapshot`.
- a plan the snapshot reports `finished-unarchived` → **drive it to done in that
  tick**: dispose every child, run an independent completeness review of the
  epic itself, close the epic, then archive `plan/<slug>/`. The other three
  actionable states (§2) are worked the same way, from the record's own act. A
  finished plan left open is exactly the condition this skill used to be blind
  to; it is ripe the moment it is reported.

**Healthy waits are silent.** Write nothing to the ledger when nothing
changed. A tick report lists what changed, by id, and does not re-argue
standing items. Fallback heartbeat 20–30 minutes; the Monitor is the wake
signal. Verify by the authoritative source — `bd show --json`, `gh pr view`,
the journal's outcome event, `fabro ps --server` — never by a peer's claim,
and never by silence: a run you cannot see is a run you have not measured
(`fabro ps --all | tail` lists finished ones).

## 6. Anti-yak-shaving — what may be filed

During a drain a new work item is created only when it is one of:

1. a **child of an open epic** that is itself in the snapshot;
2. a **discovered-during** defect that blocks a snapshot item, filed with
   `--deps discovered-from:<snapshot-id>` so provenance is a ledger edge;
3. a **consolidation** that closes two or more snapshot items into one;
4. a **mechanical child the drain files for itself** (the item-provenance
   ratchet, the factory-bypass red gate, the probe-gated launcher).

Anything else is one line in a `PARKING LOT` comment on the plan epic (or in
`handoff.md`) and is not filed. Inventing an item is not progress on anything
the drain measures. `bd create` files at `backlog`; move a keep to `ready`
yourself before an engine will take it.

Cross-tenant work follows the never-work-around rule: file or link the item in
the owning tenant, record the id here, and do not substitute a local
workaround. Product changes in another fleet repo go **spec-first** there — a
proposed change against its `SPECIFICATION/`, ratified through `revise`, then
implemented through its factory — never as a hand fix from outside.

## 7. Handoffs and resume

A handoff is ready only when a fresh session can continue from it with no
chat history. It carries: the state read fresh from the ledger (a pointer, not
a board), which engines are detached and where their logs are, every
cross-tenant id filed, the open valves, the read-first chain, and **one typed
next action** (`kind: impl|spec-op|human|none`, `ref`, one imperative
sentence). On the operator-named plan epic (§0 — the skill does not select it)
use `append_handoff` (it writes the typed action); without an epic, write the
same fields to `tmp/drain-backlog/handoff.md`.

The prose `next action:` line carries no authority; the typed field wins.

Resume protocol, in one turn: preconditions (§1), read the handoff, take the
typed action, arm the Monitor, invoke `/loop`. Do not open by asking the
maintainer which action to take when the typed action is dispatchable.

## 8. Evidence discipline and the gotchas that cost time

- **The ledger needs the wrapper**; `Error 1045` is a missing credential.
- **`bd list` hides closed items** unless `--all --limit 0`.
- **`bd exited zero with stderr`** printed by the package primitives is noise.
- **`pkill -f <pattern>` matches the shell running it** when the pattern is in
  its own argv; anchor it (`pkill -f "^/bin/bash .*<script>"`).
- **`ls` may be aliased to `lsd`** on fleet hosts and breaks path capture.
- **`echo ======` fails in zsh** (`=cmd` expansion); use `printf`.
- **The commit aggregate can outlast the harness's 20-minute tool ceiling**;
  a killed gate has NO verdict and is not a refusal. Use the pack's
  `gate-start` / `gate-wait` and read the verdict, never silence.
- **A needs-human run with no question on the item** has its reason in the
  run dump's `stages/*/response.md`, not in the journal.
- **`clear-provider-exhaustion` says "nothing to clear"** when no record is
  held; that line is success, not an error.
- **A plan-package snippet needs the bootstrap**:
  `sys.path.insert(0, "<plugin-root>/scripts/bin"); from _bootstrap import bootstrap; bootstrap()`
  then `resolve_store_config(cwd=repo, work_items_arg=None)`.
- **Two engines admit independently** up to the cap each; count claims from
  the ledger, not from what you launched.
- **Never write durable state into a component you have not confirmed is
  running the code that preserves it.** Adoption first, then arming.

## 9. Exit

The drain is complete when `snapshot.py --status` reports every frozen id
closed or dispositioned **AND `plans_needing_action` EMPTY**, every engine has
exited, no worktree or branch from the drain remains, and the final handoff
names the follow-up plan(s) or item(s) that carry anything transferred out.

**The plan half of that gate is not a footnote.** Every plan the snapshot can
identify — by directory or by ledger slug, §2 — must have reached
`archived`, `in-progress`, or `cross-tenant-anchor`; a `finished-unarchived`,
`epic-closed-directory-live`, `epic-open-directory-archived` or `unlinked`
plan is unfinished drain work, including the drain's OWN plan. Driving one to
done means: dispose every child, run an INDEPENDENT completeness review of the
epic itself, close the epic, then archive `plan/<slug>/`. A drain never
archives itself on a status flip — the report names the act; you run it
through the plan's own gates and the ledger is what records it.
