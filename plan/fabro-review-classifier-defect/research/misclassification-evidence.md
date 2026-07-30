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
  **Verified 2026-07-30 from this run's own stage events: 5.78s then 4.69s.**
  Both figures in this note are correct and they are **not** in conflict —
  they are **two different runs**. `01KYP9Z87QC3` is ~5s; `01KYQF8G2TNV`
  (below) is 13.2s then 7.8s. Do not "correct" either into the other.
- **Implement stages succeed** — only `review` dies.
- Duration correlates with nothing (see "retracted" below).

## The real cause — CONFIRMED, and confirmed twice

`fabro inspect` → `node_outcomes.review.failure.causes[1]` names an
**Anthropic org monthly spend limit**. Fleet-wide at the time: **5 runs
across 2 repos and 4 work-items**. Not repo-specific, not item-specific.

**Second, independent confirmation:** the maintainer raised the limit, and
A2's very next dispatch went `active` and proceeded past review. A cause
that disappears exactly when the named limit is lifted is the cause.

### Second capture, in the act — run `01KYQF8G2TNV5N8TGSQ19VF17J`

Dispatched **after** the maintainer raised the spend limit. `implement`
**succeeded**; `review` **failed**. Reproduce with:

```
/home/ubuntu/.local/bin/fabro inspect 01KYQF8G2TNV \
  | jq -r '.[0].checkpoint.node_outcomes.review.failure'
```

Note the path is `.checkpoint.node_outcomes`, **not** `.node_outcomes`.
Verbatim:

```
message:   "ACP turn failed"
causes[0]: "ACP protocol error"
causes[1]: "Internal error: You've hit your org's monthly spend limit ·
            ask your admin to raise it at claude.ai/settings/usage: {
              \"spawned_at\": \"/home/ubuntu/.cargo/registry/src/
                index.crates.io-1949cf8c6b5b557f/
                agent-client-protocol-0.11.1/src/session.rs:567:14\",
              \"data\": { \"errorKind\": \"rate_limit\" }
            }"
category:  "transient_infra"
```

This is the false positive **caught in the act**: `index.crates.io` appears
**only** as part of a cargo registry *source path*
(`index.crates.io-1949cf8c6b5b557f`), and the payload is still labelled
`transient_infra`. A 13-second deterministic provider `rate_limit` is about
as far from "transient infra" as a failure gets.

Two further things, kept deliberately apart — what the record **shows**, and
what is **inferred from** it. An earlier version of this note presented both as
"facts it establishes". That was wrong, and it is logged as supervisor
correction **C5**.

- **SHOWN — different PROVIDERS, which is not the same claim as different
  credentials.** `implement` ran ~5min on **Codex** and passed; `review` died
  in 13.2s then 7.8s on **Claude**. That is a provider difference, read
  straight off the stage records. Using it to reach a conclusion about *which
  Anthropic credential* is a further step nobody took.
- **DOCUMENTED, so cite rather than re-derive.** What the `review` side
  authenticates with is already recorded: `.claude/CLAUDE.md` §"The fleet has
  SEVERAL Anthropic credentials" states that the sandbox's `claude-agent-acp`
  **review** adapter authenticates with `CLAUDE_CODE_OAUTH_TOKEN`
  (`_dispatcher_credentials.py:58`). That section says explicitly to **cite**
  it, not restate it per plan thread. It supports the review-side half; it says
  nothing about what `implement` resolved, because `implement` was on a
  different provider entirely.
- **INFERRED, not measured — that the two stages resolve different Anthropic
  credentials.** Nobody read credential resolution. It is inferred from which
  stage passed, and it is probably true, but it is an inference and must be
  labelled one.
- **WELL-FOUNDED, and here is its evidence — the raise did not reach whatever
  `review` uses.** Not asserted as a mechanism: the maintainer raised the limit,
  and `review` then failed **again**, with the same verbatim provider text, on
  run `01KYQF8G2TNV` dispatched afterwards. That is the observation; the
  conclusion follows from it without needing to name a credential.

**Measured, not reasoned:** replaying the exact rendered payload against all
three hint lists shows **`index.crates.io` is the SOLE matching hint** —
`BUDGET_EXHAUSTED_HINTS` and `STRUCTURAL_HINTS` match nothing, and the
`Canceled` branch does not fire. Note `errorKind` is `rate_limit` with an
underscore, which does **not** match the `"rate limit"` hint; the source path
is the only thing carrying this payload into `transient_infra`.

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

### PRECISION CORRECTION — what the category does and does NOT drive

Read against the code, the first consequence above needs narrowing, and the
narrowing matters because it bounds what this fix buys.

**The in-stage retry is NOT caused by the misclassification.**
`attempt=1 max_attempts=2` comes from `NodeHandler::should_retry` →
`Error::is_retryable()` (`handler/mod.rs:67`), and `Error::Handler { .. }` is
**unconditionally retryable** regardless of category (`error.rs:441-457`). So
correcting the label does **not**, on its own, stop the two attempts.

What the category **does** drive, all in production paths:

- **`loop_restart` edges** are blocked unless the class is `TransientInfra`
  (`lifecycle/circuit_breaker.rs:125-131`). Mislabelling therefore **unlocks**
  restart loops for a failure that can never succeed — the retry pressure is
  real, just one level up from the stage retry.
- **Failure-signature tracking**: `is_signature_tracked()` is true only for
  `Deterministic | Structural` (`fabro-types/src/outcome.rs`). A
  `TransientInfra` label means repeated identical failures accumulate **no
  signature**, so the signature circuit breaker never trips on them — which is
  why this repeated for hours instead of tripping something.
- **Edge conditions** written as `context.failure_class=…` (`condition.rs`).
- **What the operator sees** in `fabro inspect`.

### The residual is TWO layers, not one — measured 2026-07-30

An earlier version of this section named a single residual: "make
`is_retryable()` category-aware". **That was the wrong target**, and it
mis-attributed the expensive harm. Measured, the waste splits across two
independent layers:

**Layer 1 — fabro's per-stage retry (third party).** `is_retryable()` returns
`true` for `Handler`/`Engine`/`Io` unconditionally, so 2 attempts fire inside
the stage regardless of category. This is **possibly deliberate**: `Handler`
and `Engine` are opaque string errors and retrying them is a defensible
default. It is a third party's design decision, is **not** claimed here as a
defect, and was **deliberately not filed**.

**Layer 2 — the orchestrator's re-dispatch of the work-item (in-house).**
**This is the layer that burns host dispatch cap slots**, and it is *not*
fabro's. Filed as **`overseer-fs4`** (bug, P2). Measured with a positive
control first: `transient_infra`, `budget_exhausted`, `failure_categ`,
`failure_class`, `classified_failure` and `node_outcomes` return **zero hits
repo-wide across all 2685 `.py` files** in
`livespec-orchestrator-beads-fabro` — while the control string
`host_dispatch_cap` hits at `_dispatcher_loop_command.py:48,164` and
`_dispatcher_run_commands.py:46,166`, proving the search reached real code.
Nothing consumes a run's failure category, so a work-item whose run died on a
permanent billing ceiling is re-dispatched exactly like a transient one.

The gap is **structural, not an oversight**:
`_needs_attention_stranded_dispatch.py` already counts attempts per
`work_item_id` (`:79-88`), but the record it parses — `_TerminalOutcome`
(`:31-36`) — carries `work_item_id`, `status`, `stage`, `pr_number`,
`merge_sha` and **no failure category or reason at all**, filtering only on
`status != "failed"` (`:112`). The reason never reaches the layer that would
gate on it.

**Correcting the attribution:** the cap-slot burn recorded near the top of this
note is Layer 2. It is **not** caused by fabro's per-stage retry, and it would
**not** be fixed by making `is_retryable()` category-aware. Layer 2 is fixable
**in-house with no upstream involvement** — but only once a run's failure
carries a trustworthy category, which is what this thread's classifier fix
provides and which is **merged nowhere**. That ordering is the dependency, not
a nice-to-have.

### CONFIRMED location — investigated 2026-07-29, no longer a pointer

| | |
|---|---|
| file | `/data/projects/fabro/lib/crates/fabro-workflow/src/error.rs` |
| constant | `TRANSIENT_INFRA_HINTS` (decl `:44`), flat substring list, 38 entries |
| offending entry | `"index.crates.io"` at **`:75`**, a bare sibling of `"dial tcp"`, `"i/o timeout"`, `"econnreset"` … |
| matcher | `pub fn classify_failure_reason(reason: &str)` at **`:160`** |
| consult ORDER (first match wins) | `Canceled` → **`TRANSIENT_INFRA`** → `BUDGET_EXHAUSTED` (`:85`) → `STRUCTURAL` (`:100`) → `Deterministic` fallback |
| the pinning test | `classify_reason_index_crates_io` — **local `:1605`**, upstream `:1654` |

**Every line number in this table is a coordinate in the LOCAL file at base
`d5dcd1179`.** They shift on the fix branch (`:54` / `:85` / `:205`), and they
are **not** upstream's — upstream's own numbers are given separately below.
An earlier version of this table labelled the `:1605` row "upstream pin", which
was **wrong**: `:1605` is the **local** line, and the same test sits at
upstream `:1654`. Corrected here so the row does not send a reader to the wrong
file.

**The earlier `error.rs:44/:85/:159` pointer was RIGHT about the file** — those
are the three hint-list declaration lines (`:159` being one line off the
matcher's `:160`). It was unverified only in that it **named no crate**, and
`/data/projects/fabro` holds 19 files named `error.rs`. Resolved, not wrong.

Order is load-bearing: `TRANSIENT_INFRA` is consulted **before**
`BUDGET_EXHAUSTED`, so a payload that is genuinely budget-shaped still loses to
any transient hint that matches first.

## Where the code lives — and why the obvious filing route failed

| fact | state 2026-07-29 |
|---|---|
| local clone | `/data/projects/fabro` |
| `origin` | `https://github.com/thewoolleyman/fabro.git` — the maintainer's fork. **GitHub issues DISABLED** (fork default) |
| `upstream` | `https://github.com/fabro-sh/fabro` — public, issues enabled |
| classifier vs upstream | see the CORRECTION immediately below — the previously recorded "byte-identical" was a **vacuous check** |

### CORRECTION — a recorded "measurement" that was never made

This note previously recorded, as fact:

> classifier vs upstream: **byte-identical** — `git diff --stat upstream/main
> -- <classifier>` is empty

**That check was vacuous and its result proved nothing.** Upstream has
**relocated `lib/crates/` → `lib/components/`**. `git ls-tree --name-only
upstream/main lib/` returns `lib/apps`, `lib/components`, `lib/foundation`,
`lib/packages` — there is **no `lib/crates` upstream at all** — and
`git cat-file -e upstream/main:lib/crates/fabro-workflow/src/error.rs` fails
outright. Diffing a path absent from one side is empty for the trivial reason,
not because the contents agree. Verified independently by the supervisor.

The real comparison, run against the relocated path:

```
diff <(git show HEAD:lib/crates/fabro-workflow/src/error.rs) \
     <(git show upstream/main:lib/components/fabro-workflow/src/error.rs)
→ 357 differing lines. NOT byte-identical.
```

**The conclusion survives; the evidence cited for it did not.** The defect *is*
present upstream, unmodified — measured directly on upstream's own file:
`"index.crates.io"` at upstream `:79`, the identical first-wins consult order,
and the same pinned test `classify_reason_index_crates_io` at upstream `:1654`.
So filing upstream remains justified — on this evidence, not the old one.

Recorded as an explicit correction rather than a quiet edit: asserting a
measurement that was not made is precisely the failure class this thread
exists to police.

### Branch-base divergence — a live hazard for the PR

| | |
|---|---|
| local `HEAD` | `d5dcd1179` — **2026-07-09** |
| `upstream/main` | `854f71f2c` — **2026-07-29** |
| gap | ~3 weeks, 357 differing lines **in this very file**, plus the `lib/crates` → `lib/components` relocation |

**`upstream/main` is a MOVING REF, and every upstream number here is an AS-OF
measurement against `854f71f2c` (2026-07-29) — not a current fact.** It has
since moved: measured read-only by the supervisor 2026-07-30, fabro's local
`main` now tracks upstream at `b5885b15d`. The 357-line divergence and the
"5 of 6 hunks" port result below therefore both need **re-measuring against the
live tip** before anyone relies on them. Citing a branch tip without its
as-of date is the same defect as citing a mutable commit SHA as a durable
identifier (supervisor correction **C4**) — one level up.

What does **not** decay: the conclusion that the defect is present upstream
unchanged rests on the hint entry, the consult order and the pinned test —
none of them a line count — so upstream advancing does not disturb it.
| hint counts | local pins 38/12/3; **upstream pins 38/10/3** — `BUDGET_EXHAUSTED_HINTS` has already diverged |

Any PR to `fabro-sh/fabro` must be re-expressed against
`lib/components/fabro-workflow/src/error.rs`.

### Applies to upstream — MEASURED, not assumed

**The defect still expresses on `upstream/main`.** Replaying upstream's *own*
`classify_failure_reason` logic (its hint lists, its order, including the
`HEX_RE` pre-mask it has since added) against the verbatim `01KYQF8G2TNV`
payload still yields **`TransientInfra`**, still on `index.crates.io` as the
sole match. The hash is masked to `<hex>`, but `index.crates.io-` survives the
mask, so the hint fires anyway.

**Patch portability, measured by dry-run apply** (`patch -p1 --dry-run` of the
branch diff, paths rewritten `lib/crates/` → `lib/components/`):
**5 of 6 hunks apply**; **hunk 3 fails** — the one editing
`classify_failure_reason` itself.

**Why it fails is worth knowing: upstream has independently adopted this
fix's own idiom.** Upstream now pre-masks the payload before hint matching:

```rust
// Mask commit SHAs first. They are hex, so one contains "500" or "503"
// often enough to matter, which would read as a transient infra hint.
let lower = HEX_RE.replace_all(&lowered, "<hex>");
```

That is the **same defect class** — payload text that is not fault text firing
a transient hint — fixed for hex SHAs by pre-masking. So remedy (b) is not a
foreign idea imposed on upstream; it is upstream's own established pattern
extended to the other provenance that reaches the matcher.

**A porting hazard this surfaced, and the guard now written for it.** Upstream
masks hex *before* classifying, so a strict `[0-9a-f]+` hash pattern would see
`index.crates.io-<hex>` and **silently stop matching** — the discount would
quietly no-op upstream while every test still passed. The regex was
deliberately loosened to `index\.crates\.io-[^\s"']*` (the
`/registry/src/` anchor still carries the specificity), and
`classify_reason_hex_masked_registry_source_path_is_not_a_network_fault` pins
the masked form so the port cannot regress silently.

**No silent rebase.** The RED demonstration stands on the base it was taken
against — local `d5dcd1179` — and the branch targets that base. Re-expressing
hunk 3 for upstream is a mechanical insertion after the `HEX_RE` line; it is
left for whoever opens the PR, since **opening it is the maintainer's call**.

So the defect **originates upstream**. Precisely: the *file* is **not**
unmodified between fork and upstream (357 differing lines), but the *defect* —
the hint entry, the consult order, the pinned test — is present on both,
unchanged. Filing was deliberately **held**: the maintainer chose a real
investigation and a prepared fix over an unverified bug report on a third
party's public repo.

## Cross-reference — the sibling thread still asserts two things measured here

`plan/codex-parity-and-rollout-safety/handoff.md` (~`:218-222`) is where this
thread was spun out of, and it is **the original source of the vacuous
byte-identical check**. Recorded here so the contradiction is visible from this
side: their record is **theirs**, and this thread deliberately did not edit it.

**Still asserted there, disproven here:**

1. *"The classifier file is **byte-identical** … (`git diff --stat
   upstream/main` is empty)"* — the **vacuous check**. Upstream relocated
   `lib/crates/` → `lib/components/`, so that diff compared a path **absent
   upstream**; emptiness proved nothing.
2. *"The orchestrator's `workflow.fabro` only CONSUMES the category it is
   handed"* — **inverted. Nothing consumes it.** All of `transient_infra`,
   `budget_exhausted`, `failure_categ`, `failure_class`, `classified_failure`
   and `node_outcomes` return **zero hits repo-wide across 2685 `.py` files**,
   against a **passing positive control** (`host_dispatch_cap` hits at
   `_dispatcher_loop_command.py:48,164`). Filed as **`overseer-fs4`**.

**Their conclusion survives — only its evidence did not.** The defect *is*
upstream's, unmodified: hint at upstream `:79`, same first-match-wins order,
same pinned test `classify_reason_index_crates_io` at upstream `:1654`. Keep
that distinction; it is the whole discipline of this thread.

**What they got RIGHT, and it proved load-bearing.** Their line — *"absent the
false positive the string would classify `Deterministic` … `BudgetExhausted`
would be semantically right"* — was correct on **both** counts. And the
`Deterministic` fallback turned out to matter more than it looked: it is
**signature-tracked**, which is precisely why the fix adds a permanent-provider-
limit hint *ahead* of the transient list rather than only suppressing the false
positive.

> **SUPERSEDED 2026-07-30 — DELIVERED, RECEIVED AND ACTED ON.** The section
> below describes the state before delivery and is kept for provenance. Do not
> read it as current; leaving it uncorrected already caused a reader to report
> to the maintainer that no delivery had happened.
>
> **The evidence is the recipient's own log, not this thread's transcript** —
> `tmp/overseer/codex-parity-and-rollout-safety/worker-status.log`, written by
> them: *"PEER NOTIFICATION (fabro-review-classifier-defect) VERIFIED, not
> accepted on faith"*; *"PEER FOLLOW-UP ADJUDICATED … BOTH their measurements
> REPRODUCE EXACTLY at the base ref they named"*; *"MY HYPOTHESIS WAS WRONG"*;
> *"ADOPTING THEIR ASK IN FULL"*.
>
> **A picker IS open on that pane again — a NEW one, opened after the
> exchange.** Do not read a currently-open picker as evidence that no delivery
> ever happened; that infers history from present state. Verify against the
> durable log, which is why the log is cited above rather than a screen capture.
>
> **AND THE OUTCOME MOVED FURTHER THAN THIS THREAD RECORDED.** Their `:73`
> entry **fully RETRACTS byte-identity** — not ref-pinned, *withdrawn*: at
> pinned refs with the correct `lib/components/` path on **both** sides, fork
> `49b043c1a` (87769 bytes) vs `upstream/main` `4ab090cae` (67441 bytes) =
> **484 differing lines**, with fork hint counts `1/38/10/3` against upstream
> `38/10/3` — the fork carrying an **extra hint list**, consistent with this
> thread's own fix having landed there. So "they adopted ref-pinning" is itself
> now stale: the claim was dropped outright, and this thread's difference
> finding is corroborated a third time.

**Delivery status — prepared, NOT delivered.** A peer notification sits at
`tmp/overseer/codex-parity-and-rollout-safety/PEER-NOTIFICATION-from-classifier-defect-supervisor.md`
(gitignored). It has **not** been sent by tmux: that supervisor's
`AskUserQuestion` picker has been open throughout, on a maintainer question
about admitting work. **Typing into an open picker can SELECT an option on the
maintainer's behalf** — a decision this thread does not own.

**FILE-ONLY, and NOT actively awaited. Nothing is polling; nobody will be woken
when that picker clears.** An earlier version of this note said a watcher was
waiting for it. **That is no longer true** — the watcher was **stood down**
after hitting its 40-minute ceiling **twice** with no change, the picker having
been open ~80 minutes on the same maintainer question.

The reason it was stood down is itself the point: **a watcher polling a human
decision reports "still blocked" indistinguishably from "nothing is
watching"** — the wrong-gauge defect this thread's charter already carries
forward. Re-arming a third time would have added confidence without adding
signal.

**So a successor must DO this, not wait for it:** deliver the notification **by
hand** when that session is next observed **without** an open picker — and
**check that harness's own submit idiom first, per C6**. That pane is Claude
Code, but the `fabro` pane was not, and this thread already assumed wrongly once
today.

**The other notification — the Codex addendum — is DELIVERED-BY-FILE, NOT
CONFIRMED-READ.** It sits at
`/data/projects/fabro/tmp/ADDENDUM-second-limit-payload-found.md` (gitignored),
and its text is additionally visible **unsubmitted** in that session's pane
after the C6 keystroke failure. **Do not write that they have it** — no read
has been confirmed.

## A SECOND limit payload — the defect is a CLASS, and the fix does not cover it

Found 2026-07-30 on **rung five** of the sweep (other fleet repos), in
`livespec-console-beads-fabro/plan/console-happy-path-mvp/handoff.md:817-825`.
**That record is theirs and is not edited here — it is cited because it is
better evidence than ours.** From that run's own event log:

```
stage.failed review — category: transient_infra
  "Internal error: You've hit your limit · resets Jul 31, 5am (UTC)"
```

Four attempts, all four `transient_infra` / "ACP turn failed", both burned in
34s. **So the mislabel reproduces on a second, unrelated provider message.** It
is a **class**, not one string — a material strengthening of the case.

### 1. The credential inference is now MEASURED — by someone else

That thread read the **configuration**, which this thread never did: *"The
`review` node runs on the Claude SUBSCRIPTION (`workflow.toml:85-95`,
`review_adapter`, `CLAUDE_CODE_OAUTH_TOKEN`). `implement` survived only because
it is overridden to Codex (`acp_adapter`) — a DIFFERENT account."*

**Our labelling stays as it was.** When *this* thread made the claim it **was**
an inference, and correction **C5** stands — it was not measured here, and
being later vindicated does not retroactively make it evidence. What changes is
that an independent thread has now measured it, with a config citation.

This is also the **second limit KIND**: a rolling window that names its own
reset, alongside the monthly spend cap. See `.claude/CLAUDE.md` §"The fleet has
SEVERAL Anthropic credentials", which says to expect exactly these two and to
**cite** rather than restate it.

### 2. MEASURED GAP — the fix does not classify this payload

Checked against the fix's own lists (not relayed — the list contents are quoted
in this note and the branch commit):

| list | result on `"…hit your limit · resets Jul 31, 5am (UTC)"` |
|---|---|
| `PERMANENT_PROVIDER_LIMIT_HINTS` (`["spend limit"]`) | **NO MATCH** |
| `BUDGET_EXHAUSTED_HINTS` | **NO MATCH** |
| `TRANSIENT_INFRA_HINTS` | **NO MATCH** |

So post-fix, part **(b)** correctly kills the registry-path false positive and
the payload then falls through to the **`Deterministic` fallback — which is
signature-tracked.** That is precisely the outcome part **(a)** was added to
prevent, so **(a)'s stated rationale does not hold for this payload**.

**This is a gap in the ACCEPTANCE, not a defect in the branch.** RED-then-green
still holds for the payload it was built against, and **(b) remains correct for
both**. What is now false is any claim that the fix classifies provider limit
failures **generally**. The single-hint list was flagged as brittle when the
branch was prepared; this is measured evidence of a second phrasing in the wild.

### Delivery of this finding — DELIVERED-BY-FILE, **NOT CONFIRMED-READ**

The addendum is at `/data/projects/fabro/tmp/ADDENDUM-second-limit-payload-found.md`
(gitignored; no tracked file, the branch and their handoff prompt untouched).
Its content is **also visible in their pane**, left there unsent — see
supervisor correction **C6** for why the send was abandoned rather than
retried.

**Do not record that they have it.** Delivered by file; **not** confirmed read.

State of that session when this was written: `fabro`
(`gpt-5.6-sol`, cwd `/data/projects/fabro`) running a **three-way** review — an
Opus 5 reviewer spawned via `claude --print --model claude-opus-5`, plus a
Fable reviewer which had **already returned findings** that the drive-prefix
exclusion is too narrow for **mixed-separator paths**. **No reviewer had
returned a final verdict**, and the branch was frozen and unpushed.

> **C4, vindicated a third time in one session.** The branch head has now moved
> **three times today**: `a7c42204b` → `b46a4f387` → `3251a8aa2`. The **branch
> name** `fix/classify-provider-spend-limit-not-transient` is the durable
> identifier. **No SHA in this record is durable**; every one is an as-of
> reading, and this is the clearest possible demonstration of why.

### The open design question — recorded, NOT decided

A monthly **spend cap** is permanent and needs a human. A **rolling window that
states its own reset time** genuinely clears on its own. So "retry after reset"
may be right for the second and wrong for the first, and **one shared category
may not fit both**.

The strongest option on the table is to **stop inferring from prose entirely**
and classify on the **structured `errorKind`** the payload already carries — the
original payload carried `"errorKind": "rate_limit"`. Extending substring lists
fixes **instances**; reading the structured field fixes the **class**. That is
this thread's whole thesis, applied to its own remedy.

## A RETRACTED attribution — do not resurrect it

An earlier reading blamed `bd-ib-2nq` (a >60-minute token TTL). **That is
disproven by measurement:** the review stage fails in ~5s regardless of run
length, so duration correlates with nothing. A prior session had already
retracted it, and the supervisor then repeated it back as praise — spreading
it further. It is wrong. The adjacent `code="github_token_refresh_limited"`
notice in the logs is a red herring for this failure.

## The five questions — ANSWERED 2026-07-29

**1. Is the `index.crates.io` false positive real, and exactly where?**
**YES.** Location table above. Proved by replaying the verbatim
`01KYQF8G2TNV` payload against all three hint lists: `index.crates.io` is the
**sole** match, and it matches inside the `spawned_at` source path.

**2. What SHOULD a spend-limit failure classify as?**
**`FailureCategory::BudgetExhausted`** — it already exists
(`fabro-types/src/outcome.rs:172`) and **no new variant is needed**. Upstream's
own structured classifier already agrees with this reading:
`classify_sdk_error` maps `ProviderErrorKind::QuotaExceeded → BudgetExhausted`
(`error.rs:24-26`). An org spend ceiling is a quota. The string-heuristic path
simply never reached that conclusion.

`Deterministic` was considered and **rejected**: it means "the agent's own work
is at fault", and it is one of only two signature-tracked classes
(`is_signature_tracked` → `Deterministic | Structural`), so routing a billing
ceiling there would poison the failure-signature circuit breaker with a
non-code cause.

**3. Why does a source path reach a network-fault matcher at all?**
Because `Error::handler_with_source*` / `engine_with_source`
(`error.rs:360-410`) render **message + the FULL cause chain** and then
substring-match the whole blob. ACP internal errors carry a `spawned_at`
provenance path pointing into `~/.cargo/registry/src/index.crates.io-<hash>/`.
So the matcher is reading a **file path as if it were fault text**.

**This is bigger than the spend limit.** RED test 3 below proves a payload with
that path and **no spend-limit text at all** is *still* `transient_infra` —
i.e. **every** ACP internal error carrying `spawned_at` is currently
mislabelled, whatever its actual cause.

**4. Does upstream pin the current behavior in a test?** **YES, and the pin is
LEGITIMATE.** `classify_reason_index_crates_io` (local `:1605`, upstream
`:1654`) asserts `"failed to fetch index.crates.io" → TransientInfra`, which is
**correct** — a real registry *fetch* failure genuinely is transient. Plus
three hint-count guards (`:1219` = 38, `:1224` = 12, `:1229` = 3). The fix must
**separate a fetch failure from a bare source path**, never delete the hint.

**5. Is `review` the only stage affected?** **No.** `classify_failure_reason`
backs **every** `Handler`/`Engine` error constructor in `fabro-workflow` — all
node types — plus `outcome.rs:81,93`; and a **single** shared
`AgentAcpBackend` serves all ACP nodes through `BackendRouter`
(`handler/mod.rs:298,317`). `implement` passed only because it ran on a
**different provider (Codex)**, not because it is immune — the classifier is
the same for both. Whether that also meant a different *Anthropic credential*
is an **inference**, not a measurement; see the shown-vs-inferred split above.

## The remedy — BOTH fixes, and why neither alone is enough

The two candidate remedies are **not** equivalent, so both were implemented,
each answering a different defect:

**(b) ROOT CAUSE — stop provenance reaching the matcher.** New
`discount_cargo_registry_source_paths()` blanks
`…/registry/src/index.crates.io-<hash>/…` path spans **before** any hint
matching. This is the fix question 3 actually describes, and it is the one that
closes the **general** false positive — every ACP error carrying `spawned_at`,
not just billing ones. It cannot delete a legitimate signal: a registry *fetch*
failure names the **host or URL**, never a local `registry/src` **extraction**
path, and all other fault text in the payload survives untouched.

**(a) SEMANTICS — classify the spend limit correctly.** New
`PERMANENT_PROVIDER_LIMIT_HINTS = ["spend limit"]`, consulted **before**
`TRANSIENT_INFRA_HINTS` → `BudgetExhausted`.

**(b) alone is insufficient**, and this is the load-bearing reason for keeping
(a): with only (b), the spend-limit payload stops being `transient_infra` but
falls all the way through to the **`Deterministic` fallback** — which is
*also* wrong (see Q2), and worse in one respect, because `Deterministic` is
signature-tracked. (b) makes it stop retrying; (a) makes it land in the class
that names what actually happened, so the operator sees a billing ceiling
rather than a code defect. **(a) alone** would have left the general defect
live, which is why it was not implemented alone.

Precedence rather than list-append is deliberate: the payload carries
transient-looking noise (`errorKind: rate_limit`) that would otherwise win on
first match.

## Non-weakening — what was and was NOT touched

- **Nothing deleted, loosened, or `#[ignore]`d.** No existing assertion was
  edited.
- `classify_reason_index_crates_io` (the legitimate fetch pin) **still green**.
- The three hint-count guards are **untouched at 38 / 12 / 3** — the fix adds a
  **new, separate** const with its **own** guard (`= 1`) rather than growing an
  existing list, so no pinned count needed renumbering.
- Two **additional** non-weakening guards were added and were **green before
  the fix as well as after**: a registry download **URL** still classifies
  transient, and a registry source path sitting **beside** a real
  `connection reset by peer` still classifies transient — proving the discount
  removes only provenance, never a genuine fault.
- Whole-crate result is the real evidence of non-weakening: **1007 passed, 0
  failed**, with **no test skipped or disabled**.

Nothing here required removing, loosening or skipping a check, so the
supervisor's stop-and-ask boundary was never reached.

## Acceptance for the fix — MET 2026-07-29

Branch: **`fix/classify-provider-spend-limit-not-transient`** in
`/data/projects/fabro`, based on local `d5dcd1179`.

**RED first, recorded before any fix existed.** `cargo test -p fabro-workflow
--lib error::` → **151 passed, 3 FAILED**:

| test | RED result |
|---|---|
| `classify_reason_provider_spend_limit_is_budget_exhausted` | left `TransientInfra`, right `BudgetExhausted` — on the **verbatim** `01KYQF8G2TNV` payload |
| `acp_spend_limit_failure_detail_is_not_transient_infra` | same, through the real `Error::handler_with_source` → `to_failure_detail()` chain |
| `classify_reason_cargo_registry_source_path_is_not_a_network_fault` | `spawned_at` path with **no** spend-limit text → still `TransientInfra` |

That third RED is the one that widened the diagnosis: it proves the false
positive is the **bare path itself**, so the defect was never limited to
billing failures.

**GREEN after the fix:** `cargo test -p fabro-workflow --lib` → **1007 passed,
0 failed** (1007 rather than 1006 because the upstream-port hazard above added
a seventh test). `cargo +nightly-2026-04-14 fmt --check --all` clean.

**SCOPE OF THIS ACCEPTANCE — it is NOT general coverage.** It is met for the
payload the RED test was built against (`01KYQF8G2TNV`, the monthly spend cap)
and for the registry-path false positive generally. It is **not** met for
provider limit failures as a class: a second phrasing measured 2026-07-30
matches **none** of the hint lists and falls to the signature-tracked
`Deterministic` fallback — see "A SECOND limit payload" above. Do not read
"acceptance MET" as "provider limits are classified correctly".

**Opening the PR to `fabro-sh/fabro` remains the MAINTAINER'S call** — it is
outward-facing onto a third party's public project. The branch is prepared and
stops there. No upstream PR and no upstream issue were opened.
