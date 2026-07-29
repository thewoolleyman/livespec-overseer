# Plan — codex-parity-and-rollout-safety

> # ▶ RESUME HERE — session handoff, 2026-07-29
>
> **A1 is DONE. A2 is BLOCKED ON A REPRODUCIBLE FACTORY FAILURE, not on a
> decision. A3 waits on A2. Everything below this box is older context that is
> still accurate unless this box contradicts it.**
>
> ## Slice state, read from the ledger 2026-07-29
>
> | slice | id | state |
> |---|---|---|
> | **A1** | `overseer-4km4mj` | **DONE / CLOSED.** PR **#242** merged, `ee67267e…`, verified an ancestor of `origin/master`. Content verified: `.livespec.jsonc` keeps `status: "exempt"` with a `reason` naming brief 17 **and** the archived ruling path; the stale `check-plugin-resolution` justfile comment is corrected. Maintainer accepted it through the `ai-then-human` valve; I relayed that decision, I did not self-accept. |
> | **A2** | `overseer-vyie5q` | **`ready`, no assignee — CLEAN and ready to dispatch.** Its last run was abandoned and the claim released at wrap-up, so no stale claim remains. See the blocker below before dispatching. |
> | **A3** | `overseer-kju6wh` | `pending-approval`, `admission:manual`. Blockers were A1 (now done) + A2 (not done). **Do not start until A2 lands.** |
> | **B2** | `overseer-vfz5v5` | `pending-approval`, `admission:manual`. **STOOD DOWN** — blocked on B1, which livespec-dev-tooling owns. Not this thread's to implement. |
> | **B1** | `livespec-dev-tooling-3nt9` | filed in **livespec-dev-tooling**, `backlog`. Never implement here. |
> | **C1** | `livespec-1p31` | filed in **livespec** core, `backlog`. Never implement here. |
>
> ## ⛔ THE A2 BLOCKER — do not re-dispatch blind
>
> Every Fabro run for A2 dies the same way:
>
> ```
> node: review   failure_class: transient_infra
> failure_signature: review|transient_infra|acp turn failed
> graph.default_max_retries: 0     →  escalates to "Needs human" interview, run blocks
> ```
>
> Observed **three times**: run `01KYP4WDAT4R` twice (blocked at ~13m, retried,
> died at **61m39s**) and run `01KYP9Z87QC3` at **7m30s**.
>
> **CORRECTION TO A CLAIM I MADE MID-SESSION.** I told the supervisor this
> matched `bd-ib-2nq` (the >60-min Fabro GitHub-App token-TTL bug) because the
> first run died at 61m39s. **The 7m30s reproduction disproves that** — it is not
> a TTL effect. Do not carry the TTL attribution forward; it was my hypothesis,
> not a measurement, and it is wrong. What IS established: the failure is
> **reproducible**, it is **misclassified as `transient_infra`**, and with
> `max_retries=0` a single occurrence escalates straight to a human.
>
> **Retrying is known not to work** — three attempts, three identical failures.
> Answering the interview `[1] Retry` was tried and failed. Do not loop on it.
>
> **The next session's first job is to diagnose WHY the `review` node fails in
> this repo**, then file it (orchestrator tenant — that repo owns the factory).
> `mise exec -- just check` passes locally and the first run self-reported
> implementing everything and passing 62 targets / 532 tests, so the failure is
> in the review stage itself, not in the work.
>
> The claim was already released at wrap-up, so A2 is dispatchable as-is.
> (If a future run dies and leaves it `ACTIVE` with no live run, release it with
> `drive --action move:overseer-vyie5q:ready` before re-dispatching.)
>
> ## Operational facts that cost real time to learn
>
> - **`ls` is aliased to long format in the interactive shell but NOT inside a
>   script.** `ls -t <dir> | head -1` returns a bare name in a script and a full
>   stat line inline, which silently builds a garbage path. Use `command ls`.
> - **`ls -t` is not a currency signal anyway** — directory mtime tracks last
>   USE, so the stale build an active session keeps touching floats to the top
>   forever. When the staleness gate refuses, it NAMES its target
>   (`predates latest release <X>`); that string is authoritative.
> - **Never capture and reuse a plugin build path** — re-derive at the moment of
>   each dispatch. Quoting the path a skill printed is still hand-resolving,
>   because the skill binding is itself a pinned snapshot.
> - **Check-then-dispatch on the host cap is a RACE.** Reading `fabro ps`,
>   seeing a free slot, then dispatching loses to other tracks. Retry the
>   dispatch itself — it is the atomic attempt. Won a slot on ~attempt 13 at 30s.
> - **Cap semantics:** `dispatcher.host_dispatch_cap`, unset here so default 2.
>   HOST-level; counts live Fabro processes + slot locks, NOT ledger statuses.
>   Use the RESOLVED `/home/ubuntu/.local/bin/fabro ps` — a bare `fabro` does not
>   resolve under the credential wrapper and reports an empty gauge for a full cap.
>   **A cap refusal is a resource wait, never a blocker. Never raise the cap.**
> - **Verify the CLAIM, not the command.** `drive` printed `status: failed` on a
>   run that had claimed the item, and printed nothing wrong on a dispatch that
>   never happened. The ledger (`status` + `assignee`) is authoritative:
>   `ready` + no assignee means it did NOT dispatch.
> - Long-running **background** tasks were killed externally twice; foreground
>   calls with a long timeout were reliable.
>
> ## Defects filed this session
>
> | id | tenant | what |
> |---|---|---|
> | `overseer-j1r` | **this repo** | P1 — a live in-tmux track reports the red `session-gone` when its Claude registry name is DERIVED not the topic; both the match and its softener gate on the same name equality (`_supervisor_offer.py:140`, `:202`). |
> | `bd-ib-rhv0` | orchestrator | P1 — `groom.py:306` hard-codes `admission_policy="auto"`, overriding a manual repo. |
> | `bd-ib-ah2r` | orchestrator | P2 — `prose/groom.md` stale vs its own code. |
> | `bd-ib-a8zi` | orchestrator | P1 — cross-repo slice ids minted with the LOCAL prefix are unfileable at the target, so a dependent slice blocks forever. |
> | `bd-ib-97v4` | orchestrator | P2 — staleness gate compares the executing build to the newest release, but its prescribed remedy cannot move the executing build. |
>
> ## Still outstanding, unchanged
>
> **B2's cross-repo dep pointer is dangling** and needs the one-command repoint
> in the boxed warning further down this file. It was drafted and deliberately
> NOT applied — it is a raw `--set-metadata` write outside every documented
> `drive` valve, so it awaits maintainer/supervisor vetting. It unblocks nothing.

**Owning repo:** `livespec-overseer`. **Status: A1 DONE; A2 blocked on a
reproducible factory `review` failure; A3 waits on A2; B2 stood down.
B1 and C1 are filed in their OWN repos' tenants — `livespec-dev-tooling-3nt9`
and `livespec-1p31` — not here.**

**Ledger anchor: the epic `overseer-az5nps` is CLOSED.** `groom` regroomed it
out on 2026-07-28 — that is the operation's normal disposition, not a loss, and
the maintainer ruled to accept it. The anchor is now the filed slice set below.

### The filed slice set — READ THIS BEFORE THE LEDGER

The closed epic's forwarding reason names **only the four local slices**, because
`groom` does not file cross-repo slices into this tenant. **The two cross-repo
items appear nowhere else in this repository's record, so this table is the only
place they are linked back to the thread that cut them.** That erasure is the
burial failure this thread was created to prevent — and it very nearly happened
twice, since the ids `groom` handed over for them turned out to be unusable
(see the boxed warning below).

| slice | id | owning repo | blocked by |
|---|---|---|---|
| **A1** — record the codex scope supersession in `.livespec.jsonc` without asserting a capability that does not yet exist | `overseer-4km4mj` | `livespec-overseer` | — |
| **A2** — ship the `.codex-plugin/` surface for `overseer` and `supervise-plan` | `overseer-vyie5q` | `livespec-overseer` | — |
| **B1** — build the shared codex derive-from-settings module (the `fleet/ensure_plugins.py` twin) | **`livespec-dev-tooling-3nt9`** — FILED 2026-07-28 (minted id `overseer-llz4xi` is DEAD, see below) | **`livespec-dev-tooling`** | — |
| **B2** — replace this repo's hard-coded `ensure-codex-plugins` body with the shared delegation | `overseer-vfz5v5` | `livespec-overseer` | **B1** (`sibling_work_item`), A2 |
| **A3** — flip `harnesses.codex` to `supported`, with a repo-local check that makes the green load-bearing | `overseer-kju6wh` | `livespec-overseer` | A1, A2 |
| **C1** — adopt the `oh-my-codex #3024` live-session rollout policy | **`livespec-1p31`** — FILED 2026-07-28 (minted id `overseer-qfnjj6` is DEAD, see below) | **`livespec`** core | — |

B2's cross-repo blocker is not visible to `bd dep tree`, which walks local edges
only. It is recorded on B2 as
`non_local_depends_on: [{"kind":"sibling_work_item","repo":"livespec-dev-tooling","work_item_id":"overseer-llz4xi"}]`.

> ### ⚠ B2 IS PERMANENTLY BLOCKED UNTIL THAT POINTER IS REPOINTED
>
> **The pointer above names an id that CANNOT EXIST.** `groom.py:196` mints a
> cross-repo slice's id with the LOCAL tenant's prefix, and bd refuses it at the
> destination. Measured 2026-07-28, filing B1 into `livespec-dev-tooling`:
>
> ```
> Error: prefix mismatch: database uses 'livespec-dev-tooling-'
> but ID 'overseer-llz4xi' doesn't match (use --force to override)
> ```
>
> Nothing was created. So B1 was filed under a NATIVE id,
> **`livespec-dev-tooling-3nt9`**, and B2 still points at the dead one. The
> sibling lookup fail-closes, and UNKNOWN BLOCKS. Both resolved live, side by
> side:
>
> ```
> overseer-llz4xi            -> RefStatus(value='unknown')   ← blocks FOREVER
> livespec-dev-tooling-3nt9  -> RefStatus(value='open')      ← blocks CORRECTLY
> ```
>
> Fail-closed is the CORRECT design (qiqz6b clause 1); the bug is upstream, and
> is filed as **`bd-ib-a8zi`** (P1). **The repair in THIS repo is one command**,
> pending maintainer/supervisor vetting because it is a raw metadata write
> outside every documented `drive` valve:
>
> ```bash
> bd update overseer-vfz5v5 --set-metadata \
>   'non_local_depends_on=[{"kind":"sibling_work_item","repo":"livespec-dev-tooling","work_item_id":"livespec-dev-tooling-3nt9"}]'
> ```
>
> `--set-metadata` is targeted, so `rank: a2` survives; plain `--metadata`
> replaces the whole object and would drop it. **The repair UNBLOCKS NOTHING** —
> B1 is at `backlog`, so B2 stays blocked, correctly, instead of forever.
>
> C1 needs no equivalent repair: no local slice depends on it.

### Current ledger state — read back 2026-07-28, not inferred

| slice | id | status | admission |
|---|---|---|---|
| **A1** | `overseer-4km4mj` | **`ready`** — ADMITTED | `manual` |
| A2 | `overseer-vyie5q` | `backlog` | `manual` |
| B2 | `overseer-vfz5v5` | `pending-approval` | `manual` |
| A3 | `overseer-kju6wh` | `pending-approval` | `manual` |

`next` returns exactly one candidate from this thread: **A1**. Nothing else here
is dispatchable. **A1 is admitted, NOT implemented** — dispatch is a separate,
deliberate act through the factory route (see §NEXT ACTION).

A1 was admitted from `backlog` with `move:overseer-4km4mj:ready`. The obvious
primitive, `approve:<id>`, was tried FIRST and refused — *"expected
pending-approval source state for overseer-4km4mj; found backlog"* — and
`move_item` forbids `pending-approval` as a target by ship-guard
(`_MOVE_ALLOWED = {backlog, ready, blocked}`), so there is **no
`backlog → pending-approval → approve` route**. A1 keeps `admission:manual`
deliberately: that label gates only the `pending-approval → ready` transition,
which an operator move bypasses, and leaving it `manual` records honestly that a
human admitted this item rather than policy auto-promoting it.

### Why every slice carries `admission:manual` — a defect, now filed upstream

**At filing, all four slices carried `admission:auto` and the two with no
dependency edges (A1, A2) were promoted straight to `ready`, past a maintainer
admission valve that was explicitly closed.** They were set back by hand:
`set-admission:…:manual` on all four, plus `move:…:backlog` on A1 and A2, because
the policy label alone does not hold a `ready` item.

That is not this repo's bug. Measured in plugin version `c878ea43f8cd`:
`groom.py:306` stamps `admission_policy="auto"` unconditionally on every filed
slice; `intake_dor.py:152-159` promotes a dependency-free `pending-approval`
slice to `ready` when the effective policy is `auto`; and
`_dispatcher_policy_settings.py:126-127` gives the per-item stamp precedence over
the repo default, which for this repo is the `manual` fallback
(`_dispatcher_policy_settings.py:52`) since `.livespec.jsonc` declares no
`dispatcher` key.

**Filed in the `livespec-orchestrator-beads-fabro` tenant** at the maintainer's
direction — that repo owns them, so they are recorded here by id only:

- **`bd-ib-rhv0`** (P1) — groom hard-codes `admission_policy="auto"`, silently
  overriding any manual-policy repo. Dependency-bearing slices carry a DELAYED
  form of the same fault: they hold on their edges, not on policy, so they
  auto-promote the moment their blockers clear.
- **`bd-ib-ah2r`** (P2) — `prose/groom.md` is stale against `commands/groom.py`:
  its Step 3 example omits the required `local_repo` argument, and it never
  mentions `CrossRepoSlice`, the very mechanism that keeps B1 and C1 out of this
  tenant.
- **`bd-ib-a8zi`** (P1) — `groom.py:196` mints cross-repo ids with the LOCAL
  tenant prefix, so bd rejects them at the target tenant and any local slice
  with a cross-repo dep is **permanently blocked**. Found by attempting the
  groom's own Step 4/5 routing; see the boxed warning above for the measured
  reproduction and this repo's one-command repair.

Both were hand-filed, so the `bd create` → beads-native `open` hazard DID apply
(unlike the groom route); both were filed `--no-inherit-labels`, explicitly set
to `backlog`, and read back to confirm.

Created 2026-07-28 from maintainer supervisor brief 17. **Both problems are
already root-caused with evidence. Do NOT re-derive either cause** — that is the
single most likely way to waste this thread's first session.

> **The brief is at `tmp/supervisor/brief-17.md`, which is GITIGNORED
> (`.gitignore:2`) and therefore not a readable artifact for a cold-open
> reader.** It is cited as provenance only, never as a read-first dependency.
> Everything load-bearing from it is reproduced in this file and the two
> research notes, which is what makes them self-sufficient without it.

## Read-first chain

1. This file.
2. `research/codex-plugin-visibility.md` — problem 1's cause, the scope
   supersession, and its live-acceptance bar.
3. `research/live-session-rollout-safety.md` — problem 2's cause, the
   `oh-my-codex #3024` precedent policy, and its live-acceptance bar.

That is the whole chain. `supervisor-handoff.md` now also exists in this thread
(generated 2026-07-28 02:06); it is the supervisor's charter, not part of the
worker's read-first chain. See §"Why this thread's supervisor charter needed a
workaround".

Status is READ from the ledger, never stored here: run
`/livespec-orchestrator-beads-fabro:list-work-items --json` and
`/livespec-orchestrator-beads-fabro:next`. This file carries no checkbox queue.

## The two problems, in one paragraph each

**Problem 1 — the overseer plugin is INVISIBLE to Codex.**
`ensure-codex-plugins` (fleet justfile, owned by **`livespec-dev-tooling`**)
hard-codes three marketplaces and `livespec-overseer` is not one of them, so
`~/.codex/config.toml` has no entry for it. Codex enablement is **host-wide**,
not per-repo, so the twelve-repo Claude-side registration has no analogue here.

**Problem 2 — a plugin rollout BREAKS already-running Codex sessions.** Codex
pins hook entrypoints to absolute versioned paths for the process lifetime;
`codex plugin marketplace upgrade` prunes the old versioned dir; our
`ensure-codex-plugins` runs that upgrade at session start. **Starting a new
session deletes the directory a running session is still using.**

## Goals, each with its LIVE acceptance

**The acceptance for BOTH is live testing. Config inspection is not evidence.**
That is not a style preference — it is the mistake the predecessor thread
already made once and recorded as **"REGISTRATION IS NOT INSTALLATION"**: twelve
merged `settings.json` entries while `installed_plugins.json` held zero keys.
The maintainer caught it. Its Codex twin is a `config.toml` containing the right
strings while nothing resolves.

| # | goal | owning repo | acceptance — all LIVE |
|---|---|---|---|
| 1 | **Record the scope supersession**, citing brief 17 as the superseding decision. Split by the groom into **A1** (record it; `harnesses.codex` STAYS `exempt`, the false `reason` string is replaced) and **A3** (flip to `supported`, once a surface exists to support) | `livespec-overseer` | **A1:** the supersession names the ruling it overrides (`plan/archive/cutover-and-shipping/research/operator-surface.md`) and lives in `.livespec.jsonc` itself, so it survives an archive prune. `just check` green — sound here ONLY because A1 claims no Codex capability. **A3 carries the live proof**, and must add the repo-local `check-codex-skill-picker` in the same change (see the gate hazard below) |
| 2 | **Make the overseer plugin visible to Codex** — via the derive-from-settings collapse, NOT a fourth hard-coded line | `livespec-dev-tooling` (recipe); `livespec-overseer` (its own declaration) | **`supervise-plan` AND `overseer` RESOLVE and RUN in a real Codex session that is not this repo's.** Budget TWO sessions before calling a negative — first exposure needs one session to provision and a second to see it |
| 3 | **Stop rollouts breaking live sessions** — adopt the `oh-my-codex #3024` policy: materialize new first, keep old versioned dirs by default, never delete during normal setup/update, clean up only via explicit command / TTL / liveness-aware check | **`livespec` core** (host-wide; `livespec-dev-tooling` for the recipe) | **Start a Codex session; roll a real new plugin version through the normal path WHILE IT IS ALIVE; the session still works.** A test with no live session open during the rollout proves nothing |

Goal 1 is a **precondition of goal 2 shipping**, not of goal 2 being worked:
do not ship Codex support while the repo's own declaration says Codex is exempt.
The groom's A1/A3 split is what makes both halves of that sentence true at once
— A1 records the decision immediately, A3 makes the capability claim only once
there is a capability. **The supersession decision itself is settled and is not
reopened by the split.**

### The gate hazard goal 1 walks into — measured, not reasoned

Goal 1's original acceptance was *"Gate-visible: `just check` green with the
amended declaration."* **That green is unreachable as evidence, and the groom
re-cut goal 1 on the strength of it.** Measured against
`livespec_dev_tooling/checks/plugin_resolution.py` on 2026-07-28:

- The check admits exactly two statuses, `supported` and `exempt`. Off-`exempt`
  means `supported`, and `_parse_supported` asserts only that
  `canonical_command` is a **non-empty string**. Any string passes.
- For codex the module installs a **`DelegatedResolutionRunner`**
  (`plugin_resolution.py:263`) returning `available=False` → **SKIP**, delegating
  live proof to a **repo-local `check-codex-skill-picker`**. **This repo has no
  such recipe** — `grep -n codex justfile` returns only `ensure-codex-plugins`.
- `just check` runs at the default `LIVESPEC_E2E_HARNESS=mock`, where the live
  layer never runs at all.

**Green by skip in both modes.** This is the same shape as REGISTRATION IS NOT
INSTALLATION, rebuilt at the gate layer — which is why A3 must ship the
repo-local check alongside the flip, and prove it can go RED by removing the
surface.

### The prerequisite nobody in this chain had named

**This repo ships no Codex surface at all.** `.claude-plugin/` exists; there is
**no `.codex-plugin/` anywhere in the repo**. Nothing exists for Codex to
resolve even once a marketplace entry is registered, so goal 2's live acceptance
is unreachable until **A2** lands. `_plugin_structure_codex.py` does not
generalize to this repo — it is hard-wired to marketplace `livespec-driver-codex`,
plugin `livespec`, and an eight-operation `EXPECTED_SKILLS` set.

## Ownership — name it per child, never silently absorb

| what | owner |
|---|---|
| the SHARED codex derive-from-settings module (**B1**) | **`livespec-dev-tooling`** |
| **each governed repo's OWN `ensure-codex-plugins` recipe body** (this repo's is `justfile:127-142`; **B2**) | **that repo** — for us, **`livespec-overseer`** |
| the live-session rollout policy (host-wide: also hits `livespec`, `livespec-driver-codex`, `livespec-orchestrator-beads-fabro`) | **`livespec` core**, where epic `livespec-c1k9` lived |
| `.livespec.jsonc` supersession + this repo's own acceptance | **`livespec-overseer`** |

The recipe row was split on measurement, and the correction matters because it
moves real work INTO this repo: `livespec_dev_tooling/fleet/_rows_local.py:22`
and `justfile:76-78` both state that **"the plugin set is repo-specific, so each
governed repo's recipe stays the single source; a member lacking either recipe
SKIPs that row."** dev-tooling owns building the shared module; it **cannot**
edit our recipe body for us. (`fleet/ensure_plugins.py` — the Claude side —
is already collapsed; there is no codex twin yet.)

Cite `livespec-c1k9.10` and `livespec-c1k9.14` precisely: they solved *becoming
current at session start*. They did **NOT** address *not breaking a live
session*. This thread is the second half of that story.

Prior art for goal 2's shape: **`livespec-c1k9.11`** (CLOSED) — *"Collapse fleet
ensure-plugins recipes to the shared derive-from-settings"*.

## Sequencing — independent, parallel; two couplings, NEITHER a block

- Problem 1 **enlarges** problem 2's blast radius: one more plugin whose rollout
  can break live sessions, and **this repo publishes releases several times a
  day**.
- Problem 2's fix makes problem 1's acceptance **cleaner**: testing problem 1
  means rolling a version, which is exactly what triggers problem 2.

Record both; serialize neither.

## NEXT ACTION — dispatch A1, and ONLY A1

`/livespec-orchestrator-beads-fabro:groom overseer-az5nps` ran on 2026-07-28 and
the maintainer approved the cut as drafted, all six slices unchanged. Approving
the CUT was a separate act from opening ADMISSION; the maintainer then opened
admission **for A1 alone**.

**The next concrete action is to dispatch A1 through the factory route:**

```
/livespec-orchestrator-beads-fabro:drive --action impl:overseer-4km4mj
```

That is a deliberate act for the maintainer or the supervisor to trigger. **A
planning or grooming session must not hand-build it**, and must not dispatch A2,
B2 or A3 — they remain held at `admission:manual`, and opening any of them is a
maintainer decision, recorded, not an incidental side effect.

The groom accepted the proposed first slice's *intent* and **re-cut its shape and
ordering**: goal 1 became **A1** (record the supersession, keep `exempt`) plus
**A3** (flip to `supported`, gated behind a surface that resolves and a check
that can go red). The re-cut was driven by the measured gate hazard above — the
original acceptance would have gone green while proving nothing. **The
supersession decision itself was never in question and is not reopened.**

Two things a cold-open reader should carry into that moment:

- **A1's acceptance is deliberately NOT a live Codex exercise.** It records a
  decision and deletes a false `reason` string; it claims no Codex capability.
  Do not let a reviewer demand a live proof it was never scoped to give — that
  proof belongs to **A3**, which is still held.
- **B1 and C1 are FILED, and not in this tenant.** B1 is
  `livespec-dev-tooling-3nt9` (`livespec-dev-tooling`); C1 is `livespec-1p31`
  (`livespec` core). Both at `backlog`. Their groom-minted ids
  (`overseer-llz4xi`, `overseer-qfnjj6`) are DEAD and must not be used to look
  them up — see the boxed warning near the top.
- **B2 cannot honestly complete before B1 does**, and its dependency pointer is
  still dangling pending the one-command repair.

## Why this thread's supervisor charter needed a workaround — a `supervise-plan` DEFECT, not an omission

**The charter now exists** — `supervisor-handoff.md`, generated 2026-07-28 02:06.
**It could not be generated at thread creation**, and the record below is kept as
the defect evidence, not as a description of the current state. The workaround
was to start the two tmux sessions FIRST and then run the skill, which satisfies
the gate honestly rather than by fabrication; the defect stands for the next
thread, and is filed as **`overseer-2a1`**.

Brief 17 directed that `plan/codex-parity-and-rollout-safety/supervisor-handoff.md`
be generated by `/livespec-overseer:supervise-plan`. At thread creation it could
not be, **and the skill was behaving exactly as its own contract specifies.**

`supervise-plan` opens with five HALT-first preconditions. Precondition 1:

```bash
tmux has-session -t "codex-parity-and-rollout-safety"
```

Run 2026-07-28 at thread creation: `can't find session:
codex-parity-and-rollout-safety`.
Precondition 3 (`…-supervisor`) failed identically. The contract then says:
*"Stop on the first failure… **Do not create a missing session**, do not fall
back to another session, and do not proceed read-only."* So the run halted and
no session was fabricated to satisfy the check — manufacturing state to pass a
HALT gate is the "never REMOVE, WEAKEN, or SKIP an existing check" boundary in
the skill's own vetting rubric.

**The defect is an ORDERING assumption.** Preconditions 1, 2, 3 and 5 all
require a live supervised session already working the topic — precondition 2
demands a live `claude`/`codex` process in its pane, and 5 demands that pane's
cwd resolve inside the target repo. Every one of those is satisfiable only
*after* work has started. But a supervisor charter is most useful **before** the
first session opens: that is the whole point of a durable charter. **As shipped,
`supervise-plan` cannot bootstrap a charter for a newly created thread.**

This is not a wording or thinness problem in generated output — nothing was
generated on the first attempt. It is a gap in when the operation is usable, and it belongs to
**`overseer-7lv`** ("supervise-plan residual gaps: supervisor runtime liveness
and obligations", now `plan/archive/supervise-plan-residual-gaps/` — that epic
was closed 2026-07-27, folded into `overseer-byvxlp`'s groom), with the
generated-text
quality bar owned by **`overseer-byvxlp`**. Filed as **`overseer-2a1`**.

**How the charter was obtained here, and how to repeat it on the next thread:**
start the
supervised and supervisor tmux sessions for the topic in the normal way, with
the supervised pane's cwd inside `/data/projects/livespec-overseer` and a live
agent driver in it, then re-run `/livespec-overseer:supervise-plan`. All five
preconditions will then be satisfiable and the skill will generate the charter
through the repo's reviewed worktree → PR → merge path. **Do not hand-write the
file** — a hand-written charter is exactly the evidence-free artifact the
generated-charter contract test exists to prevent.

## Hazards carried in from the predecessor thread

- **A lag/timing bound is not evidence of a negative.** `overseer-ye5` records
  that this fleet's scheduled-run ceiling was broken four times (+86 → +124 →
  +187 → +231 min). Goal 2's "two sessions before calling a negative" is the
  same lesson in a different clothing: a not-yet-visible plugin is not an
  absent one.
- **Read the forge, not the local checkout.** Also `overseer-ye5`: local adopter
  checkouts went stale on every bump and reading them called a working lane
  broken.
- **`bd create --parent` files children at beads-native `open`**, which is not a
  livespec `WorkItemStatus`, so `next`/`drive` rank zero of them. Any
  hierarchical child **hand-filed** must be created with `--no-inherit-labels`,
  then explicitly set to a real status and read back.
  **Scope correction, measured 2026-07-28: this hazard does NOT fire on the
  `groom` route.** `file_approved_slices` files each slice at
  `status="pending-approval"` — a real `WorkItemStatus` — and then routes it
  through the intake Definition-of-Ready primitive. The trap is specific to
  hand-filing. **The read-back-after-filing discipline still applies to both
  routes**, and it earned its keep here: the read-back is what revealed that the
  DoR router does not leave every slice where it was filed (A1 and A2 came out at
  `ready`, not `pending-approval`).
  **Both halves are now confirmed by measurement.** Hand-filing `bd-ib-rhv0` and
  `bd-ib-ah2r` into the `livespec-orchestrator-beads-fabro` tenant on 2026-07-28
  landed BOTH at `Status: open`, exactly as the hazard predicts. So the trap is
  real on the hand-filing route and absent on the groom route — and knowing which
  route you are on is what tells you whether the discipline is required.

## A2 BUILD SPEC — carried in from scratch, which does not survive the restart

The ledger item `overseer-vyie5q` carries the trimmed description (1953 chars);
this is the fuller working spec behind it. **The convention itself is recorded
durably in `.claude/CLAUDE.md` §"The Codex plugin surface is NESTED inside
`.claude-plugin/`" — read it there and do NOT re-derive it.**

Three files, into the EXISTING `.claude-plugin/`:

1. `.claude-plugin/.codex-plugin/plugin.json` — mirror the sibling
   `.claude-plugin/plugin.json` `name`/`version`/`description` verbatim, plus
   `"skills": "./.codex-plugin/skills/"`. READ the version at implementation
   time (lockstep); never hard-code it. (`livespec` core's nested manifest has
   NO `skills` key because it ships no skills — the key tracks reality.)
2. `.claude-plugin/.codex-plugin/skills/overseer/SKILL.md`
3. `.claude-plugin/.codex-plugin/skills/supervise-plan/SKILL.md`

Bindings: frontmatter `name` + `description` ONLY — **no `allowed-tools`**; both
Claude siblings carry it and it must not be copied. Description ends
`Invoked as livespec-overseer:<op>.` Body resolves `$PLUGIN_ROOT` explicitly
(env `LIVESPEC_OVERSEER_PLUGIN_ROOT` → validated `./.claude-plugin` under cwd →
newest cache root under `$HOME/.codex/plugins/cache/livespec-overseer/livespec-overseer/` →
`codex plugin list --json -m livespec-overseer`), then reads
`$PLUGIN_ROOT/prose/<op>.md`. Mirror
`livespec-orchestrator-beads-fabro/.claude-plugin/.codex-plugin/skills/next/SKILL.md`.

**ADAPTATION TRAP:** that reference uses `./.claude-plugin/scripts/bin` as its
marker AND final guard. **This repo has no `scripts/` dir**, so that guard can
never pass. Use `prose` — `./.claude-plugin/prose` for the candidate test and
`$PLUGIN_ROOT/prose/<op>.md` for the final guard (op-specific is strictly
stronger and free). `marketplace.json` needs NO change: its `source` is already
`./.claude-plugin`.

### A2's live acceptance — and a finding that caps what it can claim

Bar: **`supervise-plan` AND `overseer` RESOLVE and RUN in a real Codex session
that is NOT this repo's** (use `/data/projects/livespec-dev-tooling`), marketplace
hand-added as an **explicitly declared test fixture**
(`codex plugin marketplace add thewoolleyman/livespec-overseer --ref release`;
`codex plugin add livespec-overseer@livespec-overseer`). A `~/.codex/config.toml`
carrying the right strings is **NOT** evidence. **Budget TWO sessions before
calling a negative.**

**`prose/overseer.md:176-181` verifies `$CLAUDECODE` and REFUSES when unset**,
and step 3 reads Claude Code's own session registry. So under Codex the honest
maximum for `overseer` is: resolves, binding executes, prose is read, then it
emits its documented refusal. **That refusal is a working check — never disable
it to make an acceptance pass.** `supervise-plan` has no such coupling and can
run to a real precondition verdict. Do not conflate the two, and do not redefine
the bar after seeing a result.

*(Nuance: A1 replaced the old `.livespec.jsonc` exemption reason because the
SCOPE decision changed, not because that reason was factually wrong. "The
overseer's interactive pane is driven from Claude Code" still describes this
coupling accurately.)*

Pre-declared FALSE NEGATIVES to exclude before calling A2 failed: (1) checked in
the provisioning session only — open a SECOND session; (2) the released ref does
not yet contain `.codex-plugin/`, in which case the honest report is **"unproven
pending release"**, not "failed"; (3) a stale pinned plugin cache — confirm the
resolved `source.path` matches the version just installed.

### A3's bar, carried forward

A3 must demonstrate its new repo-local `check-codex-skill-picker` **RED** —
remove the surface, show it FAILS. The reference recipe
(`livespec-orchestrator-beads-fabro/justfile:1110`) **self-skips** when
`CI=true` without `LIVESPEC_REQUIRE_CODEX_TUI_PICKER=1` and when the codex CLI is
absent, so a "red" under either condition proves nothing. **Run it locally with
codex PRESENT.** F1 stands: `plugin_resolution.py` routes codex to a
`DelegatedResolutionRunner` → SKIP, and `just check` at the default `mock`
harness asserts only that `canonical_command` is a non-empty string — so flipping
to `supported` without a working repo-local check is green-by-skip in BOTH modes.
