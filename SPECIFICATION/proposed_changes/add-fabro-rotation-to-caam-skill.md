---
topic: add-fabro-rotation-to-caam-skill
author: claude-opus-5
created_at: 2026-09-08T07:26:07Z
---

## Proposal: The selected account's identity is published for credential consumers outside the host agent

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add clauses to spec.md section 'Account rotation and quota supervision' requiring the operation to publish, as a named published selection record, the identity of the account it selected, so a credential consumer outside the host's interactive agent can follow the rotation. Publication is identity-only and never credential material; it occurs on every pass that determined an active account, so a hand-run activation converges within one cadence; a pass that could not take the decision lock does not publish; an undetermined identity suppresses publication rather than guessing it; publication never influences selection; and a publication failure fails the pass without undoing the switch or suppressing the report. Adds the corresponding scenarios to scenarios.md.

### Motivation

The account-rotation operation already decides, every pass, which Claude account the host should be spending. That decision is currently consumed by exactly one party: the host's interactive agent, whose credential the operation installs. Any OTHER party that bills against the same accounts — one holding its own separately-provisioned, long-lived credential per account, which this operation neither stores nor refreshes — cannot follow the rotation, because nothing states which account was selected. Today that gap is closed by a human editing a credential store by hand whenever that party's account runs out. The operation should publish the identity of the account it selected — identity only, never credential material — so such a party can select its own pre-provisioned credential for the same account without a human in the loop. The operation is already the right sensor for this: it polls every account's quota, it applies the protection floors and the weekly reserve, and it resolves an account identity that survives token rotation (section 'Identity'). What it must not become is a credential store — the credential it installs is short-lived and agent-refreshed (sections 'Never refresh' and 'Refreshing MUST delegate to the agent, and MUST NOT touch the live credential'), so a consumer running a task for hours cannot safely be handed it, and the existing prohibition on out-of-band refresh must not be weakened by the back door. Publishing identity alone keeps the operation's credential guarantees exactly as they stand while making its decision actionable by someone else. The record's on-disk shape, location and permissions are a wire contract and are proposed separately against contracts.md. Two out-of-target co-edits fall to revise time: tests/heading-coverage.json requires one entry per new scenario heading, and each entry needs its own test and reason.

### Proposed Changes

Insert the following clauses into `SPECIFICATION/spec.md` section "Account rotation and quota supervision", after **Switching.** and before **Model enforcement.**:

**The selected account's identity MUST be published for credential consumers outside the host agent.** A CREDENTIAL CONSUMER is a party outside the host's interactive agent that bills against the same accounts under its own separately-provisioned credential — one this operation neither stores, installs, nor refreshes. Such a consumer cannot follow a rotation unless the operation states which account it selected, and MUST NOT be required to infer it. The operation MUST publish the identity of the selected account as a PUBLISHED SELECTION RECORD, whose shape and location are fixed by `contracts.md` §"The account-rotation operation".

**Publication MUST carry identity only.** The operation MUST NOT publish, copy, export, or otherwise expose credential material for the selected account or any other, and a credential consumer MUST NOT be expected to obtain a credential from this operation. Which credential a consumer presents for the published account is that consumer's own concern.

**Publication MUST occur on every pass that determined an active account, not only on a switch.** The record MUST name the account active at the end of the pass whether the pass switched, held, or found the active account changed beneath it — a hand-run activation takes no lock, so a record written only when this operation itself switches is permanently wrong after any activation it did not perform. Republishing an unchanged identity MUST have no effect beyond the write and MUST NOT be reported as a change. A pass that could not take the lock that serializes the decision-and-switch sequence MUST NOT publish, because the caller holding that lock is deciding the very fact the record states; publication is that caller's to make.

**An undetermined identity MUST suppress publication rather than guess it.** Where the operation cannot determine the active account by either path named in **Identity**, it MUST leave any previously published record intact, MUST NOT overwrite it with a candidate, a remembered value, or a partial reading, and MUST report the condition; a consumer acting on a fabricated identity would spend an account the operation never chose. A pass that determined the active account but could not read its quota MUST still publish, since the identity is known and the missing figures bear only on the report.

**Publication MUST NOT influence selection.** The published record is an output of the pass. The operation MUST NOT read it back as evidence of the active account, MUST NOT let it arm or suppress any rotation trigger, and MUST NOT let a consumer's presence, absence, or state affect eligibility, ranking, or the decision to hold.

**A publication failure MUST fail the pass without undoing it.** Failing to write the record is a failure path under **Fail loudly**: the operation MUST emit a clearly-marked failure line and MUST exit non-zero. It MUST NOT roll back a switch that already succeeded, MUST NOT suppress or alter the account table, and MUST NOT prevent the persistence of operation state — the rotation and the report are complete work, and discarding them to signal a failed publication would cost more than the failure it reports.

Add the following scenarios to `SPECIFICATION/scenarios.md` verbatim (fenced here so their headings are content to insert, not sections of this proposal):

```markdown
## Scenario: A pass that switches publishes the newly selected account's identity

Given the operation is tracking several accounts

And the active account has crossed its rotation threshold

And a candidate account is eligible and live-verified

When a scheduled pass runs and switches onto that candidate

Then the published selection record names the candidate account

And the record carries no credential material for any account

## Scenario: A pass that holds republishes the unchanged active identity

Given the operation published account A on an earlier pass

And an operator has since activated account B by hand, outside the operation

When the next pass runs, finds account B active, and holds

Then the published selection record names account B

And the pass does not report the republication as a rotation

## Scenario: An undetermined active account leaves the published record intact

Given the operation published account A on an earlier pass

And neither the account manager's report nor the stable-identifier fallback can determine the active account

When a pass runs

Then the published selection record still names account A

And the pass reports that the active account could not be determined

## Scenario: A pass that could not take the decision lock does not publish

Given the operation published account A on an earlier pass

And another caller holds the decision lock and is switching onto account B

When a pass runs and cannot take the lock

Then that pass holds without publishing

And the published selection record is left for the lock-holding caller to write

## Scenario: A record omits the stable identifier the pass did not resolve

Given a pass determined the active account from the account manager's own report

And that path resolved no stable account identifier

When the pass publishes

Then the published selection record names the account manager's profile name

And the record states that no stable account identifier is carried

## Scenario: An unreadable usage response does not suppress publication

Given a pass determined which account is active

And that account's usage response cannot be read

When the pass runs

Then the published selection record names the determined account

## Scenario: A failed publication fails the pass without undoing it

Given a pass has switched onto an eligible candidate

And the published selection record cannot be written

When the pass runs

Then the switch stands and the account table is reported

And the pass emits a clearly-marked failure line

And the pass exits non-zero
```

Each new scenario heading requires its own entry in the out-of-target file `tests/heading-coverage.json`, which MUST be co-edited atomically with these files at revise time.

## Proposal: Published-selection record: location, shape, and staleness

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Extend contracts.md section 'The account-rotation operation' with the wire contract for the published selection record introduced in the companion proposal: it lives beside the operation's existing durable store under the same owner-only permissions and atomic write discipline, is a separate artifact from the cache, always names the account-manager profile name and carries the stable account identifier where the pass resolved one while stating which identity fields it carries, records the time it was written so a consumer can detect a stale publication, and imposes no requirement that any consumer exist.

### Motivation

The companion proposal states WHAT the operation publishes and when; a consumer in another process — and, in a multi-repo fleet, specified in another repository — needs the record's location, shape, and permissions to read it, and needs a way to tell a current publication from one left behind by an operation that stopped running. The existing **Durable store** clause admits only the operation's cache and lock, so the new artifact needs its own admission; putting it under the same owner-only, atomic discipline avoids a second, weaker convention for a file that steers spending. The identity fields are asymmetric on purpose: the profile name is resolved on every path and is what an operator uses when declaring which of their pre-provisioned credentials belongs to which account, whereas `spec.md` §"Account rotation and quota supervision" under **Identity** obliges the operation to resolve a stable identifier only on the fallback path — so requiring it unconditionally would oblige a pass to carry a field it was never required to have. Deliberately excluded: how a consumer maps the published identity onto its own credential is realization mechanism belonging to that consumer's own specification, not to this repository's.

### Proposed Changes

Insert a new clause into `SPECIFICATION/contracts.md` section "The account-rotation operation", after **Durable store.** and before **Concurrency.**:

**Published selection record.** The record required by `spec.md` §"Account rotation and quota supervision" MUST live in the same host state directory as the operation's durable store, MUST be created with owner-only permissions, and MUST be written atomically, so that a consumer reading it concurrently observes either the previous publication or the new one and never a partial file. It MUST be a separate artifact from the operation's cache: a consumer MUST NOT be required to parse operation state to learn the selection, and a change to the cache's internal shape MUST NOT break a consumer.

The record MUST name the selected account by the account manager's profile name, and MUST additionally carry the stable account identifier defined in `spec.md` §"Account rotation and quota supervision" under **Identity** whenever the pass resolved one, so that a consumer whose own provisioning is keyed on either can resolve it. Because that clause obliges the operation to resolve the stable identifier only where the account manager's own report is unavailable, the identifier MAY be absent; the record MUST state which identity fields it carries rather than leaving a consumer to distinguish an absent field from an unresolved one. It MUST carry the time at which it was written, so that a consumer MAY treat a record older than its own tolerance as stale; the operation MUST NOT itself define that tolerance, and MUST NOT expire or delete the record on its own, since a stale identity remains the best available evidence of which account to spend. The record MUST NOT contain credential material of any kind.

The operation MUST NOT require that any consumer exist: an unread record MUST be normal and MUST NOT be reported as a fault, and the operation MUST NOT wait on, poll for, or discover consumers.
