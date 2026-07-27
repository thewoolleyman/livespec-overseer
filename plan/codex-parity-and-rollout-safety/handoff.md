# Plan — codex-parity-and-rollout-safety

**Owning repo:** `livespec-overseer`. **Ledger anchor:** epic
**`overseer-az5nps`** (this repo's beads tenant). **Status: OPEN — nothing
built, nothing in flight. The next action is to GROOM, not to build.**

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

That is the whole chain. **There is deliberately no `supervisor-handoff.md` in
this thread yet** — see §"Why this thread has no supervisor charter". Do not
cite one until it exists.

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
| 1 | **Record the scope supersession** — amend `.livespec.jsonc`'s `harnesses.codex.status` off `exempt`, citing brief 17 as the superseding decision | `livespec-overseer` | The declaration no longer contradicts the shipped behavior, and the supersession names the ruling it overrides (`plan/archive/cutover-and-shipping/research/operator-surface.md`). Gate-visible: `just check` green with the amended declaration |
| 2 | **Make the overseer plugin visible to Codex** — via the derive-from-settings collapse, NOT a fourth hard-coded line | `livespec-dev-tooling` (recipe); `livespec-overseer` (its own declaration) | **`supervise-plan` AND `overseer` RESOLVE and RUN in a real Codex session that is not this repo's.** Budget TWO sessions before calling a negative — first exposure needs one session to provision and a second to see it |
| 3 | **Stop rollouts breaking live sessions** — adopt the `oh-my-codex #3024` policy: materialize new first, keep old versioned dirs by default, never delete during normal setup/update, clean up only via explicit command / TTL / liveness-aware check | **`livespec` core** (host-wide; `livespec-dev-tooling` for the recipe) | **Start a Codex session; roll a real new plugin version through the normal path WHILE IT IS ALIVE; the session still works.** A test with no live session open during the rollout proves nothing |

Goal 1 is a **precondition of goal 2 shipping**, not of goal 2 being worked:
do not ship Codex support while the repo's own declaration says Codex is exempt.

## Ownership — name it per child, never silently absorb

| what | owner |
|---|---|
| the `ensure-codex-plugins` recipe | **`livespec-dev-tooling`** |
| the live-session rollout policy (host-wide: also hits `livespec`, `livespec-driver-codex`, `livespec-orchestrator-beads-fabro`) | **`livespec` core**, where epic `livespec-c1k9` lived |
| `.livespec.jsonc` supersession + this repo's own acceptance | **`livespec-overseer`** |

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

## NEXT ACTION — groom, do not build

**The maintainer's directive is explicit: the plan is to RUN, the work is NOT to
start.** Nothing in this thread may be implemented until it has been groomed
into ready, dependency-layered slices and the maintainer opens the admission
valve.

Run: **`/livespec-orchestrator-beads-fabro:groom overseer-az5nps`**

**Proposed first slice, for the groom to accept or re-cut: goal 1 — the
`.livespec.jsonc` supersession.** It is the smallest coherent unit, it is
owned entirely by this repo (no cross-repo dependency), it is a precondition of
goal 2 shipping, and it removes a live self-contradiction in the repo's own
declaration. It needs no live Codex session, so it cannot be blocked by the
very rollout hazard goal 3 exists to fix.

When slices are ready, implementation goes through the **factory dispatch
route** — `/livespec-orchestrator-beads-fabro:drive --action impl:<id>`, or the
Dispatcher drain. Do **not** hand-build slices in the planning session.

## Why this thread has no supervisor charter — a `supervise-plan` DEFECT, not an omission

Brief 17 directed that `plan/codex-parity-and-rollout-safety/supervisor-handoff.md`
be generated by `/livespec-overseer:supervise-plan`. **It could not be, and the
skill is behaving exactly as its own contract specifies.**

`supervise-plan` opens with five HALT-first preconditions. Precondition 1:

```bash
tmux has-session -t "codex-parity-and-rollout-safety"
```

Run 2026-07-28: `can't find session: codex-parity-and-rollout-safety`.
Precondition 3 (`…-supervisor`) fails identically. The contract then says:
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
generated. It is a gap in when the operation is usable, and it belongs to
**`overseer-7lv`** ("supervise-plan residual gaps: supervisor runtime liveness
and obligations", `plan/supervise-plan-residual-gaps/`), with the generated-text
quality bar owned by **`overseer-byvxlp`**. Filed as **`overseer-2a1`**.

**How to get a charter for this thread when one is wanted:** start the
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
  hierarchical child filed for this epic must be created with
  `--no-inherit-labels`, then explicitly set to a real status and read back.
