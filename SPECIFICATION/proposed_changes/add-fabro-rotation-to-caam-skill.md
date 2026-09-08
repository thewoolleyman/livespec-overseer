---
topic: add-fabro-rotation-to-caam-skill
author: claude-opus-5
created_at: 2026-09-08T08:05:12Z
---

## Proposal: The stable account identifier is resolved on every determining pass, not only on the fallback path

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Amend spec.md section 'Account rotation and quota supervision' clause **Identity** so the operation resolves the stable account identifier on every pass that determines an active account, whichever path determined it, rather than only when the account manager's report is unavailable. Today the identifier is a fallback mechanism; this makes it a property of the determined account, so that anything downstream of the decision can rely on it being present.

### Motivation

The **Identity** clause resolves the stable account identifier only as a fallback: when the account manager's own report names the active profile, no identifier is resolved at all. That is sound for the clause's original purpose — determining WHICH account is active — because either path answers that question. It stops being sound the moment anything downstream needs to name the account durably, because whether the identifier exists then depends on which path happened to answer, which is an implementation accident rather than a property of the account. The companion published-selection-record proposal is exactly such a downstream consumer, and the profile name alone is not rename-proof: renaming a profile silently redirects every consumer keyed on the name to a different account, which is the failure this identifier exists to prevent. Resolving it unconditionally costs one additional read per pass, from whichever of the live account file or the account's stored snapshot the pass has — the operation already reads both — and removes an entire class of silent misdirection. The one state where neither is available is a profile the account manager names but has never snapshotted, which the report obligation below covers rather than failing on. Reliability is the priority here: a cheaper contract that is correct only on one of two paths is not cheaper, it is conditionally wrong.

### Proposed Changes

Replace the **Identity.** clause in `SPECIFICATION/spec.md` section "Account rotation and quota supervision" with the following:

**Identity.** The operation MUST NOT depend solely on the account manager's own report of which profile is active. That report is derived by byte-matching the live credential against each snapshot and therefore becomes unavailable whenever the agent refreshes its own token as normal operation. The operation MUST fall back to matching a stable account identifier that survives token rotation, and MUST fail loudly when it cannot determine the active account by either path.

**A determined account's stable identifier MUST be resolved whichever path determined it.** On every pass that determines an active account, the operation MUST resolve that account's stable account identifier in addition to the account manager's profile name, reading it from whichever of the live account file or the account's stored snapshot the pass has available. A profile name alone MUST NOT be treated as a durable name for the account, since renaming a profile would silently redirect every consumer keyed on it. Resolving the identifier only where the account manager's report is unavailable would make its presence depend on which path happened to answer — an accident of implementation rather than a property of the account, and one that everything downstream of the decision would inherit.

**An unresolved identifier is a reported condition, not a failure path.** Where the operation determined the active account but could not resolve that account's stable identifier — a profile the account manager names but has never snapshotted, for instance — it MUST report the condition in the operator-facing report and MUST continue the pass. Its observation, reporting and rotation obligations are unaffected by the gap, and abandoning a valid rotation over an identifier that only downstream consumers require would cost more than the condition it signals. This condition MUST NOT on its own cause a non-zero exit and MUST NOT be treated as a failure path under **Fail loudly**; what it MUST do is suppress publication, per the publication clauses below.

Add the following scenario to `SPECIFICATION/scenarios.md` verbatim (fenced here so its heading is content to insert, not a section of this proposal):

```markdown
## Scenario: The stable account identifier is resolved even when the account manager names the profile

Given the account manager's own report names the active profile

And the operation therefore does not need its identity fallback

When a pass determines the active account

Then the operation also resolves that account's stable account identifier
```

This scenario heading requires its own entry in the out-of-target file `tests/heading-coverage.json`, which MUST be co-edited atomically with these files at revise time.

## Proposal: The selected account's identity is published for credential consumers outside the host agent

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add clauses to spec.md section 'Account rotation and quota supervision' requiring the operation to publish, as a named published selection record, the identity of the account it selected, so a credential consumer outside the host's interactive agent can follow the rotation. Publication is identity-only and never credential material; it occurs on every pass that fully determined an active account, so a hand-run activation converges within one cadence; a pass that could not take the decision lock does not publish; an identity the pass could not fully resolve suppresses publication rather than degrading it; publication never influences selection; and a publication failure fails the pass without undoing the switch or suppressing the report. Adds the corresponding scenarios.

### Motivation

The account-rotation operation already decides, every pass, which Claude account the host should be spending. That decision is currently consumed by exactly one party: the host's interactive agent, whose credential the operation installs. Any OTHER party that bills against the same accounts — one holding its own separately-provisioned, long-lived credential per account, which this operation neither stores nor refreshes — cannot follow the rotation, because nothing states which account was selected. Today that gap is closed by a human editing a credential store by hand whenever that party's account runs out. The operation is already the right sensor for this: it polls every account's quota and applies the protection floors and the weekly reserve. What it must not become is a credential store — the credential it installs is short-lived and agent-refreshed (sections 'Never refresh' and 'Refreshing MUST delegate to the agent, and MUST NOT touch the live credential'), so a consumer running a task for hours cannot safely be handed it, and the existing prohibition on out-of-band refresh must not be weakened by the back door. Publishing identity alone keeps the operation's credential guarantees exactly as they stand while making its decision actionable by someone else. This proposal depends on the companion Identity amendment in the same file: because the identifier is resolved on every determining pass, the record can require it unconditionally rather than carrying a rename-vulnerable profile name on whichever passes happened to take the primary path. Out-of-target co-edit at revise time: tests/heading-coverage.json requires one entry per new scenario heading, each with its own test and reason.

### Proposed Changes

Insert the following clauses into `SPECIFICATION/spec.md` section "Account rotation and quota supervision", after **Switching.** and before **Model enforcement.**:

**The selected account's identity MUST be published for credential consumers outside the host agent.** A CREDENTIAL CONSUMER is a party outside the host's interactive agent that bills against the same accounts under its own separately-provisioned credential — one this operation neither stores, installs, nor refreshes. Such a consumer cannot follow a rotation unless the operation states which account it selected, and MUST NOT be required to infer it. The operation MUST publish the identity of the selected account as a PUBLISHED SELECTION RECORD, whose shape and location are fixed by `contracts.md` §"The account-rotation operation".

**Publication MUST carry identity only.** The operation MUST NOT publish, copy, export, or otherwise expose credential material for the selected account or any other, and a credential consumer MUST NOT be expected to obtain a credential from this operation. Which credential a consumer presents for the published account is that consumer's own concern.

**Publication MUST occur on every pass that determined an active account, not only on a switch.** The record MUST name the account active at the end of the pass whether the pass switched, held, or found the active account changed beneath it — a hand-run activation takes no lock, so a record written only when this operation itself switches is permanently wrong after any activation it did not perform. Republishing an unchanged identity MUST have no effect beyond the write and MUST NOT be reported as a change. A pass that could not take the lock that serializes the decision-and-switch sequence MUST NOT publish, because the caller holding that lock is deciding the very fact the record states; publication is that caller's to make.

**An identity the pass could not fully resolve MUST suppress publication rather than degrade it.** Where the operation cannot determine the active account by either path named in **Identity**, or determined it but could not resolve its stable account identifier, it MUST leave any previously published record intact, MUST NOT overwrite it with a candidate, a remembered value, or a partially-resolved identity, and MUST report the condition. A consumer acting on a fabricated identity would spend an account the operation never chose, and one acting on a name-only record would follow a renamed profile to the wrong account; a stale but complete record is the safer failure, because its write time lets a consumer see that it is stale. A pass that fully resolved the active account's identity but could not read its quota MUST still publish, since the identity is known and the missing figures bear only on the report.

**Publication MUST NOT influence selection.** The published record is an output of the pass. The operation MUST NOT read it back as evidence of the active account, MUST NOT let it arm or suppress any rotation trigger, and MUST NOT let a consumer's presence, absence, or state affect eligibility, ranking, or the decision to hold.

**A publication failure MUST fail the pass without undoing it.** Failing to write the record is a failure path under **Fail loudly**: the operation MUST emit a clearly-marked failure line and MUST exit non-zero. It MUST NOT roll back a switch that already succeeded, MUST NOT suppress or alter the account table, and MUST NOT prevent the persistence of operation state — the rotation and the report are complete work, and discarding them to signal a failed publication would cost more than the failure it reports.

Add the following scenarios to `SPECIFICATION/scenarios.md` verbatim (fenced here so their headings are content to insert, not sections of this proposal):

```markdown
## Scenario: A pass that switches publishes the newly selected account's identity

Given the operation is tracking several accounts

And the active account has crossed its rotation threshold

And a candidate account is eligible and live-verified

When a scheduled pass runs and switches onto that candidate

Then the published selection record names the candidate account by profile name and stable account identifier

And the record carries the time at which it was written

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

## Scenario: An unresolvable stable identifier suppresses publication

Given the operation published account A on an earlier pass

And a pass determines that account B is active by profile name

And that pass cannot resolve account B's stable account identifier

When the pass runs

Then the published selection record still names account A

And the pass reports in its account table that the active account's identity could not be fully resolved

And the pass does not exit non-zero on account of that condition

## Scenario: A pass that could not take the decision lock does not publish

Given the operation published account A on an earlier pass

And another caller holds the decision lock and is switching onto account B

When a pass runs and cannot take the lock

Then that pass holds without publishing

And the published selection record is left for the lock-holding caller to write

## Scenario: An unreadable usage response does not suppress publication

Given a pass determined which account is active

And resolved that account's profile name and stable account identifier

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

Extend contracts.md section 'The account-rotation operation' with the wire contract for the published selection record introduced in the companion proposals: it lives beside the operation's existing durable store under the same owner-only permissions and atomic write discipline, is a separate artifact from the cache, names the account by BOTH the account-manager profile name and the stable account identifier, records the time it was written so a consumer can detect a stale publication, and imposes no requirement that any consumer exist.

### Motivation

The companion proposals state WHAT the operation publishes and when; a consumer in another process — and, in a multi-repo fleet, specified in another repository — needs the record's location, shape, and permissions to read it, and needs a way to tell a current publication from one left behind by an operation that stopped running. The existing **Durable store** clause admits only the operation's cache and lock, so the new artifact needs its own admission; putting it under the same owner-only, atomic discipline avoids a second, weaker convention for a file that steers spending. Both identity fields are required unconditionally, which the companion Identity amendment makes well-founded: the profile name is what an operator uses when declaring which of their pre-provisioned credentials belongs to which account, and the stable identifier is what makes that declaration rename-proof. A record carrying only one of them would push the choice between human-legibility and correctness onto every consumer. Deliberately excluded: how a consumer maps the published identity onto its own credential is realization mechanism belonging to that consumer's own specification, not to this repository's.

### Proposed Changes

Insert a new clause into `SPECIFICATION/contracts.md` section "The account-rotation operation", after **Durable store.** and before **Concurrency.**:

**Published selection record.** The record required by `spec.md` §"Account rotation and quota supervision" MUST live in the same host state directory as the operation's durable store, MUST be created with owner-only permissions, and MUST be written atomically, so that a consumer reading it concurrently observes either the previous publication or the new one and never a partial file. It MUST be a separate artifact from the operation's cache: a consumer MUST NOT be required to parse operation state to learn the selection, and a change to the cache's internal shape MUST NOT break a consumer.

The record MUST name the selected account by BOTH the account manager's profile name AND the stable account identifier defined in `spec.md` §"Account rotation and quota supervision" under **Identity**, which that section requires the operation to resolve on every pass that determines an active account. Neither field MAY be omitted: the profile name is what an operator declares their own credential provisioning against, and the identifier is what keeps that declaration correct across a profile rename. A pass that cannot supply both MUST NOT publish, per that section's suppression rule. The record MUST carry the time at which it was written, so that a consumer MAY treat a record older than its own tolerance as stale; the operation MUST NOT itself define that tolerance, and MUST NOT expire or delete the record on its own, since a stale identity remains the best available evidence of which account to spend. The record MUST NOT contain credential material of any kind.

The operation MUST NOT require that any consumer exist: an unread record MUST be normal and MUST NOT be reported as a fault, and the operation MUST NOT wait on, poll for, or discover consumers.
