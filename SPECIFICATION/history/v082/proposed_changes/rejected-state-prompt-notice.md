---
topic: rejected-state-prompt-notice
author: claude-opus-5-5
created_at: 2026-11-02T07:11:30Z
---

## Proposal: Tell a session its state value was rejected within one cycle

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Add a REJECTED-VALUE NOTICE rule to contracts.md §"The state file". When the daemon moves a malformed state file aside to `.overseer-state.rejected`, it MUST deliver one notice to that session. The notice goes out on that tick or on the first later tick where the notice's paste predicate holds. It names the rejected value and the four session-writable values. Today the session hears only at its next wrap-up.

### Motivation

Measured 2026-11-02. stall-watchdog-false-kills (livespec-orchestrator-beads-fabro, epic bd-ib-laf735) wrote `waiting: time-gated until 2026-10-25T04:48:24Z ...` on 2026-10-18. The daemon logged `malformed-state` and moved the file aside, as the contract requires, but never told the session. Under the current contract the rejected value reaches the session only through the next wrap-up, and a session with ample context may not reach one for days. That seat sat with no valid declaration for about two weeks until the overseer bottom pane told it by hand. Filed at the maintainer's direction as overseer-uzvcbn.11; the code half is overseer-uzvcbn.12.

### Proposed Changes

In SPECIFICATION/contracts.md §"The state file", directly after the MALFORMED-VALUE REJECTION bullet, insert:

- REJECTED-VALUE NOTICE. After the daemon renames a malformed state file to `.overseer-state.rejected`, it MUST deliver ONE notice to that track's session. The notice MUST be delivered on the tick of the rename, or else on the first later tick at which the notice's paste predicate (spec.md §"The keep-going nudge") holds. Its text MUST name the rejected value, rendered exactly as the wrap-up's rejected-value line renders it: the first non-empty line of the rejected copy, with control characters removed and truncated to at most 120 characters. It MUST also name the four session-writable values, each as its `overseer-declare` invocation, under the declaration-instruction rules that govern every daemon-authored instruction. It MUST state that the value was not accepted and that the session holds no declaration.
  - Delivery MUST use the same busy-safe guarded paste as the keep-going nudge, so it is never typed into a generating, changing, sub-agent-busy, gated or human-waiting pane. A notice whose predicate does not hold is deferred, not dropped, and retried at the next tick where it holds. A FAILED or UNCONFIRMED delivery MUST be retried the same way.
  - The notice is edge-triggered per spec.md §"Notify, never block". Its dedup identity is the track together with a digest of the rejected value. The daemon MUST record each delivered notice durably in its own store, so a daemon restart MUST NOT re-send a notice already delivered for the same value. A different rejected value is a new condition and earns a new notice.
  - While the rejected copy for one value has stood for 24 hours since its notice was delivered, and no valid declaration has been written in that time, the daemon MUST deliver that notice ONE more time, under the same predicate. After that it MUST NOT re-notice that value. The track MUST stay surfaced to the operator through the malformed-value attention membership for as long as the rejected copy stands.
  - A pending notice MUST be cancelled when, before delivery, the session writes a valid declaration or the rejected copy is deleted. The daemon MUST re-check both in the act's immediate pre-delivery re-read.
  - The notice authorizes no act and changes nothing else. The rejected copy still authorizes nothing, still does not suppress the low-context wrap-up, and every wrap-up still carries the rejected-value line while the copy stands.
  - A track that is done because its plan is archived, and a path-aliased state file, receive no notice, exactly as they receive no rename.

## Proposal: Scenarios for the rejected-state notice

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Add two scenarios after §"Scenario: A malformed state value is moved aside and named in the next wrap-up": one for prompt delivery, including the busy case and the cancellation by a valid rewrite, and one for edge-triggering across cycles, daemon restart, new values and the single re-notice. The existing scenario stays unchanged, so its heading-coverage row stays valid. Add the notice to the declaration-instruction scenario.

### Motivation

The behaviour in the contracts.md rule MUST be carried by Given/When/Then scenarios as well as the clause. The existing scenario heading is kept verbatim because tests/heading-coverage.json binds it to tests.integration.test_malformed_state_rejection.

### Proposed Changes

In SPECIFICATION/scenarios.md, directly after §"Scenario: A malformed state value is moved aside and named in the next wrap-up", add:

## Scenario: A rejected state value is told to its session within one cycle

Given a tracked session whose state file the daemon has just moved aside to .overseer-state.rejected

When the session is idle, settled, ungated and not waiting on a human on that tick

Then the daemon delivers one notice to that session on that tick, through the keep-going nudge's guarded paste

And the notice names the rejected value and the four session-writable values as overseer-declare invocations

And a busy session MUST instead receive the notice on the first later tick at which it is idle and settled, never typed into its running turn

But a session that writes a valid declaration, or deletes the rejected copy, before the notice is delivered receives no notice

## Scenario: A rejected-state notice is sent once per rejected value

Given a tracked session that has received the notice for a rejected value

When later ticks observe the same rejected copy, including ticks after a daemon restart

Then no further notice is delivered for that value until 24 hours after the first notice

And once 24 hours have passed with the rejected copy still standing and no valid declaration written, exactly one more notice is delivered and none after it

And the track remains surfaced to the operator while the rejected copy stands

But a different rejected value is noticed afresh

In §"Scenario: Every declaration instruction names the declaration command", change the When line to:

When the daemon composes a wrap-up, a keep-going nudge, a pair-stall nudge, a ready-expiry notice, a rejected-state notice, or a rejected-value line for it

Each of these scenarios MUST be reached by a test, or carried by a heading-coverage row naming its owning work item.

## Proposal: Count the rejected-state notice among the guarded informational pastes

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/constraints.md

### Summary

spec.md §"The keep-going nudge" and constraints.md §"Acting safety" enumerate exactly five acts that may paste under the informational-paste floor, and require the two to be amended together. Add the rejected-state notice as a sixth member that keeps all three busy legs, and say that it, like the nudge, MAY use a supported direct message channel.

### Motivation

Both sections state a closed membership and count, and spec.md requires them to be amended together. A new keystroke-bearing act that is not enumerated would be refused by the floor's own text, or would widen it silently. The notice must be busy-safe, so it belongs with the keep-going nudge, keeping the generating, changing and sub-agent-busy legs that only the low-context wrap-up and its tail drop.

### Proposed Changes

In SPECIFICATION/spec.md §"The keep-going nudge":
- Change "The keep-going nudge, the pair-stall nudge, and the charter reminder keep all three legs." to "The keep-going nudge, the rejected-state notice, the pair-stall nudge, and the charter reminder keep all three legs."
- Change "Exactly five acts apply that rule:" to "Exactly six acts apply that rule:", and add to the list, after the idle-with-context-left keep-going nudge, "the once-per-rejected-value rejected-state notice of contracts.md §\"The state file\"".
- After the paragraph "The nudge MAY instead be delivered through a supported direct channel ...", add: "The rejected-state notice of contracts.md §\"The state file\" MUST be delivered under the informational-paste safety floor below, with all three busy legs. It does NOT wait for this nudge's one-hour continuous-idle floor or its above-threshold condition: a settled idle input on any tick suffices. It MAY likewise be delivered through a supported direct channel."

In SPECIFICATION/constraints.md §"Acting safety":
- Change "It may coexist with exactly five acts under their independent complete predicates:" to "It may coexist with exactly six acts under their independent complete predicates:", and add "the rejected-state notice of contracts.md §\"The state file\"" to the enumeration after the keep-going nudge.
- Change "it MUST NOT widen any of the five informational acts above" to "it MUST NOT widen any of the six informational acts above".

The two enumerations MUST stay the same membership and count.

## Proposal: The rejected-state notice is a daemon message

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Name the rejected-state notice in contracts.md §"Daemon message delivery channel" as a DAEMON MESSAGE, bound by the pane's currently proven session identity, exactly as the keep-going nudge is.

### Motivation

The channel section enumerates which acts are daemon messages and how each binds its addressed identity. A new informational message to a worker that is left out would be ambiguous between the paste-only acts and the channel-eligible ones. The notice has no round, so its binding is the keep-going nudge's: the pane's currently proven session identity.

### Proposed Changes

In SPECIFICATION/contracts.md §"Daemon message delivery channel":
- Change "The wrap-up and the keep-going nudge to a supervised worker are DAEMON MESSAGES under this section." to "The wrap-up, the keep-going nudge and the rejected-state notice to a supervised worker are DAEMON MESSAGES under this section."
- In the Binding bullet, change "and the pane's currently proven session identity for a keep-going nudge" to "and the pane's currently proven session identity for a keep-going nudge or a rejected-state notice".

Every other obligation of that section MUST apply to the notice unchanged.
