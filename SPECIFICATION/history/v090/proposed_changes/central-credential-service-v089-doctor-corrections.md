---
topic: central-credential-service-v089-doctor-corrections
author: claude-opus-5-5-central-credential-service
created_at: 2026-11-08T21:13:40Z
---

## Proposal: A silent host stops arming triggers whatever its token's expiry

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

**Remote sessions are tracked sessions** excluded a host only while its displayed STATE was `stale`, `revoked` or `not-converted`. But STATE shows `expired` before `stale`, so a silent host's last-reported sessions became tracked again once its last-applied token expired. This judges the three conditions directly. A forwarded refusal is judged by the report that carried it, so a host that falls silent after forwarding one does not void it.

### Motivation

Found by the independent post-step LLM doctor run on v089 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that v089 merges as is and that all of that run's findings land together in one follow-up revised as v090 (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet, and overseer-3vnxkd is held from dispatch until this lands. Two independent post-step review rounds on this proposal's earlier drafts found 4 defects and 8 advisories, then 1 defect and 5 advisories; all are resolved in this text. This was the v089 run's one BLOCKING contradiction. Its example: a host powered off while a scoped-model session was running would keep arming the scoped-model trigger indefinitely once its token expired.

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", in **Remote sessions are tracked sessions.**, replace:

"but only while its host's STATE, as contracts.md §"Enrolled-host delivery" defines it, is none of `stale`, `revoked` or `not-converted`. A host that stops reporting therefore stops arming any trigger."

with:

but only while all of these hold: its host's enrolment is not revoked; its host's last report says that host's credential file holds no refresh token; and that report arrived within `delivery.stale_after`. The operation MUST judge these conditions directly, and MUST NOT judge them from the STATE that contracts.md §"Enrolled-host delivery" **Status view** displays, because that view shows `expired` before `stale`. A host that stops reporting therefore stops arming any trigger through its sessions' observed models once `delivery.stale_after` has passed, whatever the expiry of its last-applied access token. A forwarded refusal is the exception: its eligibility MUST be judged by the conditions as they stood when the report that carried it arrived, so a host that falls silent after forwarding a refusal does not void that refusal.

In SPECIFICATION/scenarios.md, immediately after the scenario "## Scenario: A remote session on the scoped model arms the scoped-model trigger", add:

## Scenario: A silent host whose token has expired arms no trigger

Given a following host whose last report listed a running session observed on the scoped model

And the host has not reported within `delivery.stale_after` and its last-applied delivery's access token has expired

And no other tracked session and no per-session pin names the scoped model

And the active account is at or below the scoped-model reserve

When the operation runs a scheduled pass

Then the status view shows the host as `expired`

And the scoped-model trigger does not fire

## Scenario: A refusal forwarded before a host falls silent is still attributed

Given a following host has applied a delivery naming the active account

And its client reported a usage-limit refusal from a session in that host's default directory, recorded after the active account became active

And the host has since not reported within `delivery.stale_after`

When the operation runs a scheduled pass

Then the operation attributes the refusal to the active account

## Proposal: A forwarded refusal carries its recording session, configuration directory and provider

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

spec.md requires a forwarded refusal's report to state that the recording session ran in the host's default configuration directory, and the same-provider conjunct needs that session's provider. The v089 **Host report** refusal entry carried neither. It also carried parsed fields, while spec.md says the operation on the role holder parses a forwarded refusal. This makes the report carry the record unaltered, with those facts. The existing attribution conjuncts then apply to them unchanged.

### Motivation

Found by the independent post-step LLM doctor run on v089 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that v089 merges as is and that all of that run's findings land together in one follow-up revised as v090 (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet, and overseer-3vnxkd is held from dispatch until this lands. Two independent post-step review rounds on this proposal's earlier drafts found 4 defects and 8 advisories, then 1 defect and 5 advisories; all are resolved in this text. This was a v089 defect: attribution of a forwarded refusal could not be established from what the report carried.

### Proposed Changes

In SPECIFICATION/contracts.md §"Enrolled-host delivery", in **Host report**, replace the bullet:

"- each refusal record that the host's sessions recorded since the previous report, with the time it was recorded, the window it names, its reported reset time if any, and the delivery sequence and stable account identifier that the host had applied at that time;"

with:

- each refusal record that the host's sessions recorded since the previous report, unaltered, with the identifier of the session that recorded it, whether that session's agent configuration directory is the host's default directory, the provider that session authenticates with, and the delivery sequence and stable account identifier that the host had applied when the refusal was recorded;

In the same section, immediately before the paragraph beginning "A report MUST NOT carry credential material.", add:

The client MUST forward each refusal record unaltered. It MUST read from a record only what it needs to recognise the record as a refusal and to know when it was recorded. It MUST NOT summarize a record or derive its window or reset time: the operation on the role holder parses it, as spec.md **Forwarded refusals** requires. A report that omits the recording session's directory or provider leaves the refusal unattributed, because the attribution conjuncts of spec.md §"Account rotation and quota supervision" then cannot be established.

In SPECIFICATION/scenarios.md, immediately after the scenario "## Scenario: A forwarded refusal under another account's delivery is not attributed", add:

## Scenario: A forwarded refusal from outside the host's default directory is not attributed

Given a following host has applied a delivery naming the active account

When the client forwards a usage-limit refusal that a session recorded under a separately provisioned configuration directory, and the report states that directory is not the host's default directory

Then the operation does not attribute the refusal to the active account

## Proposal: Reported outcomes are retained, and each enforcement instruction is its own record

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

### Summary

The v089 report store kept only each host's latest report besides forwarded refusals, so enforcement outcomes and authentication-failure times were overwritten before a rotation pass or the status view read them. No clause said where a pass hands an instruction to the service, who mints its identifier, how concurrent passes avoid losing one, how long an unanswered instruction lives, or how the client keeps at-most-once across a restart. This retains reported outcomes. Each instruction becomes its own record with a collision-free identifier, written only by the pass. An unanswered instruction is superseded by the next decision for its session. The client records an identifier before acting on it.

### Motivation

Found by the independent post-step LLM doctor run on v089 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that v089 merges as is and that all of that run's findings land together in one follow-up revised as v090 (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet, and overseer-3vnxkd is held from dispatch until this lands. Two independent post-step review rounds on this proposal's earlier drafts found 4 defects and 8 advisories, then 1 defect and 5 advisories; all are resolved in this text. These were two v089 defects, report-store retention and the undefined instruction handoff. They are made concurrency-safe, as the review of this proposal's first draft required.

### Proposed Changes

In SPECIFICATION/contracts.md §"Enrolled-host delivery", in **Service stores.**, replace the bullet:

"- the REPORT STORE, holding each host's latest report and every forwarded refusal record. A rotation pass MUST read the report store without consuming or deleting anything, as **Concurrency** requires of observation. The service MUST keep each forwarded refusal record for at least seven days, the longest window a refusal can name."

with:

- the REPORT STORE, holding each host's latest report together with every forwarded refusal record, every enforcement-instruction outcome and every authentication-failure time that any report carried. A rotation pass MUST read the report store without consuming or deleting anything, as **Concurrency** requires of observation. The service MUST keep each of those records for at least seven days, the longest window a refusal can name, so that a pass on the normal schedule reads each before it is discarded. Enforcement-instruction outcomes are recorded only here.

In the same section, immediately after the sentence "The status view takes account limits from the operation's own cache.", add:

**Enforcement instructions.** A rotation pass MUST write each enforcement instruction it decides for a remote session as a record of its own, in the operation's host state directory and separate from the cache, atomically and with owner-only permissions, as a reset claim's record is written. The pass MUST mint each instruction identifier from at least 128 random bits, and MUST record in the instruction the time it was decided. Only a rotation pass writes these records; the service MUST only read them. An instruction's outcome is exactly one of `applied`, `skipped-busy`, `failed` or `unknown`.
- The service MUST serve, for each remote session, only the newest instruction a pass has written for it, ordered by decision time with ties broken by identifier. A newer instruction for the same session supersedes an older one.
- The service MUST NOT serve an instruction decided before the host's latest return from silence, that is, before the first report the host sent after a gap longer than `delivery.stale_after`.
- The service MUST stop serving an instruction once the report store holds its outcome or a newer instruction supersedes it.
- A rotation pass MAY delete an instruction record once the report store holds its outcome or it is superseded.

Accepted and unfixed: rotation passes do not hold the decision lock while deciding enforcement, so two concurrent passes MAY each write an instruction for one session, and a client MAY act on both.

In the same section, replace:

"The service MUST stop serving an instruction once its outcome has been reported. It serves a new instruction only when a later rotation pass decides one."

with:

The service MUST stop serving an instruction as **Enforcement instructions** defines.

In the same section, in **Client schedule and single instance.**, immediately after the bullet "- The client MUST hold an exclusive lock from its sequence check until its writes and verification are complete.", add:

- Before it acts on an enforcement instruction, the client MUST record the instruction's identifier in owner-only storage that survives a restart, and it MUST NOT act on an identifier it has recorded. On starting, the client MUST report each recorded identifier whose outcome it has not reported with the outcome `unknown`. The client MAY discard a recorded identifier once the service no longer serves it.

In SPECIFICATION/constraints.md §"Atomicity and single instance", replace:

"- the enrolled-host client's writes of an enrolled host's interactive credential file and global state file;"

with:

- the enrolled-host client's writes of an enrolled host's interactive credential file and global state file, and of its record of acted enforcement-instruction identifiers;

and replace:

"- the delivery service's writes of its enrolment registry, delivery-sequence counter and report store on the role holder."

with:

- on the role holder, the delivery service's writes of its delivery-sequence counter and report store, the issuance and revocation commands' writes of the enrolment registry, which the registry lock serializes, and each rotation pass's writes of its own enforcement-instruction records.

In SPECIFICATION/scenarios.md, immediately after the scenario "## Scenario: An enforcement instruction is applied at most once", add:

## Scenario: A client restarted after recording an instruction does not act on it again

Given the client recorded an enforcement instruction's identifier and stopped before reporting its outcome

When the client restarts and the service serves that instruction again

Then the client does not act on it

And the client reports that instruction's outcome as `unknown`

## Proposal: Enrolment issuance, re-issuance after revocation, and a stopped delivery service

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

v089 defined the enrolment registry, revocation and an "enrolment issued" audit event, but not how an enrolment is issued. Its registry kept revoked entries while requiring labels and network identities to be unique across the whole registry, which would forbid ever re-enrolling a revoked device. Its rule that a failure of the delivery service MUST NOT fail a rotation pass also had no scenario. This adds an **Issuance** clause, scopes uniqueness to unrevoked entries, and adds three scenarios.

### Motivation

Found by the independent post-step LLM doctor run on v089 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that v089 merges as is and that all of that run's findings land together in one follow-up revised as v090 (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet, and overseer-3vnxkd is held from dispatch until this lands. Two independent post-step review rounds on this proposal's earlier drafts found 4 defects and 8 advisories, then 1 defect and 5 advisories; all are resolved in this text. These were two v089 advisories, unspecified issuance and the untested failure-isolation clause. The re-issuance gap and the scenario's precondition come from the review of this proposal's first draft.

### Proposed Changes

In SPECIFICATION/contracts.md §"Enrolled-host delivery", replace:

"Labels and network identities MUST each be unique across the registry."

with:

Labels and network identities MUST each be unique among the registry's unrevoked entries. A label that a revoked entry holds MAY be reused only for that entry's network identity, so a label never names two devices.

In the same section, replace "**Revocation.** Revoking a host's enrolment MUST be an operator command run on the role holder." with:

**Revocation.** Revoking a host's enrolment MUST be an operator command run on the role holder, which writes the registry under the registry lock defined in **Issuance**.

In the same section, immediately before the paragraph beginning "**Revocation.**", add:

**Issuance.** Issuing an enrolment MUST be an operator command run on the role holder that names the host's label and its network identity. Under the REGISTRY LOCK, which **Revocation** also holds for its write, the command MUST refuse a label or a network identity that an unrevoked entry already holds, or a label that a revoked entry holds for a different network identity, and MUST then write the new entry. It MUST store only the one-way digest of the enrolment credential it generates, MUST show that credential once so the operator can install it on the client, and MUST be recorded in the audit log. A revoked entry stays in the registry as a record, and a device whose enrolment was revoked MAY be enrolled again under a new entry.

In SPECIFICATION/scenarios.md, immediately after the scenario "## Scenario: Revoking one host's enrolment leaves every other host served", add:

## Scenario: Enrolling a host under a label already in use is refused

Given the enrolment registry holds an unrevoked host labelled `laptop`

When the operator issues an enrolment for another device under the label `laptop`

Then the command refuses and the registry is unchanged

And no enrolment credential is shown

## Scenario: A revoked device can be enrolled again

Given host A's enrolment has been revoked

When the operator issues a new enrolment for the same device under the same label

Then the command writes a new entry and shows its credential once

And the revoked entry is still recorded as revoked

And a request presenting the old enrolment credential is still refused

In SPECIFICATION/scenarios.md, immediately after the scenario "## Scenario: An unreachable enrolled host does not affect a rotation pass", add:

## Scenario: A stopped delivery service does not affect a rotation pass

Given the delivery service on the role holder is stopped

And no enrolled host has reported within `delivery.stale_after`

When the rotation operation runs a pass that switches accounts

Then the pass completes and reports exactly as it would with no enrolled host

## Proposal: Wording: one name for the account manager's store, no duplicated audit list, no proposal-relative phrasing

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/README.md

### Summary

Five wording corrections to v089 text, none changing behaviour. "The account manager's vault" becomes the defined term, "stored snapshots". spec.md's audit-event list is replaced by a citation of the one contracts.md list. Proposal-relative phrasing that ratified text cannot carry is removed. A **Host report** bullet's punctuation is corrected. The README scope line is aligned with the narrowed identity-only scope.

### Motivation

Found by the independent post-step LLM doctor run on v089 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that v089 merges as is and that all of that run's findings land together in one follow-up revised as v090 (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet, and overseer-3vnxkd is held from dispatch until this lands. Two independent post-step review rounds on this proposal's earlier drafts found 4 defects and 8 advisories, then 1 defect and 5 advisories; all are resolved in this text. These were the v089 run's remaining advisories: the undefined term, the duplicated rules and the stale README line. Two advisories from v089's ratification review are included as well: the carried-over phrase "this proposal adds", and the uneven **Host report** punctuation.

### Proposed Changes

1. In SPECIFICATION/spec.md §"Enrolled-host credential delivery", in **Least privilege.**, replace "- the account manager's vault;" with:

- the account manager's stored snapshots;

2. In SPECIFICATION/contracts.md §"Enrolled-host delivery", in **Moving the role.** step 2, replace "   - the account manager's vault;" with:

   - the account manager's stored snapshots;

3. In SPECIFICATION/spec.md §"Enrolled-host credential delivery", replace "Every delivery served, report received, refused request, and enrolment issued or revoked MUST be recorded in the append-only audit log. The audit log MUST contain no credential material." with:

Every event that contracts.md §"Enrolled-host delivery" **Audit log** lists MUST be recorded in that append-only audit log, which MUST contain no credential material.

4. In SPECIFICATION/spec.md §"Enrolled-host credential delivery", in **Not the credential-provider manager.**, replace "Apart from the read prohibition this proposal adds to §"LLM provider credential management", the manager's rules are unchanged." with:

Apart from the read prohibition that §"LLM provider credential management" **Direct provisioning** states for deliveries, the manager's rules are unchanged.

5. In SPECIFICATION/contracts.md §"Enrolled-host delivery", in **Host report**, replace "- the outcome of each enforcement instruction it acted on, under that instruction's identifier." with:

- the outcome of each enforcement instruction it acted on, under that instruction's identifier;

6. In SPECIFICATION/README.md, replace "identity-only account rotation" with:

account rotation (identity-only except for enrolled-host credential delivery)
