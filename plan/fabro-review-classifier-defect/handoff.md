# Plan — fabro-review-classifier-defect

**Owning repo:** `livespec-overseer` (the thread lives here; the CODE lives in
`/data/projects/fabro`). **Ledger anchor:** epic **`overseer-dtytju`**.
**Status: INVESTIGATION COMPLETE 2026-07-29; fabro work HANDED OFF
2026-07-30.** All five open questions answered; a RED-then-green fix is
prepared on an **unpushed branch** in `/data/projects/fabro`. **Nothing is
pushed and no upstream PR or issue exists.** The publication question has been
**answered and superseded** — the maintainer routed it to a **Codex session**,
which now owns the fabro-side work; see NEXT ACTION. **This thread must not
touch `/data/projects/fabro`**; its remaining work is record hygiene here.

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

> **The paragraph above overstates one thing, and the fix does NOT close it.**
> "Each retry burning a host dispatch cap slot" is real, but the
> misclassification does **not** cause it. `Error::is_retryable()`
> (`error.rs:494-497` — **branch** coordinates; `:441` on base `d5dcd1179`)
> returns `true` for `Handler`/`Engine`/`Io` **unconditionally** — it never
> consults `FailureCategory`. So relabelling the failure does **not** stop the
> two per-stage attempts or the cap-slot burn.
>
> **What the fix does buy** is the label itself: what the operator sees, the
> `context.failure_class` edge conditions, and whether `loop_restart` edges
> unlock (they require `transient_infra`, so post-fix they are **blocked**) —
> a loop-level reduction only, never a per-stage one.
>
> **Correction to an earlier version of this paragraph**, which claimed the fix
> also changes "what the failure-signature circuit breaker is fed". **It does
> not.** `is_signature_tracked()` covers only `Deterministic | Structural`, so
> the failure was untracked as `TransientInfra` and stays untracked as
> `BudgetExhausted`. Correct for a billing cause, but **not a change** — and it
> is precisely why part (a) of the fix exists, since `Deterministic` *is*
> tracked.
> **Do not read "classifier fixed" as "retry waste fixed".**
>
> **And do not read the residual as one thing.** Measured 2026-07-30, it is
> **two independent layers**, and an earlier version of this file named the
> wrong one:
>
> - **fabro's per-stage retry** (`is_retryable()`) — third party, **possibly
>   deliberate** (opaque `Handler`/`Engine` string errors are defensibly
>   retried), **deliberately NOT filed**.
> - **the orchestrator's re-dispatch of the work-item** — **this is the layer
>   that burns the cap slots**, it is **in-house**, and it is filed as
>   **`overseer-fs4`** (bug, P2). Nothing in
>   `livespec-orchestrator-beads-fabro` consumes a run's failure category at
>   all: zero hits repo-wide across 2685 `.py` files, against a passing
>   positive control.
>
> So the cap-slot burn quoted above is the **orchestrator's**, not fabro's, and
> making `is_retryable()` category-aware would not fix it.

## Do NOT re-derive these

- **`fabro logs` will not show you the cause.** It carries only a generic
  `error="ACP turn failed"`. The structured causes are in **`fabro inspect`**.
  A logs-only reading already led one reader to call the diagnosis unverified.
- **The `bd-ib-2nq` >60-minute token-TTL theory is RETRACTED and disproven** —
  review fails in ~5s regardless of run length. The adjacent
  `code="github_token_refresh_limited"` notice is a red herring here.
- **`error.rs:44/:85/:159` is RESOLVED — no longer a pointer.** The classifier
  is `lib/crates/fabro-workflow/src/error.rs`: `"index.crates.io"` at `:75` in
  `TRANSIENT_INFRA_HINTS`, matched by `classify_failure_reason` at `:160`. The
  old pointer named the **right file** (those are the three hint-list decl
  lines); it lacked only the crate. See the note for the full table.
  **These are BASE `d5dcd1179` coordinates.** They shift on the fix branch,
  where the same items sit at `:54` / `:85` / `:205` — on the branch, `:75` is
  `"try again"`, so an unlabelled number sends a reader to the wrong line.

## Where the code is

| | |
|---|---|
| local clone | `/data/projects/fabro` |
| `origin` | `thewoolleyman/fabro` — the maintainer's fork. **Issues DISABLED** |
| `upstream` | `fabro-sh/fabro` — public, issues enabled |
| classifier vs upstream | **NOT byte-identical** — the old claim was a vacuous check, see below. The **defect** is nevertheless present upstream unchanged |
| branch base | local `d5dcd1179` (**2026-07-09**) vs `upstream/main` `854f71f2c` (**2026-07-29**) — 357 differing lines in this very file |

**CORRECTION — "byte-identical" was never measured.** Upstream relocated
`lib/crates/` → `lib/components/`, so the `git diff upstream/main -- <path>`
that produced it compared a path **absent upstream**; empty output there proves
nothing. The **conclusion survives** on a real comparison against upstream's own
file (hint at upstream `:79`, same first-wins order, same pinned test) — the
**evidence originally cited for it did not**.

**Upstream port, measured.** 5 of 6 hunks apply to
`upstream/main:lib/components/fabro-workflow/src/error.rs`. **Hunk 3 conflicts**
— and the reason is the interesting part: upstream has **independently adopted
this fix's own idiom**, pre-masking payload text that is not fault text (it
masks hex SHAs because one "contains 500 or 503 often enough to matter"). That
near-miss also caught a **green-but-wrong** hazard: upstream masks hex
**first**, so a strict `[0-9a-f]+` hash pattern would have seen
`index.crates.io-<masked>` and **silently no-op'd with every test still
passing**. The regex was loosened and a test now pins the masked form.

**No silent rebase.** The RED demonstration stands on its original base
`d5dcd1179`, and the branch targets that base.

## NEXT ACTION — the fabro work belongs to ANOTHER SESSION

**The publication question has been answered and superseded.** It was neither
"push" nor "file": the maintainer routed it to a **Codex session**, which now
owns the fabro-side work. That session is writing the **PR description** and
running **adversarial review** on it — an Opus 5 sub-agent and a Codex Sol
sub-agent, briefed to look for what is wrong rather than to bless it — against
the handoff prompt at
`/data/projects/fabro/tmp/codex-handoff-classifier-spend-limit.md`
(`tmp/` is gitignored there, so none of it is a tracked change).

**This thread must not touch `/data/projects/fabro` at all** — not the branch,
not `tmp/`. Its remaining work is record hygiene here in `livespec-overseer`.

Still true, and unchanged by that routing:

- **Nothing is pushed.** The branch is local only; `main` is untouched.
- **No PR and no issue exist** on `fabro-sh/fabro` or `thewoolleyman/fabro`.
  Publication remains the maintainer's call and has still not been given.
- **Whoever takes a yes must re-express hunk 3 against `lib/components/`**
  first — see the port note above.

On credentials: this failure is a limit on **one specific** Anthropic
credential, and which one matters. **Cite `.claude/CLAUDE.md` §"The fleet has
SEVERAL Anthropic credentials"** — do not re-derive it here; that section
exists because two threads re-derived it independently and one got it wrong.

The one piece of *further* code work that is in-house and already filed is
**`overseer-fs4`** — the orchestrator-side re-dispatch gap above. It is **not
yet actionable**: gating on a category only means something once a run's
failure carries a trustworthy one, and the corrected classifier is merged
nowhere. Routing is a maintainer call; it is deliberately **not** groomed.

Any further code work still goes through the **factory dispatch route** —
`/livespec-orchestrator-beads-fabro:drive --action impl:<id>`, or the
Dispatcher drain — never hand-built in a planning session.
Epic `overseer-dtytju` is **not yet groomed**; run
`/livespec-orchestrator-beads-fabro:groom overseer-dtytju` before any such
implementation.

## Acceptance — MET

- **RED first:** `cargo test -p fabro-workflow --lib error::` → 151 passed,
  **3 failed** against the unmodified classifier, one of them on the verbatim
  `01KYQF8G2TNV` payload.
- **Green without weakening:** 1007 passed, 0 failed; `fmt` and
  `clippy --workspace --all-targets -D warnings` clean. Diff is **165
  insertions, zero deletions** — nothing deleted, loosened or `#[ignore]`d, and
  the three hint-count guards stay at 38/12/3.
- **Landed on a branch:** `fix/classify-provider-spend-limit-not-transient`,
  commit `a7c42204b`, on top of `d5dcd1179`. **Unpushed.**

Full-workspace run: 1218 passed, 4 failed — all four are pre-existing
`fabro-cli` `pre_tracing_bootstrap_*` flakes, **proved** by reproducing them
(six of them) on the unmodified base `d5dcd1179`.

**Opening the PR to `fabro-sh/fabro` is the MAINTAINER'S call** — see NEXT
ACTION. Filing an upstream issue was deliberately **held** for the same reason:
this investigation exists so any report is evidence-backed rather than a guess.

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
