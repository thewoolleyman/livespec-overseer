---
topic: enrolled-host-reissue-trigger-and-least-privilege-scenarios
author: claude-opus-5-5
created_at: 2026-11-13T12:41:15Z
---

## Proposal: One trigger and one reach for the role holder's Remote Control re-issue

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md

### Summary

Make spec.md and contracts.md state the same trigger and the same reach for the Remote Control re-issue on the role holder's own sessions: once per change of the account the role holder's live credential holds, seen in the live credential or in an issued delivery, whether or not that change produces a delivery, reaching the sessions contracts.md defines (tmux panes).

### Motivation

Owed follow-up (a) of plan central-credential-service (epic overseer-iyfjbo), recorded by the coordinator at the grading of #2960 and carried by v099. spec.md §"Enrolled-host credential delivery" fires the role-holder re-issue "after the rotation operation switches the live credential to a different account" and reaches "every agent session"; contracts.md §"Enrolled-host delivery" fires it "after it issues a delivery naming a different account from the previous delivery" and reaches tmux panes. The two triggers differ in a real case: a switch whose account confirmation fails issues no delivery, so a delivery-only trigger misses it. The coordinator's grade of #2990 ruled that the re-issue fires on whichever is seen first, once, and #2992 (overseer-fdwat6) implements that. The existing scenario "An account switch re-issues Remote Control on the role holder's own sessions" already states spec.md's trigger, so contracts.md is the text to correct.

### Proposed Changes

In contracts.md §"Enrolled-host delivery", paragraph **Remote Control re-issue.**, replace the sentence "After it issues a delivery naming a different account from the previous delivery, the service MUST apply the same re-issue, locally, to the role holder's own tmux panes." with:

"When the account that the role holder's live credential holds changes to a different account, the service MUST apply the same re-issue, locally, to the role holder's own tmux panes, once for that change. It MUST do so whether it first observes the change in the live credential or in a delivery it issues, and whether or not the change produces a delivery. The first account the service observes after it starts MUST only be recorded, never treated as a change, because the account that preceded it is unknown."

The sentence that follows it ("A session that does not run in tmux is outside what the service can reach, which is accepted and unfixed.") is unchanged.

In spec.md §"Enrolled-host credential delivery", paragraph **Remote Control follows an account switch.**:
- replace "the service MUST re-issue Remote Control on that host in every agent session whose" with "the service MUST re-issue Remote Control on that host in every agent session it can reach, as contracts.md §\"Enrolled-host delivery\" defines, whose";
- replace "The service MUST apply the same re-issue to the role holder's own agent sessions after the rotation operation switches the live credential to a different account." with "The service MUST apply the same re-issue, once, to the role holder's own agent sessions that it can reach after the account the role holder's live credential holds changes to a different account, whether or not that change produces a delivery."

No scenario changes: "An account switch re-issues Remote Control on the role holder's own sessions" already states this trigger and this reach.

## Proposal: Scenarios for the enrolled-host least-privilege clause

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Add two scenarios for spec.md §"Enrolled-host credential delivery" **Least privilege.**, which today has none: the host list and the service stores hold no credential material, and the service does not push with a role key that a user other than its operating user can read.

### Motivation

Owed follow-up (b) of plan central-credential-service (epic overseer-iyfjbo), recorded by the coordinator at the grading of #2960: the least-privilege and role-key owner-only MUSTs in spec.md §"Enrolled-host credential delivery" have no scenario, so nothing a test must exercise states them. The service runs ssh with the role key (`-i`, `IdentitiesOnly=yes`), and the host list is parsed as label, ssh destination and platform per line.

### Proposed Changes

In scenarios.md, insert the following two scenarios immediately before "## Scenario: A silent enrolled host is reported as stale". Each MUST receive a `tests/heading-coverage.json` row in the same revision, marked TODO with an integration-tier reason and owned by work item overseer-aj577z (push over ssh), until a test lands.

## Scenario: The host list and the service stores hold no credential material

Given a role holder whose host list names a listed host

When the service issues a delivery and pushes it to that host

Then neither the host list, the delivery-sequence counter nor the push state contains the delivered access token or any refresh token

And a host-list line that carries any field beyond a label, an ssh destination and a platform is rejected and reported, and the service does not push to it

## Scenario: The service does not push with a role key other users can read

Given a role holder whose role key is readable by a user other than the role holder's operating user

When the service pushes a delivery

Then no listed host applies the delivery

And each listed host's last push error records the failure and contains no credential material

The scenarios MUST NOT change the clause they exercise.
