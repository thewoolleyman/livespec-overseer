# Research — the fabro error classifier calls a spend-limit failure `transient_infra`

**Provenance:** surfaced 2026-07-29 while driving
`plan/codex-parity-and-rollout-safety/`. That thread's slice A2
(`overseer-vyie5q`) died twice at the `review` stage before the cause was
found. This note records what was MEASURED, and separates it from what is
still hypothesis, so the investigation does not start by re-deriving it.

## The failure, as observed

Run `01KYP9Z87QC3`, stage index 3:

```
Stage failed node_id="review" stage="Review (Claude Opus 4.8): correctness
  + senior-engineer design lens" error="ACP turn failed" will_retry=true
Stage retrying ... attempt=1 max_attempts=2 delay_ms=3191
Stage failed ... error="ACP turn failed" will_retry=false
Edge selected from_node="review" to_node="escalate" label="Blocked"
```

- Fails in **~5 seconds**, deterministically, on both attempts.
- **Implement stages succeed** — only `review` dies.
- Duration correlates with nothing (see "retracted" below).

## The real cause — CONFIRMED, and confirmed twice

`fabro inspect` → `node_outcomes.review.failure.causes[1]` names an
**Anthropic org monthly spend limit**. Fleet-wide at the time: **5 runs
across 2 repos and 4 work-items**. Not repo-specific, not item-specific.

**Second, independent confirmation:** the maintainer raised the limit, and
A2's very next dispatch went `active` and proceeded past review. A cause
that disappears exactly when the named limit is lifted is the cause.

> **Method note that cost the supervisor a wrong call.** `fabro logs`
> shows only the generic `error="ACP turn failed"` — no credit, quota or
> spend string anywhere. Reading logs alone, the supervisor reported the
> spend-limit diagnosis as "the worker's inference, not verified", which
> was WRONG: it was already verified via `fabro inspect`. **The structured
> failure causes live in `inspect`, not in `logs`.** Look there first.

## THE DEFECT ITSELF — the reason this thread exists

The classifier labels that spend-limit failure **`transient_infra`**, and
the reported reason is a **false positive**: the string `index.crates.io`
in the error payload matches a **source path**, not a network fault.

Consequences, all observed rather than reasoned:

- A **permanent, human-actionable** failure is retried as if transient.
- Each retry burns a **host dispatch cap slot** (cap is 2) plus a full
  `ImplementWorkItem` run, before dying in ~5s.
- The true cause is **masked** — the operator sees `transient_infra` and
  reasonably concludes "retry later", which never succeeds.
- It misled this fleet for hours across 5 runs.

Pointed at by the driving session: **`error.rs:44` / `:85` / `:159`.**
**Those line numbers are UNVERIFIED by this thread — confirm them before
relying on them.**

## Where the code lives — and why the obvious filing route failed

| fact | state 2026-07-29 |
|---|---|
| local clone | `/data/projects/fabro` |
| `origin` | `https://github.com/thewoolleyman/fabro.git` — the maintainer's fork. **GitHub issues DISABLED** (fork default) |
| `upstream` | `https://github.com/fabro-sh/fabro` — public, issues enabled |
| classifier vs upstream | **byte-identical** — `git diff --stat upstream/main -- <classifier>` is empty |

So the defect **originates upstream**, unmodified in the fork. Filing was
deliberately **held**: the maintainer chose a real investigation and a
prepared fix over an unverified bug report on a third party's public repo.

## A RETRACTED attribution — do not resurrect it

An earlier reading blamed `bd-ib-2nq` (a >60-minute token TTL). **That is
disproven by measurement:** the review stage fails in ~5s regardless of run
length, so duration correlates with nothing. A prior session had already
retracted it, and the supervisor then repeated it back as praise — spreading
it further. It is wrong. The adjacent `code="github_token_refresh_limited"`
notice in the logs is a red herring for this failure.

## Open questions the investigation must answer

1. **Is the `index.crates.io` false-positive real, and exactly where?**
   Reproduce it against the actual error payload. Confirm or correct the
   `error.rs:44/:85/:159` pointers.
2. **What SHOULD a spend-limit failure classify as?** It is permanent and
   human-actionable — retrying it is always wrong. Does a suitable class
   already exist, or is one needed?
3. **Why does a source path reach a network-fault matcher at all?** A
   substring test over a payload that legitimately contains crate paths is
   the underlying design smell; the spend-limit case may be one symptom.
4. **Does upstream pin the current behavior in a test?** If so the fix must
   extend it, never loosen it.
5. **Is `review` the only stage affected**, or does any stage inherit the
   same classifier?

## Acceptance for the fix

- A **RED demonstration first**: a test that fails against today's
  classifier because a spend-limit payload is labelled `transient_infra`.
- The fix makes it green **without weakening any existing classification**.
- Lands on a **branch in `/data/projects/fabro`** (the fork clone), in
  preparation for a PR to `fabro-sh/fabro`. **Opening that PR is the
  maintainer's call** — it is outward-facing onto a third party's project.
