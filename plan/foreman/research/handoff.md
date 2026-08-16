# Plan — foreman

## Checkpoint 2026-08-05T04:42Z — overseer-afn leg 3 measured in real `codex exec`

This is the newest AFN status block and supersedes the older AFN statement below
that leg 3 remained unexecuted.

**ACCEPTANCE LEG 3 IS DISCHARGED.** A real headless `codex exec` probe ran on
2026-08-05T04:40Z through `npx -y @openai/codex@0.146.0 exec`, because no
`codex` binary was present on the sandbox PATH. The invocation reported
`OpenAI Codex v0.146.0`, `approval: never`, `sandbox: danger-full-access`, and
workdir `/workspace/livespec-overseer`, so the measured harness was headless
`codex exec`, not the interactive TUI picker surface measured for legs 1 and 2.

The probe simulated a supervised session that needed an unanswerable human
choice and instructed it to use the marker-protocol prose fallback. The session
wrote exactly one line under the repo's ignored temp tree:

```
tmp/overseer/overseer-afn-codex-exec-probe/.overseer-state
blocked: needs human choice between release train A and B.
```

Verification after the run: `wc -l` returned `1`, `git check-ignore -v` matched
`.gitignore:2:tmp/`, and `git status --short` stayed clean. The model did not
render or rely on a structured picker; it wrote the out-of-band `blocked:`
declaration, which is the fallback this leg exists to prove. Do not rerun the
interactive YOLO exposure measurement; legs 1 and 2 were already discharged by
external pane capture and v009/marker-protocol ratification.

## Checkpoint 2026-08-05T03:33Z — WIND-DOWN: v007 RATIFIED; AFN proposal filed, ratification supervisor-owned

This is the newest resume block and supersedes every older status statement
below. Fetch and re-measure the forge, ledger, and Fabro before acting.

**PHASE C IS CLOSED. THE PHASE D POLICY FOUNDATION IS RATIFIED.** PR #688
rebase-merged as `c57d928a48b27d75521f7f7d2785605dbd08dcfd` at
2026-08-04T14:10:54Z. `SPECIFICATION/history/v007/` is present and the
self-retiring report-only clause is gone. The ratified policy has a
`report-only` safe default, the consensus disposition, hard human floors,
journal-first action, and fail-closed escalation. Do not re-run that revise or
re-file its proposal.

**THIS WORKER TOOK `overseer-afn` AND FILED ITS CONTRACT AMENDMENT.** It
announced ownership in the pane before acting so the supervisor would not
duplicate the slice. PR #689 (`d719038`) rebase-merged as
`5d6bc70ad59665758402b9ea71556bd744595896` at 2026-08-04T14:21:11Z, with all
checks green. It filed
`SPECIFICATION/proposed_changes/codex-yolo-structured-question-protocol.md`.
The proposal makes structured-question capability depend on live gate evidence
rather than the YOLO label while preserving all of these load-bearing paths:

- the general `blocked: <reason>` escape hatch;
- the `codex exec` / headless prose fallback;
- structured-gate suppression of daemon pastes; and
- the restart prohibition for a blocked declaration.

Static propose-change checks passed. The LLM doctor found no defect in the new
proposal; its only subjective drift was the already-known v007 policy-to-code
gap carried by supervisor-owned `overseer-ym6`, so no duplicate item was filed.
Two comments on `overseer-afn` carry the exact PR/merge evidence. The beads
comment write succeeded and was read back authoritatively; its secondary
auto-backup warned that the tenant user cannot register `backup_export`, which
did not undo the comment.

**THE MAINTAINER RULED `RATIFY NOW`, AND THE SUPERVISOR OWNS EXECUTION.** The
supervisor proxied the worker's picker because an open picker suppresses daemon
wrap-up. The maintainer also ruled that the two false examples at
`overseer/marker-protocol.md` around lines 240 and 256–257 must be corrected in
the SAME change: that module document sits outside `SPECIFICATION/`, so revise
alone cannot update it. The supervisor explicitly owns the revise pass plus
that marker-protocol correction. **Do not run revise, create a revise worktree,
or edit marker-protocol.md.**

Final authority measurement at 2026-08-05T03:33Z: `origin/master` was
`bb78a14`; `SPECIFICATION/history/v008/` exists for an unrelated tombstone-ban
ratification, while `SPECIFICATION/proposed_changes/` still contains the afn
proposal, an unrelated `post-void-ready-certification.md`, and README. No
marker-protocol correction commit or afn ratification PR was visible. Therefore
the supervisor-owned work was still pending at that measurement. On resume,
fetch and inspect the newest history/proposals and forge before saying whether
it landed; do not race it.

**AFN MEASUREMENT STATUS:** acceptance leg 1 is positive and leg 2 is also
satisfied: an external pane capture observed the native picker itself, proving
the tool was offered and called rather than merely described by the model.
Acceptance leg 3 — execute the prose fallback through real `codex exec` —
remains unexecuted. This assignment explicitly said **do not launch any nested
Codex session**, so this worker did not run that probe. A successor must preserve
that prohibition unless the maintainer explicitly changes it; never substitute
a unit import or prose inspection for the required real-harness evidence.

**PHASE D OWNERSHIP/ORDER REMAINS:**

- `overseer-ym6` is supervisor-owned and not a factory dispatch. Its spec leg is
  discharged by v007; remaining work is the config-key read, journal-writing
  RED test, opt-in control, and panel wiring. Do not duplicate it.
- `overseer-0fy` is gated only by ym6 now that ncx is closed.
- `overseer-ctc` is the shipped-artifact requirement-5 exit and the first point
  at which the foreman product may be run. Do not start the product earlier.
- `overseer-6eo` remains a separate open P1 with the narrowed evidence recorded
  in the previous checkpoint; do not admit it merely to stay busy.

No Fabro run, foreman runtime, sub-agent, or background subprocess was started
by this worker. The merged proposal worktree
`~/.worktrees/livespec-overseer/spec/codex-yolo-structured-question-protocol`
was clean at wind-down and its remote branch was already deleted; it is a
completed artifact, not a resume target.

## Checkpoint 2026-08-04T13:17Z — WIND-DOWN: Phase C CLOSED; ratification chosen, not yet executed

This is the newest resume block and supersedes every older status table below.
Re-fetch and re-measure before acting.

**THE REOPENED WORK THROUGH PHASE C IS CLOSED AND RELEASED.** The entrypoint
gate and the seed-3/4/6/7 shipped-artifact E2E are closed, as are both live-tick
defects (`overseer-gxzv5v`, `overseer-5f2pfj`). Phase C is now fully closed:

- `overseer-a7c` panel core — PR #668, closed and released.
- `overseer-xbn` model-pin correction — PR #675, closed and released.
- `overseer-ncx` minority-report round — Fabro
  `01KZ679ZJM93EH05HF184EP1QZ`, PR #681, merge
  `ec778b2ef792d08be9f64a8268f707f853fb2916`; 62 checks succeeded and two
  skipped, fetched `origin/master` ancestry verified, post-merge janitor green,
  ledger closed. Supervisor reports it released in v0.30.0. **Do not
  re-dispatch it.**

**THE ONLY THREAD GATE IS NOW THE MAINTAINER REVISE PASS.** PR #679 merged the
proposal
`SPECIFICATION/proposed_changes/foreman-consensus-decision-policy.md`. It was
still present at the last filesystem measurement, so it was not ratified.
At wind-down the native picker asked whether to ratify now or defer; the
maintainer selected **Ratify now (Recommended)**. That answer is authorization,
not evidence that `/livespec:revise` ran. On resume:

1. Fetch first, then check `SPECIFICATION/proposed_changes/` and the newest
   `SPECIFICATION/history/vNNN/`.
2. If the proposal is still present, route the actual maintainer
   `/livespec:revise` pass. Do not re-file PR #679 and do not claim ratification
   from the picker answer.
3. Do not start Phase D implementation until ratification is measured.

**PHASE D ORDER AND OWNERSHIP AFTER RATIFICATION:**

- `overseer-ym6` is `ready`/P1 but the supervisor binder explicitly says it is
  supervisor-owned and **not a factory dispatch**; it is cross-repo spec/config
  lifecycle work. Do not send it to Fabro.
- `overseer-afn` is `ready`; acceptance leg 1 is DONE and positive: in this
  genuine Codex YOLO session the native `request_user_input` tool was available,
  was actually called, rendered a picker, and was answered externally. The
  exact evidence is on the item. Legs 2–3 and the marker-protocol amendment
  remain; preserve the `codex exec` prose fallback and the general `blocked:`
  escape hatch.
- `overseer-0fy` follows `ncx` + `ym6`; `overseer-ctc` follows the completed
  Phase D slices and is the requirement-5 shipped-artifact E2E exit condition.
- **Do not run the foreman product before `ctc`.** The supervisor made that an
  explicit ordering constraint, even though the earlier classifier defect is
  fixed.

**`overseer-6eo` REMAINS OPEN P1 BUT ITS LIVE IMPACT NARROWED.** It is still
`backlog`, unassigned, and not admitted; do not change queue state merely to
keep busy. The same original pane/PIDs and rollout remained live, but
`~/.codex/session_index.jsonl` eventually added that rollout at
10:59:47Z (about 4h22m after rollout birth), and the fresh daemon snapshot at
12:12:03Z reported this topic `working`, `runtime=codex`, `tmux=foreman`. The
daemon then successfully injected `idle-with-context-left`. This refutes the
end-of-session-only indexing hypothesis, but the exact write trigger is still
unestablished and none of the RED/gone-control/real-tmux acceptance is built.
The measured narrowing is recorded on the item; do not close it.

**Nothing owned by this worker is in flight at wind-down.** The unrelated
factory run `overseer-cdhdlv` belonged to another track and was not touched.
No foreman runtime was started, no supervisor-owned Phase D item was
dispatched, and no background watcher or sub-agent remains. Durable ledger
comments on `overseer-z5fo4y`, `overseer-ncx`, `overseer-afn`, `overseer-ym6`,
and `overseer-6eo` carry the evidence behind this checkpoint.

## Checkpoint 2026-08-04T07:18Z — entrypoints PROVEN DEPLOYED; Phase C+D RULED IN

Two things changed since the reopening block below was written. Both are
measurements, not summaries; re-measure before carrying either forward.

**1. THE ENTRYPOINT DEFECT IS PROVEN FIXED IN THE ARTIFACT A USER RUNS.**
Release `v0.27.5` (`c35dea6`, PR #664, merged 06:51:54Z) contains the fix
`c6ace4b`. Every file in the released cache build `c35dea62368f`'s `bin/` —
enumerated from the tree, not from a list — was EXECUTED under
`env -u PYTHONPATH` at 06:56:40Z: `foreman-act`, `foreman-runtime`,
`overseer-start` and `overseerd` all exit 0 and print usage. The negative
control is what makes that meaningful: the prior build `af2e3af9aa61` (v0.27.4)
is still on disk and the identical commands still exit 1 with
`ModuleNotFoundError` on both foreman binaries. **This closes the ENTRYPOINT
question only — it says nothing about the seed requirements, which are still
the reopening's exit condition.**

**2. THE MAINTAINER RULED AT 07:12Z: BUILD PHASE C+D NOW.** Seed requirement 5 —
the Fable/Opus/GPT-sol consensus panel with the minority-report override — is
now IN scope, together with the gate-driving layer needed to auto-act or
re-present a blocked prompt, and the cross-repo spec amendments that reverse the
report-only disposition (review finding C1). **The shipped "do not add Phase C
consensus" prose and the `human_action_report_only` refusal are SUPERSEDED by
that ruling.** As of 07:18Z **no Phase C or Phase D work item exists** — the
decision is recorded on the epic and nothing carries it, which is precisely how
requirement 5 was lost the first time. Filing that cut is the highest-value next
action; the design is already binding in `research/brainstorm.md`, so it is
transcription rather than invention.

**Live items, re-measured 07:18Z:**

| Item | State |
|---|---|
| `overseer-6fm` e2e entrypoint gate | **closed**, released in v0.27.5, proven above |
| `overseer-gxzv5v` actuator filing + journal defect | **`active`/`fabro`**, run `01KZ5RWXGN67` confirmed `running`. Do NOT re-dispatch. |
| `overseer-5f2pfj` occupied-session classifier | `pending-approval`, deliberately held until `gxzv5v` lands |
| `overseer-mqpgs7` E2E for seed requirements 3/4/6/7 | `pending-approval`, blocked by BOTH `5f2pfj` and `gxzv5v` |
| `overseer-6eo` (NEW, P1) | the daemon reports this thread's own LIVE worker as `session-gone`, so nothing is supervising it — no wrap-up, no restart |

**WHILE `overseer-6eo` IS OPEN, THE WORKER GETS NO WRAP-UP.** The daemon's fresh
snapshot reports `topic=foreman` as `session-gone` with `runtime=null` because
the session's codex rollout post-dates the last write of
`~/.codex/session_index.jsonl`. A supervised session must NOT wait for a wrap-up
injection that is not coming; self-checkpoint into the ledger instead.

## Status: REOPENED 2026-08-04T06:20Z — v1 WAS NEVER PROVEN TO RUN

**The archive below was wrong, and the maintainer caught it by running the
product.** The first real invocation of `/livespec-overseer:foreman` in a
correctly-named session found that **both shipped executables are dead on
arrival**:

```
$PLUGIN_ROOT/bin/foreman-runtime  -> ModuleNotFoundError: No module named '_claude_sessions_proc'
$PLUGIN_ROOT/bin/foreman-act      -> ModuleNotFoundError: No module named 'jsonio'
```

Reproduced independently on cache build `0.27.2`, on `ff2644d0fc8e`, and on the
repo-side `.claude-plugin/bin/` copy. Both pin only the plugin ROOT onto
`sys.path` and then `from overseer import …`, but every module flat-imports its
private siblings (`import jsonio`, `import _claude_sessions_proc`). The sibling
executables do not have this defect because `bin/overseerd` and
`bin/overseer-start` go through `python3 -m overseer.daemon`, and `daemon.py`
self-pins its own directory. The one tick that appeared to work only proceeded
under an out-of-contract `PYTHONPATH=$PLUGIN_ROOT/overseer`.

**HOW ELEVEN CLOSED SLICES, 983 GREEN TESTS AND 100% COVERAGE MISSED THIS.**
Every acceptance leg was satisfied by beside-tests that `sys.path.insert` the
package directory and import modules directly. **Nothing ever executed a shipped
entrypoint.** So the unit behaviour was real and the product could not start —
and both release gates, the post-merge janitor, and a live daemon restart all
passed over it. A test that never runs the artifact the user runs proves the
artifact's *logic*, not the artifact.

**THE GOVERNING REQUIREMENT WAS NEVER TESTED END TO END, AND THAT IS THE POINT.**
`research/seed-prompt.md` is the maintainer's verbatim intent. Requirement 5 —
the Fable/Opus/GPT-sol consensus panel with the minority-report override — is
the engine for goals 2 and 3 (spend the maintainer's attention only on decisions
that are genuinely theirs). It was deferred as "Phase C" and is NOT BUILT, so
today the foreman can only *report* blocked items, which is the escalation load
the seed asked to remove. Requirement 7's loop, requirement 6's `NEEDS YOU`,
requirement 3's per-work-item tmux sessions and requirement 4's auto-created
sessions have no end-to-end proof either.

**EXIT CONDITION FOR THIS REOPENING: e2e tests that execute the shipped
artifacts and demonstrate the seed-prompt requirements actually working.** Not
unit tests with injected fakes. Do not archive this thread again on unit-green.

Three defects the first live tick surfaced, all reproduced:

1. **Shipped executables cannot start** (blocking) — above.
2. **`work_item_file` cannot complete** (blocking) — the filing subprocess runs
   `[sys.executable, "-c", …]` under a `--no-project` uv shebang and raises
   `ModuleNotFoundError: No module named 'livespec_orchestrator_beads_fabro'`;
   that package lives only in the orchestrator plugin's `scripts/` dir and
   nothing puts it on the path. Worse, `append_journal` sits AFTER the raising
   call in `act()`, so **a failed filing leaves no audit trace at all**.
3. **The classifier would start into an OCCUPIED tmux session** (latent,
   destructive) — `classify_session_lifecycle` special-cases only `unassigned`
   and `_matching_live` keys purely on the registry name. Measured live:
   `charter-gate-ratchet` returns `action=start` while its tmux session holds a
   live Claude (pid 1741876). Only the prose boundary kept this from firing.

---

## Superseded status block — v1 (phases A+B) shipped 2026-08-04

Closed `2026-08-04T01:2xZ`. The epic `overseer-z5fo4y` is CLOSED and all
**eleven** children are closed: Phase A `.1`–`.5`, Phase B `overseer-by6hrx`,
`overseer-eqbk4h`, `overseer-4opppx`, `overseer-wykyth`, `overseer-vts4lo`,
`overseer-qp3vpb`. Phases C–E (consensus, gate-driving, federation) were never
in v1 and remain separate future scope — do not read this record as covering
them.

**THE DEPLOYMENT WAS VERIFIED BY BEHAVIOUR, AND A VERSION CHECK WOULD HAVE
LIED.** The gap this file warned about below was real and was closed: the acting
daemon had been up 16h50m, was SEVEN releases behind (its own header said
`0.20.2` against master's `0.27.0`), and loads from the repo checkout via an
EDITABLE install — so the plugin-cache update to 0.27.0 could never have reached
it. On explicit maintainer authorization it was restarted in place
(`tmux respawn-pane -k` on `livespec-overseer:1.1`, pid 448432 → 1130052), after
a pre-flight that fast-forwarded the checkout to the released commit and
smoke-tested `from overseer.daemon import main` so a failed relaunch could not
strand the fleet. **53 rows before, 53 rows after — no supervision was lost.**

Slice `.4`'s surfacing was then proven live with three controls, because the
obvious test would have said the opposite: after the restart the snapshot STILL
contained no `heartbeat` string, and reading that as "the code is not live"
would have been WRONG. `_supervisor_foreman.py` surfaces a heartbeat only when
`<repo>/tmp/overseer/foreman/heartbeat.json` is PRESENT **and** stale; no foreman
runtime runs, so silence is correct behaviour and says nothing about which code
is loaded.

| control | expectation | result |
|---|---|---|
| heartbeat 2h stale, interval 60s | row appears | `foreman-heartbeat-stale`, rows 53 → 54 |
| heartbeat fresh (~0s) | row absent | absent, rows 53 (staleness RULE applied, not file presence) |
| file removed | baseline | rows 53, no residue |

The synthetic heartbeat was removed afterwards; it was report-only by design
("never authorizes a daemon act"), so nothing could act on it.

**Resume nothing from this file.**

**A LIVE-PATH TOMBSTONE WAS ADDED AT ARCHIVE TIME AND HAS BEEN REMOVED — it was
the wrong remedy and it caused a worse problem.** `plan/foreman/handoff.md`
existed briefly so a stale respawn prompt would resolve to something true.
`_registry_discovery.archived_or_gone` returns False whenever
`plan/<topic>/` is a directory ("active plan present — wins over any same-named
archive"), so the stub made this finished thread read as ACTIVE:
`_supervisor_discovery.archive_gc` could never drop its mapping row, and the
daemon went on nudging, wrap-up-injecting and restarting an archived track.
Measured here — with the stub in place, `archived_or_gone(topic="foreman")` was
`False`, the row was still in `~/.livespec-overseer.jsonl`, and the worker sat at
`ready-uncertifiable` on 17% context. The same mistake was measured on two other
threads, which were injected and RESTARTED after archiving.

**The clean `git mv` is the whole remedy.** With `plan/foreman/` gone,
`archived_or_gone` returns True, `archive_gc` drops the mapping row, and the
respawn hazard cannot fire because no row remains to respawn from. The hazard is
closed by the GC, not by a stub — which also refutes remedy 1 on `overseer-y26`.

## What this thread is

A new `livespec-overseer:foreman` surface: a singleton per-repo LLM operator
session (required tmux AND runtime-registry name `<repo-slug>-foreman`) on an
hourly loop that keeps its OWN repo's plans and work-items moving, escalates
only what a cross-vendor model-consensus panel confirms genuinely needs the
maintainer, keeps everything else progressing, and coordinates with peer
foremen in other repos by filing — never by driving their queues. It is a
PEER of the overseer daemon: the daemon stays the deterministic mechanical
layer (unchanged, including its `NEEDS YOU`), and the foreman builds the
semantic decision-routing layer on top of a new read-only daemon snapshot.

Ledger anchor: `overseer-z5fo4y` (epic). Its Phase A children are
`overseer-z5fo4y.1` – `.5`; its Phase B children are the six random-id slices
listed in the checkpoint below. Every epic edge is prose-only — this tenant's
bridge does not create parent edges — while inter-slice blockers are real
`blocks` edges.

## Read-first chain (in this order, all beside this file)

1. `research/seed-prompt.md` — the maintainer's verbatim requirements,
   including addendum item 8 (the mandatory `<repo-slug>-foreman` name).
2. `research/brainstorm.md` — the grounded architecture. Its §3 records four
   maintainer decisions that are FIXED inputs (snapshot transport; a
   consensus policy tier via spec amendment; daemon attention unchanged and
   subsumed; v1 = phases A+B). Its §4 is the CURRENT (v2, post-review)
   phasing; its correction banners are live corrections, not history.
3. `research/review-findings.md` — the external adversarial review record
   (Opus + GPT/Codex, 33 findings, every load-bearing claim independently
   re-verified). The per-phase dispositions in it are BINDING design
   constraints; do not re-litigate a finding without new evidence.

## Restart checkpoint — 2026-08-03T20:00Z, CORE `foreman-act` LANDED; FILE/JOURNAL SLICE NEXT

**ALL FIVE PHASE A SLICES ARE CLOSED.** `.1` (snapshot export), `.2`
(`list --json`), `.3` (foreman-gather), `.4` (heartbeat surfacing), `.5`
(`-foreman` reserved suffix). Landed as PRs #582/#585 + #601 (dedupe), #607,
#621, #619, #580. Re-measured from the ledger at 18:32Z.

**DO NOT ARCHIVE THIS THREAD YET — and the previous version of this file told
you to, which is the error this checkpoint exists to correct.** It said the
remaining scope after Phase A was "archive this thread, then fleet rollout".
That is wrong. The epic `overseer-z5fo4y`'s own record carries the maintainer
decision of 2026-08-02: **`v1 = phases A+B` (observe, then mechanical acts)**,
with consensus / gate-driving / federation following. Phase A is only the
OBSERVE half. Archiving here would ship half of v1 and strand the other half
with no carrier.

**PHASE B NOW HAS SIX INTAKE-TRIAGED FACTORY SLICES.** They were transcribed
from the already-reviewed Phase B design through the `capture-work-item`
store + six-gate intake seam at 18:45–18:47Z, not filed with raw `bd create`.
The two independent foundations are closed; the first integration slice is
active; every later slice remains `pending-approval` with real `blocks` edges.
The epic stays `backlog` until all six close.

The deterministic wrapper/runtime (`overseer-by6hrx`) merged as PR #625 at
`ee2a1a1`; the fail-closed classifier (`overseer-eqbk4h`) merged as PR #627 at
`07bf2ae`. Both passed their post-merge janitors and closed in the ledger.
The core session-lifecycle `foreman-act` (`overseer-4opppx`) merged as PR
#630 at `ad76472`, passed its post-merge janitor, and closed in the ledger.

**A CONCURRENT RAW-FILED DUPLICATE WAS CONTAINED:** `overseer-z5fo4y.6` was created
without `intake:triaged` after the six-slice cut and duplicates the wrapper
scope already merged in #625. Its run `01KZ4GWPDG0ARJ5Z9F2YVECJ0N` was
interrupted/steered at 19:26Z with the merge evidence and an explicit command
not to publish. It terminated failed without a PR, and the record closed at
19:31Z with `resolution:duplicate` and #625/`ee2a1a1` as replacement evidence.
No worktree or branch was touched directly.

Phase B was already SPECIFIED and its design is BINDING — see
`research/brainstorm.md` §4, which post-dates the external review:
the LLM foreman acting narrowly, behind an entry gate + tmux-name mutex + a
deterministic wrapper (lock, tick scheduling, LLM rotation from a durable
handoff), acting ONLY through a whitelisted `foreman-act` executable (session
lifecycle behind the deterministic never-started / crashed-resume /
ambiguous-report classifier, absolute repo paths, work-item sessions as
bounded one-shots with journaled claims; plus filing and journal triage), with
human valves REPORT-ONLY (C1) and act-time re-verification against a fresh
snapshot read. The ledger cut preserves that design; do not re-cut or groom it
unless a factory run returns concrete non-convergence evidence.

**HOW THE WRONG ARCHIVE CLAIM GOT HERE, because the mechanism matters more
than the correction.** It came from the supervisor binder's status block
("REMAINING ON THIS THREAD: `.2` and `.4` land, then `.3`, then archive the
thread, then fleet rollout") and was copied into this file without being
checked against the epic. It is the same defect class this thread has now
recorded three times — T2 (a ledger fact asserted, not measured), C18 (a
defect re-measured while the claim ABOUT it was not), and T4 (a cause inferred
from a label). **A scope claim is a claim with a timestamp exactly like an item
status.** The epic was one `bd show` away.

The previous prepared-revise checkpoint is fully discharged. The nine-proposal
ratification landed as v006 in `47ad0e0` (PR #575), and
`SPECIFICATION/proposed_changes/` is empty. The
`spec-revise-v005` worktree and its payload are completed artifacts, not a
resume target. **Do not run revise again.**

**THE `.1` DUPLICATION CLEANUP IS DONE — the section below that calls it "the
urgent unfinished state" is superseded and kept only as provenance.**
`overseer-41p` merged as PR #601 at 07:54:27Z and closed; master `ee0fc7f`
deletes `overseer/_supervisor_status_snapshot.py`, its `.claude-plugin` mirror
and `tests/test_status_snapshot_export.py`, leaving `_supervisor_snapshot.py`
as the single once-per-tick writer. `overseer-z5fo4y.1` is `closed`.
`overseer-n7xx67` also closed (PR #600). Re-measured from the ledger and the
forge at 08:11–08:18Z. **Do not go looking for two snapshot modules; there is
one.**

Slice `.5` also landed as `335a578` (PR #580). Task 05 investigated its only
red forge job before touching the branch. The job's actual first-attempt
complaint was an environment-setup timeout downloading `ruff==0.8.6`; it never
executed the named commit-pair check. An unchanged failed-job rerun executed
`check-commit-pairs-source-and-test`, which passed, followed by `ci-green`.
Auto-merge then landed the PR. No commit reshape, code edit, rebase, push, or
work-item re-dispatch occurred. The ledger's `.5` note claiming a REAL pairing
defect is therefore stale and contradicted by the forge log.

**RETIRED 2026-08-03T08:11–08:18Z — kept because the mechanism is the durable
part, re-tensed because the imperative expired.** For several hours the urgent
unfinished state WAS slice `.1`: two independent implementations had merged, in
`f54ff05` (PR #582) and `1065ad7` (PR #585), and `overseer-41p` (P1) recorded
the duplication and the required cleanup. That cleanup merged as PR #601;
`overseer-41p` and `.1` are both `closed`, and one writer remains.

The mechanism that caused it still binds: **`.1` was re-dispatched after its
work had already merged**, because a dispatcher that reports failure while its
PR merges (`overseer-6pn`) makes "failed" useless as a signal. Three
dispatches, two survivors. That is why the standing rule is to check
`gh pr list --state merged` BEFORE any re-dispatch, and never to re-run
`drive.py` in the foreground to capture stderr.

No task-05 worktree or local branch was created, and no task-05 subprocess is
still running.

## Where the thread stands — derive live status from the ledger, not this file

Filed status is a claim with a timestamp; re-measure before acting:

```sh
/usr/local/bin/with-livespec-env.sh -- bd show overseer-z5fo4y --json
ls SPECIFICATION/proposed_changes/
```

(a bare `bd` in this repo returns Access denied — the wrapper is required).

**As re-measured 2026-08-03T19:27Z (ledger/Fabro/forge):**

| Item | State |
|---|---|
| `overseer-z5fo4y` (epic) | `backlog` — **stays open: it spans v1 = A+B** |
| `overseer-z5fo4y.1` snapshot export | **closed** — dedupe landed, PR #601 |
| `overseer-z5fo4y.2` `list --json` | **closed**, PR #607 (sha `706f23b`) |
| `overseer-z5fo4y.3` foreman-gather | **closed**, PR #621 (sha `f699678`) |
| `overseer-z5fo4y.4` heartbeat surfacing | **closed**, PR #619 (sha `a01d3e2`) |
| `overseer-z5fo4y.5` `-foreman` suffix | **closed**, PR #580 |
| `overseer-41p` | **closed**, PR #601 |
| `overseer-n7xx67` | **closed**, PR #600 |
| `overseer-by6hrx` deterministic wrapper/runtime | **closed**, PR #625, `ee2a1a1`, post-merge janitor green |
| `overseer-eqbk4h` fail-closed session classifier | **closed**, PR #627, `07bf2ae`, post-merge janitor green |
| `overseer-4opppx` session-lifecycle `foreman-act` + fresh revalidation | **closed**, PR #630, `ad76472`, post-merge janitor green |
| `overseer-wykyth` typed filing + journal-triage actions | `pending-approval`, blocked by `overseer-4opppx` |
| `overseer-vts4lo` bounded one-shot work-item sessions | `pending-approval`, blocked by `overseer-4opppx` + `overseer-wykyth` |
| `overseer-qp3vpb` Claude/Codex skill + end-to-end v1 binding | `pending-approval`, blocked by the wrapper and all acting/lifecycle slices |
| `overseer-z5fo4y.6` raw-filed wrapper duplicate | **closed `resolution:duplicate`; no PR; replaced by #625** |

- v006 is ratified and all nine proposal files are archived. The ratification
  prerequisite for the Phase A work is satisfied — including `.4`'s stated
  precondition (attention-surface membership ratified in `contracts.md`).
- The earlier reconciliation work is all discharged: `.5`, `.1`, `overseer-41p`
  and `overseer-n7xx67` are closed. Nothing here needs re-dispatching.
- The Phase A slices carried real dependency edges (`.2` blocked by `.1`; `.3`
  by `.2` and `.1`), and all of them are now satisfied and closed. The durable
  lesson, since Phase B will have edges of its own: **a dep tree is
  directional** — querying `.1` reports what blocks `.1`, never what `.1`
  blocks, so query the item you actually care about (that is correction T2).
  `.3` also moved `pending-approval` -> `ready` BY ITSELF once `.2` closed; no
  approve valve was run, because per C10 the set-admission + approve two-step is
  unnecessary and permanently rewrites the item's recorded admission policy.

## NEXT ACTION — dispatch typed filing/journal actions, then drain the chain

FIRST, re-fetch and re-measure the six Phase B items, `fabro ps`, current
master, and `gh pr list --state all`; never infer run state from the ledger.
Then:

1. **Dispatch `overseer-wykyth` directly with `impl`.** Its blocker is closed
   and its effective policy is `admission:auto`; do not run the human approve
   valve (that correctly refused with `invalid-source-state` on the prior
   slice).
2. **Then drain `overseer-vts4lo`, and finally `overseer-qp3vpb` in
   dependency order.** The item-level `admission:auto`
   labels are intentional; linked items remain `pending-approval` until their
   real edges clear and the lifecycle admits them.
3. **Only after all six close, close/archive the epic and thread, then verify
   the released plugin is deployed fleet-wide.** v1 is A+B; Phase C–E remain
   separate future scope.

   **THAT LAST VERIFICATION HAS A KNOWN GAP ALREADY, AND A VERSION CHECK WILL
   NOT SEE IT.** Measured 2026-08-03T20:47Z: slice `.4`'s daemon-side heartbeat
   surfacing is MERGED BUT NOT RUNNING. `overseer/_supervisor_foreman.py` first
   landed at 18:10:35Z (`a01d3e2`, PR #619); the ACTING daemon has been up since
   08:34:24Z — nine and a half hours earlier — and Python caches modules at
   import, so that process cannot hold the new code. Confirmed empirically
   rather than inferred: the snapshot the daemon wrote seconds before this
   measurement contains no heartbeat notion at all.

   The other Phase A slices are fine, and the reason is worth knowing because it
   tells you which future slices will have this problem: `.1`'s snapshot export
   IS live (it landed 05:38:47Z, BEFORE that daemon started — the fresh
   `~/.livespec-overseer-status.json` carries the ratified schema), and `.2` /
   `.3` are CLI surfaces that get a fresh process per invocation, so they are
   live the moment they merge. **Only DAEMON-side code can be shipped-but-not-
   running.**

   So the deployment check must test BEHAVIOUR, not a release version: read
   `~/.livespec-overseer-status.json` and the daemon's `NEEDS YOU` block for the
   feature itself. **Restarting the daemon is what closes the gap, and it is NOT
   this thread's call** — it runs in tmux `livespec-overseer:1.1`, it supervises
   every tracked session in the fleet, and the standing rule is never to kill
   the acting daemon. Surface it; do not act on it.

   This is correction C9 one step further out. C9 recorded that "the PR merged
   and CI is green" answers a different question from "the acceptance criteria
   were met". This adds a third question those two do not answer: **is it
   RUNNING?**

Do not resume `tmp-revise-input.json`, do not re-file any of the nine spec
proposals, do not re-dispatch any of `.1`–`.5`, `overseer-41p` or
`overseer-n7xx67` (all closed), do not close the epic on Phase A's completion
(it spans A+B), and do not hand-code a factory-eligible ledger item inline.

**DISPATCH LESSONS FROM PHASE A THAT WILL RECUR IN PHASE B**, each measured
2026-08-03 rather than inherited:

- **A dispatcher `failed` is not evidence the work failed.** `.2` reported
  `failed` at stage `merge-poll` ("PR did not reach MERGED within the poll
  budget") while PR #607 merged fine — the budget expired because CI was red on
  a transient forge outage. That is `overseer-6pn`. Check
  `gh pr list --state merged`, verify the merge sha is an ancestor of
  `origin/master`, then reconcile (`--status acceptance`, then the accept
  valve) rather than re-running.
- **A run can be `blocked` on human input while `drive.py` has already said
  `failed`.** `.4`'s first attempt sat at an unwatched 3-option prompt, then
  died on a hard 240m timeout, destroying its sandbox. `fabro inspect <run>`
  distinguishes `blocked` / `human_input_required` from a real failure.
  **`fabro dump <run> --output <dir>` BEFORE deciding anything** — that dump
  was the only surviving copy of the review finding, and writing that finding
  into the item is what made the re-dispatch pass first time.
  Root cause filed as `bd-ib-hote` (P1, orchestrator tenant): review findings
  are never propagated into the disposition stage's prompt.
- **Always dispatch with `--json`.** Three plain runs reported nothing but
  `status: failed`; only the `--json` run surfaced the stale-build stderr that
  explained four consecutive refusals.
- **`ACTIVE` is never evidence of a run, and neither is a `runnable` one.**
  Confirm a run reaches `running`; a queued run can be evicted without ever
  executing and leaves an identical-looking claim.

**The batched valve picker this section used to demand is DISCHARGED.** On
2026-08-03 the maintainer replaced it with a standing instruction to drive
every phase autonomously — plan through implementation, archive and fleet
deployment — and to route any genuinely blocking question to a Codex
subsession first to test whether it truly needs them. That is a broader
grant than any single picker answer, and it is why valve 1 was executed
without one. **A resuming session should not re-raise the picker as if the
decision were still open**; it should either act under that grant or, if
the grant has lapsed, raise the valves that are still ripe. The picker
rules themselves still bind whenever a valve IS raised (recommended option
first, every option stating its cost, full repository names, one batched
call, `---` as the final line before the picker — `.ai/supervisor-protocol.md`
owns them; restated here so this file stays self-sufficient).

Completed valves: `overseer-jgqw7d` landed in `7eb7484` (PR #531); the
nine-proposal v006 revise landed in `47ad0e0` (PR #575); `.5` landed in
`335a578` (PR #580). The remaining implementation route is factory-side.
The two dispatch traps recorded in the repo-root AGENTS instructions apply
verbatim, especially that a foreground diagnostic re-run is itself a real
dispatch and `ACTIVE` is not evidence of a live run.

## Reserved-name hazard — resolved by `.5`

`plan/foreman/` is a discovered plan topic in a watched repo. Adoption
matches live sessions' REGISTRY names against discovered topics, so a
session registry-named `foreman` in this repo WILL be adopted as this
thread's worker — wrapped up at threshold, nudged when idle, and
respawn-able into this handoff.

PR #580 now refuses `-foreman` case-insensitively at topic-level and after
collision-qualified derivation, and `adopt_sessions` leaves live registry
names ending in `-foreman` unadopted. A correctly named foreman prototype is
therefore no longer capturable as a plan worker.

The distinction still matters: the bare topic/session name `foreman` does
not end in the hyphenated reserved suffix, so this thread's ordinary worker
remains adoptable and supervised as intended. Do not broaden the check to a
hyphen-less `endswith("foreman")` in a future cleanup.

## Constraints that bind this thread — do not re-derive

- The daemon is UNCHANGED in behavior and ownership: additive snapshot +
  heartbeat surfacing only. Its evaluate() cascade, cardinal rule, and
  attention semantics are out of bounds (maintainer decision 3).
- Phase A ships NO LLM loop (review O16/C5). Phase B's acting surface is a
  whitelisted executable; human valves stay report-only (C1).
- Foreman state lives under `<repo>/tmp/overseer/foreman/` — inside the
  gitignore-gated scratch, never a new `tmp/` root (O18).
- Never write a literal double-brace template token into any work-item's
  text — it makes the item undispatchable and leaves a phantom claim
  (repo-root `.claude/CLAUDE.md`); describe such constructs in words.
- `just worktree-create` fails at scale in this repo (recorded: 65
  consecutive failures at 77 worktrees; fix tracked in livespec-dev-tooling
  as `livespec-dev-tooling-zi4q`). The proven rescue: `git worktree add
  <path> -b <branch>`, then `just install-worktree-pack` inside it, then
  discard the `worktree_discipline` key it writes into the tracked
  `.livespec.jsonc` unless you mean to land it. Still true at 81+
  worktrees on 2026-08-03; the rescue was used for every branch this
  session.

- **MTIME IS NOT RELEASE ORDER — the dispatch wrapper resolved a STALE build
  and refused four dispatches before anyone read its stderr.** Measured
  2026-08-03T08:12Z. `tmp/overseer/foreman/dispatch.sh` picked "the current
  build" as the newest cache directory by mtime. That premise is false: a
  cache directory's mtime moves whenever anything touches it, so the cache
  sorted

  ```
  1785744577  0.50.0        <- newest mtime, not a dispatcher build at all
  1785742178  18e482f85b9f  <- newer mtime, OLDER release  (what it picked)
  1785732282  525886a4f799  <- older mtime, CURRENT release (what was needed)
  ```

  Every `impl:overseer-z5fo4y.2` and `.4` dispatch was refused with exit 3 and
  the message `dispatcher plugin build is stale; executing build 18e482f85b9f
  predates latest release 525886a4f799`. **Only the `--json` run captured that
  stderr** — the three plain runs reported nothing but `status: failed`, which
  is why the cause went unread. Always dispatch with `--json`.

  The wrapper now asks the AUTHORITY instead: it parses the build id out of
  `just ensure-plugins` output — the same release the dispatcher's staleness
  gate compares against — and HALTs rather than falling back to mtime.
  Positive and negative controls were run before use. The old idiom also used
  `ls`, which is aliased to `lsd` on this host, a second reason it could not
  be trusted.

- **REBASE BEFORE PUSHING, or a docs-only branch inherits everyone else's
  risk.** The pre-push hook picks its subset from the diff against
  `origin/master`. With a STALE BASE that diff sweeps in other tracks'
  `.py` commits, so the hook runs the FULL aggregate instead of the
  doc-only subset — measured 2026-08-03: 407 seconds and a red push for a
  branch touching one markdown file, then 0.96 seconds and a clean push
  after rebasing onto current master. Nothing about the failure names the
  stale base as the cause.

- **DO NOT TRUST A LOCAL FULL `just check` ON A LOADED HOST, and do not
  add to the load.** Measured 2026-08-03T04:11Z: load average 109 on an
  18-core host with 51 sessions. `tests/prompts/` drives real tmux panes
  against a fixed 5-second settle budget, which cannot hold at that load,
  so the aggregate reddens for host reasons and it does NOT look like a
  host problem — one form is a plain test failure, the other is a COVERAGE
  failure with no test reported failed, on a branch containing no Python.
  A local red is not evidence about the tree; CI is the arbiter. Tracked
  as `overseer-63y`, whose acceptance is now the timing DEPENDENCE, not
  the reporting of its expiry (PR #547 made the expiry loud, which helps
  diagnosis and does not remove the dependence).

## Discipline

Fleet-standard: worktree → PR → rebase-merge; never commit on the primary
checkout; never `--no-verify`; `mise exec -- git …` so hooks fire. Check
`git status`, not `git log`, after a hook-gated commit. Never kill the
acting overseer daemon (tmux `livespec-overseer:1.1`) — its blast radius is
the whole fleet. Beads only via the fleet credential wrapper. This thread
FILES ripe work and routes spec matter to the spec lifecycle; it does not
hand-code implementation inline.
