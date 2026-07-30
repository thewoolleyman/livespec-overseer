# Plan — codex-parity-and-rollout-safety

> # ▶ RESUME HERE — session handoff, 2026-07-30
>
> **A1 and A2 are both DONE. A2 landed through the FACTORY — PR #308, merge SHA
> `dd423a38`, post-merge janitor green, all three files verified on
> `origin/master`. The billing-cap diagnosis is CONFIRMED BY THE FIX: A2 passed
> `review` on the first dispatch after the maintainer rotated
> `CLAUDE_CODE_OAUTH_TOKEN`, having failed three times before it on that same
> node. The credential map now lives in `.claude/CLAUDE.md` §"The fleet has
> SEVERAL Anthropic credentials" — CITE it, do not restate it here.**
>
> **A2's LIVE bar was then exercised (2026-07-30): `supervise-plan` PASSES
> resolve+execute+run; `overseer` does NOT, and NOT for the reason this file
> predicted — see the ⛔ box in §"A2's live acceptance". `overseer-start` is not
> on PATH outside this repo, which makes that half of the bar unsatisfiable by
> EITHER harness and reframes A4.**
>
> > ## ▶▶ START HERE — state at 2026-07-30 session end. This block WINS over anything below it.
> >
> > **A4 IS DONE AND MERGED. Nothing is dispatchable — every remaining local
> > slice sits behind `admission:manual`, a policy-required human valve. Ask the
> > maintainer for admission FIRST; do not admit anything yourself.**
> >
> > ### Ledger, read back 2026-07-30
> >
> > | slice | id | state |
> > |---|---|---|
> > | **A4** | `overseer-ews` | **Code DONE** — PR **#347**, commit `8bd5b91` verified on `origin/master`. Ledger reads **`READY`** (a phantom claim was released; nothing is in flight). Acceptance verified: runtime check **ADMITTED-TO, not dropped** (`_CODEX_AGENT_COMMS={codex,codex-acp}`, walking **process ancestry**); tests **EXTENDED not loosened** (originals kept, three added, one gating the `$CLAUDECODE` leak). **Its LIVE bar is UNPROVEN** — see A6. |
> > | **A6** | `overseer-g6z` | **NEW.** `pending-approval`, `admission:manual`, `rank: a6`. Carries the revised PATH fix (1+3 together). **This is what blocks A4's live bar.** |
> > | **A5** | `overseer-ei3` | `pending-approval`, `admission:manual`, `rank: a5`. Version-lockstep fix **+ a check that goes RED**. Advisory `relates_to` A2, **no blocking edge** (deliberate — it must not stall A4/A3). |
> > | **A3** | `overseer-kju6wh` | `pending-approval`. **Correctly NOT dispatched.** Flipping `harnesses.codex` to `supported` while `overseer` cannot launch from another repo is the claim-a-capability-that-does-not-exist failure the A1/A3 split exists to prevent. **Hold that line.** |
> > | `overseer-oj8` | — | CLOSED, superseded by `overseer-ei3`. **Pointer IS intact** (`metadata.superseded_by` + a 738-char `close_reason`). The record has **no top-level `superseded_by`/`reason` field**, so a reader asking for those keys gets `None` — that is a READER bug, not a lost pointer. **Do not "repair" it.** |
> >
> > ### Why A4's live bar fails — MEASURED, do not re-derive
> >
> > On release 0.15.0, `env -u CLAUDECODE`, real Codex session in another repo:
> > `resolve=PASS, execute=PASS, run=FAIL(exit 1)` with the fix's OWN diagnostic —
> > `overseer-start executable not found; tried $PLUGIN_ROOT/../overseer/overseer-start and PATH`.
> > The failure MOVED from exit 127, so candidate 3 **did** run.
> >
> > **Root cause:** `$PLUGIN_ROOT` is the materialized contents of `.claude-plugin/`,
> > so `$PLUGIN_ROOT/../overseer/` **does not exist** — the codex cache materializes
> > only the plugin root, never the `overseer/` package. Explicit resolution cannot
> > find a file that was never shipped.
> >
> > **MEASURED, not assumed:** a launcher copied ALONE into a simulated plugin root
> > **fails** — `ModuleNotFoundError: No module named 'overseer'` — when run with cwd
> > **outside** the repo. (Run with cwd *inside* the repo it appears to work; that is
> > a **cwd confound**, not a result.) **The cache needs the PACKAGE too.**
> >
> > **Packaging facts (a citation I got WRONG and corrected):** `pyproject.toml:270`
> > is **`[tool.pyright]`**'s include, NOT packaging — that wrong citation is still
> > embedded in `overseer-g6z`'s description and should be fixed to **line 344**
> > (`[tool.setuptools.packages.find] include = ["overseer*"]`). Further:
> > `[tool.setuptools.package-data]` declares **only** `overseer = ["version.json"]`,
> > so the extensionless launchers are **not shipped as files** — delivery is via
> > `[project.scripts]` console-script entry points. **There is no packaged launcher
> > artifact to duplicate**, which is why the recommendation is a **packaging step**
> > over a copied shim (the copy also inherits a `uv`-via-mise-shim PATH fragility).
> >
> > ### Proven this session, so you need not redo it
> >
> > - **Negative half PROVEN on the post-A4 build, locally**: a plain shell with
> >   BOTH `$CLAUDECODE` and `$TMUX_PANE` unset refuses, **exit 1**, with A4's new
> >   message *"no supported agent runtime in process ancestry"*.
> > - `supervise-plan` PASSES resolve+execute+run, re-verified free of the
> >   `$CLAUDECODE` leak confound.
> > - **A2's agent-skill-list evidence pre-discharges NO part of A3** (different
> >   surface: A3's bar is TUI `/skills` picker rendering). Hold this guard.
> >
> > ### ⛔ RETRACTED: the "byte-identical to upstream" claim — ✅ NOW APPLIED
> >
> > **Both corrections below were APPLIED to the body on 2026-07-30** (see
> > §"Why this cost a whole session"). Nothing is left to do here; the box is kept
> > because the reasoning error is the instructive part, not the edit.
> >
> > **It was FALSE — deleted, not merely ref-pinned.** Measured at pinned refs
> > with the correct path on both sides (`lib/components/…/error.rs`): fork
> > `49b043c1a` 87,769 bytes vs upstream `4ab090cae` 67,441 bytes, **484 differing
> > lines**. It was asserted three times on three vacuous checks — a diff of a path
> > that does not exist upstream, then a diff of **two 0-byte files**, then a stale
> > fork-side path after the fork also relocated to `lib/components/`. Each time an
> > empty result was read as agreement.
> >
> > **The CONCLUSION still stands** — the defect is upstream's, unmodified — but on
> > the peer thread's evidence instead: hint present at upstream `:79`, same
> > first-match-wins ordering, same pinned test `classify_reason_index_crates_io` at
> > upstream `:1654`. **Never restate identity for a file under active divergence**;
> > those refs moved three times in two days. The nearby claim that the
> > orchestrator's `workflow.fabro` "only CONSUMES the category" was corrected in
> > the same pass — **nothing** consumes it (filed `overseer-fs4`).
> >
> > ### Pending maintainer/supervisor decisions — the actual blockers
> >
> > 1. **Admission for `overseer-g6z` and `overseer-ei3`** (both `admission:manual`).
> > 2. Correcting the `pyproject.toml:270` → 344 citation inside `overseer-g6z`.
> >
> > A tracked-file/worktree prohibition was in force at session end for everything
> > except this handoff; it lapses with that session.
>
> A3 waits on A4; the order is A4 → A6 → A3.
> Everything below this box is older
> context that is still accurate unless this box contradicts it.**
>
> ## Slice state, read from the ledger 2026-07-29
>
> | slice | id | state |
> |---|---|---|
> | **A1** | `overseer-4km4mj` | **DONE / CLOSED.** PR **#242** merged, `ee67267e…`, verified an ancestor of `origin/master`. Content verified: `.livespec.jsonc` keeps `status: "exempt"` with a `reason` naming brief 17 **and** the archived ruling path; the stale `check-plugin-resolution` justfile comment is corrected. Maintainer accepted it through the `ai-then-human` valve; I relayed that decision, I did not self-accept. |
> | **A2** | `overseer-vyie5q` | **DONE / CLOSED 2026-07-30.** Landed through the factory: PR **#308**, merge SHA `dd423a38a094c865d752dd87e8ce2abb0c274ff9`, post-merge janitor green, `resolution:completed`. All three nested files verified present on `origin/master` — **but NOT yet on `origin/release`** (release-please PR #244 `release 0.14.0` open at time of writing), which is what a `--ref release` marketplace fixture pulls. Its STRUCTURAL acceptance is fully met; its LIVE acceptance is **half proven** — see the ⛔ box in §"A2's live acceptance". |
> | **A4** | `overseer-ews` | **NEW, filed 2026-07-29** at maintainer direction — `pending-approval`, `admission:manual`, `rank: a4`. Make `overseer-start` launch under Codex WITHOUT weakening the stray-hand-run refusal. See §A4 below. |
> | **A3** | `overseer-kju6wh` | `pending-approval`, `admission:manual`. Blockers: A1 (done) + A2 (open) + **A4 (open, new)**. **Do not start until A2 AND A4 land** — see §A4 for why that ordering is correct on the merits, not merely wired. |
> | **A5** | `overseer-ei3` | **NEW, filed 2026-07-30** — `pending-approval`, `admission:manual`, `rank: a5`. **Version lockstep is BROKEN and enforced by nothing:** sibling `.claude-plugin/plugin.json` is **0.14.0** while nested `.codex-plugin/plugin.json` is **0.13.3**, on BOTH `origin/release` and `origin/master`. A2 shipped them aligned at 0.13.3; the release-please 0.14.0 bump updated the sibling only. Two required parts: (a) make release automation bump the nested manifest; (b) **add a check that goes RED when lockstep breaks** — acceptance is a RED demo. Dep shape: an **advisory `relates_to`** to A2 and **no blocking edge**, because the defect is independent of A4's PATH/marker work and A3's picker check; a blocking edge would stall two admitted slices for an unrelated bug. |
> | **B2** | `overseer-vfz5v5` | `pending-approval`, `admission:manual`. **STOOD DOWN** — blocked on B1, which livespec-dev-tooling owns. Not this thread's to implement. |
> | **B1** | `livespec-dev-tooling-3nt9` | filed in **livespec-dev-tooling**, `backlog`. Never implement here. |
> | **C1** | `livespec-1p31` | filed in **livespec** core, `backlog`. Never implement here. |
>
> ## ✅ THE A2 BLOCKER — DIAGNOSED 2026-07-29, RESOLVED 2026-07-30. Kept as the evidence trail.
>
> > **RESOLVED. Do not re-investigate.** The maintainer rotated
> > `CLAUDE_CODE_OAUTH_TOKEN` (a `claude setup-token` re-mint from a healthy org);
> > the validated probe returned **200**; A2 was dispatched and **passed `review`
> > on the first attempt**, landing PR #308. Three failures before the rotation,
> > success immediately after it, same node — **the billing-cap diagnosis is
> > confirmed by the fix, not merely by the error text.**
> >
> > **The credential map is now OWNED BY `.claude/CLAUDE.md`** §"The fleet has
> > SEVERAL Anthropic credentials — probing the wrong one is the documented
> > failure mode". **Cite it; do not restate it per thread** — that file says so
> > explicitly, and the duplication it warns about is what cost two dispatches
> > (`bd-ib-g56f`). The one validated probe, and the two documented false
> > positives (`ANTHROPIC_API_KEY_LIVESPEC_E2E`, interactive `claude -p`), live
> > in `plan/background-shell-supervision-liveness/handoff.md` §"Gate 4".
> >
> > Everything below is the original evidence trail, kept because the REASONING
> > is what generalizes: read the failure TEXT, not just the failure; a probe on
> > the wrong credential returns 200 while the adapter is hard-blocked; and
> > `fabro inspect` → `node_outcomes.<node>.failure.causes[]` carries provider
> > text that `fabro logs` and `fabro events` do NOT.
>
> > **⚠ CURRENCY WARNING, added 2026-07-29 ~19:15Z — READ BEFORE ACTING ON THIS
> > SECTION.** Everything below is a MEASUREMENT and it stands as one: at
> > **17:44Z** a run WAS created, `implement` succeeded, and Anthropic returned
> > the spend-limit error to `review`. That happened; it is not an inference.
> >
> > **But the spend cap may no longer be the FIRST gate.** A sibling thread,
> > `plan/supervisor-prompt-quality/handoff.md`, records that by **~19:01Z** a
> > re-dispatch was failing EARLIER — at **run-config-overlay, with
> > `fabro_run_id: null`**, on the **host Codex credential**
> > (`codex-cred-refresh` returns `noop-not-due`, so the automated path cannot
> > fix it). No run is created, so **the cap is never reached and never tested**:
> > the spend limit's CURRENT status is **UNVERIFIED, not cleared.**
> >
> > So do not read this section as "go raise a spend limit" without first
> > checking whether dispatch even reaches a run. That sibling thread is
> > authoritative on the Codex-credential gate; this thread is authoritative on
> > what `review` returned once a run existed. **Both are true at different
> > times, and neither refutes the other.**
> >
> > Two consequences worth carrying:
> > - **A dispatch that fails at run-config-overlay STILL CLAIMS the item**, with
> >   `fabro_run_id: null`. So a `ready` → `ACTIVE` transition is NOT evidence
> >   that a run exists. Read back status AND assignee AND `fabro ps`.
> > - Run `01KYP93877SD` went **terminal** and is not resumable, so any advice
> >   about resuming parked runs does not apply to it.
>
> **Root cause: the Anthropic credential behind the factory's `review` adapter
> has exhausted its org monthly spend limit.** The provider says so verbatim in
> every failed run:
>
> ```
> Internal error: You've hit your org's monthly spend limit · ask your admin
> to raise it at claude.ai/settings/usage        { "errorKind": "rate_limit" }
> ```
>
> **It is not repo-specific, not A2-specific, and not transient.** Measured
> across FIVE runs, TWO repos and FOUR work-items — every one dies at `review`:
>
> | run | repo / item | provider message |
> |---|---|---|
> | `01KYP4WDAT4R` | this repo, **A2** | org monthly spend limit |
> | `01KYP9Z87QC3` | this repo, **A2** | org monthly spend limit |
> | `01KYP8NDW1NF` | this repo, `overseer-4xfmez.2` | org monthly spend limit |
> | `01KYP93877SD` | this repo, `overseer-t7qqik` | org monthly spend limit |
> | `01KYP37TZJ9M` | **`livespec-console-beads-fabro`** | `You've hit your limit · resets Jul 31, 5am (UTC)` |
>
> ### ⚠ RETESTED AFTER THE MAINTAINER RESTORED QUOTA — STILL FAILS, AND THAT RE-CONFIRMS THE CAUSE
>
> The maintainer confirmed quota restored on 2026-07-29 and released the hold.
> A2 was re-dispatched: run **`01KYQF8G2TNV`**. **Review failed again**, and the
> supervisor had pre-declared that an identical failure "would disprove the
> spend-limit diagnosis". **It does not — read the failure text, not just the
> failure.**
>
> The error is NOT a generic `ACP turn failed`. At **17:44, AFTER the
> restoration**, the provider still returns verbatim:
>
> ```
> Internal error: You've hit your org's monthly spend limit · ask your admin
> to raise it at claude.ai/settings/usage        { "errorKind": "rate_limit" }
> ```
>
> If the diagnosis were wrong, that message would have disappeared when quota
> returned. Instead Anthropic restates it. **So the DIAGNOSIS is re-confirmed and
> the PREMISE is disproven: the raise did not reach the credential the review
> adapter resolves.**
>
> The same run proves the credential boundary a second time, in one sandbox at
> one moment: `implement` (Codex adapter) **succeeded in ~5 min**; `review`
> (Claude adapter) **failed in 13.2s, then 7.8s on retry**.
>
> ### WHICH ACCOUNT IS CAPPED — traced end to end 2026-07-29
>
> **Corrects a weaker claim made earlier in this same session.** An initial pass
> reported "there is NO Claude auth injection step". That was wrong as stated:
> there is no *setup command* for it (Codex gets a visible
> `printf %s "$CODEX_AUTH_JSON" > $CODEX_HOME/auth.json` step, which is why only
> Codex is greppable in the event log), but there IS an env-table projection.
> The corrected chain makes the lead STRONGER and far more specific:
>
> 1. The dispatch target's **`credential_wrapper`** — here
>    `1password-env-wrapper/with-livespec-env.sh` — injects
>    **`CLAUDE_CODE_OAUTH_TOKEN`** into the Dispatcher's process environment.
>    Confirmed present 2026-07-29 (value withheld).
> 2. The Dispatcher projects it into the per-run UNCOMMITTED overlay
>    `[environments.<id>.env]` (`_dispatcher_overlay.py:218`), mode 600, deleted
>    when the run returns (`dispatcher.py:65-83`). The committed config carries
>    no secret value and no `{{ env }}` interpolation — interpolation provably
>    CANNOT deliver credentials to server-mediated runs, so do not re-attempt it.
> 3. The sandbox's `review` adapter (`claude-agent-acp`) authenticates with that
>    token.
>
> **So the capped account is whichever Anthropic account owns the 1Password-stored
> `CLAUDE_CODE_OAUTH_TOKEN` — a fleet/service credential, which is NOT necessarily
> the interactive claude.ai account a maintainer would raise a limit on.** That is
> the single thing to verify before spending another dispatch; a further attempt
> against the same credential dies in ~13 seconds. (Note the wrapper also carries
> a separate `ANTHROPIC_API_KEY_LIVESPEC_E2E`, so more than one Anthropic
> credential exists in this fleet — raising the wrong one is an easy mistake.)
>
> Note also that **at least TWO distinct limits** are in play across the fleet's
> runs — the org monthly spend cap (four runs) and a rolling
> `resets Jul 31, 5am (UTC)` limit (the console run). Raising one clears neither
> the other nor a different account.
>
> **A2 is left `ACTIVE` / `Assignee: fabro`** with `01KYQF8G2TNV` parked at a
> Needs-human gate. Note that `drive` printed `status: failed` while the claim
> DID take — the "verify the CLAIM, not the command" rule below fired again, and
> reading the ledger is what caught it.
>
> **Why `review` and never `implement` — by design, not coincidence.**
> `workflow.fabro:124`: the review node *"runs on the Claude subscription via the
> `review_adapter` input"* (`ANTHROPIC_MODEL=claude-opus-4-8[1m] …
> claude-agent-acp`), while `implement` runs on Codex
> (`@zed-industries/codex-acp`) — a DIFFERENT provider on a DIFFERENT credential.
> So `implement` completes normally and `review` dies on contact. **Any run in
> any repo that reaches `review` fails identically.**
>
> **THE FIX IS IN NO REPO.** A maintainer must raise the limit at
> claude.ai/settings/usage. Until then no Fabro run in the fleet passes review,
> and **re-dispatching A2 only burns a cap slot and an `implement` run.**
> Separately the blocked runs above sit at "Needs human" gates **holding the host
> dispatch cap** (default 2), so slots must be cleared too — those belong to
> OTHER tracks, so do not answer their gates on their behalf.
>
> ### Two claims from the previous handoff, corrected by measurement
>
> - **The durations were never evidence of anything.** The review STAGE failed in
>   **5.77s** (attempt 1) and **4.69s** (attempt 2). The 61m39s / 7m30s figures
>   were TOTAL RUN durations dominated by `implement` (374s in the short run).
>   This is the measurement that independently confirms the TTL retraction —
>   **run duration correlates with nothing.** The `bd-ib-2nq` token-TTL
>   attribution is dead; do not revive it.
> - **`max_retries` on `review` is 1, not 0.** The GRAPH default is `0`
>   (`workflow.fabro:49`) but the review node OVERRIDES it — `max_retries=1`
>   (`workflow.fabro:141`) — and the events show a real auto-retry
>   (`stage.retrying`, 3191ms delay, attempt 2). Two attempts, not one. It
>   changes nothing: no retry count clears a spend cap. "Retrying is known not to
>   work" STANDS, and is now EXPLAINED rather than merely observed.
>
> ### Why this cost a whole session: `transient_infra` is a false positive on a FILENAME
>
> `classify_failure_reason` (fabro `lib/crates/fabro-workflow/src/error.rs:159`)
> substring-matches the rendered message against `TRANSIENT_INFRA_HINTS` (`:44`).
> Simulated over the exact failure strings, **exactly one hint matches**:
>
> ```
> TRANSIENT hits: ['index.crates.io']        BUDGET hits: []
> ```
>
> It matches the ACP payload's `spawned_at` field —
> `/home/ubuntu/.cargo/registry/src/index.crates.io-…/session.rs:567:14`. That
> hint exists to catch crates.io REGISTRY OUTAGES during toolchain builds
> (upstream's own test asserts on `"failed to fetch index.crates.io"`); here it
> matches a Rust source path in a stack annotation and says **nothing** about the
> failure. Note also that `"rate_limit"` (underscore, as sent) does NOT match the
> `"rate limit"` (space) hint, and `"monthly spend limit"` matches nothing in
> `BUDGET_EXHAUSTED_HINTS` (`:85`) — and transient is tested BEFORE budget, so a
> path-embedded hint outranks a genuine budget signal. Absent the false positive
> the string would classify `Deterministic` (non-retryable, escalate at once) —
> better than today's behavior; `BudgetExhausted` would be semantically right.
>
> **Ownership: this is fabro's, NOT the orchestrator's.** The defect is
> upstream's, unmodified in the fork — evidenced by the CODE, not by file
> identity: the `index.crates.io` hint is present at upstream `error.rs:79`, the
> same first-match-wins ordering applies, and upstream pins the behavior with
> `classify_reason_index_crates_io` at `:1654`.
>
> > **A byte-identity claim used to stand here and it was FALSE — do not restore
> > it in any form.** Measured at pinned refs with the correct path on both sides:
> > fork `49b043c1a` 87,769 bytes vs upstream `4ab090cae` 67,441 bytes, **484
> > differing lines**. It had been asserted three times on three vacuous checks
> > (a path absent upstream, then two 0-byte files, then a stale fork-side path),
> > each empty result read as agreement. The file is under active divergence and
> > its path moved three times in two days, so **identity is not a claim this
> > record can carry.** The ownership conclusion is unchanged; only its evidence is.
>
> **And the orchestrator does not "merely consume" the category — NOTHING
> consumes it.** Measured repo-wide 2026-07-30 across 2685 `.py` files with a
> positive control proving the search reaches real code: `failure_categ`,
> `transient_infra`, `budget_exhausted` and `node_outcomes` all return **zero**
> hits. What acts on the category is fabro's own node-retry layer. The
> consequence is a second defect, filed as **`overseer-fs4`** (P2, this tenant,
> `backlog`): a run that dies on a PERMANENT cause is re-dispatched exactly like
> a network flake, burning a host dispatch cap slot per retry. It is **not ready
> to work** — gating on a category is meaningless until a trustworthy one exists,
> which is the fabro-side fix below.
>
> `fabro` has **no beads tenant**
> (`/data/projects/fabro/.beads` does not exist) and **the fork has GitHub issues
> DISABLED**, so the previous handoff's instruction to "file it in the
> orchestrator tenant" was both unexecutable and a misfiling. Supervisor ruled
> 2026-07-29: file it against the fabro code, do NOT mint a tracking bead in
> another repo's tenant, because that just splits the record.
>
> **A2 itself is clean** — read back 2026-07-29: `READY`, no assignee. Nothing
> about A2 or this repo needs fixing; it waits on the spend limit alone.
>
> ## §A4 — `overseer-ews`, filed 2026-07-29: goal 2's bar was EXPANDED, not narrowed
>
> The `overseer` operation refuses under Codex **by design** — `overseer/start.py:94`
> gates on `$CLAUDECODE`. Given that finding, the maintainer chose **"make the
> daemon work under Codex"** over accepting a split acceptance bar. So the bar
> below §"A2's live acceptance" — which caps `overseer` at *"resolves, executes,
> then emits its documented refusal"* — **is superseded for goal 2's purposes.**
> The `overseer` operation must GENUINELY RUN under Codex. (That older paragraph
> still correctly describes A2's OWN bar: A2 ships bindings, not a runtime.)
>
> **It is much smaller than it sounds — a `start.py` slice, not a daemon rewrite.**
> The WATCHING half is already runtime-uniform and must not be rebuilt:
> `overseer/codex_sessions.py` already exists and is already wired;
> `_supervisor_discovery.py:137-152` routes BOTH runtimes through ONE path;
> `claude_sessions` and `codex_sessions.map_codex_sessions` emit the SAME shape;
> `resolve_tmux_session` is already runtime-agnostic; the
> pid → `/proc/<pid>/fd` → rollout filename → `session_index.jsonl` → `thread_name`
> join was verified live 2026-07-16. **The daemon's adoption side needs NO change.**
> `grep -rln CLAUDECODE overseer/` returns exactly TWO files — `overseer/start.py`
> and `overseer/AGENTS.md`. Only the LAUNCH half is missing.
>
> **The refusal is admitted-to, never removed.** A hand-run from a plain terminal
> must still fail loudly. `test_overseer_start.py:22-39` pins it and must be
> EXTENDED, not loosened: keep "plain terminal refuses", add "Codex runtime
> accepted", add "still refuses when NEITHER marker is present". The Codex-side
> marker is to be determined **at implementation time from live evidence**, not
> guessed. `$TMUX_PANE` stays "the ONE authority" for the tmux check — do not add
> a second. Sweeping `overseer/AGENTS.md` and `prose/overseer.md` step 0 is part
> of the slice, since both become FALSE once the behavior changes.
>
> ### ✅ A4 marker research — ANCESTRY NOW DISCHARGED LIVE (2026-07-30)
>
> > **The live evidence the section below said it lacked now exists.** Measured
> > against a real `codex` TUI (tmux `codex-live-probe`, cwd `/data/projects/openbrain`):
> >
> > ```
> > walking UP from a real descendant:
> >   node-MainThread  ->  codex  <== FOUND  ->  bun  ->  zsh  ->  tmux: server
> > ```
> >
> > **`comm == "codex"` is encountered BEFORE `bun`.** So for A4's SELF-detection
> > (an upward walk from the invoked process), finding `comm == "codex"` in your
> > own ancestry **IS sufficient**. The rollout-fd discrimination
> > `codex_sessions.py` needs exists to exclude `bun` when scanning OUTWARD
> > across all processes, where it is a sibling candidate — it is **not** needed
> > for an upward self-walk. **The caveat in the section below was right to raise
> > and WRONG in its conclusion**; corrected here rather than deleted, because
> > the reasoning error is the instructive part.
> >
> > **`$TMUX_PANE` is present** in the codex pane (`TMUX_PANE=%115`,
> > `TMUX=/tmp/tmux-1000/default,564588,111`), so `start.py` step 1's existing
> > check works under Codex and **A4 must NOT add a second tmux authority.**
> >
> > **~~NEW CAVEAT, still UNPROVEN~~ — NOW DISCHARGED, 2026-07-30.** One codex
> > child (pid `3175932`) had a sanitized 12-entry env with no `TMUX*`, which
> > raised the question. **Measured directly: a codex-spawned SHELL DOES inherit
> > `TMUX_PANE`** (`TMUX_PANE=[%90]`, matching the launching pane). That
> > sanitized child was an outlier node subprocess, **not** the shell path. So
> > `$TMUX_PANE` is reliable under Codex and A4 needs no second tmux authority —
> > confirmed, not inferred.
> >
> > ### ⚠ AND A FALSE-ACCEPT PATH IN THE CURRENT GATE — measured 2026-07-30
> >
> > **`$CLAUDECODE` LEAKS into a Codex session launched from inside a Claude Code
> > session.** Measured both ways:
> >
> > | topology | `CLAUDECODE` |
> > |---|---|
> > | `codex exec` spawned from Claude Code's Bash tool | **`1`** — inherited |
> > | genuine standalone codex (pid `3167772`, tmux, not under Claude Code) | **absent** (54 env entries) |
> >
> > So `start.py:94` as written would **spuriously PASS under Codex-nested-in-
> > Claude-Code**, misidentifying the runtime. The gate is correct for a *plain
> > terminal* and correct for a *standalone* Codex session; it is wrong for the
> > nested case.
> >
> > **This is a design constraint on A4, not a curiosity: do NOT simply OR-in a
> > second env marker.** Env markers are **inheritance-spoofable**, so any
> > env-only scheme inherits this same false-accept. Process ancestry
> > (`comm == "codex"`) is truthful in BOTH topologies — in the nested case
> > ancestry correctly reports Codex while `CLAUDECODE` lies. **That is a
> > correctness argument for the ancestry route, not merely a convenience one.**
> >
> > ### The two `overseer` failures are INDEPENDENT — proven 2026-07-30
> >
> > With PATH resolved (repo `.venv/bin` prepended) **and** `CLAUDECODE` stripped
> > (`env -u`, simulating a genuine standalone Codex session), `overseer-start`
> > emits its **documented refusal verbatim**:
> >
> > ```
> > overseer-start: this is the /overseer skill's bootstrap, not a standalone
> > command. … Refusing to run outside Claude Code ($CLAUDECODE unset).
> > ```
> >
> > So this file's ORIGINAL prediction was **right about the refusal** and only
> > wrong about **reachability** — PATH fails first and hides it. **Once PATH is
> > fixed, the remaining A4 work is exactly the marker admission, nothing more.**
> > That is a smaller and better-defined scope than "A4 does not address this"
> > alone implies.
> >
> > ### ⚠ METHODOLOGICAL CAVEAT — `codex exec` MISREPORTS EXIT STATUS
> >
> > In that run `codex exec` reported **`EXIT=0`** for the refusal. **That is
> > wrong.** Run directly, `overseer-start` exits **1**, and `start.py:103` is
> > literally `return 1`. The code is correct; the harness misreported it. (A
> > suspected guard-exits-0 defect was raised and RETRACTED on this check —
> > recorded because verifying before reporting is what kept a non-defect out of
> > the ledger.)
> >
> > **This directly threatens A4's RED proof.** A4 must *"prove a bare terminal
> > STILL refuses"*. Anyone verifying that **through `codex exec` must NOT trust
> > its reported exit code** — assert on the stderr refusal TEXT, or run the
> > command directly. Trusting `EXIT=0` there would silently INVERT the RED
> > proof: a working refusal would read as a non-refusal.
> >
> > ### The PATH gap's exact mechanism, for whoever scopes the fix
> >
> > `overseer/overseer-start` IS a file in the repo (executable, shebang) and
> > `pyproject.toml:270` includes it in the package — **but the codex plugin cache
> > root does NOT ship it**, because the plugin root is `.claude-plugin/` and the
> > `overseer/` package lives outside it. `prose/overseer.md:172` instructs a
> > **bare `overseer-start`**, i.e. a PATH lookup that only resolves when this
> > repo's `.venv/bin` is active.
> >
> > Three candidate fixes, **listed not chosen** — the scope call is the
> > maintainer's/supervisor's:
> > 1. ship the executable inside the plugin root;
> > 2. install the console script globally at provisioning time;
> > 3. have the prose resolve the executable explicitly, mirroring how the codex
> >    binding already resolves `$PLUGIN_ROOT` — **the fleet-consistent shape**.
> >
> > **AND THE BIGGER ONE — see the ⛔ box in §"A2's live acceptance":**
> > `overseer-start` is not on PATH outside this repo, so under Codex in another
> > repo the bootstrap dies at **exit 127 before any marker check runs**. A4 was
> > scoped around admitting a runtime marker; **PATH precedes that**, and A4 as
> > written does not address it.
>
> ### A4 marker research — the original LEAD, kept for its reasoning
>
> The slice mandates determining the Codex-side marker **at implementation time
> from LIVE evidence**. No Codex session was running during this session, so the
> following is **static binary evidence only** and does NOT discharge that
> requirement. Recorded so the implementer starts ahead, not so they skip the step.
>
> Measured against the vendored native binary (`codex-cli 0.145.0`,
> `vendor/x86_64-unknown-linux-musl/codex/codex`): the only `CODEX_*` names
> present are **`CODEX_HOME`**, `CODEX_POWERSHELL_PAYLOAD`,
> `CODEX_MANAGED_CONFIG_PATH`, `CODEX_GITHUB_PERSONAL_ACCESS_TOKEN`. There is
> **no `CODEX_SANDBOX`, no session-id marker, and nothing analogous to
> `$CLAUDECODE`.** So the tempting assumption — "find Codex's equivalent env
> flag" — may have NO answer, and an implementer who assumes one exists can burn
> a lot of time.
>
> Two candidate routes, with their weaknesses stated:
>
> 1. **`CODEX_HOME` presence** — weak. It is user- and wrapper-settable, and the
>    Fabro sandbox sets it explicitly, so it would admit non-Codex contexts.
> 2. **Parent-process-chain `comm == "codex"`** — stronger, and it reuses machinery
>    this repo already has and already verified live on 2026-07-16:
>    `codex_sessions.py` defines `CODEX_COMM = "codex"` for exactly this identification.
>    **Caveat that must be checked live:** `codex` on PATH here is a bash wrapper that
>    `exec`s `bun`, and `codex_sessions.py:80-83` records that the `bun` process is the
>    codex process's PARENT — so the ancestry a child observes needs verifying, not assuming.
>
> Whichever route is taken, the slice's constraint is unchanged: **admit Codex as a
> second valid runtime, never drop the runtime check**, and prove a plain terminal
> with neither marker still refuses.
>
> ### The dependency shape used, and why the work ORDER changed
>
> Wired as **`bd dep overseer-ews --blocks overseer-kju6wh`** — a hard, LOCAL
> blocking edge, the same shape A2→A3 already uses, and therefore visible to
> `bd dep tree` (unlike B2's cross-repo `non_local_depends_on` pointer). Read
> back and confirmed: A3's DEPENDS ON now lists A1 ✓, A2 ◇, **A4 ◇**.
>
> **A hard `blocks` edge gates A3's START, not merely its CLOSE** — beads offers
> `blocks` (enforcing) or `relates_to` (advisory, enforcing nothing), and there is
> no close-only primitive. So the requested "A3 must not close while A4 is open"
> is delivered as "A3 does not open while A4 is open". **That inverts the
> originally-stated order** (A2 → A3 → A4) **into A2 → A4 → A3**, and that
> inversion is correct on the merits, not just convenient: A3 flips
> `harnesses.codex` to `supported`, and shipping that claim while the `overseer`
> operation cannot actually launch under Codex is exactly the
> claim-a-capability-that-does-not-exist failure the A1/A3 split was cut to
> prevent. If a supervisor wants the original order back, `bd dep remove` the
> edge deliberately and record why.
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
| **A4** — make `overseer-start` launch under Codex without weakening the stray-hand-run refusal | `overseer-ews` — FILED 2026-07-29, not part of the original groom cut | `livespec-overseer` | — |
| **A3** — flip `harnesses.codex` to `supported`, with a repo-local check that makes the green load-bearing | `overseer-kju6wh` | `livespec-overseer` | A1, A2, **A4** |
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

> ### ⛔ THAT PREDICTION IS WRONG — EXERCISED LIVE 2026-07-30
>
> **`overseer` never reaches the `$CLAUDECODE` refusal.** It dies earlier, and
> for a reason that is **not Codex-specific at all**:
>
> ```
> overseer-start  ->  exit 127:  command not found: overseer-start
> ```
>
> The binding DID resolve `$PLUGIN_ROOT` (to the cache root
> `~/.codex/plugins/cache/livespec-overseer/livespec-overseer/0.13.3` — the third
> fallback, correct when cwd is another repo) and DID read `prose/overseer.md`.
> Then the bootstrap was simply absent from PATH, so **neither the `$CLAUDECODE`
> check nor the `$TMUX_PANE` check ever ran.**
>
> > **RE-MEASURED UNDER CLEAN CONDITIONS 2026-07-30 — inference is now
> > measurement.** Re-run against the **declared `--ref release` fixture** (no
> > deviation) with **`env -u CLAUDECODE`** (no leak), in a real Codex session in
> > `/data/projects/livespec-dev-tooling`: `CLAUDECODE` unset; `$PLUGIN_ROOT`
> > resolved; `prose/overseer.md` read; then verbatim
> > `zsh:1: command not found: overseer-start`, **exit 127**; and **neither the
> > `$CLAUDECODE` nor the `$TMUX_PANE` check ran.** So `overseer` fails for the
> > PATH reason **and no other** — the confounds (wrong ref, leaked marker) are
> > both excluded. **resolve=PASS, execute=PASS, run=FAIL(127, PATH).**
>
> **Root cause:** `overseer-start` is a console script (`pyproject.toml:31-32`)
> installed ONLY into this repo's `.venv/bin/`. It is not on PATH in a plain
> shell and not in `~/.local/bin`. **So a session in ANY other repo — Claude
> Code included — cannot invoke it.**
>
> **Consequence for the bar above, and it is structural:** *"`overseer` must
> RESOLVE and RUN in a Codex session that is NOT this repo's"* is
> **unsatisfiable by EITHER harness** until the bootstrap is reachable from
> outside this repo. **PATH is the binding constraint and it PRECEDES the
> runtime-marker question A4 was scoped around** — so A4 as currently written
> (admit Codex as a second runtime, extend `test_overseer_start.py:22-39`) would
> NOT fix this on its own. Whether A4's scope widens or a new slice is cut is a
> maintainer/supervisor call; it is flagged here, not decided.
>
> **What DID pass, same session, same fixture:** `supervise-plan` reached
> **RESOLVE + EXECUTE + RUN** — resolved `$PLUGIN_ROOT`, read
> `prose/supervise-plan.md`, and stopped on its own documented contract
> (*"must name a target repository and a plan topic"*), creating no tmux session
> and writing no file. **Both** operations RESOLVED in the skill list.
>
> > **CONFOUND CHECKED AND CLEARED — do not re-open this.** That PASS was first
> > measured in a `codex exec` session where **`CLAUDECODE` had leaked to `1`**
> > (see the false-accept box in §A4) — the very error class documented in this
> > same file, so the result could not be trusted until re-tested. **Re-run with
> > `env -u CLAUDECODE`**: the spawned shell reports `CLAUDECODE=[UNSET]` and
> > `supervise-plan` STILL resolves, executes, reads
> > `…/0.13.3/prose/supervise-plan.md`, and runs to its own contract (*"Which plan
> > topic … should I supervise"*), creating no tmux session and writing no file.
> > **So the PASS is NOT an artifact of the leak**, and it holds under a genuine
> > standalone-equivalent Codex session.
> >
> > Recorded because the confound was self-inflicted and easy to miss: the leak
> > was documented *after* the PASS was measured, which is exactly when a stale
> > positive silently survives.
>
> Method, for reproducibility: `codex exec -s read-only` in
> `/data/projects/livespec-dev-tooling` (not this repo), session
> `019fb155-0925-7981-b51e-f27b6c787894`. Fixture hand-added and DECLARED —
> **at the time: `--ref master`, not `--ref release`**, because `origin/release`
> still lacked the surface (A2 landed on master via PR #308; release-please PR
> #244 `release 0.14.0` was still open).
>
> > **THAT DEVIATION IS RETIRED — 2026-07-30.** PR #244 merged, and all three
> > files are now verified on **`origin/release`** (`1af636d`,
> > `git cat-file -e origin/release:.claude-plugin/.codex-plugin/plugin.json`
> > succeeds). The fixture was **re-registered at the declared
> > `--ref release`**, so the record and the actual state now agree and no
> > deviation stands. The `overseer` re-test below was run against that
> > release-ref fixture.
>
> Installed `0.13.3`, and the resolved
> `source.path` matched the version installed, which excludes the pre-declared
> stale-pinned-cache false negative. **Both operations resolved in the FIRST
> session after provisioning** — the two-session budget was not needed here,
> which does not repeal the rule for other first exposures.

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

> **Citation RE-VERIFIED CURRENT 2026-07-30 — it has not drifted.**
> `check-codex-skill-picker` is still at
> `livespec-orchestrator-beads-fabro/justfile:1110`, and both self-skips are
> exactly as described above (`CI=true` without
> `LIVESPEC_REQUIRE_CODEX_TUI_PICKER=1` → `exit 0`; `command -v codex` absent →
> `exit 0`). Checked because a stale line reference would cost A3's implementer
> real time; it is sound, so use it.
>
> **The mechanism, which was not recorded before:** the recipe runs
> `LIVESPEC_CODEX_SKILL_PICKER=1 uv run pytest tests/e2e-cli/test_codex_skill_picker.py`,
> and the assertion is that the **TUI `/skills` picker renders a row**
> `drive (livespec-orchestrator-beads-fabro)`. This repo's version would assert
> rows for `overseer` and `supervise-plan` under `livespec-overseer`.
>
> ### ⚠ DO NOT credit A2's live evidence against A3's bar
>
> A2's live work (2026-07-30) proved **agent skill-list resolution** via
> `codex exec` — both operations appeared in the session's available skills.
> **A3's bar is a DIFFERENT surface: TUI `/skills` picker RENDERING.** They are
> not the same check and one does not imply the other. **A2's proof therefore
> pre-discharges NO part of A3**, and A3 must not be treated as partly done on
> the strength of it. What A2's result *does* establish is that the plugin
> installs and resolves at all — so A3's check has a realistic path to a
> legitimate green, and its RED proof remains "remove the surface, show it
> fails, with codex PRESENT and locally".
