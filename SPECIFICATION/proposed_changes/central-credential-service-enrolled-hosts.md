---
topic: central-credential-service-enrolled-hosts
author: claude-opus-5-5-central-credential-service
created_at: 2026-11-08T14:47:02Z
---

## Proposal: One rotation decision on the credential-rotation role, followed by every following host

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Widens §"Account rotation and quota supervision" from one host to every ENROLLED host:
- Only the operation on the machine that holds the credential-rotation role may make a rotation decision that enrolled hosts follow, and the existing decision lock serializes that decision.
- Every FOLLOWING host (a converted enrolled host) receives the account the operation selected.
- The role is reached by a name bound to the role, never by a hostname.
- No selection rule changes.

This proposal is one of FOUR in this file. They cite one another's clauses and MUST be accepted or rejected together.

### Motivation

**The maintainer's statement**, recorded verbatim in plan/central-credential-service/research/001-requirement-and-prior-art.md: "I want one caam instance running somewhere, on a single machine, to manage all of my account rotations on all hosts."

**Maintainer rulings:**
- 2026-11-07: "There is a machine ROLE that runs caam. Currently the VPS is this role. It may move in the future. Do NOT hardcode hostnames."
- 2026-11-08, choosing topology B of research note 002: "OK go with B".
- 2026-11-08, on the role binding: the role's public DNS name is `ai-acct-mgr.mi-homelab.casa`, repointed when the role moves. This is recorded in the scope event on overseer-iyfjbo at 15:55:37Z.

**Why the current scope fails.** Today **Scope.** limits the operation to "the host-wide active credential" on one host. A second host must therefore either run its own rotation decision or go unmanaged, and both contradict the statement.

**What does not change.** No selection, threshold or trigger rule changes, because the plan's hard constraint and coordinator rule E/R489 forbid it. Enrolment widens only the set of sessions whose refusals and models those rules observe.

**What changed from earlier drafts.** An earlier draft said "exactly one instance". That contradicted contracts.md §"The account-rotation operation" **Concurrency**, which lets any number of callers report concurrently. This draft instead restricts who may DECIDE, and leaves the existing lock to serialize the decision.

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", replace the **Scope.** paragraph with the following. Keep the existing paragraph's last sentence, on the account-manager binary, verbatim, and place it immediately before the sentence beginning "Elsewhere in this section":

**Scope.** `caam-anthropic-loop` is the account-rotation operation governed by this section. It is identity-only, except for the delivery defined in §"Enrolled-host credential delivery".
- The ROLE HOLDER is the machine that holds the CREDENTIAL-ROTATION ROLE: the one machine to which the role name currently resolves. Where no role name is configured, the local host is the role holder and there are no enrolled hosts, which is the single-host behaviour this section had before enrolment.
- The operation MUST observe every account that the coding-agent account manager tracks on the role holder, and MUST report those accounts' remaining quota.
- When the active account's allowance is nearly spent, the operation MUST rotate the role holder's host-wide active credential.
- Every FOLLOWING HOST, as defined in §"Enrolled-host credential delivery", receives that rotation through the delivery defined there.

Elsewhere in this section, "the host" means the role holder.

Immediately after **Scope.**, add:

**One decision, on the role holder.** Only an instance of the operation running on the role holder MAY make a rotation decision that an enrolled host follows, and the decision lock defined under **Switching** serializes those decisions. An enrolled host MUST NOT make a rotation decision of its own. Every delivery MUST name the account that is active on the role holder, so every following host uses that account. Delivering different accounts to different hosts would change the selection rules, and this section does NOT authorize it.

**The role is reached by its name, never by a hostname.** The credential-rotation role MUST be reached through its ROLE NAME: a DNS name bound to the role and repointed when the role moves.
- An enrolled host's configuration, and every provisioning artifact, MUST name the role name.
- They MUST NOT name any machine's hostname or address as the delivery service's address.
- Moving the role to another machine MUST NOT require any change on an enrolled host.

**Enrolment does not change the selection rules.** Enrolling or removing a host MUST NOT change any rule by which the operation ranks, selects, holds or rotates accounts. Enrolment MUST NOT be treated as a reason to alter any threshold, reserve or margin: the usage figures the operation reads are account-wide and already count every host's use. Enrolment widens only the set of sessions whose refusals and models those rules observe, as **Forwarded refusals** and **Remote sessions are tracked sessions** define.

In SPECIFICATION/contracts.md §"The account-rotation operation", in **Surfaces.**, replace "`caam-anthropic-loop` is the identity-only account-rotation operation." with "`caam-anthropic-loop` is the account-rotation operation, identity-only except for the delivery of spec.md §"Enrolled-host credential delivery"."

In SPECIFICATION/scenarios.md, add:

## Scenario: A rotation on the role holder reaches every following host

Given the role holder runs the rotation operation

And two other hosts are enrolled and converted, and their clients are running

When the operation rotates the active account from one account to another

Then each of those hosts' interactive credential file holds the newly selected account's access token

And each of those hosts' global state file's account-identity keys name the newly selected account

And neither of those hosts made a rotation decision of its own

## Scenario: Moving the credential-rotation role changes nothing on an enrolled host

Given an enrolled host whose client reaches the delivery service through the role name

When the role is moved to another machine and the role name is repointed to it

Then the enrolled host's client reaches the new role holder with no change to that host's configuration

And that host's configuration names neither role holder's hostname nor its address

## Proposal: Enrolled-host credential delivery: the access token only, from the live credential

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

### Summary

Adds §"Enrolled-host credential delivery", a component of the account-rotation operation with two parts: a DELIVERY SERVICE on the role holder and an ENROLLED-HOST CLIENT on each enrolled host.
- The service reads the role holder's live interactive OAuth credential. It confirms which account that credential belongs to with the read-only profile request the operation already makes, and then makes it available, with the refresh token removed, to authenticated following hosts.
- Each client writes that credential into its host's interactive credential file.
- The channel is carved out, by name, as the one exception to **Publication MUST carry identity only**.
- Delivery follows the maintainer's refresh-ownership ruling R2: the role holder's own sessions keep refreshing as today, the service delivers each change it observes, and no lead time is promised.

This proposal is one of FOUR in this file. They MUST be accepted or rejected together.

### Motivation

**Topology B**, ruled 2026-11-08: only the central custodian holds refresh tokens, and each host receives only the selected account's access token. A refresh token rotates on every refresh, and a holder that presents a retired one can get the whole token family revoked. So two machines must never hold and use one refresh token (research note 002 §1).

**P0 measurements**, 2026-11-08 (research notes 002 §2.1, 003 §1 and 004 §2):
- An interactive Claude Code TUI ran on the live `claudeAiOauth` object with only its `refreshToken` removed.
- It switched accounts in place on its next turn, with no restart.
- A refresh revokes the previous interactive access token immediately.
- Factory slot tokens are unaffected by that revocation.

**Maintainer ruling 2026-11-08 on refresh ownership:** "1. R2". The role holder's sessions refresh the active account as today, and the central service watches the live credential and delivers each change. The P1 soak measures the enrolled-host turns lost in the window after each refresh, and R1 is revisited at P5.

**Why delivery no longer sits in `llm-provider-manager`.** The first draft made delivery a `host-interactive-file` ProvisioningTarget of that manager. An independent review found that this contradicts the manager's contract in four places (research note 004 §4, items 1, 2 and 4):
- the manager may provision only from its own store;
- it may not read another agent's credential source;
- every adapter is bound to one `consumer_run_id`, and the host's live interactive credential is refused as a destination;
- the manager may not act outside a command.

Under R2, P1 needs nothing the manager provides: there is no acquisition, no selection and no leasing. Note 002 §4 already records that the manager's acquisition work is not needed for P1. The live credential the service reads is the one the rotation operation already polls. So this draft places delivery under the rotation operation, and its only change to the manager is one read prohibition. Folding enrolled-host targets into the manager is deferred to P2, where the manager's open children are already a recorded dependency.

### Proposed Changes

1. **spec.md, **Publication MUST carry identity only.**** In §"Account rotation and quota supervision", replace that clause's first sentence with:

The operation MUST NOT publish, copy, export, or otherwise expose credential material for the selected account or any other, and a credential consumer MUST NOT be expected to obtain a credential from this operation. The ONE exception is the delivery defined in §"Enrolled-host credential delivery", the only channel by which the operation sends credential material to another machine. That channel carries only the role holder's live interactive credential, with its refresh token removed, and only to an authenticated following host, never to a credential consumer. Moving the role, which contracts.md §"Enrolled-host delivery" defines, is an operator act and not a sending by the operation.

2. **spec.md, **Publication MUST NOT influence selection.**** In §"Account rotation and quota supervision", append to that clause:

The delivery service of §"Enrolled-host credential delivery" does not read the published record.

3. **spec.md, new section.** Add the following section immediately after §"Account rotation and quota supervision":

## Enrolled-host credential delivery

**Components.** Enrolled-host delivery is a component of the account-rotation operation. It has two parts:
- the DELIVERY SERVICE, which runs on the role holder;
- the ENROLLED-HOST CLIENT, which runs on each enrolled host.

Three kinds of host are defined:
- An ENROLLED HOST is a host other than the role holder that holds an ENROLMENT, as **Enrolment** below defines.
- A CONVERTED host is an enrolled host whose interactive credential file holds no refresh token.
- A FOLLOWING HOST is a converted enrolled host.

Delivery never makes a rotation decision. A failure of the delivery service MUST NOT fail a rotation pass. A report the service did not receive contributes nothing to the pass, exactly as a session the operation cannot observe contributes nothing.

**The service and the client are supervised long-running processes.** Each MUST run under its machine's per-user service manager, which restarts it when it stops. **Schedule**, **Mode resolution** and **Exit contract** in contracts.md §"The account-rotation operation" govern rotation passes and do not apply to either process. **Fail loudly** applies to each of them as follows:
- On every failure, the process MUST emit a clearly-marked failure line and continue.
- A failure that stops the process MUST exit non-zero.

**The one source.** The delivery service MUST read credential material from exactly one place: the role holder's LIVE credential, the host-wide credential that §"Account rotation and quota supervision" polls as the active account's.
- From that credential, it MUST read only the interactive OAuth object, and MUST remove the refresh token from that object before the object leaves the reading.
- It MUST read the account-identity keys from the role holder's global state file, as that section defines them under **Installing an account MUST swap identity only**, and resolve from them the stable account identifier of **Identity**.
- It MUST NOT transmit any refresh token.
- It MUST NOT read the account manager's stored snapshots or the refresh-maintenance sandbox.
- It MUST NOT write any file the rotation operation writes.

**A delivery names the account its token belongs to.** Before it issues a delivery, the service MUST confirm, with the ONE read-only request contracts.md §"Enrolled-host delivery" names, that the access token it read belongs to the account whose stable identifier the identity keys carry. Where the two differ, the service MUST NOT issue a delivery, and MUST read again on the next change to either the live credential or the global state file. This covers two cases:
- a switch in progress, in which the account manager has installed the new credential before the identity keys are rewritten;
- a session that reinstates or rewrites either file after a switch.

Where the token is locally expired, the service MUST NOT send the request, as **Never refresh** requires.

**Delivery follows the live credential.** The service MUST observe the live credential continuously. Whenever the access token or the account-identity keys change, the service MUST issue a new DELIVERY once the confirmation above succeeds, provided the access token differs from the one in the last delivery issued, whether the change came from an agent session on the role holder refreshing it or from the rotation operation switching accounts. It MUST make that delivery available to every following host's client as soon as it is issued, including any client already waiting for one.
- The service MUST NOT cause a refresh. It MUST NOT invoke the OAuth token endpoint, and **Never refresh** applies to it unchanged. When to refresh remains a decision for the role holder's sessions.
- No lead time before expiry is promised. A refresh on the role holder revokes the previously delivered access token at once. The window between that revocation and each following host applying the replacement is an ACCEPTED exposure under this revision. It MUST be measured as contracts.md §"Enrolled-host delivery" **Host report** and **Status view** require.

**An expired live credential is reported, never repaired.** Where the live credential's access token reaches its expiry and no change has replaced it, the service MUST report that condition in the status view. Every following host whose last-applied delivery carried that token is then shown as `expired`. The service MUST NOT refresh the credential to prevent this.

**A refresh token never reaches an enrolled host.** The service MUST NOT send a refresh token to any host, and the client MUST NOT write one. The client MUST NOT write over an interactive credential file that already holds a refresh token, whether that token comes from the host's own login or from anywhere else. While the file holds one:
- the client MUST request no delivery and MUST report the host as NOT CONVERTED;
- the service MUST serve that host no delivery, and MUST NOT count it as following.

Converting a host is an explicit operator act that removes the host's own login. The client MUST NOT perform it. A not-converted host's own login is a separate grant from the role holder's. That host holds none of the role holder's refresh tokens.

**Applying a delivery swaps the credential and identity only.** When the client applies a delivery:
- it MUST set the interactive OAuth object of the credential file to the delivered object;
- it MUST set the account-identity keys of the host's agent global state file to the delivered values;
- it MUST preserve every other key of both files;
- it MUST verify afterwards that both files hold what it wrote, and MUST report as not applied a delivery whose verification fails.

Atomicity, serialization and rollback are defined in contracts.md §"Enrolled-host delivery". Applying a delivery MUST NOT require restarting any session.

**Deliveries never move backwards.** Every delivery MUST carry a DELIVERY SEQUENCE number strictly greater than the number of every delivery the service issued before it. The sequence MUST continue across a move of the role. A client MUST apply a delivery only when its delivery sequence is greater than the one it last applied, so a delayed or replayed delivery cannot move a host back to an earlier account or an earlier token.

**Delivery is not the request path.** The delivery service and the client MUST NOT carry, relay or observe inference traffic. Each following host's sessions MUST authenticate directly to the provider with the delivered access token.

**Not the credential-provider manager.** Enrolled-host delivery is not a provisioning path of `llm-provider-manager`. It MUST NOT read or write that manager's store, records, leases, assignments or tombstones. Apart from the read prohibition this proposal adds to §"LLM provider credential management", the manager's rules are unchanged.

**Coexistence on the role holder.** The role holder MUST keep its full live credential, and the rotation operation's handling of that credential MUST remain unchanged. Only a later revision of this section may remove the role holder's refresh tokens. An implementation MUST NOT do so on its own.

4. **spec.md, §"LLM provider credential management".** At the end of **Direct provisioning.**, add:

The manager MUST NOT read a delivery of §"Enrolled-host credential delivery" as credential material, or as authority to bypass its own validation and selection.

5. **contracts.md, §"The account-rotation operation".** In **Durable store.**, replace "the one credential write the operation makes itself" with "the one credential write the operation makes itself on the role holder".

6. **contracts.md, new section.** Add the following section immediately after §"The account-rotation operation":

## Enrolled-host delivery

**Transport.**
- The client MUST reach the delivery service over HTTPS at the role name, and only at the role name.
- The role name's DNS record MUST resolve to an address on the private network the enrolled hosts share.
- The service MUST accept requests only over that network.

**Authentication in both directions.**
- The service MUST present a SERVICE CREDENTIAL bound to the role name rather than to the machine. That credential moves with the role.
- The client MUST verify the service credential before it sends its enrolment credential or accepts any delivery, and MUST stop if verification fails.
- The service MUST authenticate every request by BOTH of the following, and MUST refuse the request when either is missing, unknown or revoked:
  - the client's ENROLMENT CREDENTIAL;
  - the NETWORK IDENTITY of the requesting device, which is the device identity that the private network's coordination service reports for the request's source address.

**The account-confirmation request.** For the Anthropic provider, the request that spec.md **A delivery names the account its token belongs to** requires is the `GET https://api.anthropic.com/api/oauth/profile` read defined under **Capacity class source** in §"The account-rotation operation". It MUST be sent with the live access token, and the service MUST compare the account identifier in the response with the stable account identifier the identity keys carry. It is read-only, and it is the only provider request the service sends.

**Operations.** The service MUST expose exactly three operations to an enrolled host:
1. `delivery` returns the host's own current delivery and its current ENFORCEMENT INSTRUCTIONS.
   - The delivery carries the delivery sequence, the selected account's stable account identifier, the account-identity key values, and the interactive OAuth object with no refresh token.
   - An enforcement instruction carries a unique INSTRUCTION IDENTIFIER, names one of that host's sessions, and names the model that spec.md **Model enforcement** decided for it.
   - Instructions are NOT gated by the delivery sequence. The client MUST act on each instruction AT MOST ONCE, whether or not the response carries a new delivery, and MUST report its outcome under its instruction identifier.
   - The service MUST stop serving an instruction once its outcome has been reported. It serves a new instruction only when a later rotation pass decides one.
   - A request MAY name the delivery sequence the client last applied, and MAY wait up to a bounded interval for a later one.
2. `report` accepts the host's report.
3. `enrolment-check` confirms that the host's enrolment is current, and returns no credential material.

The service MUST NOT return, through any operation, another host's delivery, the enrolment registry, the audit log, the report store, or any refresh token. The service MUST NOT open a connection to a host, so an unreachable host costs it nothing.

**Client schedule and single instance.**
- The client MUST request a delivery at least once per `delivery.poll_interval`, whose default MUST be 60 seconds. It MUST send a report after every request, and MAY wait on a delivery request between polls.
- A host user MUST NOT run more than one client.
- The client MUST hold an exclusive lock from its sequence check until its writes and verification are complete.

**Client writes.**
- In the credential file, the client MUST set `claudeAiOauth` to the delivered object, which MUST NOT contain a `refreshToken` field, and MUST preserve every other top-level key.
- In the global state file, it MUST change only the account-identity keys `oauthAccount` and `userID`.
- Each write MUST go to a temporary file in the same directory, with mode 0600, which is then renamed into place.

If either write fails, the client MUST restore the captured previous bytes of BOTH files, the credential file first and then the global state file, each atomically in the same way. It MUST attempt every restore whatever the outcome of an earlier one, and MUST report the delivery as not applied. A restore that fails MUST be reported as a further, distinct failure naming the file left unrestored.

Accepted and unfixed: the host's own agent sessions write the global state file without the client's lock, so they can replace the identity keys after the client's rename. The client's verification reports that case.

**Host report.** Each report MUST carry:
- the delivery sequence and stable account identifier the host last applied, and when it applied them;
- whether its credential file holds a refresh token, which is the NOT CONVERTED condition;
- the time of each authentication failure its sessions recorded since the previous report;
- the outcome of each enforcement instruction it acted on, under that instruction's identifier.

A report MUST NOT carry credential material. Times in a report come from the enrolled host's clock. Any offset between that clock and the role holder's is accepted and unfixed.

**Service stores.** The service MUST keep these stores in the operation's host state directory, each created owner-only and written atomically:
- the ENROLMENT REGISTRY;
- the DELIVERY-SEQUENCE COUNTER, written before the delivery that consumes the sequence is served;
- the REPORT STORE, holding each host's latest report and every forwarded refusal record. A rotation pass MUST read the report store without consuming or deleting anything, as **Concurrency** requires of observation. The service MUST keep each forwarded refusal record for at least seven days, the longest window a refusal can name.

The status view takes account limits from the operation's own cache.

**Enrolment registry.** Each entry records:
- the host's operator-given label;
- its network identity;
- a one-way digest of its enrolment credential;
- when the enrolment was issued;
- whether it is revoked.

Labels and network identities MUST each be unique across the registry. The service MUST NOT store an enrolment credential in recoverable form. The client MUST store its enrolment credential readable only by the user that runs it, or in that user's OS keyring.

**Revocation.** Revoking a host's enrolment MUST be an operator command run on the role holder. Revocation MUST take effect on that host's next request, MUST NOT affect any other host's enrolment, and MUST be recorded in the audit log.

Accepted and unfixed: revocation does not invalidate an access token already delivered. That token stays usable until the next refresh on the role holder revokes it, or until it expires, whichever comes first. The service MUST NOT force a refresh to shorten that window.

**Audit log.** The service MUST append one record to an append-only, owner-only log in the operation's host state directory for each of these events:
- a delivery served;
- a report received;
- a refused request;
- an enrolment issued or revoked.

Each record names the host label and the time. Where they apply, it also names the stable account identifier and the delivery sequence. A record MUST NOT contain credential material.

**Status view.** The status view MUST be readable on the role holder. It MUST NOT be served to an enrolment credential, and it MUST contain no credential material. It MUST show whether the live credential has expired without replacement. For each enrolled host, it MUST show:
- its label;
- the stable account identifier its last-applied delivery named, with the profile name the operation's account table gives that identifier;
- that delivery's sequence and when the host applied it;
- the time of the host's last report;
- the authentication failures the host's sessions recorded between each delivery's issue and its application;
- its STATE.

STATE MUST be exactly one of the values below. Where more than one applies, the one listed first MUST be shown:
- `revoked`: the host's enrolment is revoked;
- `not-converted`: the host's last report says its credential file holds a refresh token;
- `expired`: the host's last-applied delivery's access token has reached its expiry;
- `stale`: no report has arrived within `delivery.stale_after`, whose default MUST be 15 minutes;
- `lagging`: the service has issued a later delivery sequence than the one the host last applied;
- `current`: none of the above applies.

**Configuration.** The role name, `delivery.poll_interval` and `delivery.stale_after` MUST be configurable on the role holder. The role name MUST be configurable on each client, and MUST NOT default to any machine's hostname.

**Moving the role.** Moving the role MUST proceed in this order:
1. On the old holder, stop the delivery service, every agent session using the live credential, the rotation operation's schedule, and its refresh maintenance. From this step on, the old holder MUST NOT use the managed accounts' refresh tokens.
2. Copy to the new holder:
   - the account manager's vault;
   - the live credential;
   - the account-identity keys of the old holder's global state file, and nothing else from that file;
   - the operation's durable store;
   - the service stores;
   - the audit log;
   - the service credential.
3. Repoint the role name. From this step, the new machine is the role holder.
4. Remove every managed account's refresh token from the old machine.
5. Start the new holder.
6. Confirm in the status view that every enrolled host reports in.

Step 4 MUST complete before step 5, so no two machines ever use the role holder's refresh tokens. Step 4 does not breach **Coexistence on the role holder**: by then the old machine is no longer the role holder. Enrolments remain valid across the move. Clients keep their last-applied delivery until the new holder issues a later one.

7. **constraints.md, §"Runtime requirements".** Append:

Enrolled-host delivery is Linux-only on both ends in this revision.
- The delivery service depends on: the role holder's account manager and live credential; the operation's host state directory; a per-user service manager; a listener reachable at the role name over the private network; and that network's device-identity lookup.
- The client depends on: a per-user service manager; owner-only storage or the OS keyring for its enrolment credential; and the host's interactive credential file and global state file.

Each part MUST validate its prerequisites before the dependent action. Each part MUST NOT fall back to an unauthenticated request, an address other than the role name, a credential carrying a refresh token, or a refresh of its own.

8. **constraints.md, §"Atomicity and single instance".** Replace "The ONE exception within the caam operation is its own writes" with "The first of three exceptions within the caam operation is, on the role holder, its own writes". Immediately after the paragraph beginning "Writes to the overseer's own stores", add:

The second and third exceptions within the caam operation are:
- the enrolled-host client's writes of an enrolled host's interactive credential file and global state file;
- the delivery service's writes of its enrolment registry, delivery-sequence counter and report store on the role holder.

Both MUST meet the whole-file atomic-replacement guarantee of the paragraph beginning "Writes to the overseer's own stores". Neither inherits the warning-only fallback. A failed client write restores the previous bytes of both files and is reported, as contracts.md §"Enrolled-host delivery" defines.

9. **scenarios.md.** Add:

## Scenario: A following host receives an access token and never a refresh token

Given an enrolled host whose interactive credential file holds no refresh token

When its client applies a delivery

Then the credential file's interactive OAuth object is the delivered object and holds no refresh token

And every other top-level key the credential file held before the delivery is unchanged

And the host's global state file's account-identity keys name the delivered account, with every other key unchanged

## Scenario: A refresh on the role holder is delivered and its exposure is measured

Given every following host is `current`

When an agent session on the role holder refreshes the live credential

Then the delivery service issues a delivery with a greater delivery sequence carrying the new access token

And the service did not invoke the token endpoint

And the status view shows each following host as `lagging` until its client applies the new delivery

And each authentication failure a following host's sessions record before it applies that delivery appears in the status view against that delivery

## Scenario: A token and identity that disagree produce no delivery

Given the live credential holds one account's access token while the global state file's account-identity keys name another account

When the delivery service reads them

Then the service issues no delivery

And it issues one once the access token and the identity keys name the same account

## Scenario: A stale delivery cannot move a host back

Given an enrolled host has applied delivery sequence 7

When a delivery carrying sequence 6 reaches its client

Then the host's credential file and global state file are unchanged

## Scenario: A failed client write leaves the host on its previous delivery

Given an enrolled host has applied a delivery naming one account

When its client applies a delivery naming another account and the global state file write fails

Then the credential file and the global state file both hold their previous bytes

And the client reports the delivery as not applied

## Scenario: The client refuses to overwrite a host's own login

Given an enrolled host whose interactive credential file holds a refresh token

When its client runs

Then the client requests no delivery and the credential file is unchanged

And the status view shows that host as `not-converted`

## Scenario: An unreachable enrolled host does not affect a rotation pass

Given an enrolled host that is powered off

When the rotation operation runs a pass that switches accounts

Then the pass completes and reports exactly as it would with no enrolled host

And the delivery service opens no connection to the powered-off host

And the status view shows that host as `stale` once `delivery.stale_after` has passed since its last report

## Scenario: An expired live credential is reported, not refreshed

Given the live credential's access token reaches its expiry and no agent session on the role holder refreshes it

When the operator reads the status view

Then the view reports that the live credential has expired without replacement

And every following host whose last-applied delivery carried that token is shown as `expired`

And the delivery service has not invoked the token endpoint

## Scenario: The delivery sequence continues across a move of the role

Given the old role holder last issued delivery sequence 40

When the role is moved and the new holder issues its first delivery

Then that delivery carries a sequence greater than 40

And every following host applies it

## Proposal: Enrolment, least privilege and the central status view

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

This proposal defines enrolment: a per-host, revocable credential that is checked together with the requesting device's network identity, so that each host can read only its own delivery. It also adds the central status view. That view shows every managed account's limits beside each enrolled host's state, and reports a silent host as stale. The wire contract is contracts.md §"Enrolled-host delivery", added by the previous proposal.

This proposal is one of FOUR in this file. They MUST be accepted or rejected together.

### Motivation

Two Definition of Done assertions on overseer-iyfjbo apply. Both are session-derived, and the maintainer's review of them is deferred:
- "One central view shows every managed account's limits, the account each enrolled host is using, and when each host last reported, and it reports a silent host as stale."
- "A compromised enrolled host's credentials cannot read the central store or another host's credential material."

The service needs its own per-host identity. Research note 002 §2.2 measured that the tailnet policy grants every member full access to every member, so reaching the service's port proves nothing about which host is asking.

Authentication runs both ways. The maintainer ruled on 2026-11-08 that there are no Tailscale tags. A Tailscale Service host must be tagged, so the role is bound by public DNS (research note 003 §3). Someone other than the operator can repoint a public name, so the client must also authenticate the service.

### Proposed Changes

In SPECIFICATION/spec.md §"Enrolled-host credential delivery", add:

**Enrolment.** A host's ENROLMENT is an enrolment credential that the role holder issued for that host and has not revoked.
- The delivery service MUST authenticate every request by both that enrolment credential and the requesting device's network identity. It MUST refuse the request when either is missing, unknown or revoked.
- The client MUST authenticate the delivery service before it presents its enrolment credential.
- Enrolment MUST be revocable per host, without affecting any other host.
- Enrolments MUST remain valid when the role moves.

The registry, its storage and revocation are defined in contracts.md §"Enrolled-host delivery".

**Least privilege.** An enrolled host MUST be able to read only its own current delivery and enforcement instructions. It MUST NOT be able to read any of the following:
- the account manager's vault;
- any refresh token;
- the service stores or the audit log;
- any other host's delivery.

Every delivery served, report received, refused request, and enrolment issued or revoked MUST be recorded in the append-only audit log. The audit log MUST contain no credential material.

**Central status view.** The delivery service MUST provide one status view on the role holder that contains no credential material. The view MUST show:
- every managed account's limits, as §"Account rotation and quota supervision" reports them;
- for each enrolled host, the fields and STATE that contracts.md §"Enrolled-host delivery" defines.

A host that has not reported within `delivery.stale_after` MUST NOT be shown as `current`. It MUST be shown as `stale` unless a state listed before `stale` applies.

In SPECIFICATION/scenarios.md, add:

## Scenario: An enrolled host cannot read another host's delivery

Given two enrolled hosts A and B

When host A presents its own enrolment credential and asks for host B's delivery, the service stores, the audit log or any refresh token

Then the delivery service refuses the request

And the audit log records the refusal and no delivery to host A for that request

## Scenario: A valid enrolment presented from the wrong device is refused

Given host A's enrolment credential

When it is presented from a device whose network identity is not the one host A's enrolment names

Then the delivery service refuses the request and serves no delivery

## Scenario: Revoking one host's enrolment leaves every other host served

Given two enrolled hosts A and B

When the operator revokes host A's enrolment on the role holder

Then host A's next request is refused and the status view shows host A as `revoked`

And host B's next request is served

## Scenario: The client refuses a service it cannot authenticate

Given an enrolled host whose role name resolves to a server that cannot present the service credential

When the client contacts it

Then the client sends no enrolment credential and applies no delivery

## Scenario: A silent enrolled host is reported as stale

Given a converted, unrevoked enrolled host whose last-applied delivery has not expired and which has not reported within `delivery.stale_after`

When the operator reads the central status view

Then that host is shown as `stale` with the time of its last report

And the view contains no credential material

## Proposal: Forwarded refusals and remote model enforcement

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds the one additive seam into `caam-anthropic-loop` that the maintainer approved:
- Enrolled-host clients forward their sessions' refusal records and session models to the role holder.
- The existing refusal-attribution and model-enforcement rules then act on those sessions exactly as they act on local ones.

No rule's meaning changes. The seam widens only the set of sessions that the existing rules observe.

This proposal is one of FOUR in this file. They MUST be accepted or rejected together.

### Motivation

Maintainer ruling 2026-11-08 on decision 2 of research note 002 §5, the additive refusal and model-enforcement seam: "Yes."

Today the operation reads refusals only from local transcripts. Once sessions run on enrolled hosts, the refusal that catches a wrong usage reading would happen where the operation cannot see it. On 2026-10-13 an account read 45% remaining nine minutes before it refused. Model enforcement reaches only local sessions, for the same reason.

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", in the paragraph beginning "The operation MUST attribute a refusal to the active account only when ALL of these hold", replace this conjunct:

"that session authenticates with the host-wide live credential, which the operation MUST establish from the session's agent configuration directory being the host's default directory, the one holding the live credential, so that neither a separately provisioned credential nor the operation's own refresh-maintenance sandbox, whose sessions exercise other accounts' stored credentials and MUST NOT be read for refusals, can contribute"

with:

that session authenticates with the role holder's live credential or with a following host's delivered credential, as **Which credential a refusing session used** below establishes

Leave every other conjunct of that paragraph unchanged. Immediately after the paragraph, add:

**Which credential a refusing session used.** The operation MUST establish the credential conjunct above as follows, so that neither a separately provisioned credential nor the operation's own refresh-maintenance sandbox, whose sessions exercise other accounts' stored credentials and MUST NOT be read for refusals, can contribute:
- For a session on the role holder, the session's agent configuration directory MUST be the role holder's default directory, the one holding the live credential.
- For a session on an enrolled host, the report that carries the refusal MUST state three things: that the session's agent configuration directory is that enrolled host's own default directory, the one the client writes; that the host is converted; and that the delivery it had applied when the refusal was recorded named the active account's stable identifier.

**Forwarded refusals.** A FORWARDED refusal is a refusal record that an enrolled-host client reports from one of its host's sessions, as stored in the delivery service's report store.
- The operation MUST parse and attribute a forwarded refusal exactly as it does a local refusal record. It MUST apply every attribution conjunct above, including the conjunct requiring the refusal to be recorded after the operation last observed the active account become active. That conjunct, together with the departed entries, excludes a refusal recorded under an earlier activation of the same account.
- Detecting a forwarded refusal MUST NOT send any request to the provider.
- A forwarded refusal whose report does not state the delivery the host had applied when the refusal was recorded MUST NOT be attributed.
- A forwarded refusal's recorded time, and any reset time derived from it, come from the enrolled host's clock. Their offset from the role holder's clock is an accepted residual, recorded in contracts.md §"Enrolled-host delivery".

In SPECIFICATION/spec.md §"Account rotation and quota supervision", after **Model enforcement.**, add:

**Remote sessions are tracked sessions.** A session that an enrolled-host client reports is a tracked session for every clause of this section, but only while its host's STATE, as contracts.md §"Enrolled-host delivery" defines it, is none of `stale`, `revoked` or `not-converted`. A host that stops reporting therefore stops arming any trigger. Its identity is qualified by its host's enrolment label, so it can never collide with a session on another host.
- The client MUST determine each reported session's model programmatically, as **Session identity** requires.
- The operation MUST decide enforcement for a remote session by the same rules as for a local one, and the client MUST carry out the resulting enforcement instructions under the same advisory, best-effort and busy-session rules.
- Enforcement MUST record that it set a remote session's model only once that host's report states the instruction was applied. Until then the session MUST NOT be treated as operator-set on the ground that its model differs from the model enforcement last set.
- A remote session observed on the scoped model MUST arm the scoped-model clauses exactly as a local one does.
- An enforcement failure on an enrolled host MUST NOT disturb the quota report, the rotation or delivery.

In SPECIFICATION/contracts.md §"Enrolled-host delivery", extend **Host report** so that each report MUST also carry:
- each refusal record that the host's sessions recorded since the previous report, with the time it was recorded, the window it names, its reported reset time if any, and the delivery sequence and stable account identifier that the host had applied at that time;
- for each running session, its identifier, whether its agent configuration directory is the host's default directory, and its observed model, or `unknown`.

In SPECIFICATION/scenarios.md, add:

## Scenario: A refusal on a following host rotates the active account

Given a following host has applied a delivery naming the active account

And a candidate survives every selection rule

When a session on that host, configured in that host's default directory, records a usage-limit refusal after the active account became active, and the client reports it

Then the operation attributes the refusal to the active account and treats it as the refusal trigger

And the switch line names the refusal as the reason and the time it was recorded

## Scenario: A forwarded refusal under another account's delivery is not attributed

Given an enrolled host whose last-applied delivery named an account other than the active account

When the client forwards a refusal that its session recorded under that delivery

Then the operation does not attribute the refusal to the active account

## Scenario: A remote enforcement is recorded only once the client applies it

Given an enrolled host reports a session with an operator-set per-session pin it is not running

When the operation decides enforcement for that session and the host's next report has not yet stated that the instruction was applied

Then the operation does not treat that session as operator-set

And it records the enforcement once the host's report states that the instruction was applied

## Scenario: A remote session on the scoped model arms the scoped-model trigger

Given an enrolled host reports a running session observed on the scoped model

And the active account is at or below the scoped-model reserve

When the operation runs a scheduled pass

Then the scoped-model trigger fires exactly as it would for a local session on the scoped model

## Scenario: An enforcement instruction is applied at most once

Given the client applied an enforcement instruction to a remote session and reported its outcome

When the operator changes that session's model before the next rotation pass

Then the client does not apply that instruction again

And the next rotation pass, seeing the session's known model differ from the model enforcement last set, treats the session as operator-set
