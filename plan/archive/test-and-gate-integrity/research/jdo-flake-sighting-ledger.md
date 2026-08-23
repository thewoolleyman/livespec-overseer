# `overseer-jdo` — the aggregate-flake sighting ledger

**Ledger anchor: `overseer-hgq4wi`.** Owning item: **`overseer-jdo`** (P1) — "The
check aggregate is FLAKY under concurrency: a target fails in the full run and
passes standalone".

## What this file is, and why it is a file

This is the accumulated **statistical sighting ledger** for `overseer-jdo`, moved
here verbatim from that item's `notes` field on 2026-08-22. It is the evidence
record — every sighting, every measurement, every ruled-out mechanism, and every
correction the investigating sessions made to their own earlier framings.

**It moved because its size had become an obstacle to fixing the defect it
documents.** The `notes` field alone had reached 65,613 characters against a
total record of roughly 74,940. The Dispatcher renders an item's fields, its
ledger comments and the ratified lessons into one goal brief, so a record that
large burns a substantial share of a run's budget before any work begins — and
`overseer-jdo` is a P1 that must eventually be dispatched. The item was
deliberately demoted `ready` -> `backlog` on 2026-08-22 for exactly this reason,
with this move recorded as the cheap unblock. Nothing needed re-cutting; the
evidence simply needed a home that a goal brief does not have to carry.

**The content below is unedited.** No sighting was summarised away, no
correction was tidied up, and no superseded framing was deleted — several
entries exist precisely to stop a later reader re-using a framing their author
had already withdrawn, and that value survives only if the withdrawals stay
readable. Section order is the order the sessions wrote it, which is not
chronological in one place and says so where it matters. The entry headed
"STATE OF THIS ITEM IN ONE PLACE" was written last and asks to be read first.

## How to use it

- **Do not re-derive the measured figures.** Run counts, load averages, commit
  shas, CI run ids and failure signatures are recorded because re-measuring them
  is expensive and, for the historical sightings, no longer possible.
- **Do not count the runs recorded here toward the acceptance.** The acceptance
  is statistical and lane-scoped, and lives on the item, not here. Several
  entries below explain at length why an individual clean run — or a run of
  twenty-four — proves less than it looks like it proves. That reasoning is the
  most reusable thing in this file.
- **Check the item's own comment stream too.** Nineteen comments existed at the
  time of the move and were left in place; only `notes` came here.
- **The body below is plain text, not authored Markdown.** It was written into a
  ledger field, so it carries ASCII tables, aligned columns and indented blocks
  that a Markdown renderer will reflow. Where alignment is load-bearing — the
  three-mechanism table, the run tallies — read the raw file rather than a
  rendered view.

---


FIRST STATISTICAL DATA POINT, 2026-07-30T12:47-12:59Z. THE RESULT IS NEGATIVE AND MUST NOT BE READ AS VINDICATION.

MEASURED: 7 consecutive `just check` runs on the PRIMARY CHECKOUT at origin/master 83d7efa (all 63 targets, real aggregate concurrency, 18 cores), run back to back. ALL 7 CLEAN. No target failed; the two previously-implicated targets, check-per-file-coverage and test_watcher_wake_discriminates, did not fire once.

WHY THAT PROVES ALMOST NOTHING, which is the point of recording it. Both prior sightings put the rate near 1 failure in ~7 runs. If the true per-run failure probability is still 1/7, the chance of seeing 7 consecutive clean runs is (6/7)^7 = 34%. So this outcome is entirely consistent with the defect being completely unchanged. A third of the time you get exactly this.

THIS IS WHY THE ACCEPTANCE ON THIS ITEM HAD TO BE STATISTICAL, and it is worth seeing the number rather than the adjective. To rule out p >= 1/7:
    95% confidence -> 20 consecutive clean runs
    99% confidence -> 30 consecutive clean runs
    (n > ln(alpha) / ln(1 - 1/7); 7 runs buys 34% -- not even close)
PROPOSED CONCRETE ACCEPTANCE, replacing "N consecutive clean runs": TWENTY consecutive clean full-aggregate runs at real concurrency, with the failing target named if any run fails. Thirty if the fix is subtle enough that a 5% residual risk is not acceptable given this gate now blocks every contributor.

A CAVEAT ON MY OWN RUNS, so nobody over-counts them. Earlier the same session I saw TWO failing aggregate runs in this repo -- but both were MY OWN uncommitted code (a lint error, a coverage shortfall, and a genuinely broken cold-open gate), not flakes. They are NOT evidence either way and must not be added to the failure column. Only the 7 runs above, on a clean tree at a merged commit, are admissible.

WHAT WOULD MAKE THE NEXT MEASUREMENT BETTER. Run the 20 from a clean tree at a known commit, record the commit, and on ANY failure capture which target failed and whether it passes standalone immediately afterwards -- that standalone-pass is the signature that distinguishes this flake from a real regression. Do not re-run until green and call it done; that is the exact habit this item exists to stop.

TWENTY-RUN RESULT, 2026-07-30T14:47-16:40Z. THE ACCEPTANCE THRESHOLD I PROPOSED IS NOW MET FOR ONE LANE ONLY, AND THE LANE DISTINCTION IS THE REAL FINDING.

MEASURED, on a clean primary checkout at origin/master (83d7efa, then 838f377 -- the two differ only by a proposed_changes markdown file, so the executable surface is identical):
    20 consecutive `just check` runs at the LOCAL default parallelism   ALL CLEAN
     4 further runs at CI-EQUIVALENT parallelism (see below)            ALL CLEAN
    24 of 24. No target failed once. Neither previously-implicated target -- check-per-file-coverage or test_watcher_wake_discriminates -- fired.

CONTENTION WAS REAL, NOT AN IDLE BOX. Throughout the window: load average 36-44 on 18 cores (2-2.4x oversubscribed), with another repo's aggregate (livespec-console-beads-fabro running `just check-e2e-tmux`) executing concurrently. So "under concurrency" in the system-contention sense was satisfied and then some.

WHAT 20 CLEAN RUNS ACTUALLY BUY:
    20 clean rules out p >= 13.9% at 95% confidence
    24 clean rules out p >= 11.7% at 95% confidence
    probability of 20 clean if the rate were STILL 1-in-7: 4.6%
So the ~1-in-7 rate is now unlikely FOR THIS LANE. That is a bound on the rate; it is NOT a fix, and nothing was changed to make it one.

*** THE LANE DISTINCTION, WHICH ANY FUTURE ACCEPTANCE MUST NAME. *** justfile:41 sets the pytest worker count:
    hosted CI lane (LIVESPEC_CI_LANE=hosted)  ->  -n auto   = 18 workers here
    local default                             ->  nproc / 4 = 4 workers here
That is a 4.5x difference in xdist parallelism between the lane a contributor runs and the lane that gates the merge. My 20-run block used the LOCAL setting, so it bounds the LOCAL failure rate and says very little about CI. I then ran 4 at `LIVESPEC_TEST_PARALLELISM=auto` to probe the CI-equivalent condition -- all clean, but FOUR RUNS ONLY RULES OUT p >= 53%, which is nearly worthless. Do not read those four as evidence.

REVISED ACCEPTANCE PROPOSAL, superseding the bare "20 runs" I suggested earlier:
    20 consecutive clean runs AT `-n auto` (the parallelism CI actually uses),
    on a clean tree at a named commit, with system load recorded.
    On ANY failure: name the target, then immediately re-run it STANDALONE --
    a standalone pass is the signature that distinguishes this flake from a real
    regression, and it is the observation both original sightings rest on.

AND THE HONEST REMAINDER. Two independent sightings happened; 24 runs today did not reproduce either. Something differed. Candidates worth checking before concluding the item is stale: whether both sightings were under the hosted lane rather than local; whether they coincided with the seven real-tmux fixtures contending for a tmux server; and whether either occurred on a tree with uncommitted changes. I did not investigate these -- I am naming them so the next person does not start from zero, and so nobody closes this item on my 24 runs alone. A single green is exactly what both sightings looked like afterwards; so, at this sample size, is a run of twenty-four.
SIGHTINGS 3 AND 4, FOLDED IN FROM THE DUPLICATE overseer-jcw (P2, filed 2026-07-30 by the codex-parity-and-rollout-safety thread; closed as superseded by this item). Both are new to THIS record, checked rather than assumed: grep of this item's text for `30566073405`, `test_c_a_footer`, `test_repo_containment` and `check-coverage` each returned 0, against a POSITIVE CONTROL of `test_both_forms_report_busy` at 1 and a bogus phrase at 0. So the zeros are real absences, not a query that could not match.

SIGHTING 3 (LOCAL lane, 2026-07-30). Docs-only branch, unchanged working tree: `just check` failed, failed, then PASSED -- same tree, same command, three consecutive runs. Failing targets were check-per-file-coverage + check-coverage, and the shortfall pointed at tests/prompts/test_repo_containment_discriminates.py:130-134 at 92% -- the body of test_the_pane_cwd_the_forms_receive_comes_from_a_real_tmux_pane, which drives a REAL tmux server. `just check-per-file-coverage` standalone passed twice on that same tree (745 then 766 tests, 100%). That is a THIRD distinct real-tmux prompt test implicated. Reported by that thread; I did not re-run it.

*** SIGHTING 4 ANSWERS THIS ITEM'S OWN OPEN QUESTION: YES, AT LEAST ONE SIGHTING WAS ON THE HOSTED LANE. *** The HONEST REMAINDER above names, as the first thing worth checking, "whether both sightings were under the hosted lane rather than local". Measured from the forge and the raw job log, not relayed:

    master CI run 30566073405, workflow CI, headSha e1ab50510dd9820fbedf8d76390b436e81a5c8e5
    (A6's merge), created 2026-07-30T17:27:51Z
    attempt 1 -> conclusion FAILURE, failing job `check-coverage`
    attempt 2 -> conclusion SUCCESS, from a plain rerun with nothing changed

*** AND THE HOSTED-LANE SIGNATURE IS DIFFERENT IN KIND FROM EVERY LOCAL ONE. THIS IS THE PART THAT MATTERS. *** Verbatim from attempt 1's job log:

    Required test coverage of 100.0% reached. Total coverage: 100.00%
    =========================== short test summary info ============================
    FAILED tests/prompts/test_watcher_wake_discriminates.py::test_c_a_footer_in_scrollback_wakes_the_shipped_watcher - AssertionError: assert equals failed
       -'IDLE'     +'PICKER'
    1 failed, 731 passed in 14.49s
    error: Recipe `check-coverage` failed with exit code 1

COVERAGE WAS 100.00%. On the hosted lane this is a GENUINE ASSERTION FAILURE with a behavioural diff -- the watcher classified the pane as PICKER where the test required IDLE -- and NOT the coverage shortfall that both local sightings presented as. SIGHTING 2 and SIGHTING 3 are uncovered-line signatures, i.e. a test that DID NOT EXECUTE. SIGHTING 4 is a test that DID execute and returned the wrong answer. A reader comparing only target names would call these the same symptom; the logs say they are not.

ALSO NOTE THE TEST IDENTITY. SIGHTING 1 named test_both_forms_report_busy_while_a_pane_keeps_changing; SIGHTING 4 is test_c_a_footer_in_scrollback_wakes_the_shipped_watcher. Same module, different test. With SIGHTING 3's test_repo_containment_discriminates that is four distinct real-tmux prompt tests across four sightings -- consistent with the shared-fixture hypothesis and inconsistent with one bad test.

AND THE LANE IS VISIBLE IN THE RUNTIME: 731 tests in 14.49s is the `-n auto` lane, which justfile:41 sets for LIVESPEC_CI_LANE=hosted. So the confirmed hosted-lane sighting is also the most contended condition for the tmux fixtures.

WHAT THIS CHANGES FOR THE ACCEPTANCE, AND WHAT IT DOES NOT. The revised proposal above -- 20 consecutive clean runs at `-n auto` -- is still the right bar and this strengthens it, because `-n auto` is now the only lane with a confirmed sighting. What it adds is a caution: the two lanes may not share a mechanism. A test that never ran and a test that ran and answered wrong can have different causes, so a fix demonstrated on one lane must not be assumed to cover the other, and the acceptance should name which lane each clean run was taken on.

NOT DIAGNOSED. I measured the lane and the failure signature. I did not investigate the mechanism, and nothing here rules the earlier 24 clean runs out or in.
*** THIS DEFECT IS HALF-FIXED, BY ANOTHER TRACK, UNDER THE `overseer-jcw` ID I CLOSED INTO THIS ONE. READ THIS BEFORE ANY OTHER NOTE HERE. ***

The `supervisor-prompt-quality` thread diagnosed jcw properly and landed a real fix while I was folding jcw into this item. Their work is recorded in `plan/supervisor-prompt-quality/handoff.md` §"`overseer-jcw` HAS TWO MECHANISMS" (commit `c42e6d6`), and it is better evidence than anything I contributed. Pointing at it from here so it is not orphaned behind a closed id.

A COORDINATION NOTE FIRST, because it is mine to own. Their commit message states "Ledger untouched. jcw is NOT closed" and their handoff says "closing or re-scoping it is the supervisor's lane." I had already closed jcw into this item by then, without knowing they were mid-work on it. I have NOT reversed that — reopening and re-closing another track's actively-worked item is churn, and the consolidation itself still looks right (one live home, and this item is the richer, higher-priority one). But the SURVIVOR CHOICE was mine to make unilaterally and arguably was not: it is surfaced to the supervisor rather than settled here. If the supervisor prefers jcw as the live id, swap them — everything below travels either way.

*** MECHANISM 1 — A SHARED TMUX SOCKET ACROSS CONCURRENT RUNS. FIXED, PR #418. ***
The real-tmux rig named its private socket `legs-{tmp_path.name}` — the TEST's identity, byte-identical across separate pytest invocations. Unique per test and per xdist worker exactly as its docstring claimed, and NOT unique per RUN. Two concurrent `just check` invocations on one host therefore addressed the SAME `tmux -L` server; the second `new-session -s wk` failed as a duplicate WITHOUT BEING NOTICED (helpers pass `check=False`, and tmux exits 0 anyway), so the second run read the FIRST run's pane. Reproduced on demand: passes 2/2 alone, and one of two concurrent invocations fails at `assert live == str(repo)` with two different `pytest-NNNN` roots in the diff. A SECOND independent instance (`disc-{tmp_path.name}`) surfaced once the shared conftest was fixed; `tests/prompts/test_rig_sockets_are_run_unique.py` now gates the property.

*** MECHANISM 2 — A TIMING PREMISE EXTERNAL LOAD INVALIDATES. NOT FIXED, deliberately. ***
`test_both_forms_report_busy_while_a_pane_keeps_changing` asserts BUSY and reads IDLE. `watcher_proposed` polls every 150ms and declares IDLE after N identical captures; the test drives a 50ms tick and its own comment states the premise. Under load the loop is descheduled and tmux coalesces renders, so consecutive polls compare EQUAL and IDLE wins. Measured 0 of 8 alone, 0 of 8 under light paired load, 2 of 8 under two FULL concurrent suites — and after #418, EVERY remaining failure across 8 concurrent full-suite runs was this one, with no socket collision at all. They stopped because the fix is a contract choice ("always BUSY" vs "eventually, within a bounded window"), not a repair, and tuning the tick until green is the habit this item exists to stop. That judgement is right and should be respected.

*** THIS RETIRES THE GUESSED CAUSE LIST IN THIS ITEM'S OWN DESCRIPTION. ***
The filing offered three "plausible directions worth checking": a shared `.coverage` race, generic tmux server contention, and a fixture that skips rather than fails. **All three are wrong.** The third is ruled out by construction — a refuse-to-skip guard. Worth remembering the next time a filing's plausible-sounding cause list is treated as a head start; here it was a distraction, and the real cause was a uniqueness axis nobody questioned because the docstring asserted it.

*** AND IT CONFIRMS THE TWO-SIGNATURE OBSERVATION IN THE NOTE ABOVE, WITH THE MECHANISM I DID NOT HAVE. ***
My earlier note recorded that the hosted-lane failure was a genuine assertion at 100.00% coverage while every local sighting was an uncovered-line signature, and warned "the two lanes may not share a mechanism" and "a fix demonstrated on one lane must not be assumed to cover the other". That now has a cause on both sides, and the pairing is exact: **mechanism 1 dies MID-TEST, so the lines below never execute — a COVERAGE shortfall; mechanism 2 runs to completion and returns the wrong value — an ASSERTION failure.** The caution was right for the right reason, and #418 fixing only mechanism 1 is precisely the "proven on one lane" case it warned about.

ONE THING THAT REMAINS OPEN AND IS NOT COVERED BY EITHER MECHANISM AS WRITTEN. My hosted-lane sighting (SIGHTING 4 above, run 30566073405) was `test_c_a_footer_in_scrollback_wakes_the_shipped_watcher` with `-'IDLE' +'PICKER'`. Mechanism 2 is a DIFFERENT test (`test_both_forms_report_busy_while_a_pane_keeps_changing`) reading IDLE where BUSY was required. Same module and plausibly the same timing class, but the test and the expected/actual values both differ, so it is NOT established that mechanism 2 explains SIGHTING 4. Do not fold them together without checking — that is one more instance of the assumption this whole item keeps punishing.

ACCEPTANCE UNCHANGED AND STILL STATISTICAL. Mechanism 2 is live, so the 20-consecutive-clean-runs-at-`-n auto` bar has not been met and must not be considered met on #418 alone.
*** MECHANISM 3 — `settle` AND `wait_for` RETURN SILENTLY ON TIMEOUT, SO A LOAD SPIKE IS REPORTED AS A WRONG ANSWER. This is the leading explanation for SIGHTING 4, and mechanisms 1 and 2 are effectively EXCLUDED for it. ***

I raised SIGHTING 4 as an open question — it is a DIFFERENT test from mechanism 2's, with different expected/actual values, so folding them together was flagged as unestablished. Chasing it found a third, independent mechanism.

`tests/prompts/conftest.py:136-150`, `_SETTLE_TIMEOUT_S = 5.0`:

    def _settle(target, needle):
        deadline = time.monotonic() + _SETTLE_TIMEOUT_S
        ...
        # COVERAGE-EXEMPT: reached only if a pane never settles within the
        # timeout. Unreachable on a healthy run, kept so a hung pane yields the
        # last capture instead of raising ...
        return previous  # pragma: no cover

`_wait_for` has the same shape at `:115-119`, with an explicit "do not convert this into a raise."

WHAT THAT MEANS AT THE CALL SITE. `settle` does not signal that it gave up. A test that times out proceeds to assert against whatever the pane happened to hold — usually a bare prompt. So a five-second budget missed under load becomes an ORDINARY ASSERTION FAILURE with a plausible-looking value, not a timeout.

HOW IT PRODUCES SIGHTING 4 EXACTLY. `test_c_a_footer_in_scrollback_wakes_the_shipped_watcher` does `_run(..., settle=settle, needle="AFTER-25")` and then asserts `watcher_shipped(...) == _PICKER`. `watcher_shipped` returns `_PICKER` the instant `"Enter to select"` appears anywhere in a `capture-pane -S -40` window, and otherwise needs FOUR polls with the last three identical to return `_IDLE`. If `settle` timed out before the shell rendered anything, the pane holds only a prompt, four polls 0.15s apart are identical, and the watcher returns `_IDLE`. That is `-'IDLE' +'PICKER'`, verbatim.

WHY MECHANISM 1 IS EXCLUDED FOR THIS SIGHTING. It needs two concurrent pytest INVOCATIONS on one host to collide on a socket. SIGHTING 4 is CI run 30566073405, job `check-coverage` — and `.github/workflows/ci.yml` runs a MATRIX with ONE `just <slug>` per job, on GitHub-hosted runners ("Runner Image Provisioner / Hosted Compute Agent" in the log), i.e. one job per VM. One invocation. No second run to collide with.

WHY MECHANISM 2 IS EXCLUDED FOR THIS SIGHTING. Mechanism 2 is a tick-vs-poll premise on a DELIBERATELY CHURNING pane. This test settles on a needle first, and more decisively, `watcher_shipped` short-circuits to `_PICKER` on the FIRST poll whenever the footer is present at all — so poll stability is not the discriminator here. The footer's PRESENCE is, and mechanism 3 is what removes it.

THE SCROLLBACK MARGIN IS NOT THE CAUSE — checked, so nobody spends time there. The worker pane is `-x 80 -y 20` and the capture is `-S -40`, i.e. a ~60-line window against roughly 30 lines of content (a wrapped command echo, the footer, 25 `AFTER-$i` lines, a prompt). The footer cannot scroll out of that window. It was the first hypothesis and it is wrong.

*** WHY THIS IS THE MOST DANGEROUS OF THE THREE, AND IT IS STRUCTURAL. ***
The timeout path is `# pragma: no cover` on BOTH helpers. So the one code path that turns infrastructure slowness into a false verdict is exempt from the coverage gate and cannot be observed by it. A failure through this path is indistinguishable, at the call site and in the CI log, from the code under test being genuinely wrong — which is precisely how SIGHTING 4 was first read here, as evidence about the watcher. It is the surface-declared / artifact-absent shape one level down: the helper declares success by returning normally while the thing it promised never happened.

BLAST RADIUS: three modules take these fixtures — `test_watcher_wake_discriminates.py`, `test_emitted_commands_discriminate.py`, `test_supervisor_liveness_discriminates.py` — and the watcher module alone has 8 assertions downstream of a `settle`.

WHAT I AM NOT CLAIMING. I did not reproduce SIGHTING 4 through this path; a CI log records only the assertion, and the run has since been rerun green. This is a mechanism that FITS exactly and two that are excluded on structural grounds — a strong narrowing, not a proof. Reproducing it should be cheap: force the timeout (drop `_SETTLE_TIMEOUT_S`, or load the box) and confirm the failure presents as `-'IDLE' +'PICKER'` rather than as a timeout.

AND I AM NOT PROPOSING THE FIX, deliberately. Making the timeout distinguishable is a CONTRACT change against an explicit in-code decision ("do not convert this into a raise", with a stated rationale about failure-message quality), and `tests/prompts/` is the supervisor-prompt-quality thread's deliverable. Same reasoning by which that thread declined mechanism 2. Handing it over with the measurement rather than acting on it.

ONE OBSERVATION FOR WHOEVER TAKES IT. The stated rationale — a timeout should surface the pane contents rather than a traceback — is a good goal and does not actually require silence. Returning a value the caller can recognise as "never settled", or asserting on it, keeps the good failure message AND stops a timeout impersonating a verdict.

CORRECTION TO MY OWN EARLIER NOTE IN THIS ITEM: I wrote that "731 tests in 14.49s is the -n auto lane" and glossed `-n auto` as 18 workers. 18 is THIS host's `nproc`; on a GitHub-hosted runner `auto` is that runner's core count, which is smaller. The lane identification stands, the worker count does not — do not carry the 18 into any CI reasoning.
*** MECHANISM 3 IS NOW REPRODUCED, NOT MERELY FITTED. The note above says "a mechanism that FITS exactly ... a strong narrowing, not a proof" — that caveat is DISCHARGED. ***

Run on a private tmux socket (`tmux -L mech3-repro-probe`), touching nothing else on the host. Verbatim output:

    CONTROL (healthy) settle saw AFTER-25 : True
    CONTROL (healthy) watcher_shipped     : PICKER (test requires PICKER)

    CLAIM A -- settle with an unreachable needle
       raised?              : False  (a raise would make the timeout VISIBLE)
       returned after       : 5.07s (budget 5.0s)
       needle in its result?: False

    CLAIM B -- watcher_shipped against that same never-rendered pane
       verdict              : IDLE
       the test asserts     : PICKER
       pytest would print   : -'IDLE'     +'PICKER'

THE POSITIVE CONTROL IS THE FIRST BLOCK, and it is what makes the rest admissible: on the healthy path the identical rig reaches `AFTER-25` and the watcher returns PICKER. So the IDLE below is caused by the timeout, not by a broken reproduction.

CLAIM A CONFIRMED: `settle` given a needle that can never appear does NOT raise. It burns its whole 5-second budget and returns normally, handing back a capture that does not contain the needle. The caller has no way to tell that from success.

CLAIM B CONFIRMED, AND THE LAST LINE IS THE POINT: `-'IDLE'     +'PICKER'` is byte-identical to the failure line in CI run 30566073405. The signature this item recorded as a "genuine assertion failure at 100.00% coverage" is exactly what a silent settle timeout produces.

SO THE CHAIN IS CLOSED FOR SIGHTING 4: load spike -> `settle` misses its 5s budget -> returns silently -> the pane never rendered -> `watcher_shipped` sees four identical prompt-only captures -> IDLE -> an assertion failure that reads as "the watcher is broken". It is not the watcher.

THE ONE BOUND ON THIS REPRODUCTION, stated so it is not overread: the helper bodies were COPIED VERBATIM from `tests/prompts/conftest.py:136-150` and `test_watcher_wake_discriminates.py:64-78` rather than imported, so this reproduces the shipped LOGIC and not the shipped OBJECTS. A version that imports the real fixtures would be strictly stronger and is the natural first step for whoever takes this. What is NOT in question is the behaviour of the `return previous  # pragma: no cover` line, which is three lines long and was transcribed exactly.

STILL NOT PROPOSING THE FIX — see the note above. This is another thread's deliverable and the silence is a stated in-code decision, so it is handed over with a reproduction rather than changed.
*** THE LAST BOUND ON MECHANISM 3 IS DISCHARGED — re-run against the SHIPPED FUNCTION OBJECTS, not a transcription. ***

The previous note stated one caveat: the helper bodies had been COPIED from `tests/prompts/conftest.py` rather than imported, so the result was about the shipped LOGIC and not the shipped OBJECTS. Redone by importing that exact file and unwrapping the real fixtures (`_settle_fixture.__wrapped__`, `_wait_for_fixture.__wrapped__`) onto a private-socket tmux seam — the same seam the suite itself injects. Verbatim:

    IMPORTED           : /data/projects/livespec-overseer/tests/prompts/conftest.py
    shipped timeout    : 5.0 s
    settle bound from  : _settle_fixture.<locals>._settle
    wait_for bound from: _wait_for_fixture.<locals>._wait_for

    CONTROL via SHIPPED settle -- reachable needle
       needle present : True
       returned in    : 1.18s  (well under the budget)

    SHIPPED settle() -- unreachable needle
       raised?        : False   <- the timeout is INVISIBLE to the caller
       returned after : 5.02s  (shipped budget 5.0s)
       needle in out? : False

    SHIPPED wait_for() -- unreachable needle
       raised?        : False
       returned after : 5.02s
       returned value : None  <- wait_for returns None either way

The control is the healthy path through the SAME imported `settle`: it finds its needle in 1.18s. So the 5.02s silent returns below are the timeout behaviour of the shipped code, not an artifact of how it was invoked.

*** AND THE RE-RUN FOUND SOMETHING THE COPY DID NOT: `wait_for` IS STRICTLY WORSE THAN `settle`. ***
`settle` at least hands back a CAPTURE, so a caller who chose to could inspect it and notice the needle is missing. `wait_for` returns `None` on success AND on timeout — its return value carries ZERO information in either case, so there is nothing a caller could check even in principle. Its in-code comment is the more emphatic of the two ("do not convert this into a raise"), which makes it the harder half of the contract conversation, and it is used by the same three modules.

STATUS OF MECHANISM 3, now that both bounds are gone: the silent-timeout behaviour is CONFIRMED against the shipped objects, and the IDLE-instead-of-PICKER consequence is CONFIRMED against the shipped watcher logic. What remains genuinely unproven is only that CI run 30566073405 took this path specifically — a log records the assertion, not the cause, and that run has since been rerun green. Every other link is measured.
================================================================================
STATE OF THIS ITEM IN ONE PLACE — 2026-07-31. Written last; read it FIRST.
The notes above are the evidence trail and several of them correct each other.
================================================================================

THREE MECHANISMS, not one. The item was filed as a single flaky-gate defect.

  #  what                                    fate            how it PRESENTS
  -  --------------------------------------  --------------  ----------------------
  1  real-tmux rig shared one tmux socket    FIXED, PR #418  dies mid-test, so the
     across concurrent runs (name came                       lines below never run
     from the TEST's identity, not the RUN)                  -> COVERAGE SHORTFALL
  2  50ms test tick vs the watcher's 150ms   OPEN, by        completes, wrong value
     poll; load deschedules the loop and     choice          -> ASSERTION FAILURE
     consecutive polls compare EQUAL                         (BUSY expected, IDLE)
  3  settle/wait_for RETURN SILENTLY on      OPEN, not yet   completes, wrong value
     timeout (5s budget, both timeout        raised with     -> ASSERTION FAILURE
     lines are `# pragma: no cover`)         the owner       (PICKER expected, IDLE)

FOUR SIGHTINGS, mapped to mechanisms as far as the evidence goes:

  S1  local, test_both_forms_report_busy...        -> mechanism 2 (owner's measurement)
  S2  local, check-per-file-coverage shortfall     -> mechanism 1 shape
  S3  local, check-per-file-coverage + check-      -> mechanism 1 shape
      coverage, test_repo_containment 92%
  S4  HOSTED CI run 30566073405, check-coverage,   -> mechanism 3; mechanisms 1 and 2
      test_c_a_footer..., -'IDLE' +'PICKER'           EXCLUDED on structural grounds

WHY MECHANISMS 1 AND 2 ARE EXCLUDED FOR S4: mechanism 1 needs two concurrent pytest
INVOCATIONS on one host, and ci.yml runs a matrix with ONE just-slug per job on
GitHub-HOSTED runners — one job per VM, one invocation. Mechanism 2 is a
churning-pane premise, while S4's test settles first AND `watcher_shipped`
short-circuits to PICKER on the first poll if the footer is present at all, so
presence — not poll stability — is the discriminator.

WHAT IS MEASURED vs WHAT IS INFERRED, because this item punishes the difference:
  MEASURED  mechanism 3's silent timeout, against the SHIPPED function objects
            (imported conftest, unwrapped fixtures): no raise, 5.02s, needle absent,
            with a healthy-path control returning in 1.18s.
  MEASURED  the consequence: that pane -> `watcher_shipped` -> IDLE, and the line
            pytest prints is `-'IDLE'     +'PICKER'`, byte-identical to S4's.
  INFERRED  that run 30566073405 took that path specifically. A log records the
            assertion, not the cause, and it was rerun green. Unprovable from here.

MY OWN CORRECTIONS IN THIS ITEM, so nobody re-uses the superseded framings:
  - I characterised S4 as "a genuine ASSERTION failure at 100.00% coverage" and
    contrasted it with the coverage-shortfall sightings. True about the LOG, and
    it pointed the right way, but the cause is a silent settle timeout — not the
    watcher being wrong, which is how it first read here.
  - I glossed `-n auto` as "18 workers". 18 is the DEV HOST's nproc; a hosted
    runner's `auto` is its own smaller core count. The lane identification stands;
    the number must not be carried into CI reasoning.

THE ACCEPTANCE HAS NOT MOVED, and #418 does not meet it. Twenty consecutive clean
runs at `-n auto` on a clean tree at a named commit, with the lane recorded. Two of
three mechanisms are open, so a clean streak now would measure the absence of
mechanism 1 and nothing else.

WHAT IS OWED, AND BY WHOM:
  - Mechanisms 2 and 3 are BOTH contract questions in `tests/prompts/`, the
    supervisor-prompt-quality thread's deliverable. Mechanism 3 has a reproduction
    attached and has NOT yet been raised with them directly — a peer notification
    is owed.
  - The survivor choice between this item and `overseer-jcw` (closed into it, while
    that thread was mid-work under the jcw id) is the SUPERVISOR's, not settled.
  - This item still needs ADMISSION; it inherited jcw's ask.
*** `check-coverage` DOES DIFFERENT WORK IN THE TWO LANES, AND THAT RESOLVES AN APPARENT CONTRADICTION IN THIS ITEM. ***

This item's description says `check-coverage` "announces it READS an existing .coverage produced by check-per-file-coverage rather than running its own suite". SIGHTING 4's CI log for the job named `check-coverage` ends with `1 failed, 731 passed in 14.49s` — i.e. it plainly DID run a suite. Both are true. `justfile:330-339`:

    check-coverage:
        if [[ -f .coverage ]]; then
            echo ":: check-coverage: reading existing .coverage (produced by check-per-file-coverage); no duplicate suite run"
            uv run coverage report --fail-under=100
        else
            echo ":: check-coverage: no .coverage data file (CI standalone job); running the suite"
            uv run pytest -n [test_nprocs, a just interpolation] --cov --cov-branch ...
        fi

LOCALLY, inside the `just check` aggregate, `check-per-file-coverage` has already produced `.coverage`, so `check-coverage` only runs `coverage report`. **It executes no tests at all.** On CI it is a STANDALONE matrix job with no prior `.coverage`, so it runs the entire suite.

THE CONSEQUENCE, and it sharpens the lane distinction recorded earlier in this item:

  - A LOCAL `check-coverage` failure CANNOT be a test failure. It can only be a
    coverage-number failure — and the number came from a suite run by a DIFFERENT
    target. So a local sighting on this target is always a downstream symptom.
  - A CI `check-coverage` failure runs the whole suite and CAN be, and in SIGHTING 4
    was, a genuine test failure.

So the two lanes are not merely differently loaded: **the same target name performs structurally different work in each.** Anyone comparing sightings by target name — which is the natural thing to do, and which this item's own sighting list invites — is comparing two different operations. That is worth more than the load difference for reading the history correctly, and it is why SIGHTING 2 and SIGHTING 3 (local, coverage shortfalls) could never have looked like SIGHTING 4 (CI, assertion) even with an identical underlying cause.

Not a defect, and nothing to file: the conditional is deliberate and its two branches announce themselves. Recorded because the description's sentence is lane-specific while reading as general, and I nearly treated the CI log as contradicting it.
=== FOLD-IN FROM plan/supervisor-prompt-quality/, 2026-08-02T00:45Z ===

PROVENANCE, STATED FIRST SO NOTHING HERE IS OVER-READ. These are the
supervisor-prompt-quality thread's measurements, carried across by that thread's
supervisor. What I re-measured myself is the GAP, not each figure: this item's
updated_at was 2026-07-31T03:14:09Z and every probe below returned ZERO against
its 32,100-character notes field, with `per-file-coverage` (9 hits) and
`SIGHTING` (27 hits) as positive controls proving the probe could find things.
The findings themselves are that thread's, recorded in its handoff.md with their
own timestamps. Cited, not re-derived.

Why it is being written now: the fold-in that closed overseer-jcw into this item
was diligent and read back, but it was a SNAPSHOT taken at 03:14Z. Everything
below was measured AFTER that instant, so it was stranded by ordinary sequencing
rather than by anyone's oversight. The gap had stood ~45 hours across three
sessions, each of which correctly declined to write to another track's item.

--- 1. THE SEVERITY CORRECTION (measured 2026-07-31T03:43Z, 29 min after the
       fold-in) — THIS ONE CHANGES TRIAGE ---

This item's mechanism-2 note reads "0 of 8 alone, 0 of 8 under light paired load,
2 of 8 under two FULL concurrent suites". That frames mechanism 2 as needing a
CONTRIVED DOUBLE LOAD, and it is understated.

"Alone" there meant a single non-xdist pytest run of ONE module. Mechanism 2
fires in the ORDINARY `just check` aggregate with NO external load: caught live
on a pre-push, on xdist worker [gw3], minutes after a foreground `just check` on
the identical tree passed 65/65. The aggregate's OWN xdist parallelism is
sufficient CPU load.

That is precisely what jcw reported as "run-alone passes, in-aggregate flakes",
which had been read as pointing at a shared .coverage file rather than at CPU
contention. Consequence for a fixer: triage is "run the gate normally", NOT
"reproduce it by running two suites at once".

--- 2. THE ARITHMETIC, AND THE TWO DEAD OPTIONS (measured 2026-07-31T04:50Z) ---

This item says the fix is a contract choice but does not record WHICH
alternatives are already eliminated. The arithmetic eliminates the first two
instincts:

  _POLLS = 4, _STABLE_TO_IDLE = 3, poll interval 0.15s. `stable` resets to 0 on
  ANY change, so IDLE requires captures 2, 3 AND 4 to equal capture 1 — an
  unchanging pane for ~450ms, about NINE missed 50ms ticks in a row. The pane is
  visible-only and the counter monotonic, so equality means no new line RENDERED.
  That is genuine CPU starvation of the spinner, not a spacing problem.

  - "Tick faster" (sleep 0.01) CANNOT WORK. A descheduled process does not tick
    at any rate. It narrows nothing and would look like a fix until it flaked.
  - "Reduce parallelism" is a LEVER ALREADY SPENT. test_nprocs is deliberately
    25% of cores locally (4 of 18 on this host) precisely so a shared host is
    never oversubscribed, and mechanism 2 fires anyway. Contention is HOST-WIDE
    (many worktrees, other tracks, the overseer daemon), not xdist alone. Note CI
    takes the other branch (-n auto, dedicated runner).
  - Raising _POLLS / _STABLE_TO_IDLE changes the WATCHER's own parameters — the
    thing under test — to make its test pass.
  - The honest repair is asserting EVENTUALLY-BUSY within a bounded window.
    Discrimination survives: a genuinely idle pane never changes, so it yields
    IDLE at every attempt and retrying cannot manufacture a false BUSY. What is
    lost is the stronger "always" reading. That is a contract decision.

--- 3. THE ACCEPTANCE DENOMINATOR IS UNSOUND — SEQUENCING, AND IT INVERTS ---
       (measured 2026-08-01T08:05Z / 12:05Z / 12:45Z)

This is the item with the largest effect on this bug and it is absent entirely.

`just check` can report "All 65 targets passed" WITH A FAILING TEST. justfile
check-per-file-coverage sets pipefail WITHOUT errexit, so a non-zero pytest does
not abort the recipe and the recipe's status is the LAST command's — the coverage
check. Executed rather than argued: with pipefail alone, a false followed by a
true yields status 0; with errexit added, it yields 1.

It reaches the AUTHORITATIVE signal, not just developer hosts:
check-per-file-coverage is its own job in the CI matrix and is a REQUIRED status
check on master. So a test failing at an already-covered assert produces a GREEN
required check — the same green that satisfies branch protection and feeds the
Dispatcher's "latest master is green" pre-flight.

AND THE BLIND MODE IS DEMONSTRATED FOR THE VERY TEST THIS ITEM COUNTS.
test_both_forms_report_busy_while_a_pane_keeps_changing has 6 statements with
asserts at positions 4 and 5:
  - failing at assert 4 leaves statement 5 unexecuted -> coverage drops -> the
    target fails -> this is the signature EVERY recorded sighting has;
  - failing at assert 5 leaves nothing unexecuted -> coverage holds at 100% ->
    the board goes fully green over a failed P1 flake.

CONSEQUENCE FOR THIS ITEM'S ACCEPTANCE: the bar is statistical (20 consecutive
clean runs), and clean runs are counted from a board with a demonstrated blind
mode for the test being counted. An unknown fraction of any green streak may
contain the failure it is meant to disprove. The bar is not merely set against a
stale rate — THE DENOMINATOR ITSELF IS UNSOUND until the recipe is unmasked.

So the order inverts the intuitive one: UNMASK FIRST, THEN MEASURE, then decide
the contract. Unmasking is a PRECONDITION for measuring this item, not a
follow-up to it.

Stated with its limit: the masked subset is partial, not total. When the test
dies mid-body the failure IS caught. This does not mean the board has been lying
wholesale; it means the board cannot be relied on to have told the truth, and the
record cannot bound how often.

--- 4. TWO NEW SIGHTINGS, BOTH ON DOCS-ONLY CHANGES ---

SIGHTING (2026-08-01T05:30Z): docs-only change, one markdown paragraph, no Python
touched. `just check` failed check-per-file-coverage + check-coverage; the target
standalone passed at 100%; full-aggregate re-run passed 65/65.

SIGHTING (2026-08-02T00:2xZ): again docs-only, one markdown file, no Python. First
aggregate failed, immediate re-run passed 65/65 at 100% coverage. The essential
lines, quoted rather than left in a log:

    Coverage failure: total of 99 is less than fail-under=100
    error: Recipe `check-coverage` failed with exit code 2
    Failed targets (2):
      - check-per-file-coverage
      - check-coverage

ATTRIBUTION WAS LOST ON BOTH, and the reason is recorded rather than hidden: the
failing aggregate was piped through a summarising filter, so the FAILED line was
gone before it could be read. Both are consistent with mechanism 2 and are the
COVERAGE-VISIBLE mode, so neither is an instance of the masked class. Operational
rule that cost these two attributions: redirect the full output to a file FIRST;
never pipe a run you might need to read twice.

--- 5. RATE: THE ACCEPTANCE ARITHMETIC RESTS ON A STALE ESTIMATE ---

Roughly forty-odd full aggregates on this host on 2026-08-01 produced ONE
failure. That supports a per-run rate nearer 1/40 than the ~1/7 both original
sightings suggested, and this item's bar (20 consecutive clean for 95% confidence
against p >= 1/7) was set against the higher figure. If the true rate is nearer
1/40, twenty clean runs proves much less than the bar assumes.

    if the true rate is 1/7  -> P(8 consecutive green) = 29.1%
    if the true rate is 1/40 -> P(8 consecutive green) = 81.7%

This is NOT a request to lower the bar — it is the observation that the bar's
arithmetic should be redone against a measured rate, and that per item 3 the rate
cannot be measured soundly until the recipe is unmasked. Recorded with sample
sizes so nothing here is over-read: 1 failure in 2 aggregates on 2026-08-02, far
too small to move the 1/7-vs-1/40 question on its own; it is recorded so the
count accumulates across sessions rather than restarting.

--- WHAT WAS NOT DONE ---

No status change, no priority change, no acceptance edit, no assignment. This is
an evidence fold-in only. The contract decision (always-BUSY vs eventually-BUSY)
and the unmask decision both remain open and are named as maintainer/supervisor
calls in the source thread.

*** FRESH SIGHTING — 2026-08-02, LOCAL lane, and it is a THIRD target, which matters for the mechanism. ***

Hit while pushing PR #467 (overseer-kju6wh). Signature:

    just check-pre-push  ->  Failed targets (2): check-per-file-coverage, check-coverage
    FAILED tests/prompts/test_repo_containment_discriminates.py::test_the_rigs_socket_is_not_shared_with_a_concurrent_run
    1 failed, 798 passed, 1 skipped in 15.27s

Then, with the tree BYTE-IDENTICAL and no intervening change, the same `git push` ran green (`check` 113.32s) and the branch pushed. Standalone re-run of the single test: PASSES. So this is again "fails in the full run, passes standalone".

WHAT IS NEW HERE, stated because this item already carries two signatures and a reader should not fold this into either without noticing the difference:

  - The failing target is `test_the_rigs_socket_is_not_shared_with_a_concurrent_run` — a test whose SUBJECT IS THE SHARED-SOCKET MECHANISM ITSELF, i.e. the mechanism `supervisor-prompt-quality` fixed in PR #418. So the fix landed and this test still flakes under the aggregate. That is evidence the socket-sharing mechanism is either not fully closed or has a second source, and it is a stronger signal than a generic flake because the test is the mechanism's own detector.
  - Lane: LOCAL, and coverage was 100.00% ("Required test coverage of 100.0% reached"). The failure is reported THROUGH `check-coverage`/`check-per-file-coverage` because those targets run the pytest suite, but it is an ASSERTION/behavior failure, not an uncovered-line shortfall. This handoff's earlier "local sightings are an uncovered-line signature" line does NOT hold for this one — so the local lane now has BOTH signatures too.

NOT DIAGNOSED, and deliberately not fixed here. The push that surfaced it was landing an unrelated slice; re-running was the correct response and the gate was never weakened. Recorded so the sample grows rather than being lost.

CONFOUND TO RULE OUT BEFORE USING THIS DATA POINT: PR #467 adds a NEW aggregate member, `check-codex-skill-picker`, which drives a live Codex TUI on a pty for ~35s. It runs SEQUENTIALLY (the aggregate's loop is serial) and it touches no tmux socket, and the failing test ran inside `check-per-file-coverage`, a DIFFERENT target, whose suite skips the picker test. So it is not a plausible cause. But the sighting is contemporaneous with that change, and whoever mines this item should know that rather than discover it.

*** HARD SCOPE BOUNDARY FOR WHOEVER IMPLEMENTS THIS — supervisor-directed 2026-08-02. Read before touching anything. ***

NEVER RESOLVE THIS FLAKE BY WEAKENING, SKIPPING, RETRYING-AWAY OR DELETING THE GATE. Not a `pytest.mark.flaky`, not a retry wrapper, not a `skipif`, not raising a timeout until it stops failing, not removing the assertion, not dropping the target from the `check` aggregate. A flaky detector that gets muted stops detecting the thing it was built for, and this repo's whole enforcement posture rests on gates that can go red. Removing or weakening an existing check is refused rather than asked.

"ROOT CAUSE NOT YET FOUND" IS AN ACCEPTABLE AND HONEST OUTCOME. Say that, leave the gate strict, and record what was ruled in and out. It is strictly better than a green bought by muting.

THE TWO 2026-08-02 OBSERVATIONS ARE FACTS THE FIX MUST EXPLAIN, NOT ROUTE AROUND:

  1. The failing target — `tests/prompts/test_repo_containment_discriminates.py::test_the_rigs_socket_is_not_shared_with_a_concurrent_run` — IS THE SHARED-SOCKET MECHANISM'S OWN DETECTOR, and it is STILL FLAKING AFTER PR #418 fixed that mechanism. So either that fix is incomplete or there is a second source of socket sharing. A candidate explanation that does not account for the detector-of-the-fixed-thing still firing is not a root cause.
  2. THE "LOCAL LANE MEANS UNCOVERED-LINE SIGNATURE" SPLIT THIS ITEM RESTED ON IS BROKEN. This sighting is LOCAL and is an ASSERTION failure at 100.00% coverage ("Required test coverage of 100.0% reached"), surfaced THROUGH `check-coverage`/`check-per-file-coverage` only because those targets run the pytest suite. So both lanes now show both signatures, and any fix demonstrated on one signature must not be assumed to cover the other.

ALSO ON THE PILE, recorded earlier and still unfixed ON PURPOSE: a THIRD mechanism — `settle`/`wait_for` return SILENTLY on timeout, so a load spike is reported as a wrong answer rather than as a timeout. It was reproduced against `supervisor-prompt-quality`'s shipped code and NOT fixed, because converting it to a raise is a contract change against an explicit in-code decision ("do not convert this into a raise") and that is their lane. If this slice needs that changed, it is a PEER NEGOTIATION, not a unilateral edit.

CROSS-TRACK HAZARD: `supervisor-prompt-quality` owns `tests/prompts/`, and they have been working this same defect under the `overseer-jcw` id that was closed into this one. THE SURVIVOR CHOICE IS SURFACED AND NOT SETTLED. Do not edit their tree without coordinating, and do not assume this item is the only place work is happening.

*** THIS ITEM CANNOT CURRENTLY BE DISPATCHED, AND THE CAUSE IS IN THE ORCHESTRATOR, NOT IN THIS ITEM'S SUBJECT. Measured 2026-08-02. Do not re-dispatch until this is resolved — it fails identically every time AND leaves a phantom claim behind. ***

WHAT HAPPENS. `drive --action impl:overseer-jdo` fails at stage `fabro-run`:

    workflow.fabro:294:32: undefined template variable `test_nprocs`
      in graph attribute `goal` (template_undefined_variable)
    × Validation failed

THE CAUSE. The dispatcher interpolates this work-item's TEXT into the workflow's `goal` graph attribute, and that attribute is TEMPLATED. One of this item's notes quotes the `check-coverage` recipe verbatim, including justfile syntax:

    uv run pytest -n [test_nprocs, a just interpolation] --cov --cov-branch ...

The doubled-left-brace delimiter is `just`'s own interpolation syntax. The fabro template engine parses it as ITS variable, finds no binding, and rejects the graph before any agent runs. Verified by elimination: `grep test_nprocs` over the workflow file returns NOTHING, so the token is not the workflow's own — it arrives from this record.

BLAST RADIUS, measured across all three items admitted today: `overseer-jdo` carries the test_nprocs interpolation token; `overseer-0pc` and `overseer-mir` carry no doubled-brace token at all and BOTH dispatched normally. So this is not a general dispatcher outage — it is specific to work-item text containing double-brace tokens. In this fleet that is a COMMON shape, because quoting a justfile recipe as evidence is routine and every recipe variable looks like this. Any future item whose evidence quotes a justfile is undispatchable the same way.

IT ALSO LEAVES A PHANTOM CLAIM. After the failure this item read `status=active, assignee=fabro` while `fabro ps` reported "No running processes found" — the documented "a dispatch that fails still CLAIMS the item" shape. The claim was released back to `ready` by hand. ANYONE RE-DISPATCHING MUST RE-CHECK AND RELEASE, or the item silently looks worked-on while nothing runs. `ACTIVE` is not evidence of a run; `fabro ps` is.

BUILD CONTEXT, so the next person does not chase the wrong version. The FIRST dispatch attempt was refused outright by a staleness gate — "dispatcher plugin build is stale; executing build 9390b66a8f5b predates latest release c402de396ee3". `just ensure-plugins` moved the installed plugin to c402de396ee3, and the failure above is from THAT build, invoked by absolute path (a running session keeps its originally-resolved plugin path, so invoking the new `drive.py` directly is required). c402de396ee3 additionally warns: "master contains unreleased dispatcher commit(s): 8e5a24ef84d3; a release must be cut before this code takes effect."

WHAT WAS DELIBERATELY NOT DONE. The obvious local workaround is to edit or escape the offending note. REJECTED: that note is the item's own evidence about the coverage lane, editing evidence to satisfy a tool corrupts the record, and it would hide a defect that will recur on the next item that quotes a recipe. The fix belongs in the orchestrator — either escape work-item text before interpolating it into `goal`, or stop templating that attribute. Filing there is outside this track's authorization, so it is surfaced to the supervisor rather than filed unilaterally.

NOTHING ABOUT THE FLAKE ITSELF IS RESOLVED BY THIS NOTE. The hard scope boundary in the preceding note stands unchanged: never weaken, skip, retry away or delete the gate.

*** ROOT CAUSE FOUND AND REPRODUCED for the LOCAL two-signature family — and it is NOT socket sharing. Plus: the 2026-08-02 "fresh sighting" note conflates two runs, and PR #470 changes what its signature means. Measured 2026-08-02, session 8a475801. ***

== PART 1 — THE #470 RE-READ THE HANDOFF ASKED FOR ==

TIMELINE. PR #467 (whose push surfaced the fresh sighting) merged 02:09Z; PR #470 — "unmask check-per-file-coverage", adding errexit so a non-zero pytest reddens the recipe — merged 02:51Z. Every event in the fresh-sighting note therefore ran under the OLD, MASKED recipe, where a pytest failure could NOT redden check-per-file-coverage; only the trailing per-file coverage checker could.

THE NOTE FUSED TWO RUNS (verified against session c36d02b9's transcript, records 704-721):

  RUN 1 — the failing push aggregate. Only "Failed targets (2)" and the recipe
  tail were ever seen; the pytest lines were LOST to a tail truncation — the
  attribution-loss mode this item already warns about. Under the masked recipe
  those two targets go red together only via a per-file shortfall plus
  total<100, i.e. a MID-BODY death. WHICH test died was never observed; the
  note's attribution of RUN 1 to the socket-detector test is an inference
  bridged from RUN 2.

  RUN 2 — the standalone diagnosis run of check-per-file-coverage afterwards.
  THIS is where "FAILED ...test_the_rigs_socket... 1 failed, 798 passed" and
  the 100.00% total come from. And at 100% under the masked recipe, RUN 2's
  target exit status was 0 BY CONSTRUCTION — a live, in-the-wild instance of
  the masked class, visible only because the tail happened to include pytest's
  summary text. It is jdo's own flaky test, exactly as #470's commit message
  anticipated.

CONSEQUENCES: (a) "the local lane now shows the assertion signature" SURVIVES,
but its stated mechanism is corrected — pre-#470 that signature could not
redden the targets, and locally check-coverage runs no suite when a .coverage
file exists; (b) every pre-#470 TARGET-LEVEL "passed standalone" (e.g.
SIGHTING 3's "standalone passed twice at 100%") bounds only the shortfall
mode — a masked assertion failure would also have presented as target-green;
single-TEST pytest re-runs are unaffected; (c) all pre-#470 local failure
counts UNDERCOUNT, so the fold-in's ~1/40 estimate inherits the mask and rates
from before and after #470 must not be pooled. The fold-in's own directive —
UNMASK FIRST, THEN MEASURE — is satisfied as of 02:51Z.

== PART 2 — ROOT CAUSE OF THE RESIDUAL DETECTOR FLAKE (hard-fact #1), FOUND, REPRODUCED, AND IT EXCULPATES PR #418 ==

FIRST SOUND POST-UNMASK MEASUREMENT. Ten consecutive `just
check-per-file-coverage` runs on the clean primary checkout at de6a7ed
(includes #470), local parallelism (4 xdist workers), host load 39-49 on 18
cores throughout (other tracks' work — real contention, not contrived), full
output kept per run. Result: 9 clean, 1 FAIL (run 5) —
test_the_rigs_socket_is_not_shared_with_a_concurrent_run, coverage 100.00%,
recipe exit 1 (the unmask reporting honestly). And this time THE ASSERT DIFF
WAS CAPTURED:

    -'/home/ubuntu/.oh-my-zsh'
    +'/tmp/pytest-of-ubuntu/pytest-5804/popen-gw2/test_the_rigs_soc...0/mine'

`live` was NEITHER empty (transient tmux client failure) NOR a foreign pytest
root (real socket sharing). It was the shell framework's own directory.

THE MECHANISM. The test reads #{pane_current_path} IMMEDIATELY after
new-session, with no synchronization on shell readiness. The pane's shell on
this host is zsh + oh-my-zsh (via ~/.acfs/zsh/acfs.zshrc:75-76), with
auto-update enabled (zstyle :omz:update mode auto, frequency 1). omz's startup
machinery runs subshells/children whose cwd is $ZSH — e.g. oh-my-zsh.sh:114's
zcompdump-revision probe and tools/check_for_upgrade.sh, both built on
`builtin cd -q "$ZSH"` — so during startup the pane's reported current path
TRANSITS THROUGH /home/ubuntu/.oh-my-zsh. Under load the startup window
stretches and the test's single read lands inside it.

REPRODUCED OUTSIDE THE SUITE ENTIRELY, same query the test uses, scratch
sockets only: 30 fresh panes created with -c <dir>, each sampled continuously
for 1s. In 23/30 panes the reading transiently equaled /home/ubuntu/.oh-my-zsh
at some point; in 1/30 the FIRST reading — which is all the test takes — was
already .oh-my-zsh. That per-read rate (~3% under load ~40) matches the
observed per-run flake rate given the suite takes two such unsynchronized
reads per run.

AND IT UNIFIES THE TWO LOCAL SIGNATURES — one cause, two presentations,
selected purely by WHERE the cwd assert sits:

  - test_the_pane_cwd_the_forms_receive_comes_from_a_real_tmux_pane asserts
    the cwd MID-BODY (line 129); an omz-transient hit there dies with lines
    130-134 unexecuted — EXACTLY SIGHTING 3's recorded signature
    ("test_repo_containment_discriminates.py:130-134 at 92%"). Shortfall mode.
  - test_the_rigs_socket_is_not_shared_with_a_concurrent_run asserts it LAST
    (line 189, finally still runs); a hit there leaves nothing uncovered.
    Assertion-at-100% mode — RUN 2 above, and today's run 5.

SO HARD-FACT #1 IS ANSWERED WITHOUT IMPUGNING #418: the detector fires with NO
socket sharing present. Ruled out for the residual, measured on this host:
live orphan rig servers (all ~5,470 stale legs-/disc- socket files probed;
zero live servers) and PID recycling (kernel.pid_max 4194304).

WHAT THIS DOES NOT EXPLAIN, so it is not over-read: S1/mechanism 2 (churning-
pane premise, different test) and S4/mechanism 3 (CI lane, silent settle
timeout) stand exactly as documented. And the finding is HOST-SCOPED in one
respect: the transit value .oh-my-zsh is this host's shell config; a different
host's shell init may produce a different transient (or none), though the
unsynchronized-read defect is host-independent.

FIX DIRECTION, NOT ACTED ON — tests/prompts/ is supervisor-prompt-quality's
deliverable, so this is a PEER NEGOTIATION item alongside mechanisms 2 and 3.
For the negotiation: an eventually-consistent read (retry the pane_current_path
read until it equals the expected dir or a bounded window closes) is NOT a
weakening of either detector — a genuinely shared socket converges to a
FOREIGN pytest root, never to `mine`, and an absent pane stays "" — so full
discrimination survives while the shell-startup transient stops impersonating
a verdict. The gate itself was not touched, weakened, skipped or retried-away
in producing any of this evidence.

MEASURED vs INFERRED:
  MEASURED  merge order (#467 02:09Z, #470 02:51Z); the transcript's two runs;
            the recipe text both sides of #470; run 5's assert diff; the 30-
            pane probe (23/30 transient, 1/30 first-read); the socket and
            pid_max rule-outs; 1-failure-in-10 unmasked runs at load 39-49,
            per-run logs and loads recorded in session 8a475801's scratchpad.
  INFERRED  that RUN 1's dying test was one of the two cwd-reading tests
            (fits S3's exact line range; unobserved — output truncated); that
            RUN 2 and the wind-down failure took the omz-transient path (the
            diff was not captured there; today's run 5 diff is the direct
            observation of the same failure at the same assert).

MECHANISM MEASURED 2026-08-03, and it is a MARGIN ASSUMPTION STATED AS A GUARANTEE rather than an unexplained flake.

WHERE. tests/prompts/test_watcher_wake_discriminates.py::test_both_forms_report_busy_while_a_pane_keeps_changing (and its two siblings in the same module). The busy leg drives a pane with:

    i=0; while :; do i=$((i+1)); echo TICK-$i; sleep 0.05; done

and asserts the watcher reports BUSY. The watcher compares captures across _POLLS = 4 iterations separated by time.sleep(0.15). Two identical consecutive captures read as IDLE.

THE TEST'S OWN COMMENT STATES THE ASSUMPTION AS A FACT: 'A 50ms tick against a 150ms poll guarantees a new value every poll without starving anything.' That is a 3x margin, and it guarantees nothing about VALUE CHANGE - it guarantees only that the tick process, IF PROMPTLY SCHEDULED, emits three times per poll window. On a loaded host the tick shell is not promptly scheduled, the pane does not change between two polls 150ms apart, and the watcher correctly reports IDLE against a pane that is genuinely not changing. The assertion fails for a true reading.

THE MEASUREMENT, taken while this blocked a merge:
  - one-minute load average 89-169 against 18 CPUs; 10,740 threads, 88 runnable.
  - the module fails on UNMODIFIED origin/master (control), so it is not any branch's doing.
  - across five runs the FAILING PAIR VARIED (test_both_forms_report_busy..., test_c_a_footer_in_scrollback_wakes_the_shipped_watcher, test_c_a_footer_in_scrollback_does_not_wake_the_proposed_watcher in different combinations) - the signature of timing, not logic.
  - the last completed master CI run is GREEN, so a normally-loaded host passes and CI is not a witness to this.
  - the only uncovered statements in a failing run (lines 182, 200) are INSIDE the failing tests, so the accompanying coverage failure is a consequence, not a second defect. Do not chase it separately.

WHY IT MATTERS BEYOND ANNOYANCE: this is a HARD BLOCK on landing work, not a retry-and-move-on. The pre-commit red-green-replay green-verified leg requires the FULL suite to pass, so on a loaded host NO behaviour-preserving change can be committed at all - including pure documentation changes, which is how it was hit. --no-verify is not an option and must not become one.

SHAPE OF A FIX, not prescribed: the busy leg needs a signal that survives scheduling delay rather than a wider margin - e.g. assert on the pane having changed since a captured baseline with a deadline (the settle() pattern this same conftest already uses and documents as 'never a fixed sleep'), instead of on adjacent-poll inequality. Widening 150ms to a bigger number only moves the load at which it breaks.

RELATED: overseer-6i0 (the same rig leaks a socket per test and never reaps its servers - 9,137 orphan sockets, 58 zombie 'tmux: server' processes). Those are contributors to host cost, NOT the root of this; closing 6i0 does not close this.
SIBLING FILED 2026-08-03 for the BUSY leg specifically, so this general item is not closed on a specific fix. PR #547 (overseer-63y) already fixed the (c) scrollback leg of the same module; the busy leg's margin assumption is separate and still live.
WIDENED 2026-08-03: the blocker is MODULE-WIDE, not one leg. Probes show the failure alternating between the busy leg (overseer-9yo) and the (c) scrollback leg, which fails via a DIFFERENT mechanism — PR #547's deliberate 'fail_on_timeout=True' against a 5s settle deadline. Both are fixed time budgets violated by a host at load 84-169 on 18 CPUs. Fixing either leg alone does not restore the ability to commit, because the green-verified leg needs the WHOLE suite.

---

SCHEDULING HOLD APPLIED 2026-08-19 by the grooming session. This item is
UNDISPATCHABLE as written, and it was sitting at `ready` and P1 where a Dispatcher
drain would have picked it up.

WHY. Its own notes quote the `check-coverage` recipe verbatim as evidence,
including a doubled-left-brace interpolation of the test-process-count variable.
That is `just`'s interpolation syntax; the fabro template engine parses it as ITS
OWN and the graph is rejected before any agent runs. This is the trap documented
in the repo-root CLAUDE.md, and this item is the write-up OF that trap -- so it is
also the worked example of the sharpest corollary: the trap fires on prose ABOUT
the trap, because naming the hazard accurately meant reproducing the delimiter.

I HAVE NOT EDITED THE POISONED TEXT, DELIBERATELY. CLAUDE.md is explicit that
escaping or deleting it corrupts the item's own evidence and hides a defect that
recurs on the next item quoting a recipe. The dispatcher defect is tracked as
`bd-ib-vv9y` in the orchestrator tenant. The text stays exactly as filed.

WHAT I DID INSTEAD: deferred it, which removes it from the ready set without
touching a byte of its content. A deferral is a reversible SCHEDULING decision,
not a judgement on the work -- the flaky-check-aggregate defect it describes is
real, P1, and still wants fixing.

TO ACT ON IT, pick one and record which:
1. Preferred -- land `bd-ib-vv9y` so the dispatcher neutralizes template
   delimiters, then clear the deferral and dispatch this record unchanged. That
   fixes the class, not the instance.
2. Host-tier it. The work is a local investigation of check-aggregate flakiness
   under concurrency; a host session can do it without the factory at all, and
   this item never needed to be dispatch-safe.
3. Last resort -- file a clean-text successor carrying the same scope and
   acceptance with the delimiter described in WORDS rather than reproduced, and
   close this one as superseded, recording why. Note this is the ONLY remedy
   available when the poison is in a ledger COMMENT, since comments are
   append-only with no edit or delete; here the poison is in notes, so options 1
   and 2 remain open and are better.

RELATED, so the pattern is visible: `overseer-rh1` carries the same hazard (it
quotes the CI green-condition expression) and is safe only because it sits at
`backlog`, outside the ready set. If anything ever routes rh1 to `ready` without
addressing this, it acquires the same defect. `overseer-bc55wx.8` hit the terminal
comment-borne form and had to be superseded rather than fixed.

---

CORRECTION TO THE HOLD ABOVE, same day, by the session that applied it. The
deferral described above was WITHDRAWN within minutes because it caused a
tenant-wide dispatch outage. The reasoning for keeping this item out of the ready
set is unchanged and still stands; only the MECHANISM was wrong.

WHAT WENT WRONG. `bd update --defer <date>` writes bd's NATIVE status `deferred`,
which is outside the seven-status livespec lifecycle
(backlog / ready / pending-approval / active / blocked / acceptance / closed). The
Dispatcher runs a GLOBAL pre-dispatch ledger conformance sweep, so one
non-conforming item refuses EVERY dispatch in the whole tenant:

    pre-dispatch ledger checks failed; dispatch blocked
    (drive.py exit 1, dispatcher exit 1, no phantom claims)

Two items were deferred that day, and between them they would have blocked all
factory dispatch in `livespec-overseer` until 2026-08-26. Caught by the foreman
within minutes of being applied.

THE CORRECT WAY TO HOLD AN ITEM OUT OF THE READY SET is `backlog` — a real
lifecycle status that is already outside the ready set — with the horizon and the
release condition recorded in the item's own text, exactly as this note does. Do
NOT reach for `--defer`.

TWO TRAPS FOR WHOEVER REPAIRS ONE OF THESE:

1. CLEARING a deferral is ALSO non-conforming. `bd update <id> --defer ""` leaves
   the item at bd-native `open`, which is likewise outside the lifecycle, so the
   tenant stays blocked. Run `--defer ""` and `--status <lifecycle>` as a PAIR and
   verify only after both. A verification between the two shows the tenant still
   blocked and reads as "the fix is not working".

2. A CONFORMANCE CHECK THAT WHITELISTS `open` WILL PASS A BROKEN LEDGER. That is
   not hypothetical: the verification sweep run during this very repair made
   exactly that error and reported clean while an item sat at `open`. Any checker
   built for this needs a discriminating control asserting that a bd-native `open`
   item IS reported.

The `bd` guard does not currently guard the `--defer` flag, because the flag's own
documentation claims it writes no status — measured false. Both that guard gap and
the dispatcher hard-blocking on a substrate-native status are being routed to the
orchestrator as defects.

DELIMITER REPAIR, 2026-08-21, livespec-overseer grooming drain pass (seat anchor overseer-qyli). The five doubled-brace template-delimiter spans this field carried -- located by the 2026-08-19 comment below at offsets 30542, 46266, 46307, 46711 and 46773 -- were replaced in place with word-descriptions; every other byte of this field is unchanged. Done because the item had moved from backlog to READY, which made the poison a live dispatch refusal rather than a latent one, and because all five spans were in this editable field and none in an append-only comment, so no successor was needed. The fleet defect that makes a quoted just recipe undispatchable is tracked in the orchestrator tenant as bd-ib-ai9a (superseding bd-ib-vv9y); this repair does not close it.