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

## RESUME STATE — 2026-07-30 session end, read this first

**This file is the ONLY thing a restarted session inherits.** Nothing in
`tmp/`, no transcript, no scratchpad.

**Nothing is blocked on the worker.** All record work is landed and
forge-verified. There is **no half-finished edit** anywhere.

> **DO THIS FIRST, BEFORE READING ANOTHER LINE — a restart inherits a STALE
> PRIMARY CHECKOUT.** This session cold-opened at `83d7efa` while master was
> `ae712e8b` — 22 commits behind — and read a **224-line** handoff superseded by
> a 289-line one. **Nothing in the stale copy announced its own staleness**; it
> still claimed its read-chain was complete. The note predicting this failure
> was in `tmp/`, which a restart does not inherit, which is why it lives here:
>
> ```sh
> mise exec -- git fetch origin --prune && mise exec -- git merge --ff-only origin/master
> ```
>
> **Master was `8cc9f03b` when this box was written, and this file was 595
> lines.** If your copy is shorter, you are reading a stale one.

> **STATE AS OF 2026-07-30, superseding the list below where they disagree.**
>
> - **Delivery 1 is DONE** — delivered, received and acted on; the recipient's
>   own log is the evidence. **Delivery 2 remains outstanding and unawaited.**
> - **The sweep reached RUNG NINE.** Rungs 1–7 and 9 returned something; **rung
>   8 was dry as scoped**. Rung nine is the one to read first — it found this
>   repo is the **fleet's sole outlier** on branch protection and it *reframed*
>   `overseer-rh1`.
> - **The ledger is SIX items, not five** (table below is otherwise current):
>   `overseer-dtytju`, `overseer-fs4`, `overseer-816`, `overseer-b4q`,
>   **`overseer-rh1`** (new, rung seven), and **`overseer-knm`** (appended).
>   **`overseer-ya4` is CLOSED**, routed to `livespec-dev-tooling-zi4q`.
> - **TWO THINGS NEED A HUMAN AND ARE NOT BLOCKED ON THE WORKER.** (1) The
>   `overseer-ya4` root cause was appended to the **closed** item and **will not
>   reach `zi4q`**; forwarding is a cross-tenant write. (2) `livespec-console`
>   has **no branch protection at all** — recorded, not filed, wrong tenant.
> - **`overseer-b4q` and `overseer-rh1` are actionable now** by the normal
>   factory route; both were deliberately **not dispatched** (admission policy
>   is being decided in another session).
>
> **Working note that saves an hour:** `just worktree-create` / `worktree-lib.sh
> create` **SIGPIPEs to `rc=141` with zero output and no worktree when its
> stdout is a pipe.** Redirect stdout to a **file** and verify the
> **postcondition**, never the exit code:
> `test -d "$W" && test -d "$W/dev-tooling"`.

**The ledger — six items; all `backlog` and none groomed, EXCEPT `overseer-ya4`
which is now CLOSED and routed out (see the box above).** Read
via `/data/projects/1password-env-wrapper/with-livespec-env.sh bd show <id>`
(a bare `bd` is Access-denied; `bd create` has no `--status`, so hand-filed
items land at beads-native `open` — set status explicitly and **read back**,
because the wrapper exits 0 even when the binary is missing, `overseer-1sv`):

| id | what |
|---|---|
| `overseer-dtytju` | P2 epic — acceptance MET but **NOT general coverage** (see below) |
| `overseer-fs4` | P2 bug — the orchestrator never consumes the failure category; cross-referenced with `bd-ib-g56f` in the **orchestrator** tenant |
| `overseer-816` | P2 bug — the send idiom is Claude Code-specific but lives in the **generator** and the **shared protocol**, so every future charter reproduces it |
| `overseer-rh1` | P2 bug — **filed 2026-07-30 as rung seven.** `check-branch-protection-alignment` warns (exit 0) when a CI leg stops gating merges; its leniency assumes a required `ci-green` aggregate that **this repo does not have**, and it never checks that assumption. Enforcement verified as legacy branch protection, **no rulesets** (positive control run, since an empty ruleset list is otherwise indistinguishable from an auth error) |
| `overseer-b4q` | P2 bug — **filed 2026-07-30 as rung six (a); INDEPENDENTLY VERIFIED by a second party.** **ACTIONABLE NOW** by the normal factory route — needs no upstream and no classifier — but deliberately **NOT dispatched**: it sits outside this thread's epic and admission policy is being decided in another session. `check-prose-release-hygiene` reads a path-scoped diff and cannot tell "no prose changed" from "`.claude-plugin/prose/` is gone". Measured: that path and a never-existent path return **identical** empty output. It is one of the **56 required** branch-protection contexts, so the vacuous case is a **merge gate reporting success while checking nothing** — and it is the *same* vacuous-diff shape this thread already retracted once, now in our own enforcement surface |

**HUMAN-OWNED, none blocking:** closing `overseer-dtytju`; merge-and-tenant for
`overseer-fs4` vs `bd-ib-g56f`; publication of the fabro branch; whether to fix
the generator (`overseer-816`); and **re-measuring the port arithmetic against
upstream's LIVE tip** — the 357-line and 5-of-6 figures are as-of `854f71f2c`
and upstream has since moved.

> **Partially discharged 2026-07-30.** The peer session re-measured the **hint
> counts** against a then-current `upstream/main` and still got **38/12/3 vs
> 38/10/3** (see delivery 1 below), so the *divergence* survives upstream
> advancing. That is the qualitative half only. **The 357-line and 5-of-6
> figures themselves are still as-of `854f71f2c` and still need re-measuring**
> — and note their run resolved `upstream/main` at ITS clock, which this file
> cannot pin, so treat even that as as-of-unstated rather than current.

**`overseer-b4q` is NOT on that list.** It is an ordinary in-house bug in this
repo's own justfile, it depends on nothing upstream and nothing in `fabro`, and
unlike `overseer-fs4` it does **not** wait on a trustworthy failure category —
so it is actionable now by the normal factory route. It is filed rather than
fixed here only because a planning thread does not hand-build code.

**ONE DELIVERY OUTSTANDING** (was two), and it is **not awaited** — nothing is
polling for it.

1. ~~Peer notification to `codex-parity-and-rollout-safety`~~ — **DELIVERED
   2026-07-30, submitted and confirmed on screen.** Its guard condition finally
   came true: that session was found at an **empty prompt with no picker**, and
   anchored-picker plus 6s-stability checks both passed before the paste. Sent
   by the charter's own idiom — `load-buffer` → `paste-buffer -p` → **verify** →
   `Enter` as a separate step. Two things worth reusing: `paste-buffer -p`
   (bracketed) is what stops a multi-paragraph message from submitting its
   first line and scattering the rest across turns; and the message opened by
   stating **it was NOT an answer to the maintainer question that pane was
   waiting on**, because delivering into an idle-but-blocked pane can otherwise
   read as the approval. The durable file is unedited and still the record.

   **It produced a real exchange, and the outcome is now settled — read this
   before re-opening the byte-identity question.** They replied that the
   classifier files ARE byte-identical on a valid comparison, and guessed we
   had diffed our fix branch. This thread **cannot** adjudicate that (it is
   barred from `/data/projects/fabro`), so it argued from the record instead
   and asked them to run it. **They did, and this thread's record stands at the
   base ref** — independently re-measured by them:

   | check | base `d5dcd1179` | `upstream/main` |
   |---|---|---|
   | hint counts | 38/12/3 | 38/10/3 |
   | `HEX_RE` occurrences | 2 | 3 |

   **Byte-identical files cannot pin different hint counts**, so 12-vs-10
   settles it without appeal to any line count — a better instrument precisely
   because it cannot be confounded by which ref was diffed. Their fix-branch
   guess was also refuted by arithmetic already in the record: the fix is 165
   insertions / 0 deletions and cannot produce 357 differing lines.

   **Both results were true, of different refs** — theirs against the fork's
   CURRENT tree (now tracking upstream), ours against the three-week-old base.
   **Neither had stated an as-of ref; that was the actual bug**, and it is the
   moving-ref defect (**C4**) landing on both threads at once. They adopted the
   remedy in full: their `handoff.md` will read *"byte-identical as of
   `<fork-ref>` / `<upstream-ref>`, `<date>`"* — never bare.

   > **SUPERSEDED — they went further and RETRACTED byte-identity outright.**
   > Their own log (`:73`): at pinned refs with the correct `lib/components/`
   > path on **both** sides, fork `49b043c1a` (87769 bytes) vs `upstream/main`
   > `4ab090cae` (67441 bytes) = **484 differing lines**; fork hint counts
   > `1/38/10/3` vs upstream `38/10/3`, the fork carrying an **extra hint
   > list** — consistent with this thread's own fix having landed there. So the
   > claim is **withdrawn, not ref-pinned**, and this thread's difference
   > finding is corroborated a third time. *"Ref-pin it"* was the right ask and
   > is now the weaker statement of the outcome; cite the retraction instead.

   **A RECORD DEFECT OF OURS, and it is the reason this entry is verbose.**
   `research/misclassification-evidence.md` still read *"prepared, NOT
   delivered"* long after delivery, because `handoff.md` was updated and the
   research note was not. A reader consequently reported to the maintainer that
   no delivery had happened — reasonably, since the durable record said so.
   **When a state changes, sweep EVERY file that asserts the old state, not the
   one you happen to be editing.** Corrected there now.

   > **One imprecision of OURS, corrected here rather than left standing.** The
   > relayed message said upstream carries a `HEX_RE` pre-mask "that the local
   > base does not". Measured, `HEX_RE` is present in **both** — 2 occurrences
   > at base, 3 upstream. The true claim is narrower: upstream has an
   > **additional** occurrence, the pre-mask **inside the classifier path**,
   > which is what makes hunk 3 conflict. Absent-vs-present was wrong;
   > two-vs-three is right. The conclusion is untouched, and the decisive
   > instrument was always the hint counts.
2. Codex addendum at
   `/data/projects/fabro/tmp/ADDENDUM-second-limit-payload-found.md` —
   **DELIVERED-BY-FILE, NOT CONFIRMED-READ**; its text also sits **unsubmitted**
   in that pane, as `[Pasted Content 1018 chars]`.
   **Re-checked 2026-07-30 and deliberately NOT attempted.** That session was
   measured **actively working** (pane changing) with a **live Opus 5
   adversarial reviewer** (`claude --print --model claude-opus-5`, pid
   `3725995`, `--max-budget-usd 15`). Keystrokes there risk `Esc`-interrupting a
   live review in a repo this thread must not touch, and **C6's two-keystroke
   budget was already spent** by the supervisor. The fall-back to the durable
   file stands; leave it. A later session should re-check for **idle** before
   even considering it.

> **A trap while checking that:** `pgrep -af 'claude --print'` **self-matched**
> this session's own shell, exactly the failure mode the global instructions
> warn about. Harmless when listing, lethal when the next step is `kill` —
> which is the near-miss already recorded as **C6**. Verify ownership of a pid
> before acting on it, never just its pattern match.

**Before typing into ANY pane you do not own, check that harness's submit
idiom** — Claude Code's `Enter` does **not** submit in a Codex pane. See
correction **C6** in `supervisor-handoff.md`, and **stop after two failed
keystrokes**.

**THE SWEEP IS STILL UNEXHAUSTED — rung six was climbed TWICE, independently,
and NEITHER attempt was dry.** Six rungs now: thread files → ledger → repo
outside this thread → other tenants → other fleet repos → **rung six**, reached
by two sessions from different directions:

- **(a) this repo's own enforcement surface** — the worker's. Found
  `overseer-b4q` (below).
- **(b) the plugin CACHE, i.e. the generator that actually RUNS** — the
  supervisor's. Found that the running generator **contradicts itself**: its
  preconditions name a `codex` worker (`:90`, `:116`), then its send section
  hands over a Claude-only submit procedure (`:394`, `:396`, `:410`) with
  **zero** harness caveat. Recorded on **`overseer-816`**, with the reciprocal
  half on **`overseer-d4t`**.

They are **different rungs and both are kept** — collapsing them would hide
that neither session knew the other was climbing.

**RUNG SEVEN — climbed 2026-07-30, and it was NOT dry either.** It aimed one
layer above rung six (a): rung six looked at gates that *compute* a verdict,
rung seven at whether anything *consumes* it. It returned three things:

- **`overseer-rh1`** (new, P2). `check-branch-protection-alignment` downgrades
  "a CI leg is not in the required list" to a **warning, exit 0** — sound only
  under the single-gate model, where a required `ci-green` aggregate catches it
  anyway. **This repo does not run that model**: measured, `ci-green` is emitted
  but **not required**, while 56 individual contexts are; `ci.yml`'s own comment
  claims the opposite ("Branch protection requires ONLY this context"). The
  check never asks whether the model it assumes is the one in force, so it
  cannot fail in the one configuration where an unrequired leg is dangerous.
  Seven contexts run without gating anything. The detector itself is in the
  local aggregate (`justfile:195`) but **never runs in CI**.
- **An independent second-party verification of `overseer-b4q`** — all three of
  its claims reproduced by the supervisor separately from the worker who filed
  it. Recorded on the item, because a self-reported and an independently
  reproduced measurement are not the same strength of evidence.
- **One further instance of the class, committed while verifying the first** —
  the `PIPESTATUS`/zsh trap, now the first runnable reproduction of shared
  correction **C14** (see `.ai/supervisor-protocol.md`).

**RUNG SEVEN (b)** — the same layer, measured independently by the supervisor,
confirmed `ci-green` is absent from all 56 required contexts and added a worse
finding: `ci.yml:50-51` asserts *"verified live — zero rulesets,
required_merge_queue: null; branch protection requires only ci-green"*. **A
comment that asserts its own verification**, whose last clause is false — and
not uniformly false, which is what makes it dangerous: "zero rulesets" is TRUE
(independently confirmed here with a positive control), so two true clauses lend
credibility to the false third. `ci.yml:26-28` then justifies pinning `ci-green`
to `ubuntu-latest` "so the gate stays reportable host-down" — which **buys
nothing for mergeability**, since the 56 required contexts are the self-hosted
ones. Bounded honestly: **the fallback mechanism still works** (flipping
`CI_RUNNER_LABELS` reroutes the `check-*` jobs); what is broken is the recorded
*model of why*, and the harm is a reader concluding mid-outage that a green
`ci-green` means merges are fine. Appended to `overseer-rh1` rather than filed
separately — it is the same defect at a second site, and splitting one finding
across two items is forbidden. **Fix is maintainer-side**: factory branches must
not touch `.github/workflows/` (the rule is real, and lives in the
`check-no-workflow-edits` recipe — **not** in `.claude/CLAUDE.md`, whose only
"workflows" mention is about the E2E credential).

**RUNG EIGHT — DRY, and that is the result.** Scoped to
`tests/heading-coverage.json`, it returned only a confirmation of the
already-filed `overseer-knm` (23 stale rows, exactly) and **no new defect**. The
tempting finding — *a coverage gate certifying coverage that does not exist* —
**does not survive**: all 23 pointers resolve elsewhere (zero dangle), and the
gate resolves `test` node ids **only** for `scenarios.md` entries, of which the
23 include **none**. It behaves to contract. **Know what a check CLAIMS to
verify before concluding it fails to verify it.** Scope the dryness honestly:
one registry, not every coverage artifact.

So seven rungs returned something and the eighth did not — the first time this
ladder has met its own stopping rule. **That is not "finished"**; a narrow rung
is easy to make empty by choosing it narrowly. Widen before concluding.

**RUNG NINE did exactly that, and it was the most consequential rung of the
sweep.** It re-asked *rung seven's* question at **fleet scale** instead of
inventing a new one:

| repo | required contexts | `ci-green` required |
|---|---|---|
| `livespec`, `-dev-tooling`, `-runtime`, `-orchestrator-beads-fabro`, `-driver-claude`, `-driver-codex` | **1** each | **YES** |
| **`livespec-overseer`** | **56** | **NO** |
| `livespec-console` | *no branch protection at all (HTTP 404)* | — |

**Six siblings run the single-gate model exactly as `ci.yml` describes it. This
repo is the sole outlier.** That **reframes `overseer-rh1`**: the `ci.yml`
comment is **true of the fleet** and is inherited template prose — what drifted
is *this repo's configuration*. The primary defect is therefore **livespec-overseer
diverging from a fleet standard with nothing noticing**; the check's inability
to detect the outlier is the *secondary* one. It also sharpens the maintainer
decision from "pick a model" to "adopt the fleet standard (require `ci-green`,
drop the 56)", which additionally makes both false `ci.yml` comments true again.

`livespec-console` is recorded, **not diagnosed and not filed** — different
repo, different class, and filing it here would be a wrong-tenant record.

> **The transferable move: when a rung comes back dry, re-ask an earlier rung's
> question at a WIDER SCOPE before inventing a new question.** Rung eight's
> dryness was a symptom of how narrowly it was cut, not of an exhausted seam.

**`overseer-ya4` — root cause found, and it is now in the WRONG PLACE.** The
`worktree-create` failure is **not flaky**: measured back-to-back, stdout to a
**pipe** gives `rc=141` with **zero output and no worktree**, while stdout to a
**file** gives `rc=0` and a complete worktree. The pipe is the risk condition,
and the workaround needs no code change. **But `overseer-ya4` was closed at
14:09:56Z**, routed to `livespec-dev-tooling` as **`livespec-dev-tooling-zi4q`**
under route-by-owning-component, with the evidence carried verbatim — and that
evidence says *"flaky, 2 failures in 5 attempts"*, which this supersedes.
**The root cause was appended to the closed `overseer-ya4`, so it will not reach
`zi4q` on its own.** Forwarding it is a **cross-tenant write and a maintainer
call**; it was deliberately not done here, and not reopened either.

> **Rung six (b) also returned a REFUTATION, which is the more useful half and
> the part a future reader is most likely to get wrong.** The same sweep
> reported "8 bare `-t <…>` targets versus 0 exact ones **in what RUNS
> today**". It does not survive: that count came from
> `…/cache/…/efe607c6a3e7/`, a **2026-07-27 artifact**, one of **eleven**
> sibling cache dirs. The **live** dir is `013d35d48cde` — resolved from
> marketplace clone `HEAD` and independently confirmed by this session's
> `SessionStart` hook — and it is **byte-identical to master prose** (1 bare, 1
> exact). Charters emitted here today inherit the contradiction but **not** the
> bare-target defect.
>
> **The measurement had a correct positive control and was still wrong** — 291
> lines, 18 `tmux` hits, all true of the stale file. **A positive control
> proves the search reached content, not that it reached the RIGHT content.**
> Resolve *which* artifact is live before controlling for whether it is empty.
>
> It was also offered as confirming `overseer-d4t`'s stale-cache mechanism.
> Measured, it is a **negative** instance — the release had reached the cache
> the same day. Recording it as confirmation would have been a check that could
> only ever agree: **this thread's own defect, committed while sweeping for
> it.** `overseer-d4t` now carries that correction so nobody cites this sweep
> as support for it.

Rung six (a) aimed the carry-forward lesson back at our own gates and found
`overseer-b4q` above. Two notes on method, because the rung is repeatable:

- **What made it findable** was searching for the *shape* rather than the
  symptom — `git diff … -- <hardcoded path>` where an empty result takes the
  pass branch — not for anything about prose or releases.
- **One sibling was considered and deliberately NOT filed.**
  `check-no-workflow-edits` (`justfile:875`) has the identical shape against
  `.github/workflows`, but there emptiness *is* the intended success of a
  prohibition gate and the path is pinned externally by GitHub. Recorded so a
  later reader neither "fixes" it by symmetry nor reads its absence as an
  oversight. **A sweep that files everything shaped alike is the same defect
  in the other direction** — a check that cannot come back empty.

**The one thing to carry forward.** The classifier bug, the vacuous `git diff`,
the uncontrolled zero-hit grep, the under-scoped sweep, the cross-harness
keystroke, our **own required merge gate** (`overseer-b4q`), a **controlled
measurement of the wrong file** (rung six (b)), the `ls … | sort | tail -1` that
picked *lexically* and so captured a three-day-stale artifact, the
**merge-gate detector that warns instead of failing** (`overseer-rh1`), the
`${PIPESTATUS[0]:-$?}` guard that **reports success when the command it guards
failed** (C14's reproduction), and a **durable record left asserting a state
that had changed** — are all **the same defect**: *a check that cannot fail,
returning success.*

**Twelve instances.** The twelfth arrived *while recording the eleventh*, and it
is the cleanest specimen yet: a `bd update` whose note text was inlined into a
double-quoted **zsh** string containing backticked field names. zsh executed
them as command substitution, the words vanished from the record, and **`bd`
reported `✓ Updated issue` and exited 0.** The write genuinely succeeded — only
its *content* was wrong. A note about precise field references silently lost the
field references, and nothing in the success path could tell.

> **It was caught only by the mandated read-back**, which is the concrete
> justification for `overseer-1sv`'s rule. That rule was previously defended by
> the credential wrapper exiting 0 on a missing binary; here is a **second,
> independent mechanism with the same signature** — a successful write with
> wrong content. **Read-back is not belt-and-braces; it is the only step in the
> sequence that can fail.**
>
> **Reusable rule:** never inline note text into the shell. Write it to a file
> and pass `--append-notes "$(cat FILE)"` — command substitution yields the
> file's bytes literally and backticks inside are not re-evaluated. Every note
> in this thread written that way is intact; the one written inline is the one
> that broke.

But the count is not the useful part — **this is:**

> **The last six were committed *while deliberately sweeping for this exact
> defect*.** One had a correct positive control and still read the wrong file.
> One was a *safety* idiom (`:-`) that created the very silence it was written
> to prevent. One was the *detector* for the drift it failed to report. One was
> the sweep's own record contradicting the sweep's own result. One was a ledger
> write that reported success while dropping its own content. And two more were
> verification greps that reported `MISSING` for text that was present — a
> `case` arm that swallowed `supervisor-handoff.md` because it also ends in
> `handoff.md`, and an unescaped `**` read as a regex quantifier.
>
> **Those last two are the OPPOSITE polarity and are deliberately NOT in the
> count.** A check that falsely *fails* is loud and safe; this thread's defect
> is one that falsely *passes*. Counting them would inflate the tally with the
> safe direction — the same over-claiming this thread exists to police. They are
> recorded because they share the root cause: **the result was determined by an
> artifact of the check rather than by the thing measured.**
>
> **Knowing about this defect does not confer immunity to it**, and the people
> most exposed are the ones actively hunting it — **because hunting it means
> running more checks, and every check is a candidate.** That is why the count
> keeps growing, and it is stronger evidence than the count itself, because it
> explains the growth rather than merely tallying it. So the remedy cannot be
> vigilance; vigilance is what produced six of these. It has to be structural:
> **give the check a way to come back empty-handed and mean it**; — rung six
> (b)'s sharpening — **make sure it is looking at the right thing before you ask
> whether it came back empty**; and — rung eight's — **know what it claims to
> check before concluding it failed to.**

## Read-first chain

1. This file.
2. `research/misclassification-evidence.md` — what was MEASURED, what is
   RETRACTED, and the five questions, **all now ANSWERED** (they are no longer
   open; the note's own section carries the answers).

That is the whole chain. This file carries no checkbox queue.

**WORK-ITEM status is READ from the ledger, never stored here** — run
`/livespec-orchestrator-beads-fabro:list-work-items --json` and
`/livespec-orchestrator-beads-fabro:next`. The narrative state at the top of
this file describes **the investigation**, not a `WorkItemStatus`; do not read
it as one, and do not skip the ledger because of it. Both `overseer-dtytju`
(the epic) and `overseer-fs4` (the orchestrator-side re-dispatch gap) live
there.

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

**Upstream port, measured — AS OF `upstream/main` @ `854f71f2c`, 2026-07-29.**
`upstream/main` is a **moving ref and it has since moved**: as measured
read-only by the supervisor 2026-07-30, fabro's local `main` now tracks it at
`b5885b15d`. So the "5 of 6" below, and the 357-line divergence above, are
**as-of results against `854f71f2c`, not current facts** — re-measure against
the live tip before relying on either. The *conclusion* (the defect is present
upstream unchanged) rests on the hint, the order and the pinned test, none of
which is a line-count, so it is not disturbed by upstream advancing.

5 of 6 hunks apply to
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

## Acceptance — MET, but NOT general coverage

**Read this first.** Acceptance is met for the payload the RED test was built
against (the monthly spend cap) and for the registry-path false positive
generally. It is **not** met for provider limit failures **as a class**: a
second phrasing — *"You've hit your limit · resets Jul 31, 5am (UTC)"*,
measured 2026-07-30 in a sibling repo — matches **none** of the hint lists,
including the fix's own `PERMANENT_PROVIDER_LIMIT_HINTS`, and falls through to
the signature-tracked `Deterministic` fallback. That is the outcome part (a)
exists to prevent, so **(a)'s rationale does not hold for that payload**; (b)
remains correct for both. Details and the open design question are in the
research note under "A SECOND limit payload". **Do not read "acceptance MET" as
"provider limits are classified correctly".**

- **RED first:** `cargo test -p fabro-workflow --lib error::` → 151 passed,
  **3 failed** against the unmodified classifier, one of them on the verbatim
  `01KYQF8G2TNV` payload.
- **Green without weakening:** 1007 passed, 0 failed; `fmt` and
  `clippy --workspace --all-targets -D warnings` clean. Diff is **165
  insertions, zero deletions** — nothing deleted, loosened or `#[ignore]`d, and
  the three hint-count guards stay at 38/12/3.
- **Landed on a branch:** `fix/classify-provider-spend-limit-not-transient`, a
  single commit on top of `d5dcd1179`. **Unpushed.**
  **The BRANCH NAME is the durable identifier — do not cite the SHA as one.**
  An earlier version of this line named commit `a7c42204b`; that SHA is **dead**.
  Measured read-only by the supervisor 2026-07-30, the head is now `b46a4f387`
  — same subject, same author date, still one commit whose parent is still
  `d5dcd1179`, i.e. the owning session **re-committed** rather than added, which
  is what a session revising under adversarial review does. Treat any SHA here
  as **mutable**. The base `d5dcd1179` is still accurate (still `HEAD~1`).
  Also measured then: fabro's `main` has **moved** off `d5dcd1179` to
  `b5885b15d`, tracking `upstream/main` — so branch and `main` are now
  deliberately diverged, and the outstanding hunk-3 port against
  `lib/components/` is **testable locally** in a way it previously was not.

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
