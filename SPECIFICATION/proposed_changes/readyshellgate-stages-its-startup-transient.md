---
topic: readyshellgate-stages-its-startup-transient
author: claude-opus-5-5
created_at: 2026-11-13T05:40:02Z
---

## Proposal: A live herdr test's staged startup transient lives until its observer has pinned the shell, not for a fixed time

### Target specification files

- SPECIFICATION/non-functional-requirements.md
- SPECIFICATION/scenarios.md

### Summary

Adds one bullet to non-functional-requirements.md, section "Scenarios", after its last bullet, and one new `## Scenario:` heading to scenarios.md, after its last scenario. Together they state a rule for this repository's live herdr observation tests. When a test gate stages a controlled startup transient for an observer to see, the transient's lifetime is not a fixed wall-clock duration. It stays alive until the test releases it by rendezvous. The test writes the release only after the observer has pinned the shell it is watching, and it always writes it, even when the observer never sees the transient. A hang guard no shorter than the gate's establishment bound limits it. A slow first reading on a loaded host therefore cannot miss the transient. The rule is stated as observable test-harness behaviour, not as code. The new scenario adds one H2 heading to scenarios.md, so the revise that ratifies this proposal owes a `tests/heading-coverage.json` row for it and a regenerated heading-coverage debt register. No heading is removed or renamed.

### Motivation

Work item overseer-wbrvxm ("ReadyShellGate stages its startup transient with a fixed 2 s lifetime, so a slow first reading can miss it: release it by rendezvous after the shell pin") was refused before factory dispatch with rc=5 at the spec-change tier. The dispatcher's judgement found the behaviour it asks for unstated in this specification (governing-heading-kind: unstated). It named `## Scenarios` as the heading the new text generalizes from, and `readyshellgate-stages-its-startup-transient` as the proposal topic. This is that proposal.

Its predecessor, overseer-aog22f (closed; livespec-overseer#2945, commit 212236a3), added the `rendezvous_transient` test primitive and applied it to the discriminating exercise in `tests/test_herdr_live_retained_shell_launch.py`, where several bounded observers had to see one transient in sequence and nothing made them meet. No text in this specification covers that rendezvous: `git grep -i "rendezvous\|startup transient" origin/master -- SPECIFICATION` returns nothing. So the rule aog22f applied is unratified, and wbrvxm, which applies the same rule to the one remaining fixed-lifetime use, cannot be tier-judged against it.

The mechanism wbrvxm targets, read from master at 212236a3: `ReadyShellGate._establish` in `tests/test_herdr_live_observations.py` sends a transient that lives a fixed `TRANSIENT_SECONDS = 2`. `await_occupying_child` then polls at 0.1 s, with one herdr RPC per reading, until it sees that transient. Nothing makes the reading and the transient meet. On a loaded host the first usable reading can arrive after the transient has exited, and the gate then refuses with "the controlled startup transient was never observed", with nothing wrong in the code under test. It is the same unrendezvoused window as aog22f, with one observer. No failure has been recorded yet, which is why wbrvxm is P3. It is tracked as carrier 113 of the fleet-flaky-tests seat (epic livespec-dev-tooling-zwveqp), whose 2026-11-11 reopen condition was to apply aog22f's rendezvous here once it landed.

Placement. The bullet goes in non-functional-requirements.md section "Scenarios" because that is the dispatcher's named generalization target, and because a rule about how this repository's tests gather evidence is a contributor-only concern under the Boundary litmus. The scenario in scenarios.md carries the same behaviour in Given/When/Then form, per the rule that load-bearing behaviour has a clause and a scenario.

In-flight work, surveyed 2026-11-13. The pending proposal `livespec-overseer-tests-bound-waits` (non-functional-requirements.md, section "Constraints") governs a test's waits on progress the code under test is required to make. This proposal is compatible with it and restates none of it: the transient is a fixture child the test stages, its hang guard bounds that child's life rather than a verdict-bearing wait, and the rendezvous removes a wall-clock race from the gate's verdict in the same spirit. Open spec PRs livespec-overseer#2978 (revise v097, CAAM reset at the best-value moment) and livespec-overseer#2960 (enrolled-host delivery by ssh push) also touch scenarios.md, in unrelated sections; this proposal appends after the file's last scenario and aligns with both.

Heading coverage. When this proposal is ratified, the revise commit MUST add a `tests/heading-coverage.json` row for the new scenario heading. Until overseer-wbrvxm lands its test, that row is a `test: "TODO"` entry whose `reason` names the integration tier and overseer-wbrvxm, with `"work_item": "overseer-wbrvxm"`, registered in the generated debt register.

### Proposed Changes

1. In `SPECIFICATION/non-functional-requirements.md`, section "Scenarios", append the following bullet after the section's last bullet, which begins "Outside unblocking a session at a picker". No heading is added, removed or renamed in that file.

- **A staged startup transient is released by rendezvous, not by a timer.** A live herdr observation test's gate MAY stage a controlled startup transient: a real, distinctly named child process started in a created pane so that an observer can see the pane occupied and then see it clear. The transient's lifetime MUST NOT be a fixed wall-clock duration. The transient MUST stay alive until the test releases it by rendezvous. The test MUST write that release only after the observer has pinned, by identity, the shell the transient runs under, and before the test waits for the transient to exit. The test MUST write the release on every path, including when the observer never sees the transient, so that an unobserved transient never waits out its hang guard. The transient's hang guard MUST be no shorter than the gate's own establishment bound, and a transient whose hang guard expires MUST exit and report that it was never released. The gate's verdict MUST depend on what the observer saw, never on how quickly the host answered the observer's first reading. A slow first reading on a loaded host therefore MUST NOT miss the transient. The rule applies to this repository's tests.

2. In `SPECIFICATION/scenarios.md`, append the following scenario after the file's last scenario, whose heading is "## Scenario: a hand commit's passing delegated pre-commit verdict stands in at the pre-push gate". The scenario follows the file's existing Given/When/Then style.

## Scenario: A live herdr test's staged startup transient outlives a slow first reading

Given a live herdr observation test whose gate stages a controlled startup transient in a created pane for an observer to see

And the test releases the transient by rendezvous, under a hang guard no shorter than the gate's establishment bound

When the observer's first usable reading of the pane arrives later than a fixed-lifetime transient would have lived

Then the observer still sees the transient occupying the pane

And the test writes the release only after the observer has pinned the shell the transient runs under, and before it waits for the transient to exit

And the gate then observes the transient gone and that same shell idle, and establishes the pane

When the observer never sees the transient before its own bound expires

Then the test still writes the release, so the transient exits without waiting out its hang guard

And the gate refuses, naming the transient it never observed, and does not establish the pane

3. When this proposal is ratified, the revise commit MUST add one `tests/heading-coverage.json` row for the heading "## Scenario: A live herdr test's staged startup transient outlives a slow first reading" in `scenarios.md`, and MUST regenerate the heading-coverage debt register if that row is a `test: "TODO"` entry. Until overseer-wbrvxm lands its integration-tier test, the row's `reason` MUST name the integration tier and overseer-wbrvxm, and the row MUST carry `"work_item": "overseer-wbrvxm"`.
