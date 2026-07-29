# Plan — fabro-review-classifier-defect

**Owning repo:** `livespec-overseer` (the thread lives here; the CODE lives in
`/data/projects/fabro`). **Ledger anchor:** epic **`overseer-dtytju`**.
**Status: OPEN — investigation not started.**

Created 2026-07-29 from `plan/codex-parity-and-rollout-safety/`, whose slice A2
(`overseer-vyie5q`) died twice at the `review` stage before this was found.

## Read-first chain

1. This file.
2. `research/misclassification-evidence.md` — what was MEASURED, what is
   RETRACTED, and the five open questions.

That is the whole chain. Status is READ from the ledger, never stored here: run
`/livespec-orchestrator-beads-fabro:list-work-items --json` and
`/livespec-orchestrator-beads-fabro:next`. This file carries no checkbox queue.

## The problem in one paragraph

fabro's error classifier labels an **Anthropic org monthly spend-limit** failure
as **`transient_infra`**, on a false positive: the string `index.crates.io` in
the error payload matches a **source path**, not a network fault. So a
permanent, human-actionable failure is retried as if transient — each retry
burning a host dispatch cap slot (cap **2**) plus a full `ImplementWorkItem` run
before dying in ~5s — while masking the true cause from the operator.

**Confirmed twice.** `fabro inspect` →
`node_outcomes.review.failure.causes[1]` names the spend limit; and A2 went
`active` on its very next dispatch once the maintainer raised it. Fleet-wide at
the time: 5 runs, 2 repos, 4 work-items.

## Do NOT re-derive these

- **`fabro logs` will not show you the cause.** It carries only a generic
  `error="ACP turn failed"`. The structured causes are in **`fabro inspect`**.
  A logs-only reading already led one reader to call the diagnosis unverified.
- **The `bd-ib-2nq` >60-minute token-TTL theory is RETRACTED and disproven** —
  review fails in ~5s regardless of run length. The adjacent
  `code="github_token_refresh_limited"` notice is a red herring here.
- **`error.rs:44/:85/:159` is an UNVERIFIED pointer.** Confirm it; do not cite
  it as established.

## Where the code is

| | |
|---|---|
| local clone | `/data/projects/fabro` |
| `origin` | `thewoolleyman/fabro` — the maintainer's fork. **Issues DISABLED** |
| `upstream` | `fabro-sh/fabro` — public, issues enabled |
| classifier vs upstream | **byte-identical** — the defect originates upstream |

## NEXT ACTION

**Investigate first — do not open with a fix.** The five open questions are in
`research/misclassification-evidence.md`; question 1 (is the
`index.crates.io` false positive real, and exactly where) gates the rest.

Implementation of any ledger-backed slice goes through the **factory dispatch
route** — `/livespec-orchestrator-beads-fabro:drive --action impl:<id>`, or the
Dispatcher drain. Do **not** hand-build slices in the planning session.

Epic `overseer-dtytju` is **not yet groomed**. When the investigation has
established what the fix is, run
`/livespec-orchestrator-beads-fabro:groom overseer-dtytju` to cut it into ready,
dependency-layered slices before any implementation.

## Acceptance

- A **RED demonstration first**: a test that fails against today's classifier
  because a spend-limit payload is labelled `transient_infra`.
- A fix that goes green **without weakening any existing classification**.
- Landed on a **branch in `/data/projects/fabro`**, in preparation for a PR.

**Opening the PR to `fabro-sh/fabro` is the MAINTAINER'S call** — it is
outward-facing onto a third party's public project. Prepare the branch; do not
open the PR unprompted. Filing an upstream issue was deliberately **held** for
the same reason: this investigation exists so any report is evidence-backed
rather than a guess.

## Hazards carried in

- **The host dispatch cap is 2**, host-global, and reads live Fabro *processes*
  (`fabro ps`) plus per-slot lock files — **not** ledger status. Use the
  RESOLVED binary `/home/ubuntu/.local/bin/fabro`; a bare `fabro` does not
  resolve under the credential wrapper and silently reports nothing, making a
  full cap look empty.
- **Hand-filing into the ledger:** `bd create` has no `--status` flag, so a
  hand-filed item lands at beads-native `open` — which is not a livespec
  `WorkItemStatus`, so `next`/`drive` rank zero of them. File with
  `--no-inherit-labels`, set a real status explicitly, then READ BACK.
