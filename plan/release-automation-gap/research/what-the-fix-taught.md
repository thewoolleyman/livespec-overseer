# What the fix taught, beyond the two defects

Recorded 2026-08-03 by this thread's supervisor. `how-the-gap-was-found.md` is
the companion and comes first: it records how the gap surfaced. This note
records what the *fixing* found, which turned out to be the larger half.

Every claim here is a measurement with a timestamp. Re-measure before carrying
any of it forward.

## The audit that found the gap was itself under-tested

`how-the-gap-was-found.md` states the lesson that cracked the case:

> an absence that was never tested against a comparison is not evidence of
> design.

The audit then made the same error one level up. It compared **three** repos —
`livespec`, `livespec-dev-tooling`, `livespec-overseer` — and generalised to a
fleet, and `overseer-sf0`'s title says livespec-overseer is *"the ONLY fleet repo
missing auto-enable-merge.yml"*.

Widening the identical query to the nine release-please-carrying repos, measured
2026-08-03T00:11:33Z, with the seven PRESENT rows acting as the control that the
probe works and the repos are comparable:

```
livespec                           PRESENT
livespec-dev-tooling               PRESENT
livespec-overseer                  PRESENT   <- fixed by this thread
livespec-driver-claude             PRESENT
livespec-driver-codex              PRESENT
livespec-orchestrator-beads-fabro  PRESENT
livespec-orchestrator-git-jsonl    PRESENT
livespec-console-beads-fabro       ABSENT    *** GAP ***
livespec-runtime                   ABSENT    *** GAP ***
```

Consequence, observed rather than inferred: `livespec-console-beads-fabro` #404
(release 0.4.0) open since 2026-07-23 and `livespec-runtime` #322 (release
0.13.1) open since 2026-07-24, both with `autoMergeRequest: null` — and **in
neither repo had a release-please PR ever merged, once**.

**The wrong half was the reassuring half.** "Only" implied everywhere else was
fine, and two repos had been parked for over a week.

## An absence and a presence fail the same way

The parent error was calling a parked release PR *"a human gate by design"* when
the automation was simply missing. In `livespec-console-beads-fabro` the exact
opposite holds, and an audit checking only for the missing workflow would have
reported that repo fixed.

That repo's release PR is now correctly armed by `app/livespec-pr-bot` and
**still cannot merge**. Measured 2026-08-03T02:32Z on #404 head `5f36873`:
`ci-green` FAILURE via `crates/console-cli/tests/docs_release_version_lockstep.rs`,
asserting the release-please manifest version (`0.4.0`) equals
`DOCS_REVIEWED_AGAINST` (`0.3.0`) — a hand-maintained source constant recording
that a human re-read the install doc. Control: that repo's master was green
across five consecutive CI runs, so the failure is specific to the release PR.

Because the release PR is what bumps the manifest, and release-please never
updates a hand-maintained constant, **every release PR there fails by
construction**. That is a real human gate by design, at a different link. Filed
as `livespec-console-beads-fabro-53t`; the resolution is that repo's to choose.

So the honest fleet outcome is three-valued, not two:

| repo | outcome |
|---|---|
| `livespec-overseer` | automation was missing; installed; releases merge hands-off. **Proven** |
| `livespec-runtime` | automation was missing; installed; release train completed for the **first time ever** |
| `livespec-console-beads-fabro` | automation installed and arming proven; hands-off release still blocked **by design** |

**Both errors share a root: reading a presence or an absence without testing it
against what the repo actually intends.**

## Arming is not retroactive

`auto-enable-merge.yml` triggers on `pull_request`, not `pull_request_target`, so
GitHub reads the workflow **from the PR's head branch**. A parked release PR is
therefore armed only after release-please next *rebuilds* it from a master
carrying the workflow.

Predicted, then observed end to end in `livespec-console-beads-fabro`:

```
01:07:55Z  release-please rebuilds #404 from a master WITHOUT the workflow -> no run possible
01:11:34Z  PR #604 merges, putting auto-enable-merge.yml on master
01:12:51Z  FIRST-EVER Auto-enable merge run on that release branch -> success
01:13:37Z  #404 armed by app/livespec-pr-bot
```

**"The workflow is on master but the release PR is still unarmed" looks like a
broken fix and is not.** It is 3.5 minutes of ordinary sequencing.

## An enumeration is a snapshot; the command is the acceptance

`overseer-dtl` named **seven** soft-band LLOC files. The population was **ten**
when measured 2026-08-02T23:53:24Z, before the fix was written. PR #527 then
decomposed exactly the filed seven and reported success while the gate stayed
red on the other three — a fix that appears to land and changes nothing, arriving
through the *acceptance criterion* rather than through the code.

It went stale a second time during the remediation: a further member
(`test_supervisor_cli_wiring_fixed.py` at 201) appeared mid-flight. The carrier
`overseer-gxrnx5`'s first PR #540 was closed unmerged and replaced by #550, which
measured the population instead of enumerating it.

The durable form: acceptance is
`LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST=1 just check-no-lloc-soft-warnings`
exiting 0 on a **freshly fetched ref**, re-run at the END — not a list of files.

## The gate was red for two reasons and the item named one

`overseer-dtl` attributed the whole red `Release tag` to LLOC. The v0.16.2 run
failed on **two** jobs: `check-no-lloc-soft-warnings` *and*
`check-no-todo-registry` — six registered `test: "TODO"` heading-coverage
entries, every one owed by the `supervisor-wrapup-citizenship` thread.

`dtl`'s own description quotes `release-readiness.yml`'s header verbatim, and
that header names **both** causes in a single sentence: a registered TODO entry
*or* a soft-band LLOC file lands green per-commit and silently reddens every
future release gate. **The item quoted the sentence naming both and diagnosed
one.** Filed as `overseer-0kw`, which also recorded the cross-thread coupling
neither thread's records held.

It was discharged honestly: the six rows are gone because coverage was *written*
(`96eb0a2`, from the owing thread), not because rows were deleted or the lever
cleared. Verified with a positive control — injecting a synthetic `test: TODO`
into a working copy still makes the check exit 1.

## The release gate's conclusion is not a pure function of release readiness

The acceptance run, `Release tag` on `release 0.17.1`, has **two attempts**:

```
attempt 1  03:11:32Z  conclusion=failure
             check-no-lloc-soft-warnings  success
             check-no-todo-registry       success
             check-check-mutation         success
             export-telemetry             FAILURE   <- the ONLY failure
attempt 2  03:18:10Z  conclusion=success   (all four jobs green)
```

On attempt 1 **every release gate passed and the workflow still reported
failure**, because `export-telemetry` lives in the same workflow. It is not a
gate — it posts CI timings to Honeycomb and is deliberately written to fail when
ingest is rejected, so a broken telemetry pipeline cannot die silently. That is
good design for telemetry, and it means:

> `Release tag` concluding `success` is a sound acceptance bar. **Its negation is
> not.** A red conclusion can mean a release gate failed, or that telemetry
> failed with every gate green.

Read the **job** conclusions before declaring the release lane unhealthy. And
read `run_attempt`: a run's conclusion reflects its **latest** attempt, so a job
list fetched moments earlier can disagree with the run it came from. This
thread's supervisor reported the gate still red twice off attempt 1 before
catching it.

## What actually closed it

`Release tag` reached conclusion **SUCCESS** on `chore(master): release 0.17.1`
at 2026-08-03T03:11:32Z — the first green since 2026-07-27, ending
v0.14.0, v0.15.0, v0.16.0, v0.16.1, v0.16.2, v0.16.3, v0.17.0.

Hands-off merging is proven four times over: `#520` (the workflow arming its own
PR), `#516` (release 0.16.1), `#558` (release 0.17.1) here, and `#322` in
`livespec-runtime`. The negative control fired too — the `Auto-enable merge` run
on head `feat/overseer-dtl` was SKIPPED, so the author/branch-shape guard
declines a factory branch rather than arming everything it sees.

## Two items were factory-INELIGIBLE for different reasons

`overseer-sf0` because factory branches never create or update files under
`.github/workflows/` — a dispatched run drops the only file that matters and
reports success.

`overseer-zxy` because the Fabro sandbox has no `codex` CLI on PATH and no
visible host tmux server, so live Codex/TUI/tmux evidence is not observable from
it. Run `01KZ2T7YSCST` blocked with `human_input_required` and said so
explicitly, after doing the observable half first.

**That refusal is the correct outcome, not a run failure** — a sandbox that
instead emitted a green "verified" claim would have been the exact vacuous-green
shape this thread exists to stop. The thread's handoff routes `zxy` to factory
dispatch; that routing is wrong and the work must be done in-session on the host.

## The common shape

Every defect in this thread is one of two moves:

1. **Making the check stop reporting instead of making the condition go away** —
   raising the LLOC ceiling, clearing a fail-mode lever, deleting TODO rows,
   dropping the lockstep test.
2. **Reading a measurement's silence, absence, or snapshot as a settled fact** —
   a three-repo audit generalised to nine, an enumeration treated as a
   population, a superseded attempt quoted as a conclusion, an unarmed PR read as
   a broken fix.

The first is a temptation. The second is an accident, and it happened repeatedly
to careful people — including while writing this note.
