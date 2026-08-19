# Scope and inventory

Created 2026-08-19T05:16:23Z by the grooming pass that bucketed every non-done
`livespec-overseer` work-item into a plan. This note is the write-once research
artifact required by the `plan` operation; the durable coordination record is
this thread's plan epic in the beads ledger, and every handoff is a comment on
that epic. Do not author a `handoff.md` here.

## Why this thread exists

Seventeen open work-items say some version of the same thing: **a check in this
repo is not telling the truth about the repo.** They split cleanly into gates
that pass when they should fail, gates that fail when they should pass, and a
test rig that damages state outside itself. Every one of them costs real time on
every future change, and three of them (`overseer-jct`, `overseer-yc7`,
`overseer-bjrm`) currently block a whole class of `.py` work outright.

## The three strands

**Strand 1 -- hermeticity: the test rig damages production state.** Three
separately-filed items are the same violation seen from three angles: the suite
writes the REAL `~/.livespec-overseer-status.json`, publishing an empty fixture
snapshot to every fleet consumer mid-run (`overseer-rvpehf`), a scenario test's
second daemon clobbers the live snapshot (`overseer-y2252y`), and an epoch-1000
daemon instance blanked supervision rows fleet-wide during a post-merge janitor
pass (`overseer-xogp6d`). Two more are rig-lifecycle defects:
`test_ready_reports_missing_topic_when_no_tmux_context` lacks `TMUX_PANE`
isolation and fails under any real tmux (`overseer-4od1`), and the real-tmux rig
leaks a socket per test and never reaps -- 9,137 orphan sockets and 58 zombie
servers measured (`overseer-6i0`). These should be fixed together because a
single injected status-path seam plus a single rig teardown closes most of them,
and fixing them one at a time risks three different seams.

**Strand 2 -- gates that cannot fail.** `check-prose-release-hygiene` passes
vacuously if `.claude-plugin/prose` is ever relocated, because an empty
path-scoped diff is indistinguishable from a missing path (`overseer-b4q`).
`check-branch-protection-alignment` warns instead of failing when a CI leg stops
gating merges, and its leniency assumes a required `ci-green` aggregate this repo
does not have (`overseer-rh1`) -- which is exactly how a blocking
CHANGES_REQUESTED review came to be bypassed and shipped (`overseer-zfq`).
`check-coverage` leaks `bd-guard-emit.py` into the report via
`COVERAGE_PROCESS_START` (`overseer-pfn2`). The justfile cites a livespec core
section that no longer exists (`overseer-zuhv`).

**Strand 3 -- the Result railway and coverage debt.** `check-public-api-result-typed`
reports 123 unshadowed violations and blocks every `.py` push
(`overseer-jct`); the underlying blocker is that this repo cannot express
`IOResult` at all -- zero declared dependencies by design, no `_vendor` tree, and
the plugin runs on the host's bare `python3` -- so arming the ROP check needs a
spec ruling first, and it blocks roughly a third of the fleet (`overseer-yc7`).
`overseer-bjrm` is the adoption task that lets the `pure_trees` un-gating re-land.
Alongside: the check aggregate is FLAKY under concurrency, observed twice
independently (`overseer-jdo`); the `tests/prompts/` cwd flake is root-caused to
an unsynchronized `pane_current_path` read and needs peer negotiation
(`overseer-k03`); 19 unowned TODO scenario-heading entries need integration tests
(`overseer-dhkjxf`); and 23 heading-coverage rows carry stale module qualifiers
from the beside-test module split (`overseer-knm`).

## Requirement carriers admitted to this thread

`overseer-rvpehf`, `overseer-y2252y`, `overseer-xogp6d`, `overseer-4od1`,
`overseer-6i0`, `overseer-jdo`, `overseer-pfn2`, `overseer-k03`,
`overseer-dhkjxf`, `overseer-knm`, `overseer-jct`, `overseer-yc7`,
`overseer-bjrm`, `overseer-b4q`, `overseer-rh1`, `overseer-zfq`,
`overseer-zuhv`.

The authoritative member list is the ledger -- the parent-child children of this
thread's plan epic -- never this file.

## Deliberate non-membership

Daemon behavior changes live in `plan/supervision-safety-and-attention-truth`
even when a test exposed them; the discriminator is whether "done" is a corrected
gate or a corrected behavior. Dispatcher, beads-server and release-lane plumbing
lives in `plan/fleet-plumbing-and-dispatch-reliability`.

## Ordering note for the first implementer

`overseer-yc7` gates Strand 3 and needs a SPEC RULING before any code moves;
raise it first and route it through `/livespec:propose-change`, because
`overseer-jct` and `overseer-bjrm` cannot be sized until it lands. Strand 1 is
independent of that ruling and is the highest-value parallel start -- it is
actively corrupting a file other repos read.
