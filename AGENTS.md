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

**And note precisely what is and is not gated**, because the sentence above is
narrower than it reads: `tests/test_module_docs_match_the_repo.py` gates exactly
ONE premise — that no authoritative doc denies `.ai/` exists in the present tense.
It does not check inventory accuracy, and nothing else does either. So these three
documents remain the right things to read, and their INVARIANTS and mechanics are
still authoritative; what you cannot assume is that any LIST in them is complete.
**Enumerate from the tree.**

As always `SPECIFICATION/` governs and the code is the final word on
behavior — that is normal precedence, not a warning about these files.

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

## The fleet has SEVERAL Anthropic credentials — probing the wrong one is the documented failure mode

Cite this section; do not restate it per plan thread. It exists because the
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
- **The Dispatcher's own Claude check is presence-only** —
  `os.environ.get(CLAUDE_CODE_OAUTH_TOKEN, "") != ""`
  (`_dispatcher_credentials.py:252`) — so a present-but-exhausted token passes
  pre-flight and the run dies mid-review. Codex, by contrast, has a real
  usability gate plus `dispatcher.py codex-cred-refresh`. Closing that
  asymmetry is `bd-ib-3mbj` (P1, orchestrator tenant); until it lands, the
  host-side probe in
  `plan/background-shell-supervision-liveness/handoff.md` §"Gate 4" is the
  only valid signal — verified 200 on 2026-07-30 after a token rotation.
- **Never print token material.** Presence, prefix and length are enough to
  identify which credential you are holding.

## Two dispatch traps whose error messages point AWAY from the fix

Both were measured on 2026-08-02 while dispatching from this repo. Each fails in
a way that makes the correct remedy look wrong, which is why they are here rather
than only in a plan thread.

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

### "dispatcher plugin build is stale" names a remedy that appears to do nothing

```
ERROR: dispatcher plugin build is stale; executing build <old> predates
latest release <new>. Run `claude plugin update ...` before dispatching.
```

Running the update (or `just ensure-plugins`) **is correct and does work** — but
**a running session keeps its originally-resolved plugin path**, so the
Skill-resolved `drive.py` is still the old build and re-running the same command
reproduces the identical error. It reads as "the remedy is broken".

Invoke the new build by ABSOLUTE PATH instead:

```
python3 ~/.claude/plugins/cache/livespec-orchestrator-beads-fabro/\
livespec-orchestrator-beads-fabro/<new-build>/scripts/bin/drive.py --action impl:<id> ...
```

Confirm which build is current with `just ensure-plugins` (it prints
`already at the latest version (<build>)`), then point at that directory.
