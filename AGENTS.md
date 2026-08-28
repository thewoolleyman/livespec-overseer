# livespec-overseer — repo orientation

livespec-overseer is the Control-Plane operator tool for livespec: a
two-pane tmux supervisor that watches every tracked agent session's
remaining context headroom, injects an escalating wrap-up at threshold, and
atomically restarts a session ONLY once that session has declared itself
`ready` on the filesystem. Repo class: `control-plane-tool` — a peer of the
operator console, never a component of it, and an ordinary pin-consuming
fleet member (its enforcement gates come from the pinned
`livespec-dev-tooling` release).

## Layout

| Path | Purpose |
|---|---|
| `SPECIFICATION/` | The live livespec specification governing the supervision contract (maintained via the `/livespec:*` lifecycle) |
| `overseer/` | The supervision package: eight stdlib-only modules, the `overseerd` daemon and `overseer-start` bootstrap executables, their beside-tests, and the deep maintenance docs |
| `tests/` | Repo-level test fixtures (`heading-coverage.json`) |
| `justfile`, `pyproject.toml`, `lefthook.yml`, `.mise.toml`, `.livespec.jsonc`, `.beads/` | Fleet-standard toolchain, livespec, and work-items configuration |

## The three module documents

Read these beside the code before changing anything in `overseer/`:

- `overseer/marker-protocol.md` — the wrap-up + state-declaration protocol
  between the daemon and a supervised session (the cardinal rule, the one
  state file, the restart interlock).
- `overseer/SKILL.md` — the interactive bottom-pane operator contract.
- `overseer/AGENTS.md` — the maintenance guide: architecture invariants
  that must not regress, load-bearing tmux mechanics, and live-exercise
  guidance.

Those three documents are CURRENT — read them as authoritative. They
predate the relocation of this package out of livespec core, but that
staleness was swept out (work-item `overseer-zvo`, closed). Re-measured
2026-07-30: **zero** `.claude/skills/overseer/` path references across all
three, and no "local-only to this repo" framing — the single `local-only`
string in `overseer/AGENTS.md` (line 403) describes the externally-sandboxed
HOST, justifying a codex flag, and is not about the package's scope.

That date moved because the previous re-measure was not enough. It was taken
2026-07-26, four days before `.ai/` existed, and two of these documents went on
denying that directory's existence in the PRESENT TENSE — which a reader obeying
the instruction above met as authoritative while working on the very directory
being denied. Both are re-tensed, and
`tests/test_module_docs_match_the_repo.py` now gates the claim so that premise
cannot rot silently again. **Re-measure before refreshing this date; a
"CURRENT" assurance is itself a claim with a timestamp.**

**THIRD RE-MEASURE, 2026-08-01, AND IT QUALIFIES THE ASSURANCE ABOVE — read this
before treating `overseer/AGENTS.md` as a complete map.** The two earlier
re-measures checked PATH references and TENSE. Checking a third thing — whether
what the docs ENUMERATE matches what the tree HOLDS — found the architecture
inventory badly behind: it names **five** `supervisor.py` collaborators while
`ls overseer/_supervisor_*.py` returns **26**, and 22 private modules (~4,069
lines) were named in none of the three documents, including whole subsystems
(`_supervisor_evaluate`, `_supervisor_discovery`, `_supervisor_observe`,
`_supervisor_restart`, `_supervisor_pair`, `_supervisor_attention`,
`_supervisor_liveness`). The measurement is recorded in `overseer/AGENTS.md`
beside that list. The gap is DOCUMENTATION, not dead code — those modules ship
real features.

**FOURTH RE-MEASURE, 2026-08-19 — THE INVENTORY FIGURE ABOVE HAS ROUGHLY DOUBLED,
so treat the 2026-08-01 numbers as historical.** Same scope: `_supervisor_*.py` on
disk went **26 → 55**, modules named in none of the three documents went **22 → 37**,
and unnamed lines went **4,069 → 5,004** (all private `overseer/_*.py`: 75 on disk,
51 unnamed, 6,798 lines). Measured against that note's own residue — it had reduced
the figure to 15 modules / 1,968 lines the day it was written — the debt grew
**15 → 37 modules** in eighteen days. A reader taking "26 on disk" at face value
today underestimates the subsystem by half.

The other two premises behind the CURRENT assurance were re-checked at the same time
and BOTH STILL HOLD: **zero** `.claude/skills/overseer/` path references across all
three documents, and the `.ai/` present-tense premise still passes its gate. Only the
inventory aged. The `local-only` string still describes the externally-sandboxed
HOST exactly as recorded below — but it has MOVED, from line 403 to line 505, which
is its own small lesson: **grep for the string, do not navigate to the cited line.**
A line number is a measurement too, and this one aged in eighteen days while the
claim it points at stayed true.

**And note precisely what is and is not gated**, because the sentence above is
narrower than it reads: `tests/test_module_docs_match_the_repo.py` gates exactly
ONE premise — that no authoritative doc denies `.ai/` exists in the present tense.
It does not check inventory accuracy, and nothing else does either. So these three
documents remain the right things to read, and their INVARIANTS and mechanics are
still authoritative; what you cannot assume is that any LIST in them is complete.
**Enumerate from the tree.**

As always `SPECIFICATION/` governs and the code is the final word on
behavior — that is normal precedence, not a warning about these files.

## Progressive guidance — `.ai/`

Durable, non-ephemeral agent guidance in this repo lives in this file and — for
detail that would bloat it — in sibling `.ai/<topic>.md` files referenced here
and loaded **progressively**: only when working on that topic, so the
always-loaded `AGENTS.md` stays small. This is the fleet convention from
`livespec/AGENTS.md` §"Agent-instruction `.ai/` convention";
`check-agents-ai-references-resolve` verifies every reference below resolves.
Never persist durable guidance to a harness-private memory store.

Note what that check does and does not catch: it verifies references RESOLVE. A
repo that makes no references passes with its guidance orphaned — which is how
`.ai/supervisor-protocol.md` went unreferenced from this file for three weeks
after 2026-07-30. (Whether the check should also detect absence is filed as
`livespec-dev-tooling-xaxj5w`.)

Every `.ai/` file below except `supervisor-protocol.md` was moved VERBATIM out of
this file on 2026-08-23, when it stood at 157,689 chars against the 150k limit.
Their prose still says "this file", "above" and "below" in places; read those as
references to the file they were written in.

- **`.ai/supervisor-protocol.md`** — read BEFORE driving a worker as supervisor.
  The shared role-level contract that every generated per-plan binder is read
  TOGETHER with; a binder alone is intentionally incomplete and this file alone
  binds nothing to a plan.
- **`.ai/dispatch-traps.md`** — read BEFORE dispatching `impl:<id>`, and
  whenever a dispatch refuses, fails, or leaves a row at `active`/`fabro`.
  Eight measured failure shapes whose error messages point away from the fix,
  with the discriminator tables (`fabro ps -a`, the forge, the journal, the
  envelope's `detail`) that tell them apart — plus the doubled-brace token trap,
  the GitHub App installation pin, the tenant-wide `--defer` refusal, the
  `--ephemeral` retraction, ledger-edit items, and the stale plugin build.
- **`.ai/anthropic-credentials.md`** — read BEFORE probing or reasoning about
  an Anthropic credential's limits: which probe is evidence about the factory,
  separate limits per credential, and the dispatcher's own exhaustion refusal.
- **`.ai/ledger-valves-and-holds.md`** — read BEFORE concluding a ledger row is
  human-held, or touching `admission:`/`acceptance:` labels: status and
  dependencies are the only valve for the ready set, labels never gate, and
  `pending-approval` is not a hold in this tenant.
- **`.ai/record-versus-world.md`** — read BEFORE treating a ledger field, a
  file's git history, a present-tense search result, a self-written timestamp,
  or a silent log as evidence about the world. Six measured rules, one family.
- **`.ai/deferral-successor-records.md`** — read when archiving a plan that
  defers work, or filing the successor for a deferral: the both-ends
  reachability criterion, declaration versus citation, and writing the
  falsifiable expectation into the record.
- **`.ai/pr-and-gate-mechanics.md`** — read when a push, PR, or commit hook
  rejects you: the auto-merge race, the GitHub rate-limit guard matching the
  word "for", the red-green-replay edge cases, the LLOC soft-band check that
  cannot fail by hand, the charter gate's one-directional false positives, and
  the detached rebase probe.
- **`.ai/overseerd-restart.md`** — read BEFORE bouncing `overseerd` or judging
  what code the acting daemon runs: the maintainer's restart ruling and its
  top-pane rider, clock normalization, the three staleness surfaces, and the
  bounce mechanics.
- **`.ai/ci-runner-routing-history.md`** — read when triaging a red master or a
  runner-environment failure: the k3s cutover, rollback, AppArmor root cause,
  and why runner identity is part of CI triage here.

## Daily commands

- `just bootstrap` — first-touch setup on a fresh clone.
- `just check` — the full enforcement aggregate (the single local,
  pre-push, and CI gate).
- `just check-static` — fastest-first fail-fast lint/format/types subset.

## The Codex plugin surface is NESTED inside `.claude-plugin/`

The Codex surface is a `.codex-plugin/` directory **inside** the existing
`.claude-plugin/`, which hosts it — **not** a repo-root `.codex-plugin/`, a
structure that exists in **no** fleet repo. Measured 2026-07-28:
`livespec/.claude-plugin/.codex-plugin/plugin.json` and
`livespec-orchestrator-beads-fabro/.claude-plugin/.codex-plugin/{plugin.json,skills/<op>/SKILL.md}`.

The nested manifest mirrors its Claude sibling's `name`, `version` and
`description` and adds `"skills": "./.codex-plugin/skills/"`; the two are kept
in **lockstep**. Each operation gets a thin binding whose frontmatter is `name`
+ `description` only (no `allowed-tools`), and whose body resolves
`$PLUGIN_ROOT` **explicitly** — Codex does not substitute a plugin-root token
into SKILL prose. Both harnesses read the same harness-neutral `prose/`.
`marketplace.json` needs no codex entry: its `source` is already
`./.claude-plugin`, which contains the nested dir.

`livespec-driver-codex` is a **different repo shape** (repo-root
`.agents/plugins/marketplace.json`, no `.claude-plugin/`) and is **not** a model
to copy.

## Working discipline

Fleet-standard rules apply: every tracked-file change goes worktree → PR →
rebase-merge (never commit on the primary checkout; hooks refuse it);
product `.py` changes follow the red-green-replay commit ritual; never pass
`--no-verify`; use `mise exec -- git …` so hooks fire. Work-items live in
the `livespec-overseer` beads tenant (`bd` via the fleet credential
wrapper). Durable agent guidance belongs in this file — never in any
harness-private memory store.

Red-mode pre-commit skips coverage because commit-msg replay verifies the Red.
If you are repairing one specific gate that lives inside `just check`, an
exported `LIVESPEC_CHECK_SKIP` is UNIONED with the built-in Red-mode coverage
skips, so the Red commit can skip only the gate whose broken state it is
proving. Do not carry that exported skip into the Green/full-suite
verification; the final commit still owes the full aggregate with nothing
skipped.

**Create worktrees with `just worktree-create <branch> [base_ref]`, NOT with
`git worktree add`.** The recipe provisions the worktree-discipline pack into
`dev-tooling/` and hydrates; raw `git worktree add` does neither, and a
worktree without that pack **can neither commit a `.py` change nor push at
all** — `check-primary-checkout-commit-refuse-hook-installed` fails with
`worktree_pack_absent` in both the pre-commit and pre-push aggregates. Observed
both ways on 2026-07-27: a `.py` commit rejected, and a DOCS-ONLY branch
rejected at push, so do not assume the doc-only fast path exempts you.

Two things make it expensive to learn the hard way. The check is only reachable
through a full `just check`, so it fires at COMMIT or PUSH time — after the work
is done — rather than at worktree-creation time. And the rejected `git commit`
leaves the change STAGED, so a following `git log` shows some other track's
commit at HEAD and reads as success. **Check `git status`, not `git log`, after
a hook-gated commit.** To rescue an
already-created worktree, run `just install-worktree-pack` inside it — but note
it also writes a `worktree_discipline` key into `.livespec.jsonc`, a tracked
file; that key only makes the existing default explicit, so discard it unless
you mean to land it.

The lifecycle has recipes for the rest too: `just worktree-hydrate`,
`just worktree-land [base_ref]`, and `just worktree-reap [--execute]` for
orphans. `dev-tooling/*` is gitignored and byte-verified against the package
source — never hand-edit the installed copy.

**`just worktree-create` WORKS AGAIN — the rescue path below is RETIRED.**
Re-measured 2026-08-21: it succeeds normally, and the rescue it used to require
(`git worktree add` by hand, then `just install-worktree-pack`, then discarding the
`worktree_discipline` key it writes) is no longer needed. Use the recipe.

The fix is in the pinned `dev-tooling` package, not here. `worktree_primary_path`
now reads

    git worktree list --porcelain | awk '/^worktree / && !seen { print $2; seen = 1 }'

which consumes the WHOLE stream and simply ignores later matches, so awk never exits
early, never SIGPIPEs git, and `pipefail` never sees 141.

**The original entry is kept because its FRAMING is the part worth learning from.**
Measured 2026-08-04 (`livespec-dev-tooling-3pre`): the recipe exited **141** printing
nothing but `error: Recipe worktree-create failed on line 25 with exit code 141`. The
prior implementation piped the same porcelain into `awk '/^worktree /{print $2; exit}'`
under `set -euo pipefail`; once the output needed more than one write, awk's early exit
SIGPIPEd git and pipefail promoted 141, aborting inside a command substitution before
the first `echo`. That diagnosis was correct.

**What aged badly was calling it a SIZE threshold.** The entry recorded "this repo has
123 worktrees / 21545 bytes and fails; repos at ~1.5–2.7 KB work", which reads as
monotonic: bigger is worse. This repo now holds **282 worktrees / 48602 bytes — 2.25×
the size recorded as failing — and both the recipe and the bare construct exit 0.**
A threshold framing invites the reader to skip verification exactly when the condition
looks WORSE than the one recorded, so a reader arriving at 282 worktrees would
reasonably conclude the recipe is more certainly dead and never try it. State the
MECHANISM as the hazard and the measurement as evidence for it; a threshold is a
property of the broken code, and it stops meaning anything the moment that code
changes.

**Re-run `just install-worktree-pack` in ANY worktree created across a pin bump.**
`worktree-create` provisions the pack by COPYING it from the PRIMARY checkout, whose
copy came from the pin the primary resolved. A worktree on a branch that BUMPS the
pin resolves the NEW package, whose canonical pack bodies differ — and the pack is
byte-verified, so the worktree is born failing. Measured twice on 2026-08-04
(`livespec-dev-tooling-ov9o`), and the failures NAME THE WRONG THING:
`check-shell-quality` reports `just-interpolation` against recipes named
`worktree-create`/`worktree-land`/`worktree-reap`, which arrive via
`import? 'dev-tooling/worktree.just'` and are therefore attributed to the consumer's
own `justfile`. Both repos went red-to-green on that one command with no other edit.
Note also that `worktree_pack_body_mismatch`'s hint says to run `just bootstrap`,
which is the wrong verb in a LINKED worktree.

**`just worktree-reap` essentially never fires here** (`livespec-dev-tooling-teje`):
it judges merged-ness by ANCESTRY into `origin/master`, which is false for every
branch under this fleet's rebase-merge-only flow. A dry run on 2026-08-04 reported
17 worktrees, 0 removable, several genuinely landed. That accumulation is what
eventually trips the SIGPIPE above, so the two defects compound.

## Decision authority — when to ask, proceed, or self-resolve

Fleet-standard guidance, ported from
`livespec/AGENTS.md` §"When to ask, proceed, or self-resolve" and
`livespec-orchestrator-beads-fabro/AGENTS.md` §"Drive authorized work to
completion; do not over-ask". The default is to decide and report, not to
escalate.

**Why this repo carries it.** On 2026-08-20 a foreman track here sat roughly
sixteen hours parked on a picker whose option 1 was its own recorded next
action, and escalated five self-decidable engineering calls as standing
maintainer questions. Those sessions were reading an `AGENTS.md` that never
told them what they were allowed to decide. This repo's own surfaces —
`/livespec-overseer:foreman`, `:grooming`, `:supervise-plan` — are the most
exposed to that failure, because each ends a bounded pass by presenting
options.

- **Drive authorized work to completion; do not over-ask.** When the maintainer
  names a goal and says to finish or continue it, execute the WHOLE arc —
  implement, dispatch, PR, merge, iterate, archive — without pausing to confirm
  each already-authorized step. An operator-flow step that says "present
  options and let the user select" is satisfied by a standing directive once
  the goal is named; do not re-prompt. Default to acting, then reporting
  outcomes.
- **A recorded next action is an instruction, not a menu.** When a plan's
  handoff timeline names exactly one next action, take it. Re-presenting it as
  option 1 of a picker is the stall shape above, and it is why an unattended
  resume is defined to take that action directly rather than ask.
- **Research before gating.** If a question is answerable by reading the code,
  the spec, the docs, or by testing on a live system, do that, decide,
  implement, and report for objection. Reserve gates for genuine product or
  values calls, irreversible or outward-facing actions, and secret or
  host-mutation authorization.
- **Only ask on genuine doubt, one thing at a time.** Self-resolve trivial
  wording fixes, internal-consistency repairs, and items clearly aligned with
  established preferences, presenting each with its disposition. When a gate is
  warranted, ask exactly one question per turn.
- **One investigation, one finding, one question.** When a focused
  investigation surfaces unrelated discrepancies, finish the original question
  first and surface only the load-bearing finding; log side observations
  briefly. Cosmetic drift never blocks on its own.
- **Prescribed destructive ops are pre-authorized.** When a destructive git
  operation is the codified mechanism of an adopted workflow — the
  `git commit --amend` of the Red→Green step, for instance — the adoption is
  the authorization. Keep per-instance gating for ad-hoc `--amend`,
  force-push, `reset --hard`, or `branch -D` on unmerged branches.
- **An unratified filter inside a check is conformance, not ratification.**
  Narrowing, excluding, or filtering inside an enforcement check to match what
  the ratified spec already says is a conformance fix — implement it and report
  it. It only becomes a ratification question when the change would make the
  check assert something the spec does not.
- **A question you can answer with a recommendation is a finding, not a
  maintainer question.** If you can state the options, the costs, and which one
  you would pick, you have already done the deciding work. Decide it, record
  the reasoning where the work is tracked, and report it as decided.
- **Disposing a plan child is session-performable.** Closing or re-parenting a
  child that no longer belongs under a plan epic changes where work is TRACKED,
  not what the specification REQUIRES. Only a spec-change-tier child routes to
  `propose-change`; escalating the rest deadlocks the archive gate that refuses
  while a child sits undisposed.

## Prefer factory dispatch over interactive hand-implementation when the work is dispatch-safe

Maintainer-directed 2026-08-15. Autonomous mode (the Beads/Dolt ledger + Fabro
Dispatcher, `drive.py --action impl:<id>` / the `implement`/`groom` skills) and
the overseer's interactive tracks are documented as standing peers, not a
default-to-manual with dispatch as a fallback. Running a plan under the
overseer does NOT mean its implementation work should default to a live worker
pane doing it by hand — check whether the work is dispatch-safe FIRST, and
prefer `impl:<id>` when it is.

This was learned live: a supervisor let an `archive-safe-respawn` worker
continue hand-implementing a narrow, well-scoped `.py` fix (a bounded branch
in `_supervisor_restart.do_restart`, with acceptance criteria already drafted
on its ledger item) purely because that is what the worker happened to already
be doing, without ever weighing factory dispatch as the alternative. The
maintainer had to say so explicitly.

Check dispatch-safety before choosing (see "Dispatch traps" above and the
ledger-edit-item note below it): no `{{...}}` template tokens in the item's
own text, no cross-repo `depends_on` pointing at its own parent epic, the
target repo's master CI proven green, and the deliverable is a repository
change rather than a beads-ledger mutation. If genuinely in-flight manual work
is already substantially complete (verified RED, or RED+GREEN) when this
question comes up, finish and land it rather than discarding sunk, verified
progress purely to redo it via the factory — the preference governs the NEXT
piece of work, not a reflexive abort of work already done.

## Every dispatch is a PLAN CHILD, and the plan's timeline must say so BEFORE launch

Maintainer-directed 2026-08-23. Two obligations, and the second is the one that
actually gets skipped.

**1. Dispatch only a child of a plan-anchor epic.** An item with no plan parent has
no scope event that admitted it, no archive gate that will force a reckoning with
it, and no timeline a fresh session can read. Dispatching one is the "one-off
dispatching" this rule exists to stop. A CARRIER EPIC IS NOT A PLAN: it has no plan
directory, no scope event and no archive gate by construction. Check for
`plan_slug` metadata on the parent rather than assuming any epic is a thread.

**2. Append a handoff entry to that plan's epic BEFORE you launch**, naming the
item, the route (`impl:<id>` or Dispatcher drain) and what you expect back.
Handoffs are ledger-held comments on the plan epic — that is the plan's only state.
A dispatch absent from the timeline is invisible to everyone reading the plan,
including the next session on that thread and the maintainer.

**Why BEFORE, not after.** Measured 2026-08-22: three items were dispatched from a
debug pane and merged as PRs #1587, #1592 and #1597. Every one had a correct plan
parent, so nothing was orphaned — and for the entire in-flight window both plans'
timelines said nothing at all. One of the two epics had ZERO timeline entries. The
gap was closed retroactively, which is luck rather than discipline: had the session
ended mid-flight, the plans would have carried no trace of work running against
them. Recording after the fact only works when nothing goes wrong in between.

**The ledger row does not satisfy this.** A row at `active` with assignee `fabro`
says a claim exists. It does not say which plan authorized the work, what it should
produce, or what to do when it fails — and an `active` row is routinely wrong on its
own terms; see the phantom-claim shapes in "Dispatch traps" above.

**Mixed-tier items are not dispatchable at all — split them at FILING time.** An item
whose deliverable spans a repository change AND a `SPECIFICATION/` change cannot be
satisfied by the factory: `scripts/check-no-factory-spec-edits.sh` is a hard,
no-escape-hatch gate rejecting any factory-authored commit touching `SPECIFICATION/`,
and `just check` runs it in-sandbox. Measured 2026-08-21 on `overseer-lixhd3.1`: run
`01M0K8TJFWAF6QEJPGC0MV5EJ2` spent FOUR HOURS and two fix-stage passes discovering
that its own acceptance criterion required a file the sandbox forbids, then failed
`deterministic`. That item's text had correctly read "supervised for the spec half,
dispatch-safe for the code half" — accurate analysis, useless as a control, because
it was filed as ONE unit. **A mixed-tier item is not dispatch-safe merely because
part of it is.**

The same trap has a second face, and it caught the very session writing this rule an
hour after the post-mortem: any acceptance criterion naming a HOST-SIDE act the
sandbox cannot perform — bouncing the daemon, mutating the beads ledger, answering a
picker in another pane — is unsatisfiable in-sandbox and DEADLOCKS the run rather
than failing fast. Bound the in-sandbox deliverable at a green merged PR and name the
host-side step as a separate post-merge obligation on the item.

**Launch multi-minute dispatches DETACHED from the harness, never as a backgrounded
Bash task.** A session that may end its turn with `ScheduleWakeup` / dynamic `/loop`
has its still-running `run_in_background: true` tasks reaped seconds after parking
(measured 2026-08-16, `overseer-za32`). Use `scripts/detached-dispatch.sh <run_dir> --
<command>` and read `<run_dir>/verdict.env` (wait for its `status=` to CHANGE from
`running`) plus the dispatcher's JSON envelope in `<run_dir>/output.log` on wake.
`.ai/dispatch-traps.md` carries the full procedure and every envelope shape.

## Routing: `hp` is the only dispatch target for this repo

**MAINTAINER INSTRUCTION, 2026-08-22: DO NOT ROUTE ANY WORK TO THE `vps`
FACTORY FOR THIS REPO, UNTIL THE MAINTAINER LIFTS THIS.** `hp` is the only
dispatch target for livespec-overseer. A capacity defer where `active_count`
equals `wip_cap` is this repo's WIP cap working as designed: wait for a slot.
It is not a routing problem, not grounds to pass a `vps` factory argument, and
not grounds to substitute a local run. The pre-push aggregate is the sole
standing local exception, because it runs by design and cannot be dispatched.
The second factory declared in `.livespec.jsonc` is still useful for read-only
process inspection, but it is not available for routing work despite being
configured.

The mechanics behind that — the sticky per-item `dispatch_factory` pin, how to clear
it, and the intermittent ENOSPC shape that motivated the old re-route — are in
`.ai/dispatch-traps.md` §"A SEVENTH SHAPE".

## Lifecycle statuses for `bd update --status`

Use only the livespec lifecycle statuses when writing a work-item status:
`backlog`, `ready`, `blocked`, `active`, `acceptance`, `pending-approval`, and
`closed`. Beads-native names must never be passed to `bd update --status`; do
not write `open`, `in_progress`, `deferred`, or `done` by hand.

When translating a beads-native state, use the same lifecycle mapping the fleet
normalizes by: `open` maps to `backlog`, and `in_progress` maps to `active`.
So returning an item to the unstarted pool is `bd update <id> --status backlog`,
not the native intake name. The bd-guard is correct to block non-lifecycle
status writes; do not bypass, relax, or re-mode it.

Do not infer write vocabulary from create output. Beads-native create paths can
show `open` before fleet normalization is visible, but callers still must not
use that native name in any later `bd update --status` command.

What HOLDS a row — why `pending-approval` is not a hold in this tenant, why
labels never gate anything, and which policy fields the two Dispatcher valves
route on — is in `.ai/ledger-valves-and-holds.md`. Read it before reasoning
about whether a row is human-held.

## Scripting `bd` from an agent shell: two traps measured 2026-08-22

Both cost real wall clock while filing thirteen plan children, and neither
announces its cause.

**The tool shell is zsh, and zsh does not word-split an unquoted variable.**
`W="/usr/local/bin/with-livespec-env.sh -- bd"; $W create ...` fails with
`no such file or directory: /usr/local/bin/with-livespec-env.sh -- bd` — the
whole string is tried as one command name. A direct invocation works, so the
failure looks like a `bd` problem. Define a function instead:

    bdw() { /usr/local/bin/with-livespec-env.sh -- bd "$@" </dev/null; }

**`bd show <id>` repeated inside a loop hangs past a multi-minute timeout.**
Thirteen sequential shows never finished, twice, with and without stdin
attached. One `bd list --parent <epic> --json` returns every child's title,
description, acceptance and status in a second and is the right instrument for
scanning stored records (the doubled-brace token check above included) or
reading statuses. Parse a created id from the normal `Created issue: <id>`
output line; `--silent` produced nothing usable through a pipe.

## The fleet has SEVERAL Anthropic credentials — probing the wrong one is the documented failure mode

Cite this section; do not restate it per plan. It exists because the
same fact was independently re-derived by two threads on 2026-07-29 and one of
them got it wrong, costing two dispatches' green work (`bd-ib-g56f`).

| Credential | Shape | Who actually uses it |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | `sk-ant-oat0…` | **The factory path.** The `credential_wrapper` injects it into the Dispatcher's env; the Dispatcher projects it into the per-run mode-600 overlay; the sandbox's `claude-agent-acp` **review** adapter authenticates with it (`_dispatcher_credentials.py:58`) |
| `ANTHROPIC_API_KEY_LIVESPEC_E2E` | `sk-ant-api0…` | The **containerized orchestrator image** as fabro's LLM provider key (`orchestrator-image/orchestrator-entrypoint.sh:64`, `FABRO_LLM_API_KEY_ENV` default), and livespec's `e2e-real.yml` |

Both names are real and both are legitimately "the Anthropic key fabro uses"
— for **different deployment shapes**. The trap is asymmetric discoverability:
the E2E key appears in READMEs, CI workflows and four image scripts, while the
token the host path actually bills appears in one module. Reaching for the
greppable one is the easy mistake, and it fails SILENTLY — it returns HTTP 200
while the credential in use is exhausted.

The consequences to hold onto — which probe is evidence, separate limits, the
dispatcher's own exhaustion refusal and the phantom claim it leaves — are in
`.ai/anthropic-credentials.md`.

## CI runner routing

`CI_RUNNER_LABELS` routes this repo's gating `pull_request`/`push` CI matrix.
It is a repo variable, so a runner-label-only change normally belongs there,
but a `.github/workflows/` edit is a legitimate engineering option to weigh on
its merits when the workflow itself needs to change. Workflow edits are
GOVERNED here, not forbidden: the full `just check` aggregate invokes
`check-no-workflow-edits`, and that gate grants a per-change exemption through
a tracked declaration file named `.livespec-workflow-edit-exemption`.

That declaration must be authored in the branch's own diff rather than
inherited from master, so one reviewed exemption cannot disable the guard for
later branches. It must contain exactly one `work_item=` line and exactly one
non-empty `reason=` line. The narrow mechanical allowance is only for lines the
automated pin-bump lane or canonical CI-matrix reconciler can produce: pin
reference lines in workflow files, plus canonical slug lines emitted into
`.github/workflows/ci.yml`. Any other workflow edit needs the declaration above.

The guard does not create an env var, flag, or skip lever exception. Those
remain absolutely prohibited here.

**As of 2026-08-19 `CI_RUNNER_LABELS` is
`["livespec-overseer-k3s"]`** — re-cut once the root cause below was found and
fixed. The rollback history is kept because its triage lesson outlives it.

The rollback history, the AppArmor root cause, the runner-pod-is-not-the-workflow-pod
lesson and the triage lesson are in `.ai/ci-runner-routing-history.md`. Read it
when triaging a red master or any runner-environment failure.
