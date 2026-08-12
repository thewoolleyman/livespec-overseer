# Plan — supervisor-scratch-discipline

**Owning repo:** `livespec-overseer`. **Ledger anchor:** epic
**`overseer-5jttov`** (this repo's beads tenant). **Status: read it from the
ledger** — `/livespec-orchestrator-beads-fabro:list-work-items --json` and
`/livespec-orchestrator-beads-fabro:next`. This file stores no status and
carries no checkbox queue.

Created 2026-07-28 at maintainer direction, after an audit found 1,811 lines of
prose — including a groom draft and a staged set of workflow files — living in a
gitignored directory with zero durable backing.

## Read-first chain

1. This file.
2. `research/what-was-in-tmp-supervisor.md` — the audit, the three specific
   hazards, the disposition already applied, and the CI-blindness constraint
   that shapes any fix.
3. `research/brief-mirroring-verification.md` — goal 3's measurement: the
   per-brief mirroring trace and the brief-14/brief-18 count discrepancy.

That is the whole chain.

## The rule — stated by the maintainer, verbatim in effect

> Only JSON can live in `tmp/supervisor/`, and the only place prose can live is
> `tmp/supervisor/briefs/`, which should ONLY hold briefs for the supervised
> session to read.

Two corollaries follow, and both are load-bearing:

- **A brief may CITE but never CONTAIN.** Anything load-bearing must be landed
  first — ledger item, research note, or charter Corrections entry — and the
  brief then points at it. This is what makes the directory safe to lose:
  nothing important can be in it, because anything important had to be durable
  before it could be cited.
- **A changeset is never an artifact.** A staged set of proposed file changes,
  with diffs and a description of intent, held for review before landing, IS a
  branch and a pull request. Hand-rolling one gives every downside of git and
  none of the upside — no review, no CI, no history, and silent drift. If a
  change is worth staging it goes on a branch; if it is not ready for a branch
  it is not ready to be a file, and belongs in the ledger or a research note.

## Goals, each with its acceptance

**Acceptance is mechanical or demonstrated-red. "The rule is written down" is
not acceptance** — this repo has shipped two rules that ran and could not fail
(`check-no-workflow-edits`, in neither the aggregate nor CI;
`LIVESPEC_RUN_MUTATION`, a verified no-op), and the whole point of this thread
is that convention already failed once.

| # | goal | acceptance |
|---|---|---|
| 1 | **The rule ships in the generated supervisor charter**, so every future supervisor inherits it rather than rediscovering it | **Done — PR #797, `dc8e22d`, released `v0.34.0`; demonstrated red (see Status).** The prose contract `.claude-plugin/prose/supervise-plan.md` carries the rule and both corollaries, and a fixture over GENERATED output goes RED when the rule is absent — demonstrated red, not asserted |
| 2 | **An enforcement check that can actually fail** — `tmp/supervisor/` contains only `*.json`; `tmp/supervisor/briefs/` contains only briefs; nothing else anywhere beneath it | **Done — PR #795, `134fdca`; three planted violations demonstrated red (see Status).** A planted violation (a stray `.md` at top level, a non-brief under `briefs/`) turns the check RED, demonstrated. The check must state in its own output that it is LOCAL-ONLY and cannot fire in CI, because `tmp/` is gitignored |
| 3 | **Verify the existing briefs are already mirrored** — the audit asserts "mostly mirrored" from knowledge, not from measurement | **Done.** See `research/brief-mirroring-verification.md`: 16 of 16 present briefs traced to a landed artifact; 0 unmirrored (the handoff's "nonzero is expected" was itself an unmeasured guess). `brief-14.md`/`brief-18.md` from the claimed 18 do not exist on disk — unexplained, flagged as open. This measurement could not run factory-side — it reads the gitignored, local-only `tmp/supervisor/briefs/`, which no sandbox clone has — so it ran host-side in the planning session instead of being filed to the ledger |

## Ordering

Goal 3 is independent and can run first or in parallel — it is measurement over
existing files and blocks nothing. Goals 1 and 2 are independent of each other.
There is no hard edge between any of the three.

Suggested first slice: **goal 2**. It is the smallest, it makes the rule
self-policing on the machine where the risk lives, and it converts every future
violation from a judgement call into a red check.

## Scope boundary — do not silently widen

The maintainer scoped this to `tmp/supervisor/`. The same hazard exists for
anything an agent writes outside SCM and the ledger, and that generalization may
be correct — but it is a **different, larger thread** and must not be absorbed
here without an explicit decision. Name it if you find it; do not take it.

## Status — 2026-08-12. Goals 1, 2, 3 DONE and VERIFIED. THIS THREAD IS ACTIVE, NOT ARCHIVED — two fleet-wide fix items remain.

`overseer-5jttov` was groomed and is `status: done` / `resolution:
no-longer-applicable` — administratively retired because its content was split
into two replacement ledger items:

- `overseer-otjmoh` — goal 2, the `tmp/supervisor/` enforcement check.
- `overseer-m4o33z` — goal 1, the charter rule + corollaries.

Goal 3 is measured and landed in-thread (see the read-first chain above) and
was never filed to the ledger — it is not factory-dispatchable (see the goals
table).

**Do not archive this thread.** Goals 1 and 2 are now implemented, merged to
`master`, released, and confirmed working (evidence below) — but the two
fleet-wide fix items this thread's own incident created,
`livespec-dev-tooling-q3emww` and `livespec-dev-tooling-5asgvm`, are NOT done,
and archiving before they are would repeat the exact error recorded below. An
epic/work-item's ledger STATUS is
never evidence of real-world completion by itself; only a merged PR, green
CI on `master`, and (where a release applies) a shipped-and-verified
artifact are. **This is not theoretical — see "The premature-archival
incident and fleet-wide fix" below: this exact thread was already archived
prematurely once, on this exact reasoning error, and had to be corrected.**

### Dispatch outcome — goals 1 and 2 LANDED, RELEASED, and independently verified

Dispatched 2026-08-12 via `drive.py` invoked by ABSOLUTE PATH at the current
build (the first attempt died on the documented "dispatcher plugin build is
stale" trap, which a running session cannot clear by updating the plugin —
`.claude/CLAUDE.md` covers the remedy). Both runs succeeded and both PRs are
merged:

| goal | item | run | PR | merge commit | released in |
|---|---|---|---|---|---|
| 2 | `overseer-otjmoh` | `01KZSPRJCQQX` | **#795 MERGED** | `134fdca` | `v0.34.2` |
| 1 | `overseer-m4o33z` | `01KZSPRNWA8E` | **#797 MERGED** | `dc8e22d` | `v0.34.0` |

Master CI green for goal 2 at run `31551850194`.

**Neither was taken on trust — both were re-verified against the SHIPPED
artifact, because this thread exists precisely because "the rule is written
down" is not acceptance.** The verification ran in throwaway detached
worktrees; nothing was done in the primary checkout.

Goal 2, `scripts/check-tmp-supervisor-discipline.sh` (wired into the `check`
aggregate at `justfile:254`):

| planted violation | result |
|---|---|
| stray `.md` at `tmp/supervisor/` top level | RED, exit 1, names the file |
| non-brief `.txt` under `briefs/` | RED, exit 1 |
| subdirectory under `briefs/` | RED, exit 1 |
| legitimate tree (`state.json` + `brief-01.md`) | GREEN, exit 0 |
| no `tmp/supervisor/` at all | GREEN, exit 0 |

It discriminates in BOTH directions and prints its LOCAL-ONLY/CI-blindness
caveat on every run. Run against the real local `tmp/supervisor/`: passes.

Goal 1, the rule + both corollaries in `.claude-plugin/prose/supervise-plan.md`
and the shared layer `.ai/supervisor-protocol.md`, pinned by
`tests/prompts/test_generated_supervisor_handoff_contract.py` (58 tests green
on the branch). Demonstrated red by mutating the REAL files:

| mutation | result |
|---|---|
| delete the rule from `.ai/supervisor-protocol.md` | RED — 2 tests fail, exactly 3 missing requirements |
| alter the rule in `.claude-plugin/prose/supervise-plan.md` | RED — the md5 provenance pin catches ANY prose edit |

The contract asserts over CHARTER TEXT (real shared layer + real exemplar) and
over the real generator prose — not only over a synthetic in-test string — so a
charter that merely *mentions* the rule cannot pass while omitting it. Confirmed
present in the released tag: `v0.34.2` carries the rule in both files.

**Do not trust a ledger `status` field for any of this.** Every claim above is
backed by a merge commit, a CI run id, or a demonstrated red — which is the
standard this whole thread exists to enforce.

## The premature-archival incident and fleet-wide fix (2026-08-05 through 2026-08-12)

This is NOT part of goals 1–3 above — it is a separate, serious incident
this thread's own execution caused and then had to fix, spanning four repos.
Recorded here in full because it is exactly the kind of thing a resuming
session must not silently miss.

**What happened:** after goals 1 and 2 were groomed and filed (see above),
an earlier revision of this handoff **archived this thread** to
`plan/archive/` in the same commit — reasoning "the epic is closed, and this
repo's plan-thread rule says archived iff epic-closed." That PR merged (repo
auto-merge) before the maintainer caught it: both replacement items were
still `ready`, undispatched, zero code written. The maintainer's correction
(verbatim): *"By default, nothing should be archived until it is done,
tested, proven, fully merged, shipped to production... and deployed
everywhere it needs to be, and proven to be working in prod after
deployment."*

**Root cause:** `livespec-orchestrator-beads-fabro`'s `plan.md`/`contracts.md`
and `livespec` core's fleet-wide **Archive-on-epic-close** Conformance
Pattern member all treat *any* epic-closed status as archival justification,
never distinguishing a *procedural* closure (`groom`'s regroom-out: content
moved to new tickets) from a *completion* closure (work actually shipped).

**Corrections landed (all merged):**
- `livespec-overseer` PR #756 — un-archived this thread, corrected the
  status text.
- `livespec` PR #2066 (incident evidence, added to the existing open
  `planning-lane-redesign` thread) + PR #2074 (self-correction: an
  overclaim that "no mechanical verifier exists" was wrong — one does exist,
  `plan_thread_epic_parity`, it's just unarmed fleet-wide and points the
  wrong direction for this failure shape).
- `livespec-orchestrator-beads-fabro` PR #1314 (new plan thread
  `plan-archive-completion-gate`, epic `bd-ib-2vaeny`) + PR #1317
  (self-correction + re-scope: the mechanical-verifier goal moved entirely to
  `livespec-dev-tooling` since the check is shared code; `bd-ib-2vaeny`
  regroomed-out into the single correctly-scoped `bd-ib-ycihm7`).

**Fleet-wide sweep finding:** a background investigation swept all 9 local
fleet repos' `plan/archive/` trees for other victims of the same defect.
Found ONE confirmed prior incident, independent of this one: `homelab`
thread-05 epic `hl-6uldtn`, self-corrected 2026-08-03 — **two days before**
this incident, unrelated repo, zero shared context. Its false closure also
**cascaded** (a `depends_on` edge on the closed epic false-signaled readiness
to an unrelated downstream thread). Two independent occurrences of the
identical failure shape within 3 days is first-hand evidence this is
systemic, not a one-off. Recorded as corroborating evidence directly on the
fix item via `bd update --append-notes` (non-destructive ledger note, not a
new PR).

**Ledger items filed for the actual fix (cross-repo):**
- `bd-ib-ycihm7` (`livespec-orchestrator-beads-fabro`) — correct the
  prose/spec text. **DONE: run `01KZSPRVF9E2` succeeded, PR #1354 merged
  2026-08-12T01:10:04Z as `dc7bf0e`.**
- `livespec-dev-tooling-q3emww` (pre-existing, found independently by another
  thread the same day as the homelab incident) — fixes the converse gap: an
  archived thread whose anchor epic is still open passes green today.
  **NOT DONE. Run `01KZSPSTPFX6` FAILED, and its work was DESTROYED — see
  "The q3emww loss and its credential root cause" below before you touch it.
  It still reads `ACTIVE`/`fabro`: that is a PHANTOM CLAIM, not a live run.**
- `livespec-dev-tooling-5asgvm` — fixes THIS incident's specific gap:
  descendant-completion checking (an archived thread whose anchor closed via
  regroom-out, with live undisposed replacement descendants, passes green
  today). **NOT YET DISPATCHED — deliberately held.** Both `q3emww` and
  `5asgvm` touch the same check family (`plan_thread_epic_parity` and
  siblings) in the same repo; dispatching them simultaneously risked file
  collisions or two factory agents designing incompatible solutions blind to
  each other. **Dispatch `5asgvm` only after `q3emww` has merged**, so its
  implementer can see `q3emww`'s actual shipped shape:
  ```bash
  # confirm current build first: just ensure-plugins
  python3 <current-build>/scripts/bin/drive.py --repo /data/projects/livespec-dev-tooling --action impl:livespec-dev-tooling-5asgvm
  ```

**Goals 1 and 2 and `bd-ib-ycihm7` ARE done** (merge commits above).
**`q3emww` and `5asgvm` are NOT.** Do not archive anything until those two
have real merged PRs to point at.

## The q3emww loss and its credential root cause (2026-08-12)

Run `01KZSPSTPFX6` implemented the fix and COMMITTED it (`b02a1ea`), then died
without pushing. This is `.claude/CLAUDE.md`'s "fifth shape" — done, green, and
destroyed — and it is now that failure's SECOND confirmed instance
(`bd-ib-6o6h`).

Sequence: the agent finished at +81 min; the final `mise exec -- just check`
refused because `check-master-ci-green` and the real-repo test inside
`check-per-file-coverage` hit `HTTP 401: Bad credentials`; the stage failed
`will_retry: false`; the Retry/Re-implement/Abandon interview opened at
02:05:26Z and NOBODY ANSWERED IT; the run burned to its 4-hour ceiling and was
reaped. The branch `feat/livespec-dev-tooling-q3emww` was never pushed and no
PR exists, so ~81 minutes of complete, coverage-green work is gone.

**Root cause of the 401 — it is NOT a broken or revoked credential, and it is
NOT specific to this item.** Fabro authenticates to GitHub with a **GitHub App
installation token** (`fabro secret list` → `GITHUB_APP_PRIVATE_KEY`;
`~/.fabro/settings.toml` → `[server.integrations.github] app_id`). GitHub caps
those at **60 minutes**, and the token is minted **once per run**. Any run still
working past ~60 minutes gets 401 on GitHub API calls, while its git/push path
keeps working.

Measured, over the last 30 runs — exactly TWO contain a genuine
`Bad credentials` string, and both are the long ones:

| run | item | 401 at | outcome |
|---|---|---|---|
| `01KZSPSTPFX6` | `q3emww` | **+81.0 min** into the run | failed |
| `01KZSKQKYNPK` | `bd-ib-mrqoy2.5` | **+68.4 min** into the run | failed |

Every run that finished under 60 minutes passed the same check — the four
dispatched by this thread ran 9/19/21 min and all passed it. Two details pin
the mechanism down. `01KZSKQKYNPK` hit 401 at only **+40.4 min into its stage**
but +68.4 into the RUN, so **the expiry clock tracks the run, not the stage**.
And `bd-ib-mrqoy2.5` was re-dispatched, finished in **24m35s, and SUCCEEDED**
(`01KZSSNNNZDG`) — same item, same code, same credential, passing only because
it stayed inside the hour.

**Why a present-but-expired token HARD-FAILS instead of skipping.**
`livespec_dev_tooling/checks/master_ci_green.py` fail-softs only when a
credential is ABSENT; present-but-invalid is a deliberate hard failure. Its
probe `_gh_has_stored_credential()` runs `gh auth token` and reads only the
return code — offline on purpose, so it proves **presence, never validity**. An
expired token therefore ARMS the gate and then fails it. This is the same
presence≠validity trap `.claude/CLAUDE.md` documents for
`CLAUDE_CODE_OAUTH_TOKEN`. A 401 inside a sandbox is environmental and says
nothing about master's real CI state, but the check cannot tell that from an
outage.

**One control that does NOT fit, recorded honestly:** run `01KZKT8CE9MQ`
(2026-08-09, same repo) ran its full `just check` janitor from +73.8 to
+109.7 min and PASSED. Either its `master-ci-green` skipped because no
credential was present in that sandbox, or the token was still valid then. The
janitor output is a content-addressed blob that was not locatable under
`~/.fabro/storage`, so this was left unresolved rather than explained away.

**Before re-dispatching `q3emww`:** release the phantom claim by hand
(`--status ready`, clear the assignee) and record why — a `failed` run that
never pushed leaves the same `ACTIVE`/`fabro` wreckage as a queue eviction.
Then keep the re-dispatch UNDER ~60 MINUTES of agent work, or it will hit the
identical wall. Annotating the item to PUSH AND OPEN A DRAFT PR BEFORE raising
any blocking question is what actually protects the work.

## Next action

1. Release the phantom claim on `livespec-dev-tooling-q3emww` and re-dispatch
   it, sized to stay inside the 60-minute token window.
2. Once `q3emww` has a merged PR, dispatch `livespec-dev-tooling-5asgvm`
   (command above) so its implementer can see `q3emww`'s shipped shape.
3. Consider filing the two credential defects surfaced above: (a) fabro should
   refresh the installation token during long runs — the actual root cause;
   (b) `master_ci_green` should treat a 401 as *invalid credential →
   environmental*, distinct from a failed-while-credentialed API call.
4. Only once `q3emww` AND `5asgvm` have real merged PRs: replace this whole
   "Status"/"Dispatch outcome"/"premature-archival incident"/"q3emww loss"
   section with a short completion summary citing every PR, and only THEN
   consider archiving — re-running the plan operation's handoff
   self-sufficiency gate first, same as any other refresh.

Do not hand-code implementation inline in a planning session — the factory
path (`drive --action impl:<id>`) is the only implementation path for any of
this.
