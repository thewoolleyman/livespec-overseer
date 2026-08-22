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

`.ai/supervisor-protocol.md` is the shared role-level contract for every
generated supervisor handoff: the common role contract that a per-plan binder
is read TOGETHER with, since a binder alone is intentionally incomplete and
this file alone binds nothing to a plan. **Read it before driving a worker as
supervisor.**

It has existed since 2026-07-30 and, until this line, this file never pointed
at it — so an agent using AGENTS.md as its entry point was never routed to it.
That is a different failure from the one the re-measures above chased: those
were about documents DENYING `.ai/` existed. This one is silence. Both leave a
reader unaware of the directory, and neither is caught by
`check-agents-ai-references-resolve`, which verifies that references RESOLVE —
a repo that makes no references passes with its guidance orphaned. (Whether
that check should also detect absence is filed as
`livespec-dev-tooling-xaxj5w`.)

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

Consequences to hold onto:

- **A probe on the E2E key, or on interactive `claude -p`, is NOT evidence
  about the factory.** Both are documented false positives (2026-07-29
  15:00Z: probe green, adapter hard-blocked).
- **These credentials have SEPARATE limits and may belong to different
  accounts.** At least two limit kinds have been seen — an org monthly spend
  cap and a rolling window. Raising one clears neither the other nor a
  different account, so name WHICH credential you measured.
- **The Dispatcher's Claude check WAS presence-only. IT IS NOT ANY MORE, and the
  remedy this entry used to prescribe is retired.** Observed directly on
  2026-08-07 while dispatching `overseer-1gig`: the dispatch was refused **before
  sandbox launch**, at stage `run-config-overlay`, with

      C-mode dispatch refused before sandbox launch: CLAUDE_CODE_OAUTH_TOKEN is
      exhausted or rate-limited (HTTP 429, rate_limit_error).
      Observed condition: exhausted.

  That is a real usability gate, and `bd-ib-3mbj` — the item that added it —
  reads `acceptance` in the orchestrator tenant. **It is NOT symmetric to the
  Codex side** (the sentence that stood here until 2026-08-20 said it was, and
  had the direction inverted): Codex-mode dispatch still has NO usability
  preflight, so an exhausted Codex usage window launches a doomed sandbox per
  dispatch and surfaces only as an ACP protocol error — carrier `bd-ib-oj71`,
  re-measured 2026-08-19 when four runs burned into a window known-exhausted
  for hours. **So a present-but-exhausted token no longer passes pre-flight, and a
  run no longer dies mid-review from this cause.** Do NOT reach for the host-side
  probe in `plan/archive/background-shell-supervision-liveness/handoff.md`
  §"Gate 4" as "the only valid signal": the dispatcher now reports the condition
  itself, names the credential, and consumes no spend doing it.

  **THE DESCRIPTION IS RETIRED; THE MECHANICS ARE NOT.** Three things still hold,
  and they are why this entry keeps its length. The refusal is a **wait, not a
  question** — a rolling limit clears on its own and must never be escalated as a
  maintainer decision, though an org *spend* cap genuinely is theirs. The refusal
  still leaves the work-item `active` with assignee `fabro` even though
  `fabro_run_id` is `null` and no run exists, so **release the claim by hand after
  any refused dispatch**. And the credential it names is `CLAUDE_CODE_OAUTH_TOKEN`,
  the factory path — a probe against `ANTHROPIC_API_KEY_LIVESPEC_E2E` or
  interactive `claude -p` remains a documented false positive.
- **Never print token material.** Presence, prefix and length are enough to
  identify which credential you are holding.

## Dispatch traps whose error messages point AWAY from the fix

Measured 2026-08-02 and 2026-08-04 while dispatching from this repo. Each fails in
a way that makes the correct remedy look wrong, which is why they are here rather
than only in a plan.

**Check the target repo's MASTER CI before diagnosing any dispatch failure.** The
Dispatcher refuses before any sandbox work with `latest master CI is not proven
green at required check ci-green`, naming the failing run. A red master blocks
EVERY dispatch in that repo and the refusal says nothing about your item, so it
reads as a problem with the item. Measured 2026-08-04: this repo's master was red
for hours — one plan handoff declared its ledger anchor as prose ("The epic anchor
is `x`") where the gate's regex requires the literal "ledger anchor" phrase before
the backticked id, so `test_plan_records_agree` failed. One line fixed it.

### A `{{...}}` token anywhere in a work-item's text makes it UNDISPATCHABLE

`drive.py --action impl:<id>` interpolates the work-item's text into the fabro
workflow's **templated** `goal` attribute. A literal `{{name}}` in that text is
parsed as a *fabro* template variable, finds no binding, and the graph is rejected
before any agent runs:

```
workflow.fabro:294:32: undefined template variable `test_nprocs`
  in graph attribute `goal` (template_undefined_variable)
```

**The token is not the workflow's** — `grep test_nprocs` over the workflow file
returns nothing. It arrives from the ledger record. In this fleet that shape is
common: quoting a justfile recipe as evidence is routine and **every** `just`
recipe variable looks exactly like this (`pytest -n {{test_nprocs}}`).

Measured with controls: `overseer-jdo` carried the token and failed every time;
`overseer-0pc` and `overseer-mir` carried no `{{...}}` and both dispatched
normally. So it is item-text-specific, not a dispatcher outage.

**It also leaves a PHANTOM CLAIM** — afterwards the item reads
`status=active, assignee=fabro` while `fabro ps` reports no running processes.
Release it by hand before re-dispatching. `ACTIVE` is never evidence of a run;
`fabro ps` is.

**Do NOT fix this by editing the work item.** Escaping or deleting the offending
text corrupts the item's own evidence and hides a defect that recurs on the next
item that quotes a recipe. Tracked as `bd-ib-vv9y` (P1, orchestrator tenant).

### A PHANTOM CLAIM HAS A SECOND CAUSE, and this section used to imply only one

The `{{...}}` trap above is not the only way an item ends up `status=active,
assignee=fabro` with nothing behind it. **A QUEUED RUN CAN BE EVICTED WITHOUT EVER
EXECUTING**, and it leaves exactly the same wreckage.

Measured 2026-08-03 dispatching `overseer-x29.1`: `drive.py` exited **0**, and
`fabro ps` showed the run as `runnable` — queued behind three in-flight runs.
It never started. Some minutes later it was absent from `fabro ps -a`
**entirely** — not `failed`, not `succeeded`, no record at all — while the item
still read `active`/`fabro`. A sibling queued run in the same window
(`livespec-dev-tooling-uzwqm6`) disappeared identically, so it is a queue
property, not an item property.

**Tell the two causes apart before diagnosing**, because the remedies differ:

| symptom | `{{...}}` trap | queue eviction |
|---|---|---|
| `drive.py` exit code | non-zero, immediate | **0** |
| error text | `template_undefined_variable` naming a token | none |
| `fabro ps` right after | never lists the run | lists it as `runnable` |
| `fabro ps -a` later | never lists the run | run is **absent entirely** |
| remedy | fix the dispatcher defect; do NOT edit the item | release the claim and re-dispatch |

**A `drive.py` exit of 0 is NOT evidence that work started** — it means the
request was accepted. Confirm with `fabro ps` that a run exists, and confirm again
that it reaches `running`; a run parked at `runnable` has not begun and may never.

The rule the two share is the one already stated above: `ACTIVE` is never evidence
of a run, `fabro ps` is. Release the claim by hand (`--status ready`, clear the
assignee) before re-dispatching, and record WHY in the item so the next reader does
not attribute an eviction to the `{{...}}` defect and go looking for a token that
was never there.

### A THIRD CAUSE, and unlike the two above it leaves NO phantom claim

Measured 2026-08-04. An item whose THREAD MEMBERSHIP was filed as a cross-repo
`depends_on` is permanently undispatchable:

```
ERROR: requested work-item(s) not in the ready set: <id>
```

`drive.py` exits **1** and the dispatcher exits **3**. No fabro run is created at
all, so there is nothing to find in `fabro ps` and — unlike both traps above — the
item is left with NO phantom claim. That absence is the discriminator.

The cause is that `store._depends_on_from_edges` reconstructs
`metadata.non_local_depends_on` into `WorkItem.depends_on`, and the ranker excludes
any candidate with a dep that does not resolve CLOSED —
`_dispatcher_loop_selection.is_dispatch_candidate` applies the same test to a
`pending-approval` item by projecting it to `ready` first. So an anchor link pointing
at the item's own PARENT EPIC is circular by construction: an epic cannot close
before its children. It is also unresolvable independent of status whenever the
consuming repo's `cross_repo_targets` manifest has no entry for the sibling repo —
and an unresolvable sibling FAILS CLOSED.

Measured with a three-way control against the plugin's own selector: as-filed → not
a candidate; the identical item with the single `depends_on` entry stripped →
candidate; a known-ready item → candidate.

**Thread membership belongs in the item TEXT, never in a dependency edge.** The
`Read first` block already carries it. Remedy: `bd update <id> --unset-metadata
non_local_depends_on`, and record why. A GENUINE cross-repo dependency is fine — but
check the consuming repo's `cross_repo_targets` actually lists the sibling, or it
will fail closed forever.

Measured 2026-08-19 while repairing `overseer-vfz5v5`: the same `not in the
ready set` symptom has a third case. A dependency can be genuine, and the sibling
repo can be correctly listed in `cross_repo_targets`, while the edge's
`work_item_id` is simply wrong. In that case, unsetting the edge destroys the
record of a real prerequisite and makes the item look dispatchable while its real
blocker is invisible.

**Before unsetting any cross-repo edge, resolve its `work_item_id` against BOTH
tenants' full id sets.** If it resolves and the edge is only thread membership,
unset it as above. If it resolves and the sibling repo is missing from
`cross_repo_targets`, list the sibling. If it resolves nowhere, treat the pointer
as broken: look for the real counterpart and REPOINT the edge. Unset only when no
real counterpart exists. In the measured case, the broken edge named
`overseer-llz4xi`, which existed in neither tenant and even carried an
`overseer-` prefix while declaring `livespec-dev-tooling` as its repo. The real
counterpart was unambiguous: `livespec-dev-tooling-3nt9`, whose description named
livespec-overseer's `justfile:127-142` and the same three hard-coded
marketplaces that `overseer-vfz5v5` was replacing. Repointing kept the item
correctly gated until that blocker lands, instead of deleting the truth.

There is a separate false-positive source for that third case:
`bd update --set-metadata non_local_depends_on=<json>` silently stores the value
as a string, not as a JSON array. A stringified edge can later look like a broken
reference, inviting someone to unset a healthy dependency. The working form is
`bd update <id> --metadata @<file.json>` with the COMPLETE metadata object; it
replaces the whole object, so preserve sibling keys such as `rank`. Then read the
item back and verify `non_local_depends_on` is a list, not a string.

### A `not in the ready set` refusal with NO dependency edge at all — check the STATUS first

Measured 2026-08-19 dispatching `overseer-y3xhlh.1` and `.2`. Two dispatches refused,
under a minute each, neither leaving a phantom claim:

    ERROR: requested work-item(s) not in the ready set: overseer-y3xhlh.1

`drive.py` exits **1**, the dispatcher **3** — the identical signature to the
anchor-as-dependency case above. **The cause was neither a dependency edge nor a
broken pointer. `bd create` lands a new item in `BACKLOG`, and the dispatcher's ready
set excludes backlog.** One `bd update <id> --status ready` per item fixed both, and
they re-dispatched cleanly on the same build minutes later.

**The reason this is easy to miss is that the status CHANGES BEHIND THE CREATE.**
`bd create` prints `Status: open` truthfully — beads' own intake default — and the
fleet's dispatcher then normalizes `open` onto the livespec lifecycle equivalent
`backlog` (`_dispatcher_ledger_close.py`, `_NATIVE_STATUS_REMAP`, reason
`"beads-native intake default"`). Both halves are behaving as designed. The filing
session is simply never told that the status it was shown has been superseded:

    $ bd create "..." --type bug --parent <epic>
    ✓ Created issue: overseer-y3xhlh.7 — ...
      Priority: P3
      Status: open
    $ bd show overseer-y3xhlh.7
    ◇ overseer-y3xhlh.7 [BUG] · ...   [● P3 · BACKLOG]

So the session that filed the item has been told it is open. Nothing prompts it to
suspect the status, and the refusal names the ready set rather than the status.

**CHECK THE STATUS BEFORE INSPECTING ANY EDGE.** The preceding guidance sends you to
resolve a `work_item_id` across both tenants' id sets before unsetting anything — sound
advice for a real edge, and a dead end here, because there is no edge to resolve. A
freshly-filed item typically has no `depends_on` at all, so a reader following the
edge-first path finds nothing, concludes the metadata is fine, and is left with a
refusal they cannot explain.

    bd show <id> | head -1     # BACKLOG? -> bd update <id> --status ready

Costs a second, and it discriminates the status member of this symptom family:
**no edge and `BACKLOG`** is this case; an edge that resolves nowhere is the
broken-pointer case; an edge that resolves but names the parent epic is
thread-membership; an edge whose sibling repo is absent from `cross_repo_targets`
fails closed. A further no-edge case exists immediately below, and the status read
does not identify it by itself.

**File items ready when you mean them to be dispatchable**, or promote them in the same
breath as filing. Do not batch-file a plan's children and dispatch later assuming they
are startable — they are not, and the create output says otherwise.

### A `not in the ready set` refusal with READY status and NO edge — check for a live sibling claim

Measured 2026-08-22 on `overseer-b6q2`: the central autonomous loop claimed the
item between a session's pre-flight and its manual dispatch command. The loop wrote
`loop-pick` with budget 1 at 2026-08-22T02:29:31Z, then `ledger-admit`, then
`dispatch-id` at 2026-08-22T02:29:38Z
(`dc73fddda8c14817b80ba1031505b94e`, factory `hp`) in
`tmp/fabro-dispatch-journal.jsonl`. A manual dispatch 36 seconds later refused:

    ERROR: requested work-item(s) not in the ready set: overseer-b6q2

`drive.py` exited **1**, the dispatcher **3**, no fabro run was created, and **NO
phantom claim** was left. That is character-for-character the anchor-as-dependency
signature above, and the same visible shape as a stale plugin build recorded below.
It was neither: the item had no dependency edge of any kind, it was `ready` at the
moment of the attempt, its acceptance guard returned ok, and `just ensure-plugins`
had confirmed the current build minutes earlier.

This is the ready-set claim **working**. It prevented two runs from publishing to
the same branch for the same item, the collision shape already documented below.
The remedy is to do **nothing**: do not release the claim, do not re-dispatch, and
do not start editing edges or status. First grep the dispatch journal for a recent
`dispatch-id` on the same item. If one exists and no later outcome proves it ended,
the live sibling owns the work; leave it alone and inspect the factory run instead.

### A FOURTH SHAPE: the run SUCCEEDED and the item was never transitioned

Measured 2026-08-05 on `overseer-5oap`. **This is the dangerous member of the
family, because its symptom is IDENTICAL to a queue eviction while its remedy is
the EXACT OPPOSITE.** The item reads `status=active, assignee=fabro` and
`fabro ps` does not list it — the textbook eviction signature. Following the
eviction remedy there (release the claim, re-dispatch) would RE-RUN work that had
already merged and shipped.

What actually happened: run `01KZ84FG43SF` ran 56m57s, **succeeded**, its PR
merged, and the change went out in a release. Only the ledger transition never
happened.

**`fabro ps -a` IS THE DISCRIMINATOR, and it is the only one.** An evicted run is
absent from `ps -a` entirely; a completed one is listed there as `succeeded`. The
live `fabro ps` view cannot separate them, because both are simply gone from it.

So the rule "`ACTIVE` is never evidence of a run, `fabro ps` is" needs one more
turn of the screw: **the ABSENCE of a run from `fabro ps` is not evidence that no
run happened.** Check `ps -a`, and check the forge for a merged PR naming the
item, before releasing any claim. The remedy here is to CLOSE the item with the
verification recorded — never to re-dispatch.

### A FIFTH SHAPE: the work was DONE and GREEN, and the run destroyed it

Measured 2026-08-05 on `overseer-0fy`, run `01KZ87W6RNDMNSGBT7YKWZDM8N`. **This is
the most expensive member of the family, because the dispatcher reports `failed`
about work that had already succeeded.**

    05:56Z  dispatched
    ~06:33Z the AGENT FINISHED: `just check` 68/68 at 100% coverage, commit-msg
            hook re-ran the full suite green, committed as 4de441e.
            Then, verbatim: "No push/PR performed."
            Then: "Needs human: the loop cannot auto-resolve this work-item"
                  [R] Retry / [I] Re-implement from scratch / [A] Abandon
            Then: "Interview ended without an answer."  Dispatcher exits `failed`.
    ~09:56Z the RUN hits its 4-hour ceiling still waiting for input.

Afterwards the commit is unreachable — `git cat-file -t 4de441e` returns "Not a
valid object name", the run's scratch directory holds only logs, and fabro
executes remotely.

**THE WORK IS NOT GONE, AND THIS ENTRY SAID OTHERWISE FOR A WEEK. `fabro dump`
RECOVERS IT — TRY THAT BEFORE REDOING ANYTHING.**

    fabro dump <run-id> -o <dir>     # then read <dir>/stages/002-implement@1/diff.patch

The commit is unreachable, but the run's exported state carries the full
implementation as a patch. Measured 2026-08-12 on two independent runs:

| run | item | recovered | outcome |
|---|---|---|---|
| `01KZSPSTPFX6` | `livespec-dev-tooling-q3emww` | 244-line patch, 2 files | applied cleanly to master and was LANDED from the dump |
| `01KZ87W6RNDMNSGBT7YKWZDM8N` | `overseer-0fy` (this entry's own incident) | **1,248-line patch, 11 files** | preserved intact |

The second row is this entry's own "roughly four hours of green work, gone" — it
was recoverable the whole time. It no longer applies cleanly only because the
work was redone by hand afterwards and `overseer-0fy` closed; two of its files
already exist. That redo was avoidable.

The dump also works on old runs (used here on a run from three days earlier and
one from a week earlier), so retention is not the constraint — knowing the
command is. `stages/*/output.log` is exported too, which is how a janitor log
previously written off as "a content-addressed blob not locatable under
`~/.fabro/storage`" was later read.

**KNOW THE BOUNDARY — RECOVERY IS NOT UNIVERSAL, AND A DUMP WITHOUT A PATCH IS
NOT A COUNTER-EXAMPLE.** The patch exists only when the run got far enough to
capture a commit. Measured on a third run, `01KZBJNKGQXM6XWZ06EC7T8KQR`
(`overseer-1gig`, the `livespec-dev-tooling-sc0z` incident): its Green amend
itself failed — `git checkpoint commit failed` — so its dump holds
`output.log`, `prompt.md` and `response.md` but **no `diff.patch` at all**. That
work is genuinely unrecoverable, and `overseer-1gig` is still `ready`, never
redone.

So the discriminator is whether `stages/*/diff.patch` exists:

| run reached | dump holds | action |
|---|---|---|
| a captured commit, then blocked/reaped | `diff.patch` | recover and land it |
| commit itself failed | logs only, no `diff.patch` | genuinely lost; re-dispatch |

So the remedy below is still right about PREVENTION, but its premise about
recovery was wrong: **dump first, redo only if the dump is genuinely empty.**

**THE DISPATCHER'S EXIT IS NOT A REAP, AND THAT GAP IS THE RESCUE WINDOW.** The
dispatcher gave up at ~37 minutes; the run stayed live and blocking for another
**3.4 hours**. `fabro attach <run>` accepts "a running or finished workflow run",
so the interview was answerable that whole time by anyone who knew it existed.
Retry / Re-implement / Abandon are **supervisor-grade** choices, not
maintainer-grade ones. So the failure was not the loop asking — it was that
nothing was listening.

**WHAT TO DO.** Watch for the interview, not just for the terminal state: a
terminal-state watcher wakes you at the END of the rescue window, which is exactly
too late. Grep the dispatch log for `Needs human`, `Interview ended`, or `cannot
auto-resolve` and treat a hit as urgent. Annotate dispatched items to PUSH AND OPEN
A PR (draft if need be) BEFORE raising any blocking question — unpushed work behind
an unanswered question is unrecoverable. Filed as `bd-ib-6o6h` (orchestrator).

**A SIZING WARNING ON THE ITEM IS NOT THE CAUSE HERE.** The dispatcher warned this
item was 1959 chars with 5 enumerated parts and might exceed one unattended turn;
the agent completed it in ~37 minutes anyway. It was not too big to implement, it
was too big to FINISH UNATTENDED. Splitting fixes neither defect.

| | double-brace token | queue eviction | anchor-as-dependency | succeeded-untransitioned | interview-destroyed |
|---|---|---|---|---|---|
| `drive.py` exit | non-zero, immediate | **0** | **1** (dispatcher 3) | **0** | non-zero |
| error text | `template_undefined_variable` | none | `not in the ready set` | none | `Interview ended without an answer` |
| `fabro ps` after | never lists it | lists `runnable` | never lists it | ran, then gone | ran, then gone |
| `fabro ps -a` later | never lists it | **absent entirely** | never lists it | **`succeeded`** | **`failed`, wall = the full ceiling** |
| work landed | no | no | no | **yes — PR merged** | **no — done but never pushed** |
| phantom claim | yes | yes | **no** | yes | yes |
| remedy | fix the defect | release + re-dispatch | unset the dep edge | **close it** | **`fabro dump` the run and LAND the recovered patch; release the claim. Re-dispatch only if the dump is empty** |

The last two columns are the pair to keep straight: both ran and both are absent
from the live `fabro ps`, but one merged its work and must be CLOSED while the
other left its work unpushed and must be RECOVERED — `fabro dump`, not redone.
`fabro ps -a` separates them — `succeeded` versus `failed` — and the forge
confirms it.

### A SIXTH SHAPE: TWO runs for ONE item, the second colliding with the FIRST'S OWN published branch

Measured 2026-08-13 on `livespec-runtime-0u8`. **This one mimics
"interview-destroyed" — `blocked`, a human question, nothing obviously landed —
while its correct remedy is the exact opposite: do NOTHING to the work, because
the work is already published.**

The second run redid the implementation, then failed at its `pr` stage:

    push blocked: pre-push hook passed, but origin already has
    refs/heads/feat/<item> with commits not present locally; per instructions i
    did not overwrite or retry on this non-workflow-permission rejection.
    human decision needed

The remote branch was its **own sibling's output**. The agent refused to
force-overwrite and escalated to `blocked(human_input_required)`. That refusal is
CORRECT behavior and must never be "fixed" by teaching agents to force-push.

**THE DISCRIMINATOR IS ONE COMMAND, AND IT IS CHEAPER THAN EVERY OTHER CHECK IN
THIS SECTION — RUN IT FIRST, and run the FORGE query, not the ref probe:**

    gh pr list --head <publish-branch> --state all
    git ls-remote origin 'refs/heads/<publish-branch>'

The order was inverted here until 2026-08-20, and it matters (three-way control
recorded on the foreman plan epic): an EMPTY `ls-remote` discriminates NOTHING —
a merged PR's branch is routinely auto-deleted, so the ref probe reads empty
precisely when the work landed. Only the forge query over ALL states separates
never-pushed from merged-and-cleaned-up. A live publish branch, or a PR in any
state, means the work EXISTS. Releasing the claim
and re-dispatching on the "interview-destroyed" reading would have re-run work
that was already open as a PR and auto-merging.

Remedy: confirm the PR, `fabro dump` the blocked run and DIFF its patch against
what is published (here they were substantively identical — two words of
reason-string wording), then `fabro rm <run> --force`. Plain `rm` refuses a
blocked run and tells you to pass `--force`.

**Keep that order — release, inspect, remove — everywhere this remedy
generalizes** (measured twice on 2026-08-19, once by a thread that destroyed its
own run's evidence this way): claim-release and run-removal are SEPARATE acts.
Release the claim immediately, since a held claim blocks the ready set; `fabro
dump`/`fabro inspect` BEFORE any removal, because `rm --force` destroys the only
readable record of a swallowed cause; remove last. The commonly-practiced
recovery recipe ends with force-remove and trains the mistake.

**HOW TWO RUNS HAPPEN, and the correction it forces on the rule above.** The
first dispatch was killed by the CALLER's own timeout; `fabro ps -a` immediately
afterwards showed NO run for the item, so a second dispatch was issued. A run
existed anyway. So "`ACTIVE` is never evidence of a run, `fabro ps` is" needs its
final turn: **after you kill a dispatcher, absence from `fabro ps -a` is not
evidence that no run exists or will exist.** Do not re-dispatch on that basis —
check the publish branch and the forge first.

**Do not kill `drive.py` on a timeout, and do not put multi-minute dispatches in
the harness background-task tracker from a loop-parked session.** A 20-minute
foreground timeout produced both the phantom claim and the collision above; the
old replacement advice was `run_in_background: true` plus waiting for a
task-notification. That pattern is retired for any Claude Code session that may
end its turn with `ScheduleWakeup` / dynamic `/loop`: measured 2026-08-16
(`overseer-za32`), the harness reaps still-running background Bash tasks about
6-15s after parking, silently killing the dispatcher.

For loop-parked multi-minute dispatches, detach the dispatcher from the harness
process tree and read the verdict from disk:

```
run_dir="$PWD/tmp/overseer/detached-dispatch/<item>-$(date -u +%Y%m%dT%H%M%SZ)"
scripts/detached-dispatch.sh "$run_dir" -- \
  python3 /absolute/path/to/drive.py --action impl:<id> ...
```

The helper uses `setsid` + `nohup`, writes combined output to
`$run_dir/output.log`, writes the launcher pid to `$run_dir/pid`, and atomically
replaces `$run_dir/verdict.env` with `status=succeeded|failed` and `exit_code=N`
when the command exits. End the turn only after arming a wake; on wake, inspect
the disk files, `fabro ps`, `fabro ps -a`, and the publish branch/forge checks
above. The task-notification stream is no longer the record of completion for
loop-parked dispatch.

Two `verdict.env` refinements, measured 2026-08-19: the helper also writes it
with `status=running` AT LAUNCH, so wait on the value CHANGING, never on the
file existing; and its two-word verdict cannot distinguish refused-before-launch
from ran-and-failed — the dispatcher's own JSON envelope in `output.log` is the
authoritative record, so read that, not the verdict line. And across every shape
in this section: the ABSENCE of a phantom claim discriminates nothing by itself —
several shapes leave none.

| | double-brace | queue eviction | anchor-as-dep | succeeded-untransitioned | interview-destroyed | **publish-branch collision** |
|---|---|---|---|---|---|---|
| `fabro ps -a` | never lists it | absent | never lists it | `succeeded` | `failed` | **one `succeeded` + one `blocked`** |
| work landed | no | no | no | yes | no | **YES — PR open** |
| remedy | fix the defect | release + re-dispatch | unset the dep | close it | dump + land | **close the duplicate; touch nothing else** |

A **seventh** shape is documented further down rather than as an eighth column here,
because it is discriminated by something no column in this table holds: the factory
host running out of disk, which fails at stage `fabro-run` with an ENOSPC `detail`
naming a path on a machine this one cannot see. Local `df` and `fabro ps` both read
clean while every dispatch fails.

### `fabro ps` IS NOT THE EVIDENCE WHEN THE FACTORY IS REMOTE — READ THE JOURNAL

Every rule above leans on "`ACTIVE` is never evidence of a run, `fabro ps` is". **That
discriminator is LOCAL, and it silently stops working once an item is dispatched to a
remote factory.** Measured 2026-08-20: a live, executing run showed *nothing* in local
`fabro ps` because its item carried `dispatch_factory=hp` and the work was running on
another host. Read literally, the table above then says "absent from `fabro ps -a` ⇒
queue eviction ⇒ release the claim and re-dispatch" — which is how you manufacture the
publish-branch collision documented immediately above, against your own still-running
sibling.

**Check the item's dispatch factory before applying any local `fabro ps` reasoning.**
When it is remote, the local process view is blind. The journal is the first record
of truth because it names the run, but it is not the only instrument.

**THE JOURNAL IS APPEND-ONLY AND CUMULATIVE, SO MATCHING BY ID ALONE ALWAYS FINDS THE
PAST.** Two entry kinds matter: `stage: "dispatch-id"` carries `work_item_id`,
`dispatch_id` and `at`; `stage: "outcome"` carries a nested `outcome` object with
`work_item_id`, `status` and its own failing `stage`. An item dispatched more than once
has one entry per attempt, and a naive "latest outcome for this id" search happily
returns **yesterday's**.

That is not hypothetical: it produced a confident "the probe FAILED, do not dispatch"
verdict from an outcome that was 11 hours stale, while the current run was still
executing normally. **Floor every outcome query on the CURRENT run's own `dispatch-id`
timestamp** — take the latest `dispatch-id` for the item, then accept only `outcome`
entries strictly after it. An item with a dispatch-id and no later outcome is not
finished, not failed, and absolutely not evicted. That evidence is still only
negative: it cannot separate EXECUTING from WEDGED from EVICTED, and it carries no
elapsed time.

The remote factory process view is queryable. This is READ-ONLY inspection, not
routing work. Use the URLs already declared in `.livespec.jsonc` under
`dispatcher.factories` (`hp`, `vps`) and point fabro at the factory:

    fabro ps --server https://FACTORY-HOST:PORT

Measured 2026-08-22T08:26Z against `hp`: it listed three runs executing in this
repo with run ids, statuses and durations, plus one BLOCKED run in a sibling repo
at 195m — exactly the state the journal cannot distinguish from healthy progress.

Use both instruments, in order. The journal tells you WHICH run belongs to your
item: the current `dispatch-id`, floored by its timestamp. The remote process view
tells you WHAT that run is doing now. A blocked run is the interview-destroyed
shape in progress and is still rescuable; a running run at an unremarkable
duration is working and must be left alone.

This is the same failure as a stale baseline wearing a different hat, and the same rule
fixes it: a comparison has two sides, and an append-only log is one of them. See the
settings-default note in `overseer/AGENTS.md` for the general form.

### THE DOUBLE-BRACE TRAP REACHES LEDGER COMMENTS, AND THERE IT IS TERMINAL

Measured 2026-08-19 on `overseer-bc55wx.8`, which had to be **superseded** rather than
fixed. The first entry in this section says "do NOT fix this by editing the work item".
That advice quietly presumes editing is *possible*. For a comment it is not.

**Three things the original entry does not cover.**

**The goal includes COMMENTS.** `_dispatcher_goal.render_goal` assembles item fields,
**ledger comments**, and ratified lessons into one brief. A dispatch-safety check that
scans only `description`, `acceptance` and `title` — which is the obvious thing to
check, and what was checked here — passes an item that is already poisoned. The
failure arrives at stage `fabro-run` with the workflow file's own path and line number
in the message, which reads like a defect in the workflow rather than in your item:

    fabro::template::syntax
    template expansion failed in graph attribute `goal`:
    syntax error: unexpected `.` at line 73

The line number is an offset into the **expanded goal**, not into the file it names.

**The trap fires on prose ABOUT the trap.** The poisoned comment here was documenting
*this very hazard* and quoted the token in order to name it. Writing the literal
delimiter to warn a future reader is enough to break the item. **Name it in words** — "a
doubled left brace" — or describe the shape without reproducing it. The same applies to
`{%` and `{#`.

**Comments are APPEND-ONLY, so the record is unrecoverable.** `bd comments` offers
`add` and `list` and nothing else — no edit, no delete. Once a comment carries the
token, every future dispatch of that id fails identically, forever. The only remedy is
to **file a clean-text successor and close the original as superseded**, recording why,
so the finding's provenance survives even though the record cannot be dispatched.

**Run the successor as a CONTROL rather than assuming the diagnosis.** Here
`overseer-bc55wx.9` carried the identical scope and acceptance with no brace tokens and
dispatched normally on the *same* plugin build minutes later, which is what proved the
item text — not the build, not the fleet — was at fault. Two failed dispatches, each
under a minute, both leaving a phantom `active`/`fabro` claim to release by hand.

**THE ESCAPER IS NOT MISSING — ITS OUTPUT IS WHAT FABRO REJECTS.** Measured later the
same day, and it changes what you should ask for. `render_goal` *does* run
`escape_minijinja_literal` over the whole assembled brief, comments included, and it
produces exactly what it intends. It still fails.

**The proof is an artifact you can go and read, which is the useful part of this
entry.** The Dispatcher writes the assembled brief to `/tmp/fabro-goal-<item-id>.md`
before invoking fabro, and **that file survives a failed run** — so after any dispatch
failure you can inspect the exact bytes fabro was handed. Two of them, seven minutes
apart on the same build, are a clean two-way control:

| goal file | escaped openers | outcome |
|---|---|---|
| `fabro-goal-overseer-bc55wx.8.md`, 77 lines | exactly one, on **line 73** | rejected: `syntax error: unexpected` `.` **at line 73** |
| `fabro-goal-overseer-bc55wx.9.md`, 35 lines | none | ran normally, merged |

The error names *the very line the escaper produced*. So "add escaping" is not the fix,
and asking for it sends an implementer the wrong way. Filed with both candidate
mechanisms and a cheap disambiguation as `bd-ib-ai9a` (orchestrator tenant), which
supersedes `bd-ib-vv9y` — whose own **title** quotes the token, making the item that
describes the defect one of its casualties.

**QUOTING THE EVIDENCE POISONS THE REPORT.** This is the part to design around rather
than resolve to remember. A good bug report quotes the failing line verbatim; here the
failing line *is* the poison. The session that wrote the section above lost a
freshly-filed orchestrator item to exactly that within minutes of merging this guidance,
because what it needed to quote was the escaped line itself. Warnings do not fix this.
**Describe the byte sequence in words, and check mechanically before you file.**

**THE CHECK, which costs a second and needs no new tooling.** Run it against the item as
*stored*, not against your draft — a title, an acceptance clause or someone else's
earlier comment can carry the token:

    bd show <id> | grep -nF -e "$(printf '\173\173')" -e "$(printf '\173%%')" -e "$(printf '\173#')"

`printf` keeps the delimiters out of your own command line and shell history. No output
means the record is dispatchable. Any hit names the line to reword. Do this **before**
`bd comment` too — the comment is the common poisoning route, and once it lands it is
permanent.

### A SEVENTH SHAPE: the FACTORY HOST has no room for a run directory, and every local signal reads healthy

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

**INSPECTING A FACTORY IS NOT ROUTING WORK TO IT.** Pointing `fabro ps` or
`fabro inspect` at the second factory's server to read the state of a run that is
already there is a READ, and it stays permitted — it is the only way to report
accurately on a run you must not touch. Sending work is what is forbidden.

**THE ROUTE IS STICKY, WHICH IS WHY ONE RE-ROUTE OUTLIVES THE DECISION THAT MADE
IT.** `resolve_dispatch_factory_target` resolves the factory in the order explicit
`--factory`, then `LIVESPEC_FABRO_FACTORY`, then **the factory recorded on the work
item's own ledger metadata**, then `default_factory` — and it then writes the
resolved value BACK onto the item. So a single re-route PINS that item, and every
later dispatch of it goes to the pinned factory with nobody passing anything and
nobody intending it. Measured 2026-08-22: `overseer-v2vs` carried
`dispatch_factory: vps` in its metadata after one re-route, and would have returned
there on any re-dispatch.

Clear a stale pin with

    bd update <id> --unset-metadata dispatch_factory

and READ THE ITEM BACK. Do not use `bd update <id> --metadata @<file>` with an empty
object to do it: measured the same day, that reports `✓ Updated issue` and leaves the
key in place. `--unset-metadata` worked and the metadata read `null` afterwards. This
is the same shape as the `added_at` defect recorded elsewhere in this file — a write
path that reports success while writing nothing — and the remedy is the same: verify
the read-back, never the exit message.

Three things make a pin sweep read falsely clean. A default `bd list` omits `closed`
and `backlog` items, so pinned items resting in either state are invisible and the
sweep reports zero. The dispatch journal records the field as `dispatch_factory`,
not `factory`, so a tally keyed on `factory` returns every row unattributed and reads
as though no dispatch ever named a factory at all. And the journal only began
emitting `dispatch_factory` at 2026-08-21T04:12:10Z; a factory census built from the
journal is blind to every dispatch before that instant, and it under-reports silently
rather than erroring. Measured 2026-08-22T09:3xZ against
`tmp/fabro-dispatch-journal.jsonl`: `overseer-fwxl` carried
`metadata.dispatch_factory=vps` from dispatches at 2026-08-17T23:35:30Z,
2026-08-18T00:18:45Z, and 2026-08-18T01:34:56Z, but journal searches missed it and
it was found only by a full ledger metadata sweep over 711 items. The ledger stores
only the LAST route an item took, never a history, so once a pin is cleared neither
the journal nor the ledger can reconstruct that the item was ever pinned. A pin
sweep is evidence only at the moment it was taken; record the result where it was
taken instead of treating the sweep as a repeatable audit.

**DO NOT GO HUNTING FOR THE SEAT THAT CHOSE THE FORBIDDEN ROUTE.** On 2026-08-22 that
search was requested and could not have succeeded, because there was no freelancing
caller: the re-routes were seats correctly following the remedy this very entry used
to prescribe, and later dispatches came from the sticky pin above. When guidance and a
standing instruction disagree, the guidance is the caller.

**IT IS INTERMITTENT — do not escalate this as a factory outage.** The same host
carried a full run to an opened PR thirteen minutes after the failures below; the
evidence is at the end of this entry. Re-try `hp` first unless the standing
maintainer instruction above has been lifted. The diagnosis that follows is
accurate and worth reading in full; only its urgency is not.

Measured 2026-08-22T00:51Z dispatching `overseer-temi26.2` on plugin build
`392b3fa90f86`. The dispatcher's own JSON envelope, stage `fabro-run`, status
`failed`, `fabro_run_id` null:

    could not create run
    ╰─▶ Failed to persist run state: I/O error: creating run directory
        /home/cwoolley/.fabro/storage/scratch/<run>: No space left on device (os error 28)

**While it lasts, the blast radius is the whole factory, not one item.** The failure is in
run-DIRECTORY creation, so it precedes every item-specific step: the ready-set
test, the goal render, the acceptance guard. Nothing about your item causes or
avoids it, and every repo pointing at that factory is down at once.

**BOTH LOCAL INSTRUMENTS READ CLEAN, WHICH IS WHAT MAKES THIS EXPENSIVE.** The
path is on a REMOTE host: `/home/cwoolley` does not exist on the dispatching
machine (the local user is `ubuntu`), and local `df` reported **127G free at 82%
used** at the moment of the failure. So a `df` clears the host, `fabro ps` is
blind for the reason already documented above — the factory is remote — and the
investigator is sent back to the item text, which is the one thing that is fine.
**Read the `detail` string. It names the host's path and the errno.**

**It leaves a phantom claim, and its signature is its own.** Afterwards the item
read `status=active, assignee=fabro` with `fabro_run_id` null and no run in
existence; release it by hand before re-dispatching. Do not read it as any of
the six shapes above: the discriminator is an **immediate** failure at stage
`fabro-run` carrying an explicit ENOSPC `detail` that names the factory's
storage path — not `run-config-overlay` (exhausted credential), not `not in the
ready set`, not a `template_undefined_variable` token, and not silence.

**THE OLD SECOND-FACTORY MITIGATION IS FORBIDDEN HERE, AND THE DRIVE FLAG CLAIM
WAS FALSE.** A generic dispatcher re-route, where permitted, is only reachable
through the dispatcher entrypoint:

    python3 /absolute/path/to/dispatcher.py dispatch --repo <repo> --item <id> --factory <name>

Measured 2026-08-22T08:38Z on plugin build `088d313a361e`: `drive.py` rejects
`--factory` with `drive: error: unrecognized arguments: --factory`, and
`drive.py --help` exposes only `[--repo REPO] [--action ACTION] [--json]` plus a
retired positional. The detached-dispatch verdict `status=failed exit_code=2`
does not distinguish this argparse rejection from a factory refusal; read
`output.log`, not only `verdict.env`.

Do not apply that generic re-route in this repo while the 2026-08-22 maintainer
instruction stands. The measured 2026-08-22 violation was exactly this shape: an
`hp` dispatch of `overseer-6l7v.1` returned stage `capacity-deferred` at
08:36:57Z with the WIP cap saturated, and a follow-up `vps` re-route at
08:39:36Z treated configured topology as approval. It was not approval. A
capacity defer, including `active_count` equal to `wip_cap`, leaves the item
`ready` with no phantom claim and means wait for `hp`, not route elsewhere.

**Expect accumulation, not a spike.** Fabro run state persists per run under
`.fabro/storage`, the documented recovery recipes call `fabro rm --force` only
for specific blocked runs, and `fabro dump` is documented working on runs a week
old — so retention is long *by design* and nothing reaps succeeded runs on a
schedule. A host serving several repos at this fleet's dispatch rate fills.
That also means **a blind purge is the wrong remedy**: `fabro dump` is the fleet's
only rescue path for work stranded by the interview-destroyed shape, so deleting
recent run state to reclaim space trades an outage for the loss of that safety
net. Reclaiming space is host-mutation tier — not session-performable, and not
factory-dispatchable either, since a sandboxed agent cannot clean the host it
runs on. Carrier: `bd-ib-gr9f` (orchestrator tenant).

**IT IS INTERMITTENT, NOT AN OUTAGE — and this correction is here because the
first version of this entry said otherwise.** As filed, it claimed the host "is
out of disk" and that "every dispatch routed to it fails". The sibling tenants'
journals disprove the second half:

    00:51:02Z  overseer-temi26.2                  hp   FAILED at fabro-run, ENOSPC
    00:51:46Z  livespec-console-beads-fabro-jmqb  hp   FAILED identically, another session
    00:55:09Z  livespec-console-beads-fabro-jmqb  vps  re-routed, independently
    01:04:12Z  bd-ib-jb7rzr.10                    hp   dispatch-id issued
    01:18:03Z  bd-ib-jb7rzr.10                    hp   fabro-run COMPLETED, PR opened

The host accepted and completed a full run **thirteen minutes after** the
failures — whatever filled the disk cleared on its own, most plausibly a run
finishing and returning its scratch directory. So the condition is
threshold-shaped: it bites everything routed there while it lasts, and then stops
without intervention.

**Two consequences for how you act on it.** Do not declare a factory outage from
one failure — **re-try or re-route, and check a sibling tenant's journal before
escalating**, because a stop-the-line report costs a maintainer's attention and
this one would have been wrong. And do not read a later success as evidence the
first failure was misdiagnosed: both are real, and the durable defects are that
the host runs close enough to full to fail at all, that neither factory host has
headroom telemetry, and that there is no preflight refusal — the dispatcher
already refuses before sandbox launch for an exhausted credential and names the
condition, and a factory with no room deserves the same.

**The method lesson, which is the transferable part.** The claim was filed from
one observation plus one corroborating failure sixty seconds apart, and a
continuing state was inferred from two points. The check that overturned it cost
a single journal read in a sibling tenant — and it was run while trying to
QUANTIFY the blast radius, not to test the claim. **Quantifying a scope claim and
testing it are the same act**; going to look for the boundary first would have
filed it correctly.

### A DEFERRED item ANYWHERE in the tenant blocks EVERY dispatch in the repo

Measured 2026-08-19. This trap is not about your item, and its error text names
ids that have nothing to do with what you dispatched.

    LEDGER: status-conformance  <other-id>  status 'deferred' is outside the
      livespec lifecycle (allowed: acceptance, active, backlog, blocked,
      closed, pending-approval, ready)
    ERROR: pre-dispatch ledger checks failed; dispatch blocked

The pre-dispatch ledger check is a GLOBAL conformance sweep over the whole
tenant, not a check on the requested item. ONE non-conforming row refuses EVERY
dispatch in the repo until it is cleared.

**The cause is a TOOLING CONFLICT, not operator error, which is why it recurs.**
`bd` offers `--defer <date>` on both `create` and `update` ("Defer until date.
Issue hidden from bd ready until then"), and using it sets `status=deferred`
plus a `defer_until` timestamp. That status is native to the substrate and
absent from the orchestrator's allowed set above, so an ordinary, supported
scheduling action by ONE thread silently disables the factory for EVERY thread.
Nothing in the refusal points at the deferring action, and the deferring session
gets no signal at all.

**Check the horizon before deciding to wait it out.** `defer_until` is
arbitrary. The instance measured here had one item deferred about six hours and
another a full WEEK, so "wait for it to clear" was a seven-day answer.

**Its signature is in none of the shapes above — do not read it as one.**

| | this trap | anchor-as-dep |
|---|---|---|
| `drive.py` exit | 1 | 1 |
| dispatcher exit | **1** | 3 |
| error text | `status-conformance`, naming OTHER ids | `not in the ready set` |
| fabro run | none | none |
| phantom claim | **no** | no |

Dispatcher exit **1** with a `status-conformance` line is the discriminator. No
run is created, so there is nothing to find in `fabro ps -a` and nothing to
release.

**The remedy is NOT to un-defer someone else's item.** A deferral is a
deliberate scheduling decision by the thread that owns the item, and reverting
it discards that intent. Route it to that thread and ask for the intent to be
re-expressed as a conforming status with the horizon recorded in a comment or in
metadata: that unblocks the tenant immediately and keeps the schedule. Only the
owning thread should change it.

**Verify AFTER the whole repair, never between commands.** Clearing a deferral
with an empty `--defer` lands the item at the bd-native intermediate that is
itself outside the allowed set — so the documented remedy RE-TRIGGERS the same
global refusal mid-repair, and a repairer who checks the tenant between the
clear and the status-set watches it flip back to blocked and concludes the fix
is failing. Do the clear and the status-set as a pair, then verify once.

**That paragraph used to be fenced as an unreproduced report, and the fence is
now retired.** It is measured, and it is filed: `bd-ib-cleg6g` (orchestrator
tenant) carries it as its Defect 3, with the safe ordering recorded from the
live repair. Its acceptance requires the fix to cover the CLEAR path and not
only the set path — which is exactly the leg an implementer would otherwise
skip, since the set path is the one the bug report is written about.

**Two further things that item establishes, both of which change how you read
this section.** First, the incident it records happened HERE — measured live in
this tenant, roughly forty minutes of tenant-wide dispatch refusals, stop-the-
line. Second, and worse for anyone relying on tooling to protect them:
**bd-guard does NOT guard the `--defer` flag, and its own documentation of why
is false.** The guard blocks the `defer` SUBCOMMAND while deliberately passing
the FLAG through, documented as "a defer-date FLAG that writes no status". On
the deployed bd that premise was measured false — the flag DOES set the status.
So the trap is armed by default and the guard is not standing between you and
it.

**Do not let the immediate unblock close the underlying defect.** A consumer
that hard-blocks on a first-class status its own substrate produces will break
the fleet again the next time anyone uses a documented flag. That belongs in the
orchestrator tenant, sibling to the delimiter-token defect above. Likewise, any
conformance checker written to detect this needs a discriminating control
proving it REPORTS a genuinely non-conforming row — a scan that quietly
whitelists a status it should flag reports a clean tenant and is worse than no
scan.

### RETRACTED: `bd create --ephemeral` does NOT block dispatch — `open` is auto-healed

**This entry previously claimed the opposite, and the claim was wrong.** It is
kept rather than deleted because the wrong version was published here and
routed to another repo's foreman, who folded it into a tracked item as a third
defect channel. A silent deletion would leave that claim circulating with
nothing to find when someone came looking.

**What was claimed:** that `bd create --ephemeral` leaves a row at `open`, that
bd-guard exempts ephemeral from its backlog normalization, that the
conformance sweep has no ephemeral filter, and therefore that such a row
refuses every dispatch in the tenant.

**What is actually true — measured in the dispatcher's own source:**

- `_dispatcher_ledger_close.py` defines `_NATIVE_STATUS_REMAP` mapping `open` →
  `backlog` and `in_progress` → `active`, and the apply function WRITES that
  remap to the store.
- `_dispatcher_ledger_gate.py` orders the work: load, plan the remaps, heal and
  report, and only THEN run the ledger checks over the *projected* items. So
  `open` is healed in place and never survives to become a residual
  status-conformance finding.
- Only KEY-MISSES block — `deferred`, hooked, ad-hoc, unknown. **That is why
  the `--defer` trap above is real and this one is not.** The two statuses are
  not interchangeable, and the whole error was assuming they were.

**The design says so explicitly, and reading it first would have prevented
this.** The gate's own docstring: *"On a SHARED tenant the two transient
statuses appear CONTINUOUSLY (any active session's raw `bd create` lands
`open`; any raw `bd update --claim` lands `in_progress`). A detect-and-fail
gate blocks every session on any OTHER session's fresh transient item —
constant cross-session friction."* An ephemeral row at `open` is precisely the
case that design accommodates on purpose.

**What survives, and it is small.** Two measured facts still hold: the row IS
created at `open`, and bd-guard DOES exempt `--ephemeral` from its own
normalization. The consequence drawn from them does not, because a second layer
heals what the first declines to. The only residue worth knowing is a curiosity
rather than a hazard: a wisp row — documented as "not exported to JSONL", i.e.
deliberately disposable — gets mutated to `backlog` in the store by the
auto-heal on the next gate or dispatch run.

**Still delete a probe row when you are done with it.** That advice was right
for the wrong reason. The reason is tidiness in a shared tenant, not blast
radius.

**WHICH SURFACE YOU RUN DECIDES WHAT YOU SEE, and this is the part that
reconciles the retraction with a contradictory-looking report elsewhere.**
"Auto-healed" is true of the GATES and not of the bare check:

| surface | heals first? | reports `open`? |
|---|---|---|
| pre-dispatch (`ledger_blocked_after_normalization`) | yes — writes + journals | no |
| pre-push gate (`run_ledger_gate`) | yes — writes, prints each remap | no |
| `ledger-normalize` | yes (or projects, under `--dry-run`) | no |
| bare `ledger-check` | **NO** | **YES** |

So the intake status **never blocks a dispatch or a push**, and a standalone
`ledger-check` **does** report it. Both statements are true and they are about
different code paths — the pre-dispatch entry point is literally named
*after normalization*, while the plain check loads and runs the checks with no
remap step at all.

**Why that matters beyond pedantry.** An orchestrator-tenant item records a
repair in which clearing a deferral left the item at this status and appeared to
re-trigger a global refusal mid-repair. That reads as contradicting everything
above — and it does not. A repairer checking the tenant BETWEEN commands runs
the standalone check, which is exactly the surface that does not heal. The
dispatch that would have healed it never ran. **Both measurements are correct;
they were taken on different surfaces.**

So when you see a conformance finding for this status, ask which surface
produced it before concluding anything is blocked. And if you are writing
acceptance criteria around it, name the surface — an acceptance written as "the
status no longer appears" is satisfiable on one path and meaningless on
another.

**The method lesson, which is the reason this stays here.** The original entry
*fenced itself correctly* — it stated in terms that a dispatch refusal had not
been observed, and marked the blast radius as inherited from the `--defer` trap
rather than reproduced. **The fence named exactly the leg that turned out to be
false.** What was missing was the cheap follow-up the fence implied: read the
dispatch path to see whether the refusal *could* occur, instead of assuming it
transferred from a neighbouring status. A fence is only worth what you do about
it, and an unactioned fence reads to everyone else as diligence.

### A LEDGER-EDIT item can never be factory-dispatched

Measured 2026-08-04. If an item's deliverable is a beads mutation rather than a repo
change, no sandboxed agent can satisfy it: the fabro sandbox has no `bd` on PATH, no
`/usr/local/bin/bd`, no `BEADS_DOLT_PASSWORD` and no `.beads/metadata.json`, and the
assignment forbids writing a `.beads/` directory, so the documented recovery path is
closed too. The run reports the blocker honestly and parks at
`blocked(human_input_required)`, holding a claim until force-removed.

Tier such items supervisor/host and do them with the credential wrapper. The tell at
filing time: the acceptance is phrased as `bd show <id>` reading a certain way.

### "dispatcher plugin build is stale" names a remedy that appears to do nothing

```
ERROR: dispatcher plugin build is stale; executing build <old> predates
latest release <new>. Run `claude plugin update ...` before dispatching.
```

Running the update (or `just ensure-plugins`) **is correct and does work** — but
**a running session keeps its originally-resolved plugin path**, so the
Skill-resolved `drive.py` is still the old build and re-running the same command
reproduces the identical error. It reads as "the remedy is broken".

**Ruling, measured 2026-08-03:** dispatch-time absolute-path resolution is the
sanctioned remedy for an already-updated-but-stale session. It does not bypass
the stale-build gate; it uses the build that the gate itself names as current.
Session restart remains acceptable, but it is not required before routine
dispatch. The older Gate 1 sentence in
`plan/archive/background-shell-supervision-liveness/handoff.md` that equated this
with `--no-verify` is retired for dispatch commands.

Invoke the new build by ABSOLUTE PATH instead:

```
python3 ~/.claude/plugins/cache/livespec-orchestrator-beads-fabro/\
livespec-orchestrator-beads-fabro/<new-build>/scripts/bin/drive.py --action impl:<id> ...
```

Confirm which build is current with `just ensure-plugins` (it prints
`already at the latest version (<build>)`), then point at that directory.
Take the build id from `ensure-plugins`' own output, never from the error
message: the `<new>` id the error names is whatever was latest when the stale
build resolved, and can itself be superseded by the time you read it — pointing
at it reproduces the refusal with a fresher pair of ids (measured 2026-08-19).

**AND ITS FOUR-WAY SIGNATURE IS NOT UNIQUE — IT COLLIDES WITH THE
ANCHOR-AS-DEPENDENCY ROW OF THE TABLE ABOVE.** Measured 2026-08-21 dispatching
`overseer-7pqr3p`. A stale build refuses with `drive.py` exit **1**, dispatcher
exit **3**, **no** fabro run, **no** dispatch-id in the journal, and **no**
phantom claim — the item stays `ready` with no assignee. That is character for
character the reading the table maps to "anchor-as-dependency", whose remedy is
to inspect and possibly unset a dependency edge. Following it sends you looking
for an edge that is not there: status was `ready`, there was no `depends_on` of
any kind, and the repo's own `dispatch_acceptance_guard.py` returned `ok`.

**The refusal text is NOT in the detached run's `output.log`.** That file held
only the credential re-exec line and `drive`'s four-line report — status failed,
dispatcher exit code 3, "did not report green". `drive` swallows the
dispatcher's own stderr, so the one sentence naming the cause never reaches the
place a loop-parked session is told to read.

**So on any dispatcher exit 3 with no run, re-invoke the dispatcher DIRECTLY and
read its refusal before reasoning from the exit-code table:**

```
python3 <build>/scripts/bin/dispatcher.py dispatch \
  --repo <repo> --item <id> --json
```

It refuses before any sandbox work, creates no run, costs no spend, and prints
the actual cause. The table's rows are discriminators only once you have the
message; they are not a substitute for it.

**The window is narrower than it looks.** These two dispatches were nineteen
minutes apart: `overseer-vr3ym4.1` went out on build `15a4ae9aff88` at
06:29:42Z and succeeded; `overseer-7pqr3p` was refused on that same build at
06:48:48Z because `15b9787566a7` had been released in between. A build id
resolved at the top of a session — or even one that worked a quarter of an hour
ago — is not evidence about the next dispatch. Re-read `ensure-plugins` per
dispatch, not per session.

## A ledger field describes the RECORD, not the WORLD — `Updated:` is not activity, `status` is not scheduling

Measured 2026-08-19 with a live positive control. This one is cheap to get
wrong because the field sits directly under `Created:`, exactly where a reader
expects a last-touched date, and reads like one.

**IT DOES NOT MOVE ON A COMMENT WRITE.** A ledger item can be actively
investigated, argued over, and annotated at length while `bd show` keeps
reporting a months-old `Updated:` date. Comments are where this fleet records
nearly all of its evidence, so the field is blind to most of what actually
happens to an item.

**The control, and why the obvious one is not enough.** The first
counter-example found was `livespec-dev-tooling-qrunmn`: a comment dated
2026-07-20 against `Updated: 2026-07-19`. That is suggestive and **not
sufficient** — a migrated or backdated comment would produce the same reading
on a field that works correctly. The discriminating test is a **write you
perform yourself**:

    bd comment <id> "..."     # then immediately:
    bd show <id> | grep '^Created:'

Done on `overseer-mim`, whose `Updated:` stayed at `2026-07-26` across a
comment added seconds earlier. A sibling item touched by a genuine field
mutation the same day *did* show that day's date, so the field tracks record
mutations and not the comment stream.

**Why it matters beyond tidiness.** Staleness judgements route real decisions
here: whether a blocker is likely to move, whether to dedup onto an existing
record or file fresh, whether a "successor" is a genuine handoff or a parking
space. Reading `Updated:` as an activity signal makes a live item look
abandoned and — the more expensive direction — makes a **parked** item look
merely quiet when it is neither.

**What to do instead: verify behaviorally.** Ask what would be TRUE IN THE
WORLD if the item had progressed, and check that. For a code item, whether the
change is present on the owning repo's `origin/master`. For a forge item, the
PR state — GitHub's own `updated_at` *is* a real activity field, unlike this
one. Comment count is a useful secondary signal precisely because the
`Updated:` field ignores it.

This is a close cousin of the "check that cannot fail" hazard, with one
difference worth holding: there the check was RUN and could only return one
answer; here a field is READ and means something narrower than it appears.
Both end the same way — a confident claim resting on evidence that could not
have contradicted it.

### The same trap wears a second field name: `status` is not a scheduling signal

**The section above was originally written about `Updated:` alone, and that
framing was too narrow — proven the same day, by its own author, minutes after
landing it.** Having switched off `Updated:` and onto comment counts, the same
session then read a work item's **`status`** as evidence about whether anyone
was working, and recorded that four routed items were "not scheduled". One of
them, a P1 reading `BACKLOG`, had a **dedicated plan opened that very
day** in the owning repo — a published branch, a committed research note naming
that item as its anchor, and a live session on it.

**In this fleet the ledger row is the LAST thing to move, not the first.** Work
is planned in threads and branches, measured, and often half-done before any
row changes. So a row's status tells you what the record says about itself, and
nothing about whether a person or a factory run is on it right now.

**Check the world, not the row:** branches in the owning repo (including plan
branches), plan directories on its master, open PRs, running sessions, and the
state of the code the item describes.

**And weigh a negative correctly.** A search across another repo's planning
surface that finds nothing is *not* a negative result — the plan above
would have been missed entirely but for a coincidentally-noticed session name.
Say "I found no evidence of in-flight work", never "it is not scheduled". The
two sound alike and only the first is supportable from outside the owning repo.

**Why this generalization is the durable form.** Both instances are one error:
reading a field that describes a RECORD as though it described the WORLD. The
narrow rule did not prevent the second instance even in the mind that had just
written it, which is the strongest available evidence that the general rule is
the one worth carrying.

### And a THIRD field name, which is not a field at all: a FILE's history is not a FEATURE's history

Measured 2026-08-21, and it earns its place here because it defeated a reader who
had just re-read the two rules above and was actively applying them.

The question was whether a long-running `overseerd` predated a fix. `git log
--diff-filter=A -- <path>` showed the module carrying the behaviour was **created
hours after the daemon started**, which looks like proof. It was not. `git log -S
<symbol>` over the same tree showed the function had existed for **three weeks**;
the recent commit was a soft-band **split** that moved it into a file of its own
without changing a line of it.

**A refactor moves code without changing behaviour, so file history is the wrong
instrument for behaviour age.** This repo splits modules constantly — the LLOC
soft band makes that a routine, encouraged operation — so the wrong instrument is
wrong *often* here, not rarely.

    git log -S '<symbol>' --all -- <dir>     # when did this BEHAVIOUR appear
    git log --diff-filter=A -- <path>        # when did this PATH appear

**The expensive part is that the wrong instrument AGREED.** The conclusion being
tested — that the daemon was stale — happened to be TRUE, for an entirely
different reason. So the bad measurement produced a correct answer and a false
account of why, which is strictly worse than being wrong: nothing about the
result invites a second look. It was caught only because the live status file
plainly showed the supposedly-absent behaviour working.

Same family as the two rules above, one level down: there the hazard was reading a
RECORD's field as the WORLD's state; here it is reading a PATH's age as a
BEHAVIOUR's age. When a claim rests on "this did not exist yet", name which
instrument established that, and prefer the one keyed on the thing itself.

### And a FOURTH: a search result is not evidence about the PAST — date the information before you retract

Measured 2026-08-21. This one closes the family, because its victim is the very
habit the three rules above are meant to instil: checking yourself.

A completeness review found that a plan had deferred a concern to an owner that
turned out to be CLOSED, so the concern had no owner. Hours later, a broader
search found a live, well-groomed epic owning exactly that concern, with six P1
children. The obvious reading — the reviewer searched badly and the owner was
there all along — was about to be written up as a correction.

**It was wrong.** The owning plan's directory landed at 23:14:44Z and its scope
event was stamped 22:43. The review ran at 15:00Z. The owner did not exist then;
it was created roughly seven and a half hours later, plausibly *because* of the
finding.

**Both readings look identical today, and only a timestamp separates them.** A
present-tense query answers "what is true now" and is silent about when it became
true — so using it to audit a past claim reads the record's current state as the
world's history, exactly as the three rules above warn.

**An unnecessary retraction is not free.** It puts a false admission of error into
the permanent record, and it undermines a sound finding — here, one that had
already caused a P1 to be filed and may have prompted the cure. Over-correction
looks like diligence and costs the same as being wrong.

So before retracting on new information, ask **when the new information became
true**, and prefer the instrument that carries a date: the commit that added the
file, the stamped scope event, the run's `createdAt`. If the new evidence
post-dates the claim, you have an UPDATE — "correct when written, since cured" —
not a correction. Say so in those words; the two are different facts and the
record needs the difference.

### A FIFTH, AND THE FIELD IS ONE THE SESSION WROTE ITSELF: a timestamp a session WROTE is not a time that was MEASURED

Measured 2026-08-21, twice in one hour, by two seats independently — which is the
evidence that it is a method defect rather than carelessness.

**A session that never calls the clock estimates it, and the estimate runs ahead.**
One seat labelled a peer message `16:48Z` from its own sense of elapsed time; the
reading under that label had been taken meaningfully earlier, and it reported a PR
as open that had merged at `16:38:35Z`. The other seat published a
`plan-handoff-entry` declaring `timestamp: 17:10:00Z` while the ledger stored the
comment at **16:47** — a self-declared time twenty-three minutes in its own future.
Neither had run `date -u` at any point in the session.

**The two are not equally expensive, and the difference is the point.** A
mislabelled message costs a re-read; the value under it was never wrong. A
fabricated timestamp inside a handoff entry corrupts the **ordering key**: entries
in this fleet declare that they supersede the one below, and a resuming session
reads the newest. So the second one does not mislabel a reading, it reorders the
record a resume depends on.

**THE RULE: STAMP THE READ, NOT THE MESSAGE.** Bracket the call and quote what it
returns beside the value. Never estimate, never carry a stamp forward from earlier
in a session, and never let composition time stand in for measurement time.

    date -u +%Y-%m-%dT%H:%M:%SZ    # before the read, and again beside the value

**The independent check, when a declared stamp looks wrong:** the ledger records
its own storage time for every comment. A declared `timestamp:` that disagrees with
the stored time is settled by the stored one, and the disagreement is worth naming
in an appended correction rather than left for a reader to trip over.

Same family as the four rules above, and closest to the first: `Updated:` is not
activity, a PATH's age is not a BEHAVIOUR's age, and a timestamp a session WROTE is
not a time that was MEASURED. In each, a field that describes the RECORD gets read
as though it described the WORLD — here the record is the session's own prose, which
is why nothing external contradicts it. It also pairs directly with the rule
immediately above: that one says to date the information before retracting, and this
one is about the dates themselves being trustworthy.

Deliberately no mechanical enforcement is proposed here: a check that parses declared
stamps out of handoff entries and diffs them against storage times is a real idea and
a SEPARATE proposal, and folding it in would turn a guidance fix into a gate.

## `check-no-lloc-soft-warnings` CANNOT FAIL when you run it by hand

Measured 2026-08-22, after it rejected two pushes in a row while every attempt to
reproduce it standalone said the tree was clean.

Run the recipe directly and it prints rows that look reassuring and exits **0**:

    {"file": "overseer/_supervisor_core.py", "lloc": 224, "soft_ceiling": 200,
     "hard_ceiling": 250, "failing": false, "event": "file in 201-250 LLOC soft band",
     "level": "warning", ...}

`"failing": false`, `"level": "warning"`, exit 0. Run `just check` and the same
tree fails on the same target. **The row is not lying about itself — it is
answering a different question than the aggregate asks.** The check only converts
warnings into failures when `LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST` is set,
and only the aggregate sets it. The variable's name is right there in every row,
which is the tell, but a row that says `failing: false` reads as a verdict rather
than as a conditional.

**Reproduce it the way the aggregate runs it, or it will keep telling you the tree
is clean:**

    LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST=1 just check-no-lloc-soft-warnings

which prints the row the aggregate actually acts on, with the remedy in it:

    "expected_marker": "# livespec-lloc-soft-band-owner: <work-item-id>",
    "failing": true, "level": "error",
    "event": "file in 201-250 LLOC soft band with no owning work-item marker"

**The remedy is a marker, not a split.** A file between the 200 soft ceiling and
the 250 hard ceiling is allowed to sit there as long as it names an owning
work-item, which is how its siblings already carry the debt — `grep -rn
'livespec-lloc-soft-band-owner' overseer/` shows the convention and where in the
file the line goes. A split is what the HARD ceiling forces; the soft band asks
only that the debt be owned. Crossing 200 is easy to do without noticing: adding
~25 lines to a 190-line module does it, and nothing warns you at edit time.

**Why this belongs beside the charter-gate entry below.** That one says to suspect
the detector when a gate looks wrong. This is the mirror case — the detector is
correct and its STANDALONE INVOCATION is the thing that misleads, because it
cannot fail. This repo already catalogues checks that cannot fail as a hazard when
they are *written*; here one arrives through how a healthy check is *invoked*. The
general rule covers both: **before concluding a gate is flaky or wrong, confirm you
are running it with the same environment the aggregate gives it.** A green
standalone run is not evidence about a red aggregate.

## The charter gate's false positives all point ONE way — suspect the detector first

`tests/prompts/test_charters_carry_no_known_defects.py` scores every supervisor
charter in the fleet. During the 2026-08-03 fleet sweep (119 defects → 0, all six
repos) **every** false positive it produced pointed the same direction: it flagged
code that was **already correct**, and "fixing" the charter would have made it
worse. Three measured instances:

| what fired | the charter was actually | fixed by |
|---|---|---|
| `(h)` × 4 in `homelab` | resolving the wrapper from `.livespec.jsonc` — **better** than the hard-coded name the detector demanded | keying `(h)` on the wrapper PROPERTY |
| `(h)` × 1 in the orchestrator | invoking the wrapper across a `\` **line continuation** | joining continuations before matching |
| `(a)`+`(f)` in `homelab` | a **worked counter-example** in a block labelled `# DEMONSTRATION, not a check` | unfencing the block (see below) |

**So when a charter looks wrong, prove it with a THREE-WAY CONTROL before editing
it:** the suspect form, the same thing written differently, and a known-real
defect. If the first two disagree, the detector is wrong. Two of the three above
were caught exactly that way, and each would otherwise have had a session rewrite
correct code to satisfy a broken check.

**The escape for legitimate counter-examples needs NO gate change.** The detectors
read **fenced** bodies only — `_code_blocks` matches ``` and `~~~`, nothing else.
A charter that must SHOW a defective form as evidence puts it in an **indented
literal block** or in prose with inline code spans, and scores zero while changing
not one character of the demonstration. That is why this repo's own charters score
zero while discussing every one of these hazards. **Never add a self-declared
"skip this block" marker**: it would need its own discrimination leg and is exactly
the thing that later gets used to silence a real finding.

## Two PR mechanics that cost rework, both measured 2026-08-03

**Auto-merge is enabled in several fleet repos and it RACES you.** A PR merges
itself the moment checks go green — before you can push a follow-up commit or amend
a title. Observed twice in one session: one PR merged a minute after a supervisor
measured it, carrying a title that overclaimed by one defect; another merged at an
older commit, which **orphaned** the newer commit onto the branch and cost a second
PR to land it.

**Push every commit you intend to ship BEFORE opening the PR**, and never plan to
amend a title afterwards. When it happens anyway, correct the record with a comment
on the merged PR rather than leaving the claim standing.

**IT STILL HAPPENS WHEN YOU KNOW ABOUT IT — recorded 2026-08-13 as a repeat.** A
session that had just READ this warning opened a PR, kept working on the same
file, and pushed the follow-up commit four minutes after auto-merge had already
landed the first. The orphaned commit needed its own PR, exactly as described
above. Reading the warning does not help if the follow-up work is discovered
AFTER the PR is open. The operative discipline is narrower than "push first":
**once a PR is open, treat that branch as frozen** — put the next thought on a
new branch instead of reaching back.

### The GitHub rate-limit guard hook denies on the WORD "for", not on your intent

Measured 2026-08-13, after four consecutive denials of a legitimate command. The
`github_rate_limit_guard.py` PreToolUse hook denies any command matching BOTH a
GitHub call and a "loop or sleep":

    _GH_READ      = \bgh\s+(?:run|pr)\b
    _LOOP_OR_SLEEP = \b(?:for|while|until|select)\b|\bsleep\b

Those alternations match ordinary ENGLISH. A PR title containing the word "for",
or a commit message mentioning `while`, is enough — the guard cannot tell prose
in a `--title` from a shell loop. Denials it produced here included a `gh pr
create` whose only sin was the title "... extrapolations **for** the lessons
tally", and a `git commit` whose message quoted a `gh pr list` command.

The message it prints ("use the cached alternative `gh api --cache`") is sound
advice for a genuine polling loop and actively misleading for this case: there is
no loop, and no cache flag exists on `gh pr create`.

**Remedies, in order:** reword the title or message to avoid `for` / `while` /
`until` / `select` / `sleep` as standalone words; put long prose in a file and
pass `--body-file` / `-F` so it never reaches the command line; and split
`gh` calls away from any `sleep` used to wait. The guard is doing useful work
against real polling — do not disable it.

**THE `--body-file` REMEDY IS NECESSARY BUT NOT SUFFICIENT, AND THE MISSING HALF
IS WHAT ACTUALLY BITES: WRITE THE FILE IN A SEPARATE TOOL CALL.** The guard matches
the WHOLE command string it is handed, so a heredoc that writes the body and a
`gh pr create --body-file` in the SAME invocation still puts every word of that
prose on the command line — and the file indirection buys nothing. The denial then
looks inexplicable, because you did exactly what the remedy above says. Write the
body in one call, then invoke `gh` in the next, with no prose beside it.

Recorded because it caught the same session TWICE on 2026-08-19, the second time
minutes after it had hit the first and written up the guard's behaviour. Knowing
about the trap does not help; the shape of the command is what matters. Note also
that a body long enough to need a file is *precisely* the body most likely to
contain the word "for" somewhere, so these two remedies are needed together far more
often than either alone.

**AND THE THIRD DENIAL THAT SAME DAY HAD NO `gh` INVOCATION IN IT AT ALL — WRITING
*ABOUT* THIS GUARD TRIPS IT.** The denied command was a plain heredoc writing a file,
with no GitHub call anywhere. It matched because the PROSE BEING WRITTEN quoted the
command form the guard looks for, and that same prose — being ordinary English about
a defect — also contained "for" and "while". Both alternations hit inside a document
that was merely *describing* the hazard.

This is the same shape as the delimiter-token trap elsewhere in this file: **quoting
the evidence poisons the report.** A good write-up quotes the failing command
verbatim, and here the quoted command *is* the poison. So when documenting this guard
— in a PR body, a commit message, a ledger comment, or a file written by a heredoc —
**name the subcommand in words rather than reproducing the literal invocation form**,
or keep the quoted form and the English in different files. Do not rely on there
being no actual GitHub call to save you; the guard reads the command string, not your
intent.

**The red-green-replay ritual is ONE commit with `--amend`, not two commits.** Red
stages the test file **alone**; Green stages the impl and amends it. The test-file
bytes must be **byte-identical** across the pair, and exactly **one** test file may
be staged at Red — editing the test after the Red commit invalidates the pair.

**A change confined to `tests/` has no impl bucket at all**, so it never reaches
the Green leg. It takes the **green-verified** leg instead: a single commit, a
**non-`feat:`/`fix:`** prefix, and the full suite must pass. A `feat:` prefix there
is rejected with `test-passed-at-red`.

**THREE MORE, ALL MEASURED 2026-08-21 while landing `overseer-5lrp` and unblocking
PR 1397.** Each cost a full aggregate run or a CI cycle to discover, and none of
them announces its cause.

**A `.claude-plugin/` edit FORCES a `fix:`/`feat:` subject — and that does NOT put
you on the Red leg.** `check-prose-release-hygiene` refuses a `chore:` subject on
any commit touching the shipped plugin surface: a plugin edit must produce a
version bump on merge, or it does not belong under `.claude-plugin/`. The remedy it
prints is correct. What the remedy does not say, and what makes it look dangerous
to follow, is that the replay ritual routes on **HEAD state** once product impl is
staged, not on the subject — `_dispatch_impl_staged` is explicitly prefix-agnostic.
So with no Red awaiting a Green at HEAD, a `fix:` subject still takes the
green-verified leg. The Red-intent regex only reaches a **tests-only** staged tree.
Reading the ritual docs alone suggests `fix:` will demand a failing test; it will
not, when impl is staged.

**`git commit --amend -F <file>` SILENTLY DROPS THE HOOK-STAMPED `TDD-*`
TRAILERS.** The commit-msg hook writes its evidence trailers into the message.
Amending with a fresh message file replaces the whole message — trailers included —
and the amend re-runs the hook with an **empty staged set**, which is the
no-content-trigger branch: it returns 0 without re-stamping. The commit is then
carrying no evidence and `check-red-green-replay`'s range validation is what finally
refuses it, at push, several minutes later. **The tell is a sub-second replay
hook**: a real leg runs the suite and takes minutes. The fix is
`git reset --soft HEAD~1` and commit again so the hook re-runs with content staged.
(This is about re-wording, not about the ritual's own Green amend, which stages impl
and therefore has content.)

**A PR WHOSE BASE MOVED DOES NOT RE-TEST ITSELF, AND CLOSE-REOPEN RACES THE
MERGE.** `ci.yml` triggers on bare `pull_request:`, whose default types do not
include base-branch updates, so after you land the fix a PR was waiting on, that
PR's rollup keeps reporting the **stale** verdict indefinitely. `gh run rerun` does
not help: it replays the same event payload and therefore the same old merge SHA.
Close-and-reopen fires `reopened` and does produce a fresh run — but measured here,
a reopen fired **seventy seconds after** the unblocking PR merged still tested a
merge computed without it and failed identically, because GitHub's `refs/pull/N/merge`
lags. Two further consequences: close-and-reopen **clears auto-merge**, which must be
re-armed by hand; and the second re-trigger is indistinguishable from the first
unless you have independent evidence.

**THE CHEAP INSTRUMENT BEHIND ALL THREE IS A DETACHED REBASE PROBE**, and it is
worth reaching for before any of the reasoning above:

    git worktree add --detach <scratch> origin/<pr-branch>
    cd <scratch> && git rebase origin/master && just <the-one-failing-gate>

Under a minute, no push, no commit, nothing published. It answers — with a
measurement rather than an argument — whether the rebase conflicts at all, what the
merged tree actually contains, whether a proposed fix works **before** you author
it, and whether a re-triggered CI run was even testing the right tree. This repo
allows rebase-merge only, so that probe tree is precisely what CI evaluates. Used
four times in one session here; each use replaced a guess that would otherwise have
been committed.

## The `overseerd` daemon may be restarted at any time, as long as it isn't broken

Ratified by the maintainer 2026-08-17, superseding an earlier operator-gated
posture that had been established as a same-thread convention during a live
verification session rather than written down anywhere — this section is that
missing write-down, not a change to a previously-documented rule.

**The ruling, verbatim:** the daemon can be restarted at any time as long as
it isn't broken. No maintainer approval is required per restart. This applies
to the acting `overseerd` process specifically; it does not authorize
force-killing or force-respawning a tracked *session* (a worker or supervisor
pane) — that remains gated by the cardinal rule in
`overseer/marker-protocol.md` (a session is restarted only after it declares
itself `ready`).

**The "isn't broken" carve-out.** Before restarting, a quick sanity check that
the daemon is currently serving correctly (e.g. `overseerd --help`, or reading
a recent, sane `~/.livespec-overseer-status.json`) is reasonable diligence,
but this is not a formal precondition requiring separate sign-off — an agent
acting under this ruling uses ordinary judgment, the same as for any other
routine operational action.

**The checkout-fast-forward + respawn procedure**, observed working correctly
across three bounces during the ratifying session:

1. Fast-forward the primary checkout to the target commit
   (`git pull --ff-only` or `git merge --ff-only origin/master`) — do this
   *immediately* before the restart, not minutes ahead, since `overseerd` is a
   single long-lived process that imports `overseer.*` once at startup and
   never hot-reloads; whatever the checkout holds at the moment of import is
   what runs until the next bounce.
2. Stop the running `overseerd` process and start a fresh one
   (`overseerd`) from that checkout.
3. Verify the bounce actually picked up the intended change — do not assume:
   confirm the new process's pid and start time (`ps -o lstart=`), confirm via
   `git reflog` that the fast-forward landed *before* that start time (not
   after — a checkout pulled forward post-start does not affect an
   already-running process), and confirm the target commit is an ancestor of
   what was checked out (`git merge-base --is-ancestor`). A checkout pulled
   forward even a few seconds late produces a daemon that silently runs the
   prior release; this was observed directly during the ratifying session (one
   bounce landed one release behind because the pull that would have carried
   the fix arrived after the daemon had already started).

   **NORMALIZE THE CLOCKS BEFORE COMPARING THEM — `ps -o lstart` prints LOCAL
   time.** Step 3 is a before/after comparison between two instruments, and on
   this host they do not speak the same clock: the timezone is `Europe/Berlin`
   (CEST, **UTC+2**), so `ps -o lstart=` renders two hours ahead of the `Z`
   timestamps used by the ledger, the dispatch journal, `date -u`, and this
   file's own measurements. Applying that offset to only one side inverts the
   very test the step exists to make — a bounce that landed two hours BEFORE a
   fast-forward reads as having landed after it, and vice versa.

   Measured 2026-08-22, and it very nearly produced a published wrong
   conclusion: a listener's owning process showed `lstart` of `01:43:39` against
   a UTC wall clock of `01:23:53`, i.e. **twenty minutes in the future**, which
   reads as "started by the thing I just ran". Normalizing gave a true start of
   `23:43Z` — an hour and forty minutes EARLIER, a different process, a different
   session, and the opposite conclusion. A future start time is the tell; treat
   it as a unit error, never as a clock skew to reason around.

   Take the process start as an absolute instead of parsing the rendered string:

       stat -c '%y' /proc/<pid>          # start time WITH its UTC offset
       date -u -d "@$(stat -c %Y /proc/<pid>)" +%Y-%m-%dT%H:%M:%SZ

   and pin the other side to the same clock with `git reflog --date=iso-strict`
   (which carries an explicit offset) rather than the default relative rendering.
   The rule generalizes past this one step: **every timestamp comparison in this
   fleet has two sides, and any side rendered without an offset is a guess.**

**Rider, ratified 2026-08-20 — maintainer, typed directly into the foreman
pane; verbatim on the `overseer-z5fo4y` decision-batch comment:** "Yes it can
be restarted any time but whatever is restarting it must ensure that it stays
properly in the top pane of the overseer TMUX session as the overseer skill
prescribes." So the procedure above carries one more obligation: whatever
performs the restart must ensure the fresh `overseerd` lands, and stays, in
the TOP pane of the two-pane overseer tmux session per the overseer skill
(`overseer/SKILL.md`) — a daemon respawned into the wrong pane or into a
detached shell satisfies the three bounce steps and still violates the ruling.

**BEFORE TRUSTING THE ACTING DAEMON, CHECK WHAT IT IS RUNNING — AND USE THE ONE-READ
DISCRIMINATOR.** The section above is about restarting correctly. This is the
inverse and more common case: the daemon is healthy, serving, writing a fresh
status file every tick, and running **code from hours ago**. Nothing surfaces
that, because a stale daemon and a current one are indistinguishable from every
symptom except the one that is missing.

`~/.livespec-overseer-status.json` publishes the answer directly:

    daemon_package: {"package_dir": "…/overseer", "version": "1.7.4"}

Compare that to `git describe --tags --abbrev=0`. Measured 2026-08-21: the acting
daemon reported **1.7.4** while master was at **v1.12.0**, and two tracks sat at
`ready-uncertifiable` — one for **fifteen hours** — in precisely the state a fix
merged that afternoon was written to make certifiable.

**Prefer this to reasoning from process start times or file dates.** Both were
tried on that incident; the start-time argument was sound but laborious, and the
file-date argument was outright wrong (see the symbol-history rule above). The
version field settles it in one read and needs no argument about import semantics.

**The asymmetry to expect, because it sends investigators at the wrong half.**
Commands like `overseer-declare` are **separate entrypoints** — a fresh subprocess
per call — so they pick up new code immediately. The daemon does not: it imports
`overseer.*` once and never hot-reloads. After a merge and before a bounce, the
command half is fixed and the daemon half is not, so a session can be told the
truth by the command and then stranded anyway by the daemon. That reads as the
command being wrong.

**So a merged fix to daemon-side code is not in effect until a bounce**, and
"merged" is not a synonym for "live on this host". When a plan's deliverable is
daemon behaviour, its acceptance should include the bounce and a live control —
not merely a green CI run.

**THERE IS A THIRD STALENESS SURFACE, AND THE TWO ABOVE ARE THE EASY ONES.**
Measured 2026-08-22 (`overseer-lixhd3.1`). The paragraphs above frame this as a
two-way split: separate entrypoints are always fresh, the daemon is stale until
bounced. A third surface behaves like neither. **Prose — the operator contracts
under `.claude-plugin/prose/` — is read at SKILL-INVOCATION time and held for the
life of that session.** A session that invoked its skill before a contract change
runs the OLD contract however current the daemon is, and **no bounce reaches it**,
because the daemon does not own that copy. It goes current only when a fresh
session starts.

**The specimen shows both halves disagreeing in one row**, which is what makes it
worth recording rather than deducing. Minutes after a correct bounce onto a merge
that changed both daemon code and `foreman.md`, the status file carried a
`foreman-blocking-prompt` row against a live foreman seat: the post-bounce daemon
raising a condition that had shipped minutes earlier, against a seat that was
still behaving under the pre-merge contract because it had started first.
**Detection current, behaviour stale, same row.**

**The trap this sets, and it is expensive because it looks like a failed bounce.**
An acceptance criterion phrased as an observed end-to-end BEHAVIOUR can be
UNSATISFIABLE after a completely correct bounce, because only a session that
STARTED AFTER the merge can demonstrate it. Do not diagnose that as a bad bounce,
and do not re-bounce chasing it. Split such an acceptance in two: the daemon half,
provable immediately after the bounce, and the contract half, which is a WAIT for a
fresh session rather than a task anyone can perform.

**And keep the claim boundary straight.** "The daemon runs current code" does not
imply "the fleet is running current code". The second is false for every session
already in flight, and a reader will infer it from the first unless told otherwise.

**Two bounce mechanics worth having before you need them.** Confirm a bounce by the
daemon's INSTANCE ID changing, not by its version — version discriminates only when
the release actually changed, so a within-release bounce checked by version is a
check that cannot fail. And stop the daemon with `kill -TERM` on its pid, never
Ctrl-C into the pane: the pane's process is an interactive shell with `overseerd` as
its child, so TERM returns the shell to a prompt and the pane survives, while Ctrl-C
closes the pane and violates the top-pane rider even though all three procedure
steps were followed. Allow ~40s for the new instance to publish its first snapshot;
reading too early shows the PREVIOUS instance's snapshot, which is indistinguishable
from a failed bounce.

**When requesting or reporting a bounce, say which kind of evidence it can carry:**
an OBSERVED ROW, or only an INSPECTION OF THE LOADED TREE. A change whose new
condition has no live input yet can only be confirmed structurally, and saying so
keeps a structural check from reading as weaker than it is — and a positive one from
reading as stronger. Of three bounces on 2026-08-22, exactly one carried both a new
status-vocabulary entry and a live input for it.

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

Between 2026-08-17 ~13:05Z and that re-cut it was on `["ubuntu-latest"]`: the
morning's cutover to the ARC k3s scale set
`livespec-overseer-k3s` (livespec-s43svm.16) deterministically failed FOUR of
this repo's environment-sensitive tests on every master run it touched — both
`tests/prompts/test_repo_containment_discriminates.py` tests (tmux pane-cwd
reads return `''` in the pod), `tests/test_detached_dispatch.py`'s
process-group survival test (`os.killpg` PermissionError), and a foreman e2e
whose cwd-identity change went undetected — yet the SAME commits are green on
hosted runners and in the fabro sandbox container image under docker. The
flip-back is the workflow's own sanctioned direction (see the routing comment
block at the top of `ci.yml`) and was panel-ratified after master sat red
about three hours. Re-cut condition, recorded on `livespec-s43svm.16`
(livespec tenant): the pod must pass this repo's full suite — those four
named tests specifically — before `CI_RUNNER_LABELS` points at the scale set
again. See `livespec/plan/fleet-ci-runner-pool/research/
k3s-arc-kueue-migration.md` ("Real-traffic cutover log") and the
`livespec-s43svm.16` ledger comments.

**Root cause, found 2026-08-18 (livespec `livespec-s43svm.18`): ONE AppArmor
denial behind all four failures — nothing to do with the pid namespace, and
nothing wrong with the tests.** Ubuntu's
`kernel.apparmor_restrict_unprivileged_userns=1` *stacks* the AppArmor label of
every confined task, so a workflow-pod process carries
`cri-containerd.apparmor.d//&unconfined` rather than the bare profile name.
containerd's default profile grants intra-container `signal` and `ptrace` only
to `peer=cri-containerd.apparmor.d` — a bare peer name, which a stacked label
does not match — so the profile denied its own containers both operations.
`os.killpg` returns `EACCES` outright; tmux's `#{pane_current_path}` reads back
EMPTY because tmux derives it by `readlink()`ing `/proc/<pane pgrp>/cwd`, and
reading another process's `/proc/PID/cwd` is a ptrace-read. That is why the
denial arrived as an empty string instead of an error, and why it laundered into
assertion failures in tests that look unrelated to each other. Plain docker is
unaffected because `docker-default` is not stacked the same way — which is
exactly why the same Fabro image was green under docker and red in a pod.

The fix is in `livespec-dev-tooling`
(`ci-runner/k3s/phase2/apparmor/ci-runner-workflow`,
https://github.com/thewoolleyman/livespec-dev-tooling/pull/1531): a node-loaded
profile keeping every containerd deny rule and widening only the
`ptrace`/`signal` peer expressions, applied to hook-generated workflow pods via
`ACTIONS_RUNNER_CONTAINER_HOOK_TEMPLATE`. AppArmor stays in enforce mode; no
capability was added and nothing was made privileged. Verified in real CI by
run `32199679954`: all ten gating jobs carried
`labels=["livespec-overseer-k3s"]` with real pod runner names and went green,
including the full-suite `check-coverage` job.

**Second lesson, and it generalizes past this repo: in ARC's
`containerMode: kubernetes`, the pod your tests run in is NOT the runner pod.**
The container hook creates a separate `<runner-pod>-workflow` pod per job and
builds its spec itself, with an empty `securityContext`. Anything set under the
scale set's `template.spec` reaches the runner pod only. Reading a scale set's
`securityContext` and concluding you know what the tests executed under is
reading the wrong object — the same class of error as the runner-identity
mistake below.

**Triage lesson that cost a withdrawn revert (PR #1063):** these failures were
first mis-attributed to test interference from the PR that merged minutes
before the cutover took effect. Runner identity is part of CI-failure triage
in this repo — check WHICH runner executed the failing jobs (the jobs API's
`runner_name`) before attributing a red master to content. A docs-only commit
failing CI is the tell that the environment, not the tree, changed.
