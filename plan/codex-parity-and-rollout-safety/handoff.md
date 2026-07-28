# Plan — codex-parity-and-rollout-safety

**Owning repo:** `livespec-overseer`. **Status: GROOMED 2026-07-28 — six slices
cut and filed, nothing built, nothing in flight. The admission valve is a
SEPARATE valve and it is NOT open.**

**Ledger anchor: the epic `overseer-az5nps` is CLOSED.** `groom` regroomed it
out on 2026-07-28 — that is the operation's normal disposition, not a loss, and
the maintainer ruled to accept it. The anchor is now the filed slice set below.

### The filed slice set — READ THIS BEFORE THE LEDGER

The closed epic's forwarding reason names **only the four local slices**, because
`groom` files cross-repo slices into their own repo's tenant rather than this
one. **The two cross-repo ids exist nowhere else in this repository's record, so
they are written down here or they are lost.** That erasure is the burial failure
this thread was created to prevent.

| slice | id | owning repo | blocked by |
|---|---|---|---|
| **A1** — record the codex scope supersession in `.livespec.jsonc` without asserting a capability that does not yet exist | `overseer-4km4mj` | `livespec-overseer` | — |
| **A2** — ship the `.codex-plugin/` surface for `overseer` and `supervise-plan` | `overseer-vyie5q` | `livespec-overseer` | — |
| **B1** — build the shared codex derive-from-settings module (the `fleet/ensure_plugins.py` twin) | **`overseer-llz4xi`** | **`livespec-dev-tooling`** — minted here, **NOT filed in this tenant** | — |
| **B2** — replace this repo's hard-coded `ensure-codex-plugins` body with the shared delegation | `overseer-vfz5v5` | `livespec-overseer` | **B1** (`sibling_work_item`), A2 |
| **A3** — flip `harnesses.codex` to `supported`, with a repo-local check that makes the green load-bearing | `overseer-kju6wh` | `livespec-overseer` | A1, A2 |
| **C1** — adopt the `oh-my-codex #3024` live-session rollout policy | **`overseer-qfnjj6`** | **`livespec`** core — minted here, **NOT filed in this tenant** | — |

B2's cross-repo blocker is not visible to `bd dep tree`, which walks local edges
only. It is recorded on B2 as
`non_local_depends_on: [{"kind":"sibling_work_item","repo":"livespec-dev-tooling","work_item_id":"overseer-llz4xi"}]`.

**Observed status at filing, which is NOT uniform:** A1 and A2 came out of the
intake Definition-of-Ready router at **`ready`**; B2 and A3 at
**`pending-approval`**. All four carry `admission:auto`. `next` ranks A1 first
and A2 third of all implementable work in this tenant. Nothing here opens the
admission valve — but do not assume these slices are parked.

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

## NEXT ACTION — the groom is DONE; the admission valve is NOT open

`/livespec-orchestrator-beads-fabro:groom overseer-az5nps` ran on 2026-07-28 and
the maintainer approved the cut as drafted, all six slices unchanged. **The
maintainer approved THE CUT, not implementation.** The admission valve is a
separate valve and it has not been opened.

The groom accepted the proposed first slice's *intent* and **re-cut its shape and
ordering**: goal 1 became **A1** (record the supersession, keep `exempt`) plus
**A3** (flip to `supported`, gated behind a surface that resolves and a check
that can go red). The re-cut was driven by the measured gate hazard above — the
original acceptance would have gone green while proving nothing. **The
supersession decision itself was never in question and is not reopened.**

When the valve opens, implementation goes through the **factory dispatch route**
— `/livespec-orchestrator-beads-fabro:drive --action impl:<id>`, or the
Dispatcher drain. Do **not** hand-build slices in a planning session.

Two things a cold-open reader should carry into that moment:

- **A1 and A2 are already at `ready` with `admission:auto`**, and `next` ranks A1
  first in this tenant. They are not parked behind a status.
- **B1 (`overseer-llz4xi`) and C1 (`overseer-qfnjj6`) are not in this tenant.**
  They need filing in `livespec-dev-tooling` and `livespec` respectively, and
  B2 cannot honestly complete before B1 does.

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
