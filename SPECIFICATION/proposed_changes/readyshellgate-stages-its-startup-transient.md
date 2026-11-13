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

Adds one bullet to non-functional-requirements.md, section "Scenarios", after its last bullet, and three new `## Scenario:` headings to scenarios.md, after its last scenario. Together they state a three-part rule for this repository's live herdr observation tests. When a test gate stages a controlled startup transient for an observer to see, the transient's lifetime is not a fixed wall-clock duration. It stays alive until the test releases it by rendezvous. The test writes the release only after the observer has pinned the shell it is watching, and it always writes it, even when the observer never sees the transient. A hang guard no shorter than the gate's establishment bound limits it, so a slow first reading on a loaded host still observes the transient. When the hang guard, not a release, ends the transient, the exercise fails with a message naming that, and never passes silently or retries quietly. The bullet states the rule as a normative clause, and each of its three behaviours gets its own Given/When/Then scenario. The rule is stated as observable test-harness behaviour, not as code. The three scenarios add three H2 headings to scenarios.md, so the revise that ratifies this proposal owes a `tests/heading-coverage.json` row for each and a regenerated heading-coverage debt register. No heading is removed or renamed.

### Motivation

Work item overseer-wbrvxm ("ReadyShellGate stages its startup transient with a fixed 2 s lifetime, so a slow first reading can miss it: release it by rendezvous after the shell pin") was refused before factory dispatch with rc=5 at the spec-change tier. The dispatcher's judgement found the behaviour it asks for unstated in this specification (governing-heading-kind: unstated). It named `## Scenarios` as the heading the new text generalizes from, and `readyshellgate-stages-its-startup-transient` as the proposal topic. This is that proposal.

Its predecessor, overseer-aog22f (closed; livespec-overseer#2945, commit 212236a3), added the `rendezvous_transient` test primitive and applied it to the discriminating exercise in `tests/test_herdr_live_retained_shell_launch.py`, where several bounded observers had to see one transient in sequence and nothing made them meet. No text in this specification covers that rendezvous: `git grep -i "rendezvous\|startup transient" origin/master -- SPECIFICATION` returns nothing. So the rule aog22f applied is unratified, and wbrvxm, which applies the same rule to the one remaining fixed-lifetime use, cannot be tier-judged against it.

The mechanism wbrvxm targets, read from master at 212236a3: `ReadyShellGate._establish` in `tests/test_herdr_live_observations.py` sends a transient that lives a fixed `TRANSIENT_SECONDS = 2`. `await_occupying_child` then polls at 0.1 s, with one herdr RPC per reading, until it sees that transient. Nothing makes the reading and the transient meet. On a loaded host the first usable reading can arrive after the transient has exited, and the gate then refuses with "the controlled startup transient was never observed", with nothing wrong in the code under test. It is the same unrendezvoused window as aog22f, with one observer. A failure has since been attributed to it: on 2026-11-13 a factory run for an unrelated item (01M79JJPSC83, overseer-33kyxp) was refused with `tests/test_herdr_live_alias_shell_launch.py::test_workspace_root_setup_consumes_one_controlled_fault_before_native_coherence[incoherent-/bin/bash]` as its first failing test, a test that goes through this fixed-lifetime path, and herdr-overseer raised wbrvxm to P2. It is tracked as carrier 113 of the fleet-flaky-tests seat (epic livespec-dev-tooling-zwveqp), whose 2026-11-11 reopen condition was to apply aog22f's rendezvous here once it landed.

Shape. herdr-overseer (plan herdr-overseer, epic overseer-uzvcbn), which will cut the ratifying revise, required through the coordinator on 2026-11-13 that the proposal carry a behaviour clause plus one Given/When/Then scenario for each of three behaviours: rendezvous release after the shell pin, the hang guard, and a guard-ended transient failing loudly. This file was amended to that shape before its pull request was opened. The third behaviour is new relative to overseer-wbrvxm's Definition of Done. Today the rendezvous transient already exits with a message saying its hang guard ended it, but no rule requires the exercise to fail on that message, so overseer-wbrvxm's implementation owes that check.

Placement. The bullet goes in non-functional-requirements.md section "Scenarios" because that is the dispatcher's named generalization target, and because a rule about how this repository's tests gather evidence is a contributor-only concern under the Boundary litmus. The three scenarios in scenarios.md carry the same three behaviours in Given/When/Then form, per the rule that load-bearing behaviour has a clause and a scenario.

In-flight work, surveyed 2026-11-13. The pending proposal `livespec-overseer-tests-bound-waits` (non-functional-requirements.md, section "Constraints") governs a test's waits on progress the code under test is required to make. This proposal is compatible with it and restates none of it: the transient is a fixture child the test stages, its hang guard bounds that child's life rather than a verdict-bearing wait, and the rendezvous removes a wall-clock race from the gate's verdict in the same spirit. Open spec PRs livespec-overseer#2978 (revise v097, CAAM reset at the best-value moment) and livespec-overseer#2960 (enrolled-host delivery by ssh push) also touch scenarios.md, in unrelated sections; this proposal appends after the file's last scenario and aligns with both.

Heading coverage. When this proposal is ratified, the revise commit MUST add a `tests/heading-coverage.json` row for each of the three new scenario headings. Until overseer-wbrvxm lands its tests, each row is a `test: "TODO"` entry whose `reason` names the integration tier and overseer-wbrvxm, with `"work_item": "overseer-wbrvxm"`, registered in the generated debt register.

### Proposed Changes

1. In `SPECIFICATION/non-functional-requirements.md`, section "Scenarios", append the following bullet after the section's last bullet, which begins "Outside unblocking a session at a picker". No heading is added, removed or renamed in that file.

- **A staged startup transient is released by rendezvous, not by a timer.** A live herdr observation test's gate MAY stage a controlled startup transient: a real, distinctly named child process started in a created pane so that an observer can see the pane occupied and then see it clear. The rule has three parts.
  - *Rendezvous release after the shell pin.* The transient's lifetime MUST NOT be a fixed wall-clock duration. A control MAY stage a fixed-lifetime transient to show that the rendezvous is what holds the window open. The transient MUST stay alive until the test releases it by rendezvous. Where the observer sees the transient and pins its shell, by identity, the test MUST write the release only after that pin and before it waits for the transient to exit; on every other path, including when the observer never sees the transient or cannot pin its shell, it MUST still write the release once the observation has ended, so that an unreleased transient never waits out its hang guard.
  - *Hang guard.* The transient's hang guard MUST be no shorter than the gate's own establishment bound, which is the bound of the gate's wait to observe the transient (`ReadyShellGate.seconds`), the liveness floor within which the gate must establish the pane. The gate's verdict MUST depend on what the observer saw, never on how quickly the host answered the observer's first reading, provided that reading arrives within the gate's establishment bound. A slow first reading on a loaded host MUST therefore still observe the transient.
  - *A guard-ended transient fails loudly.* When the hang guard ends the transient instead of a release, the transient MUST report that its hang guard ended it, and the exercise MUST fail with a message naming the hang-guard expiry. Such an exercise MUST NOT pass, and it MUST NOT retry the observation quietly.

  The rule applies to this repository's tests.

2. In `SPECIFICATION/scenarios.md`, append the following three scenarios, in this order, after the file's last scenario, whose heading is "## Scenario: a hand commit's passing delegated pre-commit verdict stands in at the pre-push gate". Each follows the file's existing Given/When/Then style.

## Scenario: A live herdr test releases its staged startup transient only after the shell pin, and always releases it

Given a live herdr observation test whose gate stages a controlled startup transient in a created pane for an observer to see

And the test releases the transient by rendezvous rather than after a fixed lifetime

When the observer sees the transient occupying the pane

Then the transient stays alive until the test writes the release

And the test writes the release only after the observer has taken its pin, by identity, on the shell the transient runs under

And the test writes the release before it waits for the transient to exit

And the gate then observes the transient gone and that same shell idle, and establishes the pane

When the observer never sees the transient before its own bound expires

Then the test still writes the release

And the transient exits on that release, without waiting out its hang guard

And the gate refuses, naming the transient it never observed, and does not establish the pane

## Scenario: A live herdr test's staged startup transient outlives a slow first reading

Given a live herdr observation test whose gate stages a controlled startup transient in a created pane, released by rendezvous

And the transient's hang guard is no shorter than the gate's establishment bound, the liveness floor within which the gate must establish the pane

When the observer's first usable reading of the pane arrives later than a fixed-lifetime transient would have lived, and within the gate's establishment bound

Then the observer still sees the transient occupying the pane

And the gate establishes the pane exactly as it does when the first reading is prompt

## Scenario: A staged startup transient ended by its hang guard fails the exercise loudly

Given a live herdr observation test whose gate stages a controlled startup transient in a created pane, released by rendezvous under a hang guard

And the test has not written the release when the hang guard expires

When the hang guard, not a release, ends the transient

Then the transient reports that its hang guard ended it

And the exercise fails with a message naming the hang-guard expiry

And the exercise does not pass

And the exercise does not retry the observation quietly

3. When this proposal is ratified, the revise commit MUST add one `tests/heading-coverage.json` row for each of the three new headings in `scenarios.md`, and MUST regenerate the heading-coverage debt register for every row that is a `test: "TODO"` entry. The three headings are:

- "## Scenario: A live herdr test releases its staged startup transient only after the shell pin, and always releases it"
- "## Scenario: A live herdr test's staged startup transient outlives a slow first reading"
- "## Scenario: A staged startup transient ended by its hang guard fails the exercise loudly"

Until overseer-wbrvxm lands its integration-tier tests, each such row's `reason` MUST name the integration tier and overseer-wbrvxm, and the row MUST carry `"work_item": "overseer-wbrvxm"`.
