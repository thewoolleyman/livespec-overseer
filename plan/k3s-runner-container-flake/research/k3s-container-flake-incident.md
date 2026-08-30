# The 2026-08-30 master-red incident: what the k3s container annotation actually meant

All times UTC, read from `date -u` at the moment of measurement. All run, job and
runner identifiers below were read from the GitHub Actions API on 2026-08-30
between 07:21:47Z and 07:24Z, not from a prior scrape.

## The headline correction

This incident was handed to this thread as *"master red from a k3s workflow-pod
container failure"* — an infrastructure fault in the ARC self-hosted runner, with
the fix expected to land in `livespec-dev-tooling`'s `ci-runner/k3s` config, in the
lineage of the 2026-08-17/18 AppArmor incident recorded in
`.ai/ci-runner-routing-history.md`.

**That framing is wrong, and the annotation that produced it is a consequence
rather than a cause.** The measured cause is a **missing-wait race in this
repository's own end-to-end test**, in `tests/e2e-cli/test_plugin_bin_entrypoints.py`.
The fix belongs here, not in the runner-infrastructure repo.

The correction matters beyond bookkeeping: acting on the original framing would
have sent someone to inspect a k3s cluster, compare against the AppArmor-era
signature, and potentially exercise the sanctioned rollback of `CI_RUNNER_LABELS`
to hosted runners — none of which would have touched the actual defect, and the
last of which would have discarded a working runner pool over a test bug.

## What the annotation says, and why it is not the cause

The failed job carried four annotations. Verbatim, in the order the API returns
them:

    warning: Node.js 20 is deprecated. The following actions target Node.js 20 but
    are being forced to run on Node.js 24: actions/checkout@v4. For more
    information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

    failure: Executing the custom container implementation failed. Please contact
    your self hosted runner administrator.

    failure: Process completed with exit code 1.

    failure: Error: failed to run script step: command terminated with non-zero
    exit code: error executing command [sh -e /__w/_temp/a6e6a940-a441-11f1-8bed-a9d1bf515d78.sh],
    exit code 1

Read alone, the second one reads as "the runner could not execute your container"
and names a self-hosted-runner administrator as the person to call. That is what
the original scrape concluded.

**The job log's own timestamps refute it.** The four lines arrive in this order,
inside 0.65 of a second, and every one of them is *downstream* of a test failure
that had already been printed:

    07:11:26.9172560Z  FAILED tests/e2e-cli/test_plugin_bin_entrypoints.py::test_shipped_foreman_e2e_covers_seed_session_attention_and_cadence
    07:11:26.9174499Z  1 failed, 3035 passed, 1 skipped in 154.56s (0:02:34)
    07:11:27.0400545Z  error: Recipe `check-per-file-coverage` failed on line 572 with exit code 1
    07:11:27.6253273Z  ##[error]Error: failed to run script step: ... exit code 1
    07:11:27.6321883Z  ##[error]Process completed with exit code 1.
    07:11:27.6402336Z  ##[error]Executing the custom container implementation failed. ...

So the sequence is: pytest fails one test → `just` reports the recipe exited 1 →
the ARC Kubernetes container hook observes its script step exited non-zero and
emits its own generic wrapper text. **The container hook is reporting that the
command it ran failed, not that it failed to run the command.** The message is
badly worded for that case — it names an administrator for what is an ordinary
non-zero exit — but it is emitted on every failing step in `containerMode:
kubernetes`, and carries no information about the cause.

**The transferable rule.** This is the same shape as the dispatcher-envelope rule
in `.ai/dispatch-traps.md`: a wrapper's status describes the layer that gave up,
not the layer that failed. When an infrastructure-sounding annotation sits at the
END of a log, read upward for the first non-zero exit before attributing anything
to the infrastructure. An annotation list is ordered by severity and position, not
by causality.

## The actual failure

Run `33298390930` (workflow `CI`, event `push`), head `6b2589ab`, "docs(spec):
bound per-session model-enforcement exception to servability (v043)", created
2026-08-30T07:05:29Z.

Failing job `check-per-file-coverage`, job id `99221898843`, runner
`livespec-overseer-k3s-tjvgd-runner-6xmxp`, labels `["livespec-overseer-k3s"]`,
started 07:06:09Z, completed 07:11:33Z, conclusion `failure`.

Everything else in that job was healthy. The suite ran 3035 passing tests, one
skipped, in 154.56 seconds, and coverage reported `Required test coverage of
100.0% reached. Total coverage: 100.00%`. Exactly one test failed.

The traceback, on pytest-xdist worker `gw17`:

    tests/e2e-cli/test_plugin_bin_entrypoints.py:1510  _assert_blocked_consensus_chain
    tests/e2e-cli/test_plugin_bin_entrypoints.py:1125  _assert_unanimous_blocked_answer_act
    tests/e2e-cli/test_plugin_bin_entrypoints.py:1066
        assert "Yes, proceed with the bounded retry.\n" in log.read_text(encoding="utf-8")
    FileNotFoundError: [Errno 2] No such file or directory:
        '/tmp/pytest-of-root/pytest-0/popen-gw17/test_shipped_foreman_e2e_cover0/blocked-claude-input.log'

## Why that file was absent: the race, and where the wait is missing

The test stands up a fake `claude` in a tmux pane. The stub, written by
`_write_blocked_claude`, prints a blocking prompt and then consumes stdin:

    for line in sys.stdin:
        with log.open("a", encoding="utf-8") as handle:
            handle.write(line)
        print("ANSWER_RECEIVED", flush=True)

**The log file is created lazily, inside that loop, when the first line arrives.**
Nothing pre-creates it. Its absence therefore means the stub had not yet consumed
a line — not that anything wrote the wrong content.

The assertion that failed runs immediately after `_run_foreman_act`, which is a
`subprocess.run` of the shipped `foreman-act` binary. The test then reads the file
with `Path.read_text` and no retry at all.

The assertions immediately BEFORE the failing one all passed: `acted.returncode ==
0`, and the actuator's own JSON verdict was

    {"action_id": "blocked_session_answer", "mutated": true,
     "outcome": "acted", "reason": "answered_existing_prompt"}

**That verdict is not evidence against the race — it is confirmation at a
different layer, and this is the objection most readers will raise, so it is worth
being precise about.** `overseer/foreman_blocked_answer.py::_deliver_answer` does
not paste blindly and exit. It sends the keys, then RE-CAPTURES the pane and
requires the answer text to be visible in it (`_confirmed_answer_text`), returning
`answer_text_undelivered` if it is not. The numbered-picker branch above it does
the same against the chosen option's text.

But a tmux pane echoes input at the terminal independently of whether the child
process has read it from stdin. So `_confirmed_answer_text` establishes that the
text reached the PANE; it says nothing about whether the stub has been scheduled,
consumed the line, and flushed its log. Those are two distinct layers, and the
actuator can only confirm the first.

An `acted` verdict and an absent log file are therefore perfectly consistent, and
the product code is behaving correctly in both respects. The test is the component
that conflates the two layers: it accepts a pane-layer confirmation and then
immediately asserts on a process-layer effect, with nothing bridging the gap.

**The same file already contains the correct pattern, and the test uses it in the
setup leg but not the assertion leg.** `_prepare_blocked_session` waits for the
prompt to appear with `_wait_for_pane_capture` (line 314) — a 5.0 second deadline
polled every 50 ms. The answer-delivery leg has no equivalent. The setup half of
this test is race-aware and the verification half is not.

**Note precisely what this does and does not establish.** A bare `read_text` cannot
distinguish "not yet" from "never": if delivery had genuinely failed, the symptom
would be identical. So this evidence proves the test is *capable* of failing for a
reason unrelated to what it tests, and — combined with the run history below —
makes scheduling latency by far the best-supported reading. It does not by itself
exclude a real delivery failure on this one occasion. Reproduction under load is
the discriminator, and it is named as work below.

## It is a first occurrence, not a deterministic environment fault

The 23 `CI` runs on `master` immediately preceding this one, between
2026-08-30T02:10:32Z and 06:41:37Z, all concluded `success`, on the same
`livespec-overseer-k3s` pool. Run `33298390930` is the first failure in that
sequence.

This is the load-bearing difference from the 2026-08-17/18 AppArmor incident in
`.ai/ci-runner-routing-history.md`. That one **deterministically** failed four
named environment-sensitive tests on **every** master run it touched, which is what
justified rolling `CI_RUNNER_LABELS` back to hosted runners. Nothing of that shape
is present here: one test, one occurrence, twenty-three green runs before it.

The two incidents do share a family resemblance worth recording — one of the four
AppArmor-era casualties was also a foreman e2e — but the mechanism is different.
The AppArmor failures were denials producing empty reads and `EACCES`; this is a
timing race with no denial anywhere in the log.

The environmental contribution here is load, not configuration: this suite runs
under pytest-xdist with enough workers to reach `gw17`, inside a Kubernetes
workflow pod that had six sibling jobs contending for the same node. That raises
scheduling latency, which is exactly what an unbounded-wait assertion is sensitive
to. The pool is not misconfigured; the test has no margin.

## Master's state, and the blast radius

At 07:23:53Z:

- `master` head is `e905f46a`, "docs(plan): archive statusline-veto-wedge-repair thread".
- The red run `33298390930` is for `6b2589ab`, the **previous** commit. It still
  reported run status `queued` while carrying a failed job, because `check-lint`
  had not yet been allocated a pod — a run's status stays `queued` until every job
  has been dispatched, so a run can hold a failed job and still not read as failed.
  That is worth knowing: **run-level status is not a safe proxy for job-level
  results while jobs remain queued.**
- The run for the current head, `33298462732`, was still in flight with six jobs
  queued since 07:07:27Z.

The blast radius is the Fabro dispatcher's pre-dispatch gate, which refuses every
dispatch in this repo unless the **latest** master run is proven green at
`ci-green`. While the latest master run is red or pending, the whole repository's
factory is stopped — so a single flaky test in one job halts autonomous work
repo-wide.

Two things follow. The gate reads the latest run, so the operative question is what
`33298462732` concludes, not the older run's colour. And the cost asymmetry is
severe: this test's missing wait is a small defect, and its blast radius is every
dispatch in the repo.

## No merge-gate defect exists to fix

Pre-merge CI was green for the change that produced the red run; the failure is
post-merge, on the push event, and the commit was documentation only. **No broken
build was merged.** There is therefore no gate that failed to do its job and
nothing to tighten on the merge path. Recording this explicitly because a red
master invites a search for the gate that let it through, and here there was none.

## Fix shape

**Immediate re-green.** Confirm the run for the current master head; if it is green,
master is green and nothing needs re-running, because the dispatcher gate reads the
latest run. If it is red with this same single test, re-run only the failed jobs of
that run. If a re-run reproduces the same test failure, that is evidence the reading
above is wrong and the failure is deterministic — stop re-running and diagnose.

**The repair, which is small and lives in this repo.** Give the answer-delivery
assertion the bounded wait its sibling setup leg already has: poll for the log
file's existence and expected content against a deadline, mirroring
`_wait_for_pane_capture`, rather than reading once. The sabotage leg later in the
same helper reads the same log and needs the same treatment for the same reason —
it asserts a NEGATIVE (`"SABOTAGE SHOULD NOT PASTE" not in ...`), which a
not-yet-written file satisfies vacuously, so that assertion currently cannot fail
for the right reason either. Both are one helper.

**Before repairing, reproduce.** A fix for a race that was never reproduced is a
guess. Run this test under contention locally — heavy xdist parallelism, or an
artificial delay inserted before the stub's first stdin read — and confirm the
current assertion fails and the polled one does not. That reproduction is also the
control that distinguishes the race reading from a genuine delivery failure.

**What is NOT in scope on current evidence.** No change to `ci-runner/k3s` in
`livespec-dev-tooling`; no `CI_RUNNER_LABELS` rollback; no merge-gate change. Each
of those becomes live only if the diagnosis overturns the reading above, and the
reconsideration point is named in this plan's scope deferrals.

## Cross-repo routing note, kept because it was the original hypothesis

Runner infrastructure for this repo — the ARC scale set, the AppArmor profile, the
container-hook template — lives in `livespec-dev-tooling` under `ci-runner/k3s`,
not here. `.ai/ci-runner-routing-history.md` records the precedent, including that
in ARC's `containerMode: kubernetes` the pod tests execute in is the
hook-generated `<runner-pod>-workflow` pod and NOT the runner pod, so a scale set's
own `securityContext` is the wrong object to read.

That routing stands ready if the diagnosis turns up an infrastructure component
after all. On the evidence gathered here it should not be exercised, and this note
exists so that a later reader who arrives via the container annotation finds the
refutation rather than repeating the trip.

### The successor naming convention, pinned in advance

Maintainer-confirmed 2026-08-30. Recorded here so the diagnosis session inherits
it rather than inventing one under time pressure.

**This plan stays in `livespec-overseer`.** It anchors three things and only these:
the incident record, the re-green, and the diagnosis. It does not own any
runner-infrastructure change.

**If the diagnosis relocates the cause to runner infrastructure, it routes to
`livespec-dev-tooling` in one of two shapes:**

**(a) The likely shape — a work item in the `livespec-dev-tooling` tenant.** Its id
is assigned at filing and cannot be predicted here. Once filed, record it on this
plan's epic **from both ends**, per the rule in `.ai/deferral-successor-records.md`:
this thread's archive record names the successor row, and the successor row's own
**title or description** names this thread. Both directions are required and they
are separate facts — a successor reachable from only one end is the
one-directional shape that rule calls out, and it reads as fine from whichever
seat happens to check. Note also that the tie must be a **declaration** of
successorship, not a passing citation in a comment; a measurement note that merely
mentions this thread does not satisfy it.

**(b) If the fix is large enough to warrant its own plan over there, that plan MUST
reuse the identical slug `k3s-runner-container-flake`.** The point of reusing the
slug is that one grep locates both halves fleet-wide. Do not derive a variant name
(no suffix, no repo prefix, no rewording) — a near-miss slug defeats the entire
purpose, and this fleet already has a documented family of near-miss-name traps
where two plausible adjacent names cost real time.

**Related, and NOT the same thing:** the fleet's standing runner-pool plan is
`fleet-ci-runner-pool`, in the `livespec` repo. That is where the AppArmor-era
cutover work lived and it remains the fleet-level home for runner-pool strategy.
It is context and precedent for a successor, not the successor itself — do not
fold this incident into it by default.

**Nothing is filed in another tenant from this thread.** Filing is the diagnosis
session's act, and only if the diagnosis actually relocates the cause. On present
evidence it does not.

## Method note

The standing triage rule in `.ai/ci-runner-routing-history.md` — *a docs-only commit
failing CI is the tell that the environment, not the tree, changed* — pointed
correctly at "not the tree" and was then over-read as "therefore the runner
configuration". "Not the tree" admits a third possibility that the rule does not
name: **a latent defect in the tree that only load exposes.** The commit was
innocent and the test was not. Worth adding to that rule the next time it is
revised.
