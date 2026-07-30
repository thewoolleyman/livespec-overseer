# Plan — codex-parity-and-rollout-safety

> # ▶▶▶ RESUME HERE — written at wind-down, end of 2026-07-30. THIS BLOCK WINS OVER EVERY OTHER BLOCK IN THIS FILE.
>
> Everything below this block is HISTORY. It is accurate as evidence and often
> wrong as *current state* — several of its claims were corrected later the same
> day, and the corrections are boxed in place. **Read this block for what to do;
> read below it for why.**
>
> ## Nothing is in flight. Nothing is dispatchable by you. The cap is 0 of 4.
>
> | slice | id | state at wind-down |
> |---|---|---|
> | A1 | `overseer-4km4mj` | CLOSED |
> | A2 | `overseer-vyie5q` | CLOSED |
> | **A4** | `overseer-ews` | **`ready` — and you must NOT dispatch it (see the trap below).** Code landed long ago (PR #347, `8bd5b91`). Only its LIVE discharge is open. |
> | A5 | `overseer-ei3` | CLOSED — PR #385, `ad6669b` |
> | A6 | `overseer-g6z` | CLOSED — PR #386, `e1ab5051` |
> | `overseer-e18` | — | CLOSED — PR #399, `0411f060`. **Its stated root cause was FALSE (mine); the PR is still worth having.** |
> | `overseer-yms` | — | CLOSED — PR #397, `b6fe98dc` |
> | `overseer-wr8` | — | CLOSED — PR #403, `556ad8ac` |
> | **A3** | `overseer-kju6wh` | `pending-approval`. **Admission is ALREADY GRANTED by the maintainer — do NOT re-ask.** Held only by A4's live bar. |
> | **`overseer-jcw`** | — | **P2 `backlog`, NEW.** The gate is intermittently red. Needs admission. |
> | B2 / B1 / C1 | — | unchanged; other repos' work or stood down |
>
> ## The four things that will bite you first
>
> 1. **`next` RANKS A4 — DO NOT ACT ON IT.** It returns exactly one candidate,
>    `implement: overseer-ews`. A4's code merged in **PR #347**; `next` ranks on
>    status, not on whether the work exists. Dispatching burns a factory run
>    re-implementing merged code. **A4 closes on EVIDENCE, not on a run.**
> 2. **ADMISSION ASKS GO TO THE SUPERVISOR, NOT THE MAINTAINER.** The maintainer
>    gave the supervisor a standing authorization for this track, so it resolves
>    in ONE hop. **Never self-admit.** Older text below says "ask the maintainer
>    FIRST" — superseded.
> 3. **A4's live bar: the LAUNCH half is PROVEN, the DAEMON half is not provable
>    on this host — and that is NOT a defect.** From a real Codex session in
>    `/data/projects/openbrain`, `CLAUDECODE` unset: resolve/execute/run all PASS,
>    `overseer-start` exits **0** in 463 ms and splits the pane (`%137`, then
>    `%138` on a rerun — distinct ids). The daemon then refuses on the **singleton
>    lock**, which is *correct behavior* while the acting daemon holds it. Proving
>    the adopt-a-track clause would need that daemon killed (**forbidden**) or an
>    `act=True` scratch daemon over the real fleet (**unsafe to other tracks**).
>    **Whether the bar may be discharged anyway is a MAINTAINER decision about
>    narrowing it — the supervisor is carrying it up. Do not absorb it.**
> 4. **The fixture is pinned `--ref master`, a DECLARED deviation.** It retires
>    when **release PR #360** merges (`origin/release` is still 0.15.0 and does
>    not carry the launcher). Merging it is a release decision, not yours.
>    Re-registering PRUNES cache dirs and breaks live Codex sessions.
>
> ## Corrections made today — do NOT re-derive these, and do NOT re-break them
>
> - **The singleton lock WAS the cause** of the daemon pane dying. I retracted
>   that and was wrong; the retraction is itself retracted. Evidence:
>   `<plugin_root>/tmp/overseer/daemon.log` in the codex cache, two entries.
> - **`overseer-e18`'s root cause (cwd-relative log path) is FALSE.** The pane's
>   cwd is set explicitly. The PR still earned its place: it added the
>   daemon-liveness check, because `overseer-start` used to report SUCCESS for a
>   daemon that had already died.
> - **"The adoption code is what was verified live on 2026-07-16" is FALSE.**
>   This repo's first commit is `ceaca74`, **2026-07-21** — it did not exist then.
>   The path has since moved `+483/-136` on top of a `+720` relocation. **Treat
>   that date as PROVENANCE, never CURRENCY.**
> - **The charter-regeneration BLOCK IS LIFTED** — `overseer-wr8` moved both
>   role-level rules into `.ai/supervisor-protocol.md`. The triage I shipped
>   (`grep -c supervisor-protocol`) is a **SCREEN, NOT A VERDICT**: it matches
>   headings and over-reports. Confirm any orphan **by content**. Swept all seven
>   charters: nothing else is at risk.
> - **A5's automation half is PROVEN in the field** on release PR #360 — both
>   manifests bump `0.15.0 → 0.16.0`. Check VALUES, not file presence: a wrong
>   `jsonpath` fails *silently*.
>
> ## Two environment traps that cost real time
>
> - **`just worktree-create` is a coin flip** (~50% at 41 worktrees): SIGPIPE →
>   **exit 141**, sometimes with **ZERO bytes on both streams**, so an empty log
>   is the whole symptom. Capture `$?` and loop. Never `git worktree add`.
> - **`fabro ps` puts everything on STDERR when idle** — measured at wind-down:
>   stdout **0 bytes**, stderr **74 bytes** (`No running processes found…`), exit
>   **0**. Even with runs present the count line is on stderr. So
>   `fabro ps 2>/dev/null` cannot tell "no runs" from "fabro is broken".
> - **zsh eats `:ready` off an action id**: `"move:$id:ready"` → `move:<id>eady`
>   via the `:r` modifier. bash is unaffected. Use `"move:${id}"":ready"`.
> - **The gate is intermittently red** (`overseer-jcw`): `just check` failed,
>   failed, then passed on an unchanged tree. It presents as a COVERAGE shortfall,
>   not a test failure. Re-run before believing it; never `--no-verify`.
>
> ---
>
> # ▶ (HISTORY BELOW) earlier session handoff, 2026-07-30
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
> > **A4 IS DONE AND MERGED.**
> >
> > > **SUPERSEDED LATER THE SAME DAY — the admission valve was opened.** This box
> > > used to end *"nothing is dispatchable … ask the maintainer for admission
> > > FIRST; do not admit anything yourself."* **That instruction was followed and
> > > is now discharged**: the maintainer ruled BOTH slices in, and **A6
> > > (`overseer-g6z`) and A5 (`overseer-ei3`) are ADMITTED and IN FLIGHT** — see
> > > the discharged-decisions section below for run ids and read-back. **A3
> > > (`overseer-kju6wh`) is still held and still must not be self-admitted.**
> >
> > ### Ledger, read back 2026-07-30
> >
> > | slice | id | state |
> > |---|---|---|
> > | **A4** | `overseer-ews` | **Code DONE** — PR **#347**, commit `8bd5b91` verified on `origin/master`. Ledger reads **`READY`** (a phantom claim was released; nothing is in flight). Acceptance verified: runtime check **ADMITTED-TO, not dropped** (`_CODEX_AGENT_COMMS={codex,codex-acp}`, walking **process ancestry**); tests **EXTENDED not loosened** (originals kept, three added, one gating the `$CLAUDECODE` leak). **Its LIVE bar is UNPROVEN** — see A6. |
> > | **A6** | `overseer-g6z` | **CODE DONE, MERGED** — PR **#386**, `e1ab5051` on `origin/master` (needed a manual union rebase of `justfile`). Its launcher fix is **PROVEN LIVE**. Item still reads **`ACTIVE`**: `reconcile-merged` re-ran the post-merge janitor, which is red only on `check-master-ci-green`, a LOCAL-ONLY gate. **A6 does not block A4's live bar. Neither, it turns out, does `overseer-e18` — see the ⛔⛔ box.** |
> > | **A5** | `overseer-ei3` | **DONE / CLOSED** — PR **#385**, `ad6669b`, post-merge janitor green, `resolution:completed`. Its fix is visible in the field: the refreshed plugin cache reads nested **0.15.0**, in lockstep with its sibling. |
> > | **NEW** | `overseer-e18` | **P1. Its stated root cause is FALSE — I filed it on a mis-measurement; see the ⛔⛔ box.** Landed anyway as `0411f060`, and the run was NOT wasted: the same PR added the daemon-liveness check, which fixes the real defect that `overseer-start` reported SUCCESS for a daemon that had already died. It is **not** what blocks A4's live bar. |
> > | **NEW** | `overseer-yms` | **P2, `backlog`.** `prose/overseer.md` cites `.ai/agent-disciplines.md` under `$PLUGIN_ROOT`, a path the plugin cache never contains. |
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
> > ### ~~Pending maintainer/supervisor decisions~~ — BOTH DISCHARGED 2026-07-30
> >
> > 1. ~~Admission for `overseer-g6z` and `overseer-ei3`~~ — **the maintainer ruled
> >    BOTH**, put to them independently by two askers who agreed. Both approved
> >    through the valve (`approve:<id>`, `pending-approval → ready`) and **both
> >    DISPATCHED**: runs `01KYSYT9AZBQ` (g6z) and `01KYSYTEJ9QR` (ei3), claims
> >    read back **`ACTIVE` + `Assignee: fabro`**, cap 2 of 2 in use.
> > 2. ~~The `pyproject.toml:270` → 344 citation~~ — **corrected in the ledger, and
> >    it was worse than a wrong line.** The description told its implementer *"do
> >    NOT hand-maintain a duplicate of a file `pyproject.toml:270` already
> >    packages"*, and **no line packages the launchers as files at all**:
> >    `:343-344` is `packages.find`, `:356-357` is `package-data` declaring ONLY
> >    `overseer = ["version.json"]`, and delivery is `[project.scripts]` at
> >    `:30-32`. So the duplicate-vs-packaging choice it posed had a false premise.
> >
> > A tracked-file/worktree prohibition was in force at session end for everything
> > except this handoff; it lapses with that session.
> >
> > ### ▶ e18 AND yms ARE IN FLIGHT — dispatched 2026-07-30, and the ADMISSION ROUTE CHANGED
> >
> > | item | run | claim, read back |
> > |---|---|---|
> > | `overseer-e18` (P1, the critical path) | `01KYT4NT0QFT` | `ACTIVE` + `Assignee: fabro` |
> > | `overseer-yms` (P2) | `01KYT4P0CMBT` | `ACTIVE` + `Assignee: fabro` |
> >
> > Dispatched onto a base proven green — `fa730705 completed success`, not a
> > pending run. **The committed dispatch cap here is 4**, so two in flight is well
> > inside it; earlier notes in this file assume the default 2.
> >
> > > **A phantom claim was ruled OUT, not assumed away.** The first `fabro ps`
> > > after dispatch listed only ONE run while BOTH items already read `ACTIVE` —
> > > which is precisely this file's documented "a dispatch that fails at
> > > run-config-overlay still CLAIMS the item" shape. Re-checked: both runs were
> > > live, the second was simply seconds behind. **`ACTIVE` is still not evidence
> > > of a run; `fabro ps` is.**
> >
> > **THE ADMISSION ROUTE CHANGED — stop routing admission to the maintainer.** The
> > maintainer gave the supervisor a **standing authorization** to admit anything
> > belonging to this track. So an admission ask goes to the **supervisor** and
> > resolves in ONE hop. **The split still stands: never self-admit.** Earlier
> > sections of this file say "ask the maintainer FIRST" — that is superseded for
> > this track.
> >
> > ### ✅ A5's AUTOMATION HALF IS PROVEN IN THE FIELD — first observation possible, 2026-07-30
> >
> > A5 had two halves: **(a)** make release automation bump the nested manifest,
> > and **(b)** a check that goes RED when lockstep breaks. **(b) was verified when
> > it landed. (a) could not be — its effect is only visible on a RELEASE PR**, and
> > none had been cut since. **Release PR #360 (`0.16.0`) is the first, and it
> > works:**
> >
> > ```
> > .claude-plugin/.codex-plugin/plugin.json   "0.15.0" -> "0.16.0"
> > .claude-plugin/plugin.json                 "0.15.0" -> "0.16.0"
> > ```
> >
> > **Both bump, to the SAME value.** Before A5, release-please touched only the
> > sibling — which is exactly what produced the 0.15.0 / 0.13.3 skew this slice
> > was filed for.
> >
> > **The causal chain is closed, not inferred:** `ad6669b` (A5's merge) added
> > `{"type": "json", "path": ".claude-plugin/.codex-plugin/plugin.json",
> > "jsonpath": "$.version"}` to `release-please-config.json`'s `extra-files`,
> > and the first release PR cut afterwards bumps that file. **I checked the
> > VALUES, not merely that both files appear in the diff** — a file can be touched
> > for an unrelated reason.
> >
> > **Why that distinction is load-bearing here, in this repo's own words:** the
> > neighbouring `uv.lock` entry carries a comment warning that a wrong `jsonpath`
> > **fails SILENTLY** — *"release-please logs 'No entries modified' at warn level
> > and returns the content unchanged, so a wrong path here reports success while
> > doing nothing."* The nested-manifest entry is the same shape and would fail the
> > same way. **What rules that out is precisely this observation: #360 actually
> > changes the value.**
> >
> > **So A5's two halves now guarantee different things, and both are evidenced:**
> > the gate catches skew AFTER it happens; the automation prevents it happening.
> > Only the second was open, and it is now closed.
> >
> > ### ⚠ THE FIXTURE DEVIATION RETIRES WHEN **#360** MERGES — a named PR, not "some release"
> >
> > `origin/release` is still `013d35d` (0.15.0) and **does NOT carry the
> > launcher**: `git cat-file -e origin/release:.claude-plugin/bin/overseer-start`
> > fails, and `e1ab5051` is not an ancestor of `origin/release`. So the declared
> > `--ref master` deviation still stands, correctly.
> >
> > **Its retirement condition is now a specific merge — release PR #360** — not
> > the vague "once a release carrying `e1ab5051` is cut" this file said before.
> > Merging it is a RELEASE decision and deliberately not the worker's. Once it
> > lands, re-register at `--ref release` and the deviation is retired for free,
> > with no extra prune beyond the one the release itself causes.
> >
> > ### ⚠ zsh EATS `:ready` OFF AN ACTION ID — and bash does not, which is why it bites HERE
> >
> > Building an action id by interpolation is unsafe in this fleet's shell.
> > **Measured, both shells side by side:**
> >
> > ```
> > zsh:   id=overseer-e18; echo "move:$id:ready"   ->  move:overseer-e18eady
> > bash:  id=overseer-e18; echo "move:$id:ready"   ->  move:overseer-e18:ready
> > zsh:   echo "move:${id}"":ready"                ->  move:overseer-e18:ready
> > ```
> >
> > Unbraced `$id:r` triggers zsh's **`:r` history modifier** (strip extension),
> > which consumes the `:r` and leaves `eady`. **bash is unaffected**, so a snippet
> > that is correct everywhere else silently mangles here — the same class as
> > shared correction C14 (`PIPESTATUS` is bash; this fleet runs zsh).
> >
> > It failed LOUDLY this time (`invalid-action-id`), and that is luck, not
> > safety: the same mangling anywhere that accepts a malformed string would pass
> > quietly. **Use `"move:${id}"":ready"` and echo the id before firing it.**
> >
> > ### ⚠ `supervisor-handoff.md` IS STALE — the regeneration BLOCK is now LIFTED (was: MUST NOT)
> >
> > > **TWO CORRECTIONS LIVE IN THIS BOX, IN ORDER.** First: the remedy this
> > > section originally gave — *"regenerate before trusting it"* (shipped in
> > > `fa730705`) — was WRONG, because at that time regenerating DELETED two
> > > role-level rule sections this thread paid for and nothing caught the loss.
> > > Second: **`overseer-wr8` has since fixed that, so the block is lifted.**
> > > Both are kept rather than collapsed, because the reasoning is what
> > > generalizes. The staleness table below stands throughout.
> > >
> > > **✅ `overseer-wr8` HAS LANDED — PR #403, `556ad8ac`, verified an ancestor of
> > > `origin/master`. THE PROHIBITION IS LIFTED, and the triage test I shipped
> > > with it is now WRONG. Both corrections are below; regeneration itself
> > > remains the supervisor's act, not the worker's.**
> > >
> > > **What wr8 changed, measured:** both rule sections now live in the SHARED
> > > layer — `.ai/supervisor-protocol.md` returns `empty result is not a finding`
> > > **1**, `positive control` **2**, `wait is not a question` **1**, against
> > > `armed re-entry` **1** as a positive control and a bogus phrase at **0**.
> > > They were all `0` before.
> > >
> > > **MY TRIAGE TEST WAS A PROXY, AND IT NO LONGER TRACKS THE DANGER.**
> > > `grep -c supervisor-protocol <charter>` still returns **0** for ours — it
> > > tests *"is this a fat single-layer charter"*, which was only ever a STAND-IN
> > > for the real question, *"does role-level content exist ONLY here?"* After
> > > wr8 the proxy says DANGER while the danger is gone. **A heuristic that
> > > outlives its cause is its own defect** — use the direct test instead:
> > >
> > > ```
> > > enumerate the charter's `## ` sections; for each, ask whether the shared
> > > layer carries it OR the generator emits it. Anything answering NO to both
> > > is what regeneration would destroy.
> > > ```
> > >
> > > **Run against ours, that yields exactly two charter-only sections, and
> > > NEITHER is a loss:**
> > > - `RESUME STATE — written at wind-down 2026-07-30` — **thread-specific and
> > >   already stale**; refreshing it is what a regeneration is FOR.
> > > - `AskUserQuestion presentation rules` — role-level, and it looked like a
> > >   SECOND instance of the wr8 defect. It is not: the generator emits picker
> > >   rules (`AskUserQuestion` ×4, `picker` ×3, `full repository names` ×1,
> > >   against a bogus control at 0) **and** the new gate pins them with dedicated
> > >   RED fixtures — `test_a_charter_with_no_picker_rule_is_rejected`,
> > >   `test_picker_recommended_first_has_its_own_red_fixture`, and three more.
> > >
> > > **⚠ THE LIMIT OF THIS EVIDENCE, stated because today punished exactly this
> > > gap twice:** I verified WHERE each section's content lives. **I did not run
> > > a regeneration and diff the result.** So the claim is *"no section is
> > > sourced only from the charter"* — NOT *"regeneration was tested"*. Whoever
> > > regenerates should still diff the output against the current file before
> > > accepting it.
> > >
> > > ### ✅ SWEPT ACROSS ALL SEVEN CHARTERS — nothing else is at risk
> > >
> > > The triage above was only ever run against OUR charter, so it was run across
> > > **every** `supervisor-handoff.md` in the repo (3 live + 4 archived).
> > > **Result: no role-level content is at risk anywhere.**
> > >
> > > | charter | sections | heading-orphans | verdict |
> > > |---|---|---|---|
> > > | `codex-parity-and-rollout-safety` | 12 | 1 | thread-specific (`RESUME STATE`) |
> > > | `fabro-review-classifier-defect` | 10 | 0 | clean |
> > > | `supervisor-prompt-quality` | 7 | 0 | clean (the wr8-touched thin one) |
> > > | `archive/background-shell-supervision-liveness` | 13 | 3 | all thread-specific |
> > > | `archive/cutover-and-shipping` | 7 | 0 | clean |
> > > | `archive/ship-overseer-to-fleet` | 7 | 0 | clean |
> > > | `archive/supervise-plan-residual-gaps` | 11 | 2 | **FALSE POSITIVES — see below** |
> > >
> > > ### ⚠ AND THE METHOD I SHIPPED HAS A FALSE-POSITIVE MODE — found by testing it
> > >
> > > `archive/supervise-plan-residual-gaps` flagged `[R2] Keep your own obligation
> > > record` and `[R3] Handing an obligation to a peer track`. Both read as
> > > ROLE-level, so they looked like a second wr8-class loss. **They are not.**
> > > The triage matches HEADINGS, and the shared layer carries that content under
> > > DIFFERENT headings — by content it is richly covered on both sides:
> > >
> > > ```
> > >               protocol  generator
> > > obligation      12         9
> > > peer            10         4
> > > receipt          3         2
> > > confirmation     2         1
> > > (controls)       1        11      bogus phrase: 0 / 0
> > > ```
> > >
> > > The new gate pins the same concepts independently
> > > (`test_a_record_without_the_durable_obligation_schema_is_rejected`,
> > > `test_a_peer_held_handoff_without_receipt_ack_confirmation_is_rejected`, …).
> > >
> > > **So use the heading triage as a SCREEN, never as a verdict: a heading
> > > orphan must be confirmed BY CONTENT before it counts as a loss.** Recorded
> > > because I put that method into this record as guidance — a tool handed to
> > > others earns the same scrutiny as a claim, and this one over-reports.
> > >
> > > **Why, verified independently rather than taken on report.**
> > > `prose/supervise-plan.md:15-24` now emits **TWO** layers — the shared
> > > `.ai/supervisor-protocol.md` plus a *"thin per-thread binder"* that is
> > > *"intentionally incomplete"*. Our charter predates that split. It carries two
> > > standalone `##` rule sections — *"An empty result is not a finding. Run a
> > > positive control first."* (`fdd0a5a`, after FOUR vacuous checks in one day)
> > > and *"A wait is not a question…"* — and **`.ai/supervisor-protocol.md` has
> > > NEITHER**:
> > >
> > > ```
> > > empty result is not a finding  0   |  armed re-entry   1   <- positive control
> > > positive control               0   |  AskUserQuestion  1   <- positive control
> > > wait is not a question         0   |  bogus phrase     0   <- negative control
> > > vacuous                        0
> > > ```
> > >
> > > **The preservation rule does not cover them.** `prose/supervise-plan.md:544+`
> > > preserves byte-for-byte only from the `## Corrections` heading. These are
> > > standalone `##` sections OUTSIDE Corrections — so the Corrections LOG entry
> > > about the four vacuous checks survives while **the RULE it produced is
> > > deleted.** And nothing else catches it: `tests/heading-coverage.json` pins
> > > SPECIFICATION headings, not charter ones (`positive control` 0,
> > > `wait is not a question` 0, `supervisor-protocol` 0, against
> > > `supervisor-handoff` **1** as a positive control). **A regenerated charter
> > > would look clean and freshly generated with the rules simply gone.**
> > >
> > > That is REMOVING AN EXISTING CHECK, which this role refuses rather than asks
> > > about. The supervisor refused it, and was right to.
> > >
> > > **A clean specimen of the very rule at stake, from the supervisor's own first
> > > attempt:** they "controlled" a `git diff` by diffing a file they EXPECTED to
> > > be clean — which returns empty either way and proves nothing. The real
> > > control was `git ls-files --error-unmatch` plus diffing the file across its
> > > own last change (84 insertions). **An empty result is not a finding, and the
> > > control has to be able to come out non-empty.**
> >
> > The charter (`00f0cbf`) is the first thing an incoming supervisor reads, and
> > four of its statements are now false. Measured against the ledger and the
> > forge, **this file wins**:
> >
> > | charter says | actually |
> > |---|---|
> > | A4 "blocked on A6" | **A6 is CLOSED**, and A4 is blocked by **no defect at all** — see the ⛔⛔ box |
> > | A5 `active`, "PR #385 OPEN, auto-merge armed" | **CLOSED**, merged `ad6669b`, janitor green |
> > | "then A4's live bar is finally provable" | **exercised** — launch half PASS, daemon half FAIL |
> > | PR #384 "was OPEN" at wind-down | settled: **not this thread's**, merged as `4e0faba` |
> >
> > **The charter is in a genuine BIND, and naming it is the point.** It was not
> > hand-corrected — a charter is generated by `/livespec-overseer:supervise-plan`,
> > and this thread's record says a hand-written one is the evidence-free artifact
> > the contract test exists to prevent. But per the box above it must not be
> > REGENERATED either, because regeneration deletes two rule sections. **Neither
> > lever is available, so do NOT force one.** Until `overseer-wr8` lands, treat
> > **this file** as authoritative over the charter on every row in the table
> > above, and take the charter's *role-level rules* as still binding — they are
> > the part regeneration would destroy, which is exactly why they are worth
> > keeping.
> >
> > > **One correction the other way, since it was asserted OF this charter:** the
> > > charter **never predicted the singleton-lock cause.** Grepped for
> > > `singleton`, `already running`, `holds .*lock`, `pane .*disappear`,
> > > `second daemon` — **zero hits**, against a positive control (`live bar`
> > > appears twice, so the search reaches real content). The wrong prediction
> > > lived in **this** file and is retracted **here**. The charter is stale, not
> > > wrong on that point.
> >
> > ### ⛔ `next` RANKS A4 AND YOU MUST NOT DISPATCH IT — verified 2026-07-30
> >
> > `next` returns **exactly one** candidate, and it is a trap:
> >
> > ```json
> > {"action": "implement", "work_item_ref": "overseer-ews",
> >  "rank": "a4", "reason": "ranked ready item (rank a4, origin freeform)"}
> > ```
> >
> > **A4's CODE ALREADY LANDED — PR #347, `8bd5b91`.** The item sits at `ready`
> > only because its LIVE discharge is outstanding, and `next` ranks on status, not
> > on whether the work exists. **Dispatching it burns a factory run
> > re-implementing merged code.** A4 needs no implementation; it needs
> > **`overseer-e18`** fixed, which is the sole thing between it and closure.
> >
> > This is the same shape as the thread's other recurring failure — a signal that
> > is *correct about its own inputs* and wrong about the world. Read it, then
> > check whether the code is already on `origin/master` before acting on it.
> >
> > ### ▶ A4's LIVE BAR — EXERCISED 2026-07-30. The LAUNCH half PASSES; the DAEMON half fails on a NEW, measured defect.
> >
> > **Both slices landed: A5 `ad6669b` (item CLOSED), A6 `e1ab5051` (PR #386).**
> > A6 needed a manual rebase — its branch went `DIRTY` on exactly one file,
> > `justfile`, because #385 and #386 each appended a slug to the `check`
> > aggregate. **Resolved as a UNION** — both `check-plugin-manifest-lockstep` and
> > `check-codex-plugin-runnable-launcher` kept, since dropping either silently
> > removes a check. Verified not just present but **EXECUTING**: `just check`
> > shows both `::: just <slug>` banners, 65 targets green. The launcher gate was
> > additionally **RED-demoed** — one appended byte to
> > `.claude-plugin/overseer/signals.py` → **exit 1**; restored → **exit 0**.
> >
> > #### Per-stage verdicts — real Codex session, `/data/projects/openbrain`, `CLAUDECODE` UNSET
> >
> > | stage | verdict | evidence |
> > |---|---|---|
> > | resolve | **PASS** | `$PLUGIN_ROOT` → `~/.codex/plugins/cache/livespec-overseer/livespec-overseer/0.15.0`, `prose/overseer.md` read, exit 0 |
> > | execute | **PASS** | `"$plugin_root/bin/overseer-start"` ran from the CACHE — **this is A6's fix; it was exit 127, then exit 1, now exit 0** |
> > | run | **PASS** | `overseer-start: started overseerd in top pane %138. adopted 0 existing session(s).` **Exit 0**, in 463 ms |
> > | two-pane split | **PASS** | pane created; **`%137` on the first run and `%138` on a second** — distinct ids, so the split is real and repeatable |
> > | adopt | **ran, 0 new** | `adopted 0 existing session(s)` — the call executed; every track was already mapped |
> > | **daemon survives** | **NOT PROVABLE HERE** | `overseerd` RAN and refused on the singleton lock — **correct behavior**, not a defect. See the ⛔⛔ box; the "FAIL / cwd-relative path" reading was mine and it was wrong |
> >
> > > # ⛔⛔ THE ROOT CAUSE BELOW IS **FALSE**. I got this wrong. Read this box first.
> > >
> > > **The daemon did NOT die on a cwd-relative log path. It ran, and it refused
> > > on the SINGLETON LOCK — the cause I had "retracted".** The retraction was the
> > > error; the Codex agent's original stage-7 report was RIGHT.
> > >
> > > **DECISIVE EVIDENCE — the daemon's own log, inside the plugin cache:**
> > >
> > > ```
> > > ~/.codex/plugins/cache/livespec-overseer/livespec-overseer/0.15.0/tmp/overseer/daemon.log
> > > 17:34:16Z overseer[SURFACE]: another overseer daemon holds
> > >           /home/ubuntu/.livespec-overseer.jsonl.daemon.lock; refusing to start
> > > 17:41:52Z overseer[SURFACE]: (same, second run)
> > > ```
> > >
> > > Two entries, one per run, timestamps matching both exercises. **The file
> > > exists**, so the redirect WORKED; **`overseerd` wrote to it**, so the daemon
> > > RAN. Neither is compatible with "the redirect failed before overseerd
> > > executed".
> > >
> > > **HOW I GOT IT WRONG, because the mechanism is the lesson.** The daemon pane
> > > does not inherit the invoking repo's cwd — `start.py` passes it explicitly:
> > > `split_window_top(..., cwd=str(core), ...)` where
> > > `core = Path(__file__).resolve().parent.parent`, and the pre-fix code ALREADY
> > > ran `(core / "tmp" / "overseer").mkdir(parents=True, exist_ok=True)` right
> > > before the split. So the relative redirect resolved against `core`, where the
> > > directory had just been created. **My "measurement" ran
> > > `cd /data/projects/openbrain && sh -c '… 2>> tmp/overseer/daemon.log'` — a
> > > true result about a directory the daemon never uses.** I measured the wrong
> > > cwd because I ASSUMED inheritance instead of reading the call.
> > >
> > > **That is this thread's own recurring failure, committed by me, in the same
> > > file where I had just written the warning for it:** a check that is correct
> > > about its own inputs and wrong about the world. A positive control would have
> > > caught it — *"if the redirect really failed, no daemon.log exists anywhere"*
> > > was one `ls` away, and I never ran it.
> > >
> > > **WHAT `overseer-e18` AND `0411f060` ACTUALLY LEFT BEHIND — the run was not
> > > wasted.** The absolute-log-path change is harmless robustness on a false
> > > premise, but the SAME PR added the thing that was independently right and was
> > > also in the filing: `overseer-start` now VERIFIES the daemon survived
> > > (`pane_exists` → *"overseerd did not stay alive in the daemon pane; check
> > > `<log>` for startup errors"* → exit 1). The old code reported **success for a
> > > daemon that had already died**, which is exactly the
> > > surface-declared/artifact-absent shape this thread keeps hitting — and it is
> > > why I could not see the truth from `overseer-start`'s own output.
> > >
> > > **CONSEQUENCE FOR A4's BAR, and it is better news than the false cause was:**
> > > the daemon half is **not blocked by a defect at all.** A second daemon
> > > refusing while the acting daemon holds the lock is **correct behavior**. It
> > > cannot be proven on this host without either killing the acting daemon
> > > (forbidden) or running an `act=True` scratch daemon over the real fleet
> > > (unsafe to other tracks — it could inject into their sessions). **So record
> > > it as: launch half PROVEN, daemon-under-contention CORRECT, and the
> > > adopt-a-track clause NOT PROVABLE HERE — not as a defect.**
> >
> > **~~The daemon dies on a CWD-RELATIVE LOG PATH.~~ (FALSE — see the box above.)**
> > `start.py:85` builds
> > `overseerd 2>> tmp/overseer/daemon.log`. The split pane's cwd is the repo the
> > operator invoked `/overseer` from, so a repo without `tmp/overseer/` cannot
> > start the daemon at all. Measured both ways:
> >
> > ```
> > cd /data/projects/openbrain && sh -c 'echo x 2>> tmp/overseer/daemon.log'
> >   -> cannot create tmp/overseer/daemon.log: Directory nonexistent   (exit 2)
> > /data/projects/livespec-overseer/tmp/overseer  -> EXISTS
> > ```
> >
> > **It works in THIS repo and nowhere else** — which is exactly why it survived
> > every prior exercise. And it is **SILENT**: the error goes to the pane being
> > destroyed, while `overseer-start` reports success (exit 0) because it checks
> > only that the split happened, not that the daemon lived. Filed **`overseer-e18`
> > (P1)**.
> >
> > > **⛔ THIS RETRACTION WAS ITSELF WRONG AND IS HEREBY UN-RETRACTED.** It said:
> > > *"The Codex agent reported stage 7 as 'the pane disappeared because an
> > > overseer singleton was already running' … Both were wrong: `overseerd` never
> > > ran, so the lock was never reached … The relative-path defect fires FIRST."*
> > >
> > > **Every sentence of that is false.** The daemon's own log inside the plugin
> > > cache shows `overseerd` ran and refused on the lock, twice, once per run —
> > > see the ⛔⛔ box at the head of this section. **The agent was RIGHT, I was
> > > wrong to overrule it, and I was wrong on the confident side: I dismissed a
> > > correct report as "an inference, not a measurement" while my own contrary
> > > claim rested on measuring the wrong directory.**
> > >
> > > Keep the useful half: the singleton refusal IS independently reproducible
> > > (`overseerd` from this repo → *"another overseer daemon holds …; refusing to
> > > start"*). That reproduction was sound. What was unsound was concluding it
> > > therefore was not what happened in the probe.
> >
> > #### ⛔ AN OBSERVE-ONLY (`act=False`) RUN CANNOT PROVE ADOPTION — checked before running it
> >
> > A proposed third route — exercise the real adoption path from a Codex session
> > with the action seam OFF, so nothing is injected — was **verified before being
> > pointed at anything, and it does not work.** The premise *"adoption is
> > discovery, not action"* is **false in this codebase**, and the code says so
> > itself.
> >
> > `_supervisor_discovery.build_rows` returns on the `not act` path at **`:293`**,
> > and `adopt_sessions(sup=sup)` is at **`:302`** — *after* the return. Its own
> > docstring classes adoption as a MUTATION:
> >
> > > *"When `act` (the daemon loop) this runs archive-GC + **registry adoption** +
> > > auto-link, all of which **MUTATE the store**. When NOT `act` (the `list`
> > > command, advertised read-only) it does **NONE** … so `list` cannot silently
> > > rewrite / GC / **adopt** / re-link the store out from under a running daemon
> > > (adversarial code review 2026-07-13, blocker B6)."*
> >
> > **So the very thing the bar asks for is the thing `act=False` is built to
> > skip.** An observe-only pass proves discovery ⋈ join — not adoption.
> >
> > **The safety half DID check out, and is worth keeping:** `act=False` is inert.
> > The early return sits above every mutator, and `_supervisor_evaluate.py`,
> > `_supervisor_offer.py` and `_supervisor_idle.py` contain **no** stamp,
> > registry or tmux writers. That zero was taken with a **positive control** —
> > the same symbols resolve in `_supervisor_restart.py`, `_registry_stamps.py`
> > and `_supervisor_discovery.py` — and a negative control at 0. **An empty
> > result is not a finding; this one has its control.**
> >
> > #### The adoption code is UNCHANGED since it was verified live — a fact for the bar decision, not a decision
> >
> > A4's filing holds a real tension: it says the pid → `/proc/<pid>/fd` → rollout
> > → `session_index.jsonl` → `thread_name` join *"was verified LIVE on
> > 2026-07-16"* and that *"the daemon's adoption side needs NO change"*, while its
> > acceptance sentence still asks that the daemon adopt and supervise a track.
> > **Do not resolve that by preferring whichever half is convenient.**
> >
> > What CAN be measured, and is: **none of the three landed commits touched the
> > adoption source.** `8bd5b91` (A4) and `0411f060` (e18) do not touch it at all;
> > `e1ab505` (A6) touches only the `.claude-plugin/` MIRROR copies — there is no
> > bare `overseer/_supervisor_discovery.py`, `codex_sessions.py` or
> > `claude_sessions.py` in its file list.
> >
> > > # ⛔ THE CONCLUSION I DREW FROM THAT WAS FALSE — do not hand it to anyone
> > >
> > > I wrote: *"So the adoption code running today is the code that was verified
> > > live on 2026-07-16."* **It is not, and this nearly became the basis for
> > > closing A4.**
> > >
> > > **The query was adjacent to the question.** "Did these three commits touch
> > > it?" is answered correctly — NO. The question that decides the claim is
> > > **"what HAS touched it since 2026-07-16?"** That returns **EIGHT commits**:
> > >
> > > ```
> > > 1918f36 refactor: convert the seams this repo owns to keyword-only Protocols
> > > 80423ca refactor: make the production surface keyword-only
> > > 58f053e refactor: make the tmux surface and its double keyword-only
> > > 5312cfa refactor: declare the annotated __all__ on every overseer module
> > > e83853a refactor: extract the watch-set + discovery group, rehome resolve_watch
> > > b5d0cfe refactor: publicise Supervisor's shared state and diagnostics surface
> > > 236209c fix(overseer): close six UnicodeDecodeError boundary leaks   <- a fix, not a refactor
> > > ceaca74 chore: scaffold livespec-overseer (control-plane-tool)
> > > ```
> > >
> > > **And the decisive one: `ceaca74` is THIS REPO'S FIRST COMMIT, dated
> > > 2026-07-21. The repo did not exist on 2026-07-16** — that verification
> > > happened in livespec core, before the package was relocated here.
> > >
> > > **Measured churn:** `+720 / -0` for the scaffold (the relocation, arriving
> > > wholesale) and a further **`+483 / -136`** on top of it — including one
> > > BEHAVIORAL fix (`236209c`, six UnicodeDecodeError boundary leaks) and a
> > > 306-line extraction of the discovery group itself.
> > >
> > > **Pathspec positive control**, since a negative is being asserted: the
> > > identical `git show --numstat <sha> -- <path>` form returns `+48 / -14` for
> > > `0411f060` against `overseer/start.py`. So the empty results above are real
> > > absences, not a malformed pathspec.
> > >
> > > **Same error class as the e18 mis-diagnosis, twice in one session:** a query
> > > that is correct about its own inputs while answering a question next to the
> > > one that mattered. Both times the fix was to ask what the WORLD did, not what
> > > my chosen inputs did.
> >
> > So the honest statement is the opposite of what I first wrote: **the adoption
> > path has been through a repo relocation plus ~483 further insertions since it
> > was last exercised live, and has NOT been re-verified since.** Whether the bar
> > may be discharged anyway is a MAINTAINER decision about narrowing it;
> > deliberately not decided here.
> >
> > #### The NEGATIVE half — DISCHARGED, with a positive control
> >
> > Run **directly**, never through `codex exec` (whose exit status is documented
> > to misreport):
> >
> > | condition | result |
> > |---|---|
> > | `env -u CLAUDECODE -u TMUX -u TMUX_PANE` | **exit 1** — *"Refusing to run outside Claude Code or Codex (no supported agent runtime in process ancestry)"* |
> > | **CONTROL:** `CLAUDECODE=1`, tmux markers still unset | **exit 1 at the NEXT gate** — *"not inside a tmux pane ($TMUX_PANE unset)"* |
> >
> > The control is what makes the negative non-vacuous: the refusal is the
> > **runtime gate specifically**, not a blanket refusal. Ancestry proven in the
> > same breath — `zsh → claude → tmux: server`, a `claude` ancestor and **no**
> > `codex` ancestor, so with `CLAUDECODE` unset both admission routes are
> > genuinely closed. That is "neither marker", measured rather than assumed.
> >
> > #### Consequences for A3 — it stays HELD, and that is the right answer
> >
> > **A3's admission is already granted; do not re-ask.** But A3 flips
> > `harnesses.codex` to `supported`, and `overseer` still cannot bring up a daemon
> > from another repo. Shipping that claim now is the exact
> > claim-a-capability-that-does-not-exist failure the A1/A3 split exists to
> > prevent. **A3 is blocked on `overseer-e18`, not on paperwork.**
> >
> > #### Two more defects the live run surfaced
> >
> > - **`overseer-yms` (P2)** — `prose/overseer.md` step 3 sends the agent to
> >   `$PLUGIN_ROOT/.ai/agent-disciplines.md`, which the cache never contains. The
> >   agent "recovered" by reading `/data/projects/livespec/.ai/agent-disciplines.md`
> >   — **which only worked because an unrelated repo happens to be checked out on
> >   this host.** Same class as exit-127 and `overseer-e18`: resolves in a checkout,
> >   not in the cache.
> > - **PROBLEM 2 OF THIS THREAD REPRODUCED LIVE, incidentally.** Re-registering the
> >   marketplace **pruned `…/cache/livespec-overseer/livespec-overseer/0.13.3`,
> >   the directory the already-running probe session had pinned.** That is goal 3's
> >   failure mode, observed directly rather than argued. It belongs to
> >   **`livespec-1p31`** (C1, livespec core) — not this repo.
> >
> > #### ⚠ DECLARED FIXTURE DEVIATION — still in force, restore deliberately
> >
> > The marketplace is pinned at **`--ref master`**, not the declared `--ref
> > release`, because A6 landed on master and `origin/release` does not carry it
> > yet. To restore: `codex plugin marketplace remove livespec-overseer` then
> > `add thewoolleyman/livespec-overseer --ref release`. **Do it deliberately —
> > re-registration PRUNES cache dirs and breaks live Codex sessions**, as the
> > bullet above demonstrates. A re-verification at the release ref is owed once a
> > release carrying `e1ab5051` is cut.
> >
> > ### ⛔ WHY A6 SHIPS A DUPLICATE OF THE PACKAGE — read this BEFORE "fixing" it
> >
> > **A6 copies the whole `overseer` package to `.claude-plugin/overseer/` — ~40
> > files, kept byte-identical to `overseer/`. That is DELIBERATE and supervisor-
> > accepted. Do not delete it, and do not "de-duplicate" it.** The instruction was
> > to name both options and recommend one; both are named here, with the
> > measurement that decides between them.
> >
> > **A packaging change CANNOT reach this surface — this is the decisive fact.**
> > Measured on this host: the codex plugin CACHE, which is what `$PLUGIN_ROOT`
> > resolves to at runtime, holds exactly five entries —
> > `.codex-plugin/`, `marketplace.json`, `plugin.json`, `prose/`, `skills/`. That
> > is the contents of `.claude-plugin/` and **nothing else from the repo.** The
> > codex install path never builds or installs a WHEEL: it clones the repo to
> > `~/.codex/.tmp/marketplaces/livespec-overseer/` and materializes the plugin
> > root into `~/.codex/plugins/cache/…`. Every setuptools key —
> > `packages.find` (`:343-344`), `package-data` (`:356-357`) and
> > `[project.scripts]` (`:30-32`) — governs the wheel, **and nothing in the codex
> > path consumes a wheel.** So no `pyproject.toml` edit can put a file where the
> > launcher has to be. The packaging lever does not reach this surface at all.
> >
> > **The other candidate — install the console scripts host-globally at
> > provisioning — was rejected on two counts:** it moves runnability OUTSIDE the
> > plugin, where the plugin's own check cannot see it, and it re-introduces
> > exactly the PATH dependency (a `uv`-via-mise shim) whose absence produced the
> > original **exit 127**. What remains is content under `.claude-plugin/` — i.e. a
> > copy. Its real cost is two sources of truth for ~40 files.
> >
> > **THE SHARPEST MEASUREMENT, which also explains why A4's fix "executed and
> > still failed":** the marketplace CLONE is a full repo checkout and **does**
> > contain `overseer/`; the CACHE does not. So `$PLUGIN_ROOT/../overseer/` is
> > *correct* against the clone layout and *wrong* against the cache layout. That
> > assumption was not careless — it was right about the wrong one of two real
> > directories that both exist on disk.
> >
> > **What pays the duplication cost down is the gate, and it is why the copy is
> > defensible where an ungated copy would not be:**
> > `check-codex-plugin-runnable-launcher` enforces `cmp -s` byte-identity over
> > every `overseer/*.py` in **BOTH** directions (source→plugin *and* plugin→source,
> > so orphans are caught too), rejects unexpected subdirectories, and **EXECUTES**
> > the launcher from a temp dir OUTSIDE the repo, grepping its output — a genuine
> > positive control for the exact exit-127 failure that started this, not a
> > `test -x` that proves nothing. **Silent drift is impossible.** If you ever
> > weaken that check, the duplicate stops being defensible — remove the check and
> > you must remove the copy too.
> >
> > ### ⚠ THE FACTORY WAS DOWN FOR AN HOUR AND THE CAUSE WAS A DOC — 2026-07-30
> >
> > Both dispatches above were **refused before any sandbox work** on the first
> > attempt, and the refusal named neither slice:
> >
> > ```
> > ERROR: latest master CI is not proven green at required check `ci-green`;
> > refusing dispatch before sandbox work.
> > ```
> >
> > **Master's `check-coverage` had been red since 08:57**, across the SEVEN
> > commits that followed, and nobody noticed. Cause: `fd5bb8a` added the first
> > runnable C14 reproduction to `.ai/supervisor-protocol.md` — a file in
> > `_CHARTER_GLOBS` — as a fenced `sh` block with bare `PIPESTATUS` on two
> > non-comment lines. Detector (g) of `test_charters_carry_no_known_defects.py`
> > exists to catch exactly that, and did. That commit's own subject was *"the
> > defect keeps being committed by the people sweeping for it."*
> >
> > Fixed by **PR #380, merge `a4b26aa`**: the reproduction moved to the form the
> > module's OWN control test blesses (`test_prose_explaining_the_pipestatus_
> > hazard_is_not_flagged`) — inline prose, both commands and both outputs intact.
> > **The detector was not touched.** A boxed note in the protocol records that
> > re-fencing it reddens master.
> >
> > Three things worth carrying:
> >
> > - **A red master is a FLEET-WIDE factory outage, not one repo's badge.** No
> >   dispatch anywhere reaches a run while it stands.
> > - **`check-master-ci-green` cannot go green on the branch that fixes master.**
> >   `just check` on the fix branch failed on that one target and nothing else.
> >   It is a LOCAL-ONLY gate — not among CI's 63 jobs — and `check-pre-push` has
> >   a doc-only fast path, so a docs fix still lands. Do not read that single
> >   failing target as a broken fix.
> > - **A pass from `master_ci_green` right after a merge is NOT proof.** It
> >   returns 0 on a *pending* run — *"master CI is still pending; treating as
> >   non-blocking"* — BY DESIGN, so it read green while the fix's run was still
> >   `queued`. That is a deliberate non-blocking choice, **not a defect; do not
> >   file it.** But for evidence, wait for `completed` + `success` (measured
> >   `a4b26aa4 completed success`) before claiming a proven-green base.
> >
> > ### `just worktree-create` is RACY at this repo's worktree count — retry it
> >
> > `worktree_primary_path` is `git worktree list --porcelain | awk '…exit'` under
> > `set -euo pipefail` (`livespec_dev_tooling/worktree_pack/worktree-lib.sh:89`).
> > `awk` exits on the first match, `git` keeps writing, takes **SIGPIPE**, and
> > `pipefail` turns that into **exit 141** before anything is created. Measured
> > here at **41 worktrees: 10 failures in 20 runs.** It is a coin flip, not a
> > blocker — **retry the recipe; it succeeds within a few attempts.** Never
> > `git worktree add` instead. Owner is `livespec-dev-tooling`; **not filed** —
> > awaiting direction, since it is another tenant's queue.
> >
> > > **⚠ IT CAN FAIL COMPLETELY SILENTLY — added after being bitten again
> > > 2026-07-30.** Two consecutive attempts returned **exit 141 with ZERO bytes**
> > > on stdout AND stderr, then the third succeeded. Earlier failures at least
> > > printed a few trace lines; these printed nothing at all. **So "the log is
> > > empty" is the whole symptom** — a wrapper that logs output and ignores the
> > > exit code sees success. **Capture `$?` explicitly and loop on it.**
> > >
> > > **And a C14 instance, committed by me while investigating this one:** I
> > > reached for `EXIT=${PIPESTATUS[0]:-unknown}` and got `EXIT=unknown` — in zsh
> > > `PIPESTATUS` is empty, so the defensive `:-` swallowed the real status
> > > exactly as shared correction C14 says it does. **C14 was written after a
> > > supervisor who had *read* it hit it; I had written today's note about it
> > > and hit it anyway.** The zsh form is `$pipestatus[1]`, and the safer move is
> > > not to pipe the command whose status you need.
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
>    this repo already has and already verified live on 2026-07-16 — **but see the
>    ⛔ box in §"The adoption code is UNCHANGED": that verification predates this
>    repo's existence (first commit `ceaca74`, 2026-07-21) and the code has moved
>    ~483 lines since, so treat "verified 2026-07-16" as PROVENANCE, never as
>    CURRENCY**:
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
