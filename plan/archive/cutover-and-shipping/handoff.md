# Plan — cutover-and-shipping (ARCHIVED)

**Owning repo:** `livespec-overseer`. **Status: CLOSED 2026-07-25.** This thread
is finished and archived. Its ledger anchor, epic `overseer-3wt`, is closed.

**Nothing here is actionable.** This file is a RECORD of what this thread
genuinely completed and — just as importantly — what it did NOT. Every piece of
remaining overseer work lives in the living successor thread
**`plan/ship-overseer-to-fleet/`**, anchored by epic **`overseer-hbr`**.

> **Read this before citing anything below.** This thread's defining lesson is
> that "shipped" was recorded as TRUE while the plugin was in nobody's hands —
> structurally true, functionally false. The successor thread exists because of
> that. Nothing in this file should be read as a claim that the overseer plugin
> is available to anyone.

---

## The honest status of the product

The overseer **DAEMON** is real, proven, and running. The overseer **PLUGIN** is
not shipped. Concretely, as measured on 2026-07-25:

| | state |
|---|---|
| Daemon cutover | **PROVEN** — Stage-4 twice, live |
| Plugin **built** | yes — `.claude-plugin/` ships both skills, and its `marketplace.json` is structurally identical to all four working fleet peers |
| Plugin **fleet-released** | **NO** — zero git tags, zero GitHub releases |
| Plugin **installed** | **NO** — installed in ZERO projects; absent from `known_marketplaces.json` |
| Plugin **e2e-tested** | **NO** — zero top-of-pyramid tests; all 54 `tests/heading-coverage.json` rows are `TODO`, and the gate that would fail on them is UNARMED |
| `supervise-plan` **works** | **NOT ESTABLISHED.** It is BUILT. It was never demonstrated in a session outside this repo, and was reported ABSENT in another live fleet session. |

**Do not write or repeat any claim that `supervise-plan` "works".** That is
goal 1 of the successor thread, and it is not done.

---

## What this thread GENUINELY completed

- **Daemon cutover PROVEN** — Stage-4 reached twice on two separate tracks
  (declare-ready → atomic restart; and daemon-injected wrap-up → ready →
  restart).
- **`SPECIFICATION/history/v002` ratified** (PR #73) — the attended-skill
  carve-out plus the bounded existence-only probe allowance. doctor-static 21/21.
- **Supervision surfaces A+B shipped** (`overseer-6uobos`, PR #74 + review fix
  PR #75) and live-exercised: `02-parameter-store-bootstrap` hit the fourth
  truth-table cell (live supervisor session, no `supervisor-handoff.md`) and
  correctly surfaced the capture offer.
- **PR #75 fixed a sabotage test that could not fail** — proven toothless by
  mutation, then red-then-green. This produced the thread's most durable lesson:
  **a verifier must be able to fail.**
- **Acting daemon restarted onto latest master** — single instance, 12/12
  watch-set, header `0.11.0`. `overseer-2boaoy`'s append live-exercised
  mechanically: fd2 flags `0100001` → `0102001` (O_APPEND set), prior 80 log
  lines byte-identical underneath.
- **Rollback retired** by maintainer decision after Stage-4 was proven twice
  (commit `19ddac7`).
- **13 items accepted and closed** — verified individually on 2026-07-25, all 13
  genuinely `CLOSED`: `overseer-m5dtmj`, `overseer-tn3hmi`, `overseer-myjovi`
  (`supervise-plan` **BUILT — not fleet-available**), `overseer-vlu5cd`,
  `overseer-kfbcv4`, `overseer-2boaoy`, `overseer-5aaeyd`, `overseer-6uobos`,
  `overseer-3o9`, `overseer-y8o`, `overseer-4dr`, `overseer-zvo`,
  `overseer-tvko3z`.
- **Slice 4 needed NO filing** — both upstream targets already carried the
  ratified "hosted supervision artifact" declaration (livespec core **v175**,
  livespec-orchestrator-beads-fabro **v048**).
- **The successor thread was opened BEFORE this one archived** (PR #78, merged
  2026-07-25), so no incomplete work was ever buried by the archive. That
  ordering was the maintainer's explicit instruction (supervisor brief 22).

### PR #78's dual adversarial review — the gate that produced the successor's DoD

Brief 22 required TWO independent fresh-context adversarial reviews before #78
could merge. Both ran, on different vendors, and both found real defects:

- **Codex GPT-5.6 (OpenAI leg)** — `VERDICT: BLOCK`. One blocker (the six goals
  did not cover acknowledged residue) and three majors (a wrong `source_repo`
  breaking the release path; a `git mv` that orphaned a live reference; three
  non-executable tmux commands in the new charter). All addressed.
- **Fable (Anthropic leg)** — `VERDICT: MERGE WITH FIXES`. Four minors, including
  a payload miscount and a mislabelled provenance claim in a Corrections log.
  All addressed. It independently re-executed the successor thread's sabotage
  evidence rather than trusting it.

The review is worth recording because it worked: a single pass had previously
missed a false "shipped" claim, and requiring two caught defects neither found
alone.

---

## What this thread did NOT do — and where that work went

The plugin is **BUILT but FUNCTIONALLY UNSHIPPED**, the specification is
**UNVERIFIED at the top of the pyramid**, and release automation is **PARTIAL**.

All of it, plus Phase-2 adopter-family shipping, was handed to
**`plan/ship-overseer-to-fleet/`** (epic **`overseer-hbr`**) as a six-goal
definition of done: fleet-wide `supervise-plan` availability; top-of-pyramid e2e
tests for every scenario WITH the rule enforced; auto-release; auto-install;
auto-pin-bump; and Phase-2 shipping absorbed into those.

**Phase-2 / productization is explicitly OUT OF SCOPE of this thread.** Its
former anchor `overseer-19s` is closed as *superseded* — not delivered — so
there is exactly one anchor.

Known open work, all anchored in the successor thread's ledger children:

| item | what |
|---|---|
| `overseer-fitvmo` | `supervise-plan` prompts must not stall on conflict boundaries — a PRECONDITION of goal 1 |
| `overseer-hbr.1` | `release-dispatch.yml` announces this repo as `livespec-runtime`; orphaned release PR #21 |
| `overseer-hbr.2` | the 7 untied v002 gaps + `livespec-b1uo{,.1–.5}` dispositions |
| `overseer-hbr.3` | the orphaned `operator-surface.md` reference and its live Codex-exemption ruling |
| `overseer-hbr.4` | non-executable tmux commands in a supervisor handoff |
| `overseer-hbr.5` | `registry.py` docstring citing a removed function |
| `overseer-hbr.6` | **this epic's own items 3 and 5** — Gate E's 705 latent findings, and the deferred entry-point surface |
| `overseer-hbr.7` | `.claude/CLAUDE.md`'s CAUTION block is stale on both counts |
| `overseer-hbr.8` | goal 4's fleet-registration precondition `livespec-cbmw` (core tenant) |

`overseer-hbr.6` matters most to this file: **epic `overseer-3wt` listed SIX
numbered payload items, and items 3 and 5 were still open when it closed.** They
were NOT dropped — they were durably re-anchored under `overseer-hbr.6` FIRST,
which is why closing this epic did not bury them. Item 6 (Phase-2 shipping) is
goal 6 of the successor thread; items 1, 2 and 4 were genuinely delivered.

Also open and owned ELSEWHERE, deliberately not absorbed here:
`check-no-workflow-edits` copy-drift across the 4 carrying fleet repos, which is
`livespec-dev-tooling`'s call.

---

## Operational map (true at archive time)

The acting daemon runs in tmux `livespec-overseer:1.1` (pid 2954933 at archive
time), stderr log `tmp/overseer/daemon.log` (appends). **It is the shipped
product supervising the whole live fleet — never part of any one session, and
never to be killed as part of session cleanup.**

Protocol: `overseer/marker-protocol.md`. Invariants: `overseer/AGENTS.md`.
Operator contract: `overseer/SKILL.md`. This thread's supervisor charter:
`supervisor-handoff.md` beside this file.

Research beside this file: `research/operator-surface.md` — **still LIVE**; it
carries the settled "Codex stays exempt" ruling the successor thread depends on
(see `overseer-hbr.3`) — and
`research/slice4-upstream-one-liners-and-unit3-home.md`, whose Packet A/B
sections are SUPERSEDED because slice 4 needed no filing.
`research/phase-2-adopter-shipping.md` moved to the successor thread by `git mv`
and is no longer here.

Cross-track coordination log (shared, still active — append only, never
rewrite): livespec core `tmp/fleet-pin-propagation-supervisor/status.log`.
