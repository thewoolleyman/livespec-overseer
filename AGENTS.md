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

**`just worktree-create` is currently DEAD IN THIS REPO, and it fails SILENTLY.**
Measured 2026-08-04 (`livespec-dev-tooling-3pre`): it exits **141** printing
nothing but `error: Recipe worktree-create failed on line 25 with exit code 141`.
`worktree_primary_path` pipes `git worktree list --porcelain` into
`awk '/^worktree /{print $2; exit}'` under `set -euo pipefail`; once the porcelain
output needs more than one write, awk's early exit SIGPIPEs git and pipefail
promotes 141, aborting inside a command substitution before the first `echo`. It is
a SIZE threshold, not flakiness — this repo has 123 worktrees / 21545 bytes and
fails; repos at ~1.5–2.7 KB work. Passing an explicit `base_ref` does NOT help; the
SIGPIPE precedes base-ref resolution. Until it is fixed, use the documented rescue:
`git worktree add -b <branch> <dest> origin/master`, then
`just install-worktree-pack` inside it, then discard the `worktree_discipline` key.

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

  That is a real usability gate, symmetric to the Codex one, and `bd-ib-3mbj` —
  the item that closed the asymmetry — reads `acceptance` in the orchestrator
  tenant. **So a present-but-exhausted token no longer passes pre-flight, and a
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
THIS SECTION — RUN IT FIRST:**

    git ls-remote origin 'refs/heads/<publish-branch>'
    gh pr list --head <publish-branch> --state all

A live publish branch, or an open PR, means the work EXISTS. Releasing the claim
and re-dispatching on the "interview-destroyed" reading would have re-run work
that was already open as a PR and auto-merging.

Remedy: confirm the PR, `fabro dump` the blocked run and DIFF its patch against
what is published (here they were substantively identical — two words of
reason-string wording), then `fabro rm <run> --force`. Plain `rm` refuses a
blocked run and tells you to pass `--force`.

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

| | double-brace | queue eviction | anchor-as-dep | succeeded-untransitioned | interview-destroyed | **publish-branch collision** |
|---|---|---|---|---|---|---|
| `fabro ps -a` | never lists it | absent | never lists it | `succeeded` | `failed` | **one `succeeded` + one `blocked`** |
| work landed | no | no | no | yes | no | **YES — PR open** |
| remedy | fix the defect | release + re-dispatch | unset the dep | close it | dump + land | **close the duplicate; touch nothing else** |

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

**Verify AFTER the whole repair, never between commands.** Reported by the
thread that performed the repair, and NOT reproduced here, so treat it as
operational caution rather than as a measured fact: clearing a deferral can land
the item at an intermediate status that is itself outside the allowed set, so a
repairer who checks the tenant between the clear and the status-set will watch
it flip back to blocked and conclude the fix is failing. Do the clear and the
status-set as a pair, then verify once.

**Do not let the immediate unblock close the underlying defect.** A consumer
that hard-blocks on a first-class status its own substrate produces will break
the fleet again the next time anyone uses a documented flag. That belongs in the
orchestrator tenant, sibling to the delimiter-token defect above. Likewise, any
conformance checker written to detect this needs a discriminating control
proving it REPORTS a genuinely non-conforming row — a scan that quietly
whitelists a status it should flag reports a clean tenant and is worse than no
scan.

### `bd create --ephemeral` DOES THE SAME THING, and the guard exempts it ON PURPOSE

Measured 2026-08-19 on a live throwaway row. This is the same tenant-wide
outage as the `--defer` trap above, reached through a different documented
flag — and the guard that exists to prevent exactly this has an explicit
carve-out that produces it.

**The chain, each link measured:**

1. `bd create --ephemeral "..."` returns a row at status **`open`**. Not a
   display artifact — `bd show --json` reads `'status': 'open'` from the
   database.
2. **The guard deliberately does not normalize it.** `/usr/local/bin/bd`
   forces ordinary creates to `backlog`, but its create-exclusion list is
   `--ephemeral|--dry-run|--help|-h`, commented *"do not force"*. So the one
   mechanism that would have made the row conforming is switched off for
   precisely this flag.
3. **The pre-dispatch sweep does not exempt it.** The `status-conformance`
   check iterates active items and tests each against `ALLOWED_BEADS_STATUSES`;
   its own docstring names beads' native `open`/`deferred` as the values that
   "must not silently park dispatchable work in an unknown lane". There is no
   ephemeral or wisp filter anywhere in that module.

So an ephemeral row sits `open` and outside the allowed set until it is closed
or deleted, and — per the trap above — **one non-conforming row refuses EVERY
dispatch in the repo.**

**Why this is worth its own entry rather than a line on the `--defer` one.**
`--ephemeral` reads as the *safe* choice. It is documented as "not exported to
JSONL", which sounds like a row that stays out of everyone's way, so it is the
natural thing to reach for when you need a disposable row — a probe, a scratch
record, a test subject. It is the flag whose whole purpose is *not disturbing
anything*, and it is the one that takes the factory down.

**If you need a disposable row, delete it in the same breath.** `bd delete <id>`
removes it permanently and reports the reference cleanup. Do not leave one
parked over a break; the blast radius is every dispatch in the tenant, and the
refusal names other people's ids, never yours.

**Census after any such probe**, which is one command and closes the loop:

    bd list --all --json   # then count statuses against the seven allowed

**What was NOT observed:** a dispatch actually being refused on an ephemeral
row. The chain above is read from the guard's exclusion list and the checker's
own iteration, plus a live row confirmed sitting at `open`. That is a strong
chain and it is not the same as watching the refusal, so treat the blast-radius
claim as inherited from the `--defer` trap — which WAS observed — rather than
independently reproduced here.

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

## CI runner routing

`CI_RUNNER_LABELS` (a repo variable, never a `.github/workflows/` edit —
the full `just check` aggregate now invokes `check-no-workflow-edits` to
forbid that here) routes this repo's gating
`pull_request`/`push` CI matrix. **As of 2026-08-19 it is
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
