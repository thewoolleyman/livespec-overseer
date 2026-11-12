---
topic: livespec-overseer-tests-bound-waits
author: claude-opus-5-5
created_at: 2026-11-12T22:40:00Z
---

## Proposal: A test's verdict does not depend on how fast the host runs it: waits on required progress carry no short wall-clock bound, and a worker thread's exception fails the test

### Target specification files

- SPECIFICATION/non-functional-requirements.md

### Summary

Adds one bullet to non-functional-requirements.md, section "Constraints", after its last bullet, which begins "Every shell script this repository ships or runs in its tests". The bullet states three rules. A test that waits for something the code under test is required to do does not fail just because that took longer than a short fixed time. A bound on such a wait is a hang guard only: one value per repository, at least 120 seconds, whose expiry fails the test as a named hang. An exception raised in a test's worker thread fails the test and is named in the report. It names the two kinds of wait the rule does not govern. No heading is added, removed or renamed, so `tests/heading-coverage.json` does not change.

### Motivation

livespec-dev-tooling's `tests/livespec_dev_tooling/test_incident_recovery_journal.py::test_exact_concurrent_reservation_survives_restart_and_conflicting_bytes` failed `assert not True` in CI run 43287363009 (livespec-dev-tooling#4359, a diff that touched no incident code). It started two `reserve()` threads behind `Barrier(2).wait(timeout=3)`, then ran `worker.join(3)` and `assert not worker.is_alive()`. On a loaded runner the file-locked reserve took longer than 3 s, so the join returned with the thread still alive and the assert fired, with nothing wrong in the code under test. legacy-coordinator-agent ordered a fleet sweep of the same shape (rule K). The livespec-dev-tooling half of the rule is proposed in livespec-dev-tooling#4395 (topic `test-exact-concurrent-reservation-survives`), which it graded PASS on 2026-11-12. That clause binds only livespec-dev-tooling, because each member's work items are tier-judged against that member's own specification. So each member carries the rule in its own specification, and this is that member's proposal.

This specification has no rule on wall-clock bounds in tests, and this repository's tests use bounds of 1 to 10 seconds on thread joins and event waits. Examples are `test_lpm_acquisition_commit.py:120` and `:154` (`assert …wait(timeout=1)`), `test_lpm_proof_runtime_effects.py` (2-second barrier and event waits), and `test_supervisor_log_structured_events.py:224` (`assert not thread.is_alive()`). Any of them can fail on a loaded runner with nothing wrong in the code under test. The 120-second floor is 40 times the bound that fired in livespec-dev-tooling, and below the 180 seconds livespec-dev-tooling already uses for its slowest guarded call.

A mechanical check is deliberately not proposed. A pattern-level check cannot tell a teardown wait or an expected-expiry window from a verdict-bearing bound without the per-line judgment the sweep below records. The same deferral is recorded in livespec-dev-tooling#4395.

The root-fix item for this repository is overseer-pzr23n. It was filed through this repository's capture seam on 2026-11-12 ~21:28Z, and intake held it at the spec-change tier with this topic as its linked proposal. Its cross-tenant link to livespec-dev-tooling (plan expedited-incident-hardening, epic livespec-dev-tooling-dh3hub, items livespec-dev-tooling-dqndbz and livespec-dev-tooling-rs6o3q) is recorded in prose on both sides, never as a dependency edge.

### Fleet sweep (this repository)

Swept 2026-11-12 ~21:25Z at the checked-out `HEAD`, over test files (`*test*.py`, `tests/**/*.py`, `conftest.py`), with the pattern:

```text
\.join\(\s*(timeout\s*=\s*)?[0-9][0-9.]*\s*\)|\.wait\(\s*timeout\s*=\s*[0-9]|assert\s+not\s+.*\.is_alive\(\)
```

26 pattern hits in 12 files. These are pattern hits, not per-line verdicts, because the one pattern also matches teardown waits and expected-expiry windows. The root-fix item classifies each line against the ratified rule, fixes every verdict-bearing bound and every swallowed worker exception, and records why it leaves each exempt line alone. Line numbers are as of the sweep.

- `tests/e2e-cli/test_codex_skill_picker.py`: 912, 916, 919
- `tests/integration/test_overseer_start_public_herdr.py`: 336
- `tests/integration/test_ready_arm_until_idle_live_tmux.py`: 674, 678, 683, 685, 687
- `tests/test_detached_dispatch.py`: 74
- `tests/test_herdr_absolute_bounds.py`: 271
- `tests/test_herdr_live_server.py`: 430, 442
- `tests/test_herdr_operator_delivery.py`: 55
- `tests/test_lpm_acquisition_commit.py`: 120, 154
- `tests/test_lpm_proof_runtime_effects.py`: 372, 418, 421, 433, 805, 811
- `tests/test_lpm_review_fixes.py`: 551, 558
- `tests/test_overseer_declare.py`: 270
- `tests/test_supervisor_log_structured_events.py`: 224

### Proposed Changes

In `SPECIFICATION/non-functional-requirements.md`, section "Constraints", append the following bullet after the section's last bullet, which begins "Every shell script this repository ships or runs in its tests". No heading is added, removed or renamed in that file.

- **Load-independent concurrency waits.** A test's verdict MUST NOT depend on how fast the host runs it. When a test waits for something the code under test is required to do — a worker thread or child process to finish, or a barrier, event or condition to be reached — it MUST wait either without a wall-clock bound or under a hang guard. A hang guard is one value the repository defines once for every such wait, MUST be no shorter than 120 seconds, and its expiry MUST fail the test as a hang that names what the test was waiting for. A test MUST NOT bound such a wait more tightly, as `join(3)` followed by `assert not worker.is_alive()`, `Barrier(2).wait(timeout=3)` or `assert event.wait(timeout=2)` do. An exception raised in a test's worker thread MUST fail that test, and the failure report MUST name that exception, never surface only as a missing or short result. Two kinds of wait are outside this rule: a teardown wait whose expiry falls through to a forced stop and decides no verdict, and a wait whose expiry is the outcome the test expects, such as a check that a blocked party has not yet proceeded. The rule applies to this repository's tests.
