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

Two further facts it establishes:

- **The two stages resolve DIFFERENT credentials.** `implement` ran ~5min on
  Codex and passed; `review` died in 13.2s then 7.8s on Claude.
- **The maintainer's raise did not reach the credential `review` uses.**

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
| upstream pin | `classify_reason_index_crates_io` at **`:1605`** |

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
(`handler/mod.rs:298,317`). `implement` passed only because it ran on **Codex
under a different credential**, not because it is immune.

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

**Opening the PR to `fabro-sh/fabro` remains the MAINTAINER'S call** — it is
outward-facing onto a third party's public project. The branch is prepared and
stops there. No upstream PR and no upstream issue were opened.
