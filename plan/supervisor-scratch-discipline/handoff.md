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
| 1 | **The rule ships in the generated supervisor charter**, so every future supervisor inherits it rather than rediscovering it | **Merged and released — PR #797, `dc8e22d`, `v0.34.0`; demonstrated red. NOT yet confirmed reaching a generated charter: the installed plugin build is empty (`overseer-0xg7`, P1). See Status.** The prose contract `.claude-plugin/prose/supervise-plan.md` carries the rule and both corollaries, and a fixture over GENERATED output goes RED when the rule is absent — demonstrated red, not asserted |
| 2 | **An enforcement check that can actually fail** — `tmp/supervisor/` contains only `*.json`; `tmp/supervisor/briefs/` contains only briefs; nothing else anywhere beneath it | **Done — PR #795, `134fdca`; three planted violations demonstrated red (see Status).** A planted violation (a stray `.md` at top level, a non-brief under `briefs/`) turns the check RED, demonstrated. The check must state in its own output that it is LOCAL-ONLY and cannot fire in CI, because `tmp/` is gitignored |
| 3 | **Verify the existing briefs are already mirrored** — the audit asserts "mostly mirrored" from knowledge, not from measurement | **Done.** See `research/brief-mirroring-verification.md`: 16 of 16 present briefs traced to a landed artifact; 0 unmirrored (the handoff's "nonzero is expected" was itself an unmeasured guess). `brief-14.md`/`brief-18.md` from the claimed 18 do not exist on disk — unexplained, flagged as open. This measurement could not run factory-side — it reads the gitignored, local-only `tmp/supervisor/briefs/`, which no sandbox clone has — so it ran host-side in the planning session instead of being filed to the ledger |

## Ordering

Goal 3 is independent and can run first or in parallel — it is measurement over
existing files and blocks nothing. Goals 1 and 2 are independent of each other.
There is no hard edge between any of the three.

Suggested first slice: **goal 2**. It is the smallest, it makes the rule
self-policing on the machine where the risk lives, and it converts every future
violation from a judgement call into a red check.

## Verification lessons from this thread's own execution — read before quoting a number

This thread's standard is "mechanical or demonstrated-red". Executing it on
2026-08-12 produced a clean split worth stating, because it repeated three
times in one day:

**Every single-instance demonstration held. Every extrapolation from one
instance to a population was wrong, and always in the same direction —
overstating scope.**

| what was demonstrated by hand | held? | what was extrapolated | outcome |
|---|---|---|---|
| planted violations turn the `tmp/supervisor/` check red; a legitimate tree stays green | yes | — | — |
| deleting the rule from the real shared layer reddens the charter contract | yes | — | — |
| reformatting ONE anchor line flips the armed parity check from silent pass to firing | yes | "39 of 49 threads (80%) never examined" | wrong — 30 of 49; an intermediate "7" was wrong too |
| two dead runs' patches recovered from `fabro dump` | yes | "the work is always recoverable" | wrong — a run whose commit failed has no `diff.patch` |
| a 401 killed a long run at +81 min | yes | "the token dies at 60 min; keep runs under an hour" | wrong — refuted by a janitor verifying at +73.9 min |
| `livespec-overseer`'s current plugin build is empty | yes | "2 of 3 plugin builds are empty" | wrong — one is |

Three specific traps, all of which produced a confident wrong number:

- **`find … | wc -l` returns `0` for an ABSENT directory exactly as for an
  empty one.** That is how "the `livespec` plugin build is empty" happened: the
  path measured was a different marketplace's namespace and did not exist.
  Distinguish absent from empty explicitly.
- **"Not examined" and "defectively not examined" are different populations.**
  The parity check deliberately ignores cross-tenant anchors, so counting
  everything it skips inflates the defect.
- **A classifier written to confirm a hypothesis inherits the hypothesis.**
  The "7" correction searched for the literal phrase `ledger anchor` and so
  could not see homelab's `Ledger epic anchor:` — 13 threads it should have
  counted.

The practical rule: **a demonstration proves the mechanism; it does not size
the population.** Sizing needs its own measurement, with its own control, and
the two should be reported separately so one can be wrong without discrediting
the other. Every wrong number above is left visible in this file rather than
quietly replaced, because the counting error is the part worth learning from.

## Scope boundary — do not silently widen

The maintainer scoped this to `tmp/supervisor/`. The same hazard exists for
anything an agent writes outside SCM and the ledger, and that generalization may
be correct — but it is a **different, larger thread** and must not be absorbed
here without an explicit decision. Name it if you find it; do not take it.

**FOUND AND NAMED, 2026-08-12 — `tmp/overseer/`, filed as `overseer-yqza`, NOT
taken.** The sibling directory the rule does not cover is larger than the audit
that created this thread. It holds **308 files**, including **9,953 lines of
prose** across 63 `.md` files — roughly five and a half times the 1,811 lines
that prompted the original rule — and all three of the original hazards:

| original audit found in `tmp/supervisor/` | present in `tmp/overseer/` |
|---|---|
| a groom draft | `supervisor-prompt-quality/groom-decision-packet.md`, 31 KB |
| a staged set of workflow files | `ready-certification-deadlock/v010-amendments/` — `spec.md` 42 KB, `contracts.md` 26 KB, plus `revise-payload.json` |
| prose with no durable backing | 63 `.md` files, 9,953 lines |
| — | **`v009-amendments-BLOCKED.patch`, a real 22 KB unified diff against `SPECIFICATION/contracts.md`, with a `.README` supplying its intent** |

That last row is the "a changeset is never an artifact" corollary's exact
subject, existing as a file.

**Why it is named rather than fixed here.** `tmp/supervisor/` had a clean rule
available because its legitimate contents are narrow. `tmp/overseer/`
legitimately holds daemon logs, per-thread state, and working material for
operations that have no other durable home yet — a spec revision mid-assembly,
a groom decision mid-draft — plus 51 `.sh` and 26 `.py` helpers. Forbidding
prose there without first naming a home for each kind of material would move
the problem rather than solve it. That is a maintainer design decision, which
is precisely why this boundary says name it and stop.

**Not claimed:** whether any of those 9,953 lines is load-bearing and
unmirrored. Goal 3's equivalent measurement took a dedicated pass. The exposure
is demonstrated; loss is not.

## Status — 2026-08-12. Goals 2 and 3 DONE; goal 1 merged+released but blocked from reaching charters by `overseer-0xg7`. THIS THREAD IS ACTIVE, NOT ARCHIVED.

`overseer-5jttov` was groomed and is `status: done` / `resolution:
no-longer-applicable` — administratively retired because its content was split
into two replacement ledger items:

- `overseer-otjmoh` — goal 2, the `tmp/supervisor/` enforcement check.
- `overseer-m4o33z` — goal 1, the charter rule + corollaries.

Goal 3 is measured and landed in-thread (see the read-first chain above) and
was never filed to the ledger — it is not factory-dispatchable (see the goals
table).

**Do not archive this thread.** Goal 2 is implemented, merged, released and
confirmed working; goal 1 is merged and released but **not** confirmed
reaching a generated charter (`overseer-0xg7`, below). `q3emww` has since
merged, but `livespec-dev-tooling-5asgvm` — the other fleet-wide fix item this
thread's own incident created — is NOT done, and archiving before it is would
repeat the exact error recorded below. An
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

**GOAL 1 CARRIES ONE HONEST CAVEAT, AND IT IS THE KIND THIS THREAD EXISTS TO
CATCH.** Merged, released, and present in the released tag is as far as the
evidence goes. It does **not** currently reach a generated charter on this
host, because the installed plugin build is EMPTY — `just ensure-plugins`
reports `livespec-overseer` "already at the latest version (21d87caf3804)"
while that build directory contains zero content files: no `prose/`, no
`skills/supervise-plan`, nothing for the generator to read. The source is
fine (commit `21d87ca` carries 112 files under `.claude-plugin/`); the
install produced nothing, and re-running `ensure-plugins` does not repair it.
**An earlier revision added "the `livespec` plugin's current build is empty
the same way". That is WITHDRAWN — it was a measurement error.** The
`livespec` plugin is healthy: its build lives at
`cache/livespec-driver-claude/livespec/09cc286f4477` and holds 24 content
files. The empty path I measured, `cache/livespec/livespec/09cc286f4477`, is
a DIFFERENT marketplace namespace where the directory does not exist at all —
and `find … | wc -l` returns `0` for an absent directory exactly as it does
for an empty one. Absent and empty are not the same observation; the tool
could not tell them apart, and I did not check. Exactly ONE build is empty,
`livespec-overseer`'s, which is also the only path that sha resolves to
anywhere under the cache. The consequence for THIS repo is unchanged, but
this is not a fleet-wide installer outage and must not be escalated as one.

Filed as **`overseer-0xg7` (P1)**. Note what it means for the goal's own
wording: `check-prose-release-hygiene` exists to stop exactly this ("the fix
never reaches the plugin cache that generates charters"), the prose rode a
`fix:` commit and shipped in a release as designed, and it STILL did not
arrive — because that gate reads the commit range, not the installed
artifact. So goal 1 is **merged and released, not yet confirmed working
end-to-end**, and this file should not claim otherwise until a session with a
populated build generates a charter carrying the rule.

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
  2026-08-12T01:10:04Z.** Chase commit **`86836a95`** ("docs: require
  completion evidence before plan archive",
  `.claude-plugin/prose/plan.md` + `SPECIFICATION/contracts.md`), NOT the
  `dc7bf0e` that GitHub reports as the merge commit — that one is a fabro
  janitor commit holding only a `SPECIFICATION/history/v060/` snapshot, and a
  reader who chases it finds nothing about archiving. Verified content: the
  old "archived if and only if its epic is closed" rule is replaced by a
  completion-evidence rule that explicitly warns closed "can also mean
  regroomed out, superseded, or otherwise retired without completing the
  work" — the precise error this thread committed — and it names `5asgvm`
  and `q3emww` as the outstanding mechanical enforcement.
- `livespec-dev-tooling-q3emww` (pre-existing, found independently by another
  thread the same day as the homelab incident) — fixes the converse gap: an
  archived thread whose anchor epic is still open passes green today.
  **Run `01KZSPSTPFX6` failed and was reaped, but its work was NOT lost: the
  patch was recovered with `fabro dump` and landed unchanged as
  `livespec-dev-tooling` PR #1368, **MERGED 2026-08-12T10:31:12Z as commit
  `201cabb`** — verified by reading `origin/master`, where
  `plan_thread_epic_parity.py` now carries `_ARCHIVED_HANDOFF_GLOB`. The item
  is CLOSED.** Red leg
  hook-confirmed, Green amend and push gates each 66/66 targets. The phantom
  claim was released 2026-08-12. See "The q3emww loss" below — it is now a
  recovery story, not a loss.
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
PR exists.

**BUT THE WORK IS NOT GONE — THAT CLAIM, WHICH THIS FILE MADE ON 2026-08-12 AND
WHICH `.claude/CLAUDE.md`'s "fifth shape" STILL MAKES, IS WRONG.** `fabro dump
<run> -o <dir>` exports a reaped run's durable state, and
`stages/002-implement@1/diff.patch` holds the complete implementation.
Recovered for this run: `livespec_dev_tooling/checks/plan_thread_epic_parity.py`
plus `tests/.../test_plan_thread_epic_parity.py`, 244 patch lines, and it
**applies cleanly to current `livespec-dev-tooling` master**. It contains
exactly what the acceptance demanded — an `archive/**/handoff.md` scan
(`_ARCHIVED_HANDOFF_GLOB`, the converse direction nothing scanned before) and
the demonstrated-failing fixture `test_armed_archived_open_epic_fails`.

So the remedy for a run reaped mid-interview is **dump it first**, not redo it.
The dump also works on old runs — it was used here on a 2026-08-09 run — so
retention is not the constraint.

**Root cause of the 401 — it is NOT a broken or revoked credential, and it is
NOT specific to this item.** Fabro authenticates to GitHub with a **GitHub App
installation token** (`fabro secret list` → `GITHUB_APP_PRIVATE_KEY`;
`~/.fabro/settings.toml` → `[server.integrations.github] app_id`). GitHub caps
those at 60 minutes. The credential the AGENT holds inside its own long-lived
session goes stale on a long run; a freshly-started stage gets a working one.

Measured, over the last 30 runs — exactly TWO contain a genuine
`Bad credentials` string, and both are long runs where **the AGENT itself ran
`just check` from inside its own session**:

| run | item | 401 at | who ran the check | outcome |
|---|---|---|---|---|
| `01KZSPSTPFX6` | `q3emww` | **+81.0 min** into the run | the agent, in-session | failed |
| `01KZSKQKYNPK` | `bd-ib-mrqoy2.5` | **+68.4 min** into the run | the agent, in-session | failed |

Every run that finished under 60 minutes passed the same check — the four
dispatched by this thread ran 9/19/21 min and all passed it. `bd-ib-mrqoy2.5`
was re-dispatched, finished in **24m35s, and SUCCEEDED** (`01KZSSNNNZDG`) —
same item, same code, same credential.

**AN EARLIER REVISION OF THIS FILE CLAIMED THE RULE IS SIMPLY "the token is
minted once per run and dies at 60 minutes, so keep runs under an hour". THAT
IS REFUTED — DO NOT ACT ON IT.** The disproof is run `01KZKT8CE9MQ`
(2026-08-09, same repo): its **janitor** stage ran the full `just check` from
+73.8 to +109.7 min and `check-master-ci-green` passed in 3.1s at **+73.9 min**,
well past the hour. That it genuinely VERIFIED rather than skipped is provable
from the module's own shape — every skip path calls `log.warning`, the green
path returns 0 silently, and the recovered janitor log contains **no** check
output at all beside `exit_code: 0`. In the same run the agent's own `just
check` runs were at +1 min and +37.5 min, both inside the hour.

So the discriminator that fits ALL THREE observations is **who runs the check
and how old their session is**, not raw run elapsed time: an agent working past
the hour inside one session fails, while a fresh command stage started past the
hour succeeds. The exact TTL/refresh mechanism is NOT established, and this
entry deliberately stops short of asserting one.

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

**The control that once "did not fit" is now RESOLVED, and resolving it is what
overturned the 60-minute story above.** An earlier revision recorded run
`01KZKT8CE9MQ` as unexplained because its janitor output was "a
content-addressed blob not locatable under `~/.fabro/storage`". That was a
search failure, not an absence: **`fabro dump <run> -o <dir>` exports it**, as
`stages/003-janitor@1/output.log`. Read it before calling any run's internals
unavailable — the same command is what recovered q3emww's lost patch.

**`q3emww`'s phantom claim is already released** (status `ready`, assignee
cleared, root cause appended to the item, 2026-08-12). Do not release it again.

**Prefer RECOVERY over re-dispatch for `q3emww`.** Its implementation exists and
applies cleanly to current master (see above); re-dispatching would pay for the
same work twice and re-run the same risk. Whichever path is taken, annotating
the item to PUSH AND OPEN A DRAFT PR BEFORE raising any blocking question is
what actually protects future work — the item's own escalation happened with
nothing pushed.

## Next action

**ON RESUME, ORIENT HERE FIRST — session of 2026-08-12 ended at this point.**

All three goals and both dispatched fleet-fix items that could be finished
WERE finished; nothing is half-done and no branch is left dangling. Every PR
this thread opened is merged, no worktree of this thread's remains, and the
ledger matches. Concretely:

| thing | state |
|---|---|
| goals 2, 3 | done, verified by demonstration |
| goal 1 | merged + released, **not** confirmed reaching a generated charter — `overseer-0xg7` |
| `bd-ib-ycihm7`, `livespec-dev-tooling-q3emww` | merged; `q3emww` recovered from a dead run, master CI 30/30, item closed |
| `livespec-dev-tooling-5asgvm` | ready and annotated — **THE ONE BLOCKING DECISION** (item 2 below) |

**There is exactly one thing a resuming session cannot decide for itself: the
`5asgvm` dispatch (item 2). Everything else below is either done or is
independent work you may pick up.** If the maintainer has not answered, do NOT
dispatch it — say so and pick up item 3 or 5 instead.

Three items were FILED this session and are NOT part of goals 1–3; they are
named here only so they are not rediscovered from scratch:

- **`overseer-0xg7` (P1)** — install records name an EMPTY plugin build while
  `ensure-plugins` reports success. 3 of 55 livespec-family records point at
  `livespec-overseer` build `21d87caf3804`, affecting `livespec`,
  `livespec-overseer` and `homelab`. This is what blocks goal 1 end-to-end.
  The fix shape and a ready-made acceptance fixture are recorded on the item;
  the code lives in `livespec-dev-tooling`, so a sibling item belongs there
  when it is scheduled.
- **`livespec-dev-tooling-ivd8` (P2)** — see item 4 below.
- **`overseer-yqza` (P2)** — the `tmp/overseer/` generalization, NAMED and
  deliberately NOT taken. See the scope boundary section.

**A WARNING ABOUT THIS REPO'S PRIMARY CHECKOUT.** It was left BEHIND `master`
because two other tracks (`adoptable-launch-discipline`,
`resume-submit-integrity`) have uncommitted work in `plan/` that a
fast-forward would clobber, so the merge correctly refuses and their files
were deliberately not touched. **`git fetch` and compare against
`origin/master` before trusting any file you read there**, including this one.

1. **DONE 2026-08-12** — `livespec-dev-tooling` PR #1368 merged (`201cabb`)
   and `q3emww` is closed with the merge recorded. The patch was recovered
   from the dead run rather than reimplemented. Master CI for that commit was
   still running when it was closed; if it goes red for this change, reopen.
   The recovery technique is now written up in this repo's `AGENTS.md` "fifth
   shape" entry (PRs #840, #841 — both MERGED), which previously told every
   session that such work was destroyed.
2. Dispatch `livespec-dev-tooling-5asgvm` (command above) now that `q3emww`'s
   shipped shape exists for its implementer to compose with. The item is
   already annotated with that shape and with the push-a-draft-PR-before-
   escalating rule; **this is real factory spend, so it is a maintainer
   go/no-go, not an automatic step.**
3. Consider filing the two credential defects surfaced above: (a) fabro should
   refresh the installation token during long runs — the actual root cause;
   (b) `master_ci_green` should treat a 401 as *invalid credential →
   environmental*, distinct from a failed-while-credentialed API call. **Weigh
   (b) carefully rather than filing it reflexively:** that check's present-but-
   invalid hard-failure is a DELIBERATE design decision, documented in its own
   docstring, taken to close a hole where an outage routed a credentialed
   caller onto the fail-soft path. Narrowing it to 401-only is defensible, but
   it is a design change with a real trade-off, not an obvious bug — and this
   repo's charter-gate experience is that "the detector is wrong" is usually
   the wrong first guess.
4. **A THIRD DEFECT WAS FOUND WHILE LANDING (1) AND IS ALREADY FILED:**
   `livespec-dev-tooling-ivd8`. `plan_thread_epic_parity` decides whether to
   examine a thread by regex-matching the handoff's anchor PROSE, and silently
   skips it — no warning, exit 0 — when that fails. Measured with the real
   check, armed, changing only formatting: as-filed → silent pass; anchor line
   reformatted → fires with `epic_status: closed`. Fleet-wide, **30 of 49
   active plan threads declare a same-tenant anchor this regex cannot parse**
   (61%); 10 parse correctly, and 9 more have no same-tenant id near any
   anchor line and are left unclassified. It is orthogonal to `q3emww` and
   `5asgvm` — it drops the thread before either assertion runs, so neither fix
   helps on those 30.

   **An earlier revision of this file said "39 of 49 (80%) are never
   examined". That number is WITHDRAWN** — it counted every thread the check
   does not examine, but the check DELIBERATELY ignores anchors outside the
   repo's own tenant, so "not examined" and "defectively not examined" are
   different populations. (A first correction said "7", which was wrong too:
   its classifier searched for the literal phrase "ledger anchor" and so
   missed homelab's "Ledger epic anchor:" convention — 13 threads that do
   declare a same-tenant anchor the regex cannot read.) Three unparseable
   shapes are now known: bold wrapped around the backticked id; an unbolded
   label; and a different label phrase entirely. The hand-verified
   demonstration above is unaffected by the counting and still stands.
   **This thread is itself a live instance of BOTH `5asgvm` and `ivd8`:** its
   anchor `overseer-5jttov` is closed procedurally (regroom-out) while its work
   continued, and its own handoff is one of the 39 the check cannot see. Note
   the hazard if `ivd8` is fixed alone: the check would then start firing on
   this thread with the remediation "the plan thread is complete — archive it",
   which is exactly the premature-archival error recorded above.
5. Only once `5asgvm` has a real merged PR (`q3emww` now does): replace this
   whole "Status"/"Dispatch outcome"/"premature-archival incident"/"q3emww
   loss" section with a short completion summary citing every PR, and only
   THEN consider archiving — re-running the plan operation's handoff
   self-sufficiency gate first, same as any other refresh. `ivd8` is a
   separate thread's problem and must NOT be absorbed here; name it and leave
   it, per the scope boundary above.

Do not hand-code implementation inline in a planning session — the factory
path (`drive --action impl:<id>`) is the only implementation path for any of
this.
