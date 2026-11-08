---
topic: central-credential-service-enrolled-hosts
author: claude-opus-5-5-central-credential-service
created_at: 2026-11-08T14:47:02Z
---

## Proposal: One rotation authority on the credential-rotation role, for every enrolled host

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Widens the scope of §"Account rotation and quota supervision" from one host to every ENROLLED host. Exactly one running instance, on the machine that holds the credential-rotation role, makes the rotation decision, and every enrolled host follows it. The selection rules themselves are unchanged.

### Motivation

Maintainer statement, recorded verbatim in plan/central-credential-service/research/001-requirement-and-prior-art.md: "I want one caam instance running somewhere, on a single machine, to manage all of my account rotations on all hosts." Maintainer ruling 2026-11-07: "There is a machine ROLE that runs caam. Currently the VPS is this role. It may move in the future. Do NOT hardcode hostnames." Maintainer ruling 2026-11-08, choosing topology B of research note 002: "OK go with B". Today §"Account rotation and quota supervision" scopes the operation to "the host-wide active credential" on one host, so a second host either runs its own caam (a second rotation decision) or is unmanaged. Both contradict the statement. This proposal does not change any selection, threshold or trigger rule. Both the plan's hard constraint and coordinator rule E/R489 forbid that.

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", replace the **Scope.** paragraph's single-host scope with the following clauses, keeping its last sentence on the account-manager binary unchanged:

**Scope.** `caam-anthropic-loop` is the identity-only account-rotation operation governed by this section. It MUST observe every account tracked by the account manager on the machine that holds the CREDENTIAL-ROTATION ROLE, MUST report their remaining quota, and MUST rotate the active account when the active account's allowance is nearly spent. That rotation MUST apply to the role holder's own host-wide active credential AND to every ENROLLED host defined in §"LLM provider credential management".

**Exactly one rotation authority.** Exactly one instance of the operation MUST make rotation decisions at any time, and it MUST run on the machine that holds the credential-rotation role. An enrolled host that does not hold the role MUST NOT make a rotation decision of its own; it MUST follow the selection that instance publishes. Every enrolled host MUST be assigned the account the operation selected. Assigning different hosts different accounts is a selection-rule change and is NOT authorized by this section.

**The role is the binding, never a hostname.** The credential-rotation role MUST be addressable by a name bound to the role. No enrolled host's configuration, and no provisioning artifact, MAY name the role holder's hostname as the service's address. Reassigning the role to another machine MUST NOT require any change on an enrolled host that does not hold the role.

**Selection rules are unchanged by enrolment.** Enrolling or removing a host MUST NOT change how the operation ranks, selects, holds or rotates accounts. The usage figures it reads are account-wide and already count every host's use, so enrolment MUST NOT be treated as a reason to alter thresholds.

In SPECIFICATION/scenarios.md, add:

## Scenario: A rotation on the role holder reaches every enrolled host

Given the machine holding the credential-rotation role runs the rotation operation

And two other hosts are enrolled and reachable

When the operation rotates the active account from one account to another

Then each enrolled host's interactive credential is replaced with the newly selected account's access token

And a Claude session already running on each enrolled host authenticates as the newly selected account on its next turn, without a restart

And neither enrolled host made a rotation decision of its own

## Scenario: Moving the credential-rotation role changes nothing on an enrolled host

Given an enrolled host whose client reaches the service through the role's name

When the credential-rotation role is reassigned to another machine and the role's name is repointed to it

Then the enrolled host's client reaches the new role holder with no change to that host's configuration

And that host's configuration contains no hostname of either role holder

## Proposal: host-interactive-file target: deliver only an access token, never a refresh token

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds a second ProvisioningTarget adapter, `host-interactive-file`, beside `isolated-run`. It writes the selected account's ACCESS TOKEN, never its refresh token, into an enrolled host's interactive credential file. It does so by an atomic merge that leaves every other key intact, and it updates the host's account identity to match. It also makes three clarifications this needs: credential delivery is not the inference request path or a pooled endpoint; only the role holder holds refresh tokens; and the protected-path rule keeps guarding every other adapter.

### Motivation

Topology B (research note 002 §3, ruled 2026-11-08): the central custodian alone holds refresh tokens, and each host receives only the selected account's access token. A refresh token rotates on every refresh, and a holder presenting a retired one can get the whole token family revoked. So two machines must never hold and use one refresh token, and copying the vault to each host is ruled out (note 002 §1). P0 proofs on 2026-11-08 (research note 003 §1) measured an interactive Claude Code TUI running on an access token with no refresh token, and then switching to a different account in place, on its next turn, with no restart. Three current clauses block this as written. §"LLM provider credential management" **Direct provisioning** allows only the requesting consumer's isolated credential file. It also forbids pooling "subscription credentials behind a shared network endpoint", which reads ambiguously against a service that delivers credentials over the tailnet. And contracts.md's protected-path list refuses any write to the user's `.claude/.credentials.json`, which is exactly the file this target owns.

### Proposed Changes

In SPECIFICATION/spec.md §"LLM provider credential management", after the **Direct provisioning.** paragraph, add:

**Enrolled-host provisioning.** The manager MUST support a second ProvisioningTarget adapter, `host-interactive-file`, enabled only for an ENROLLED host that does not hold the credential-rotation role. It MUST write the access token of the account the rotation operation selected into that host's interactive credential file, and MUST update the account identity in that host's agent configuration to the same account. It MUST NOT write, transmit or expose a refresh token to any enrolled host that does not hold the role; only the role holder MAY hold refresh tokens. The write MUST replace the file atomically, and MUST merge, preserving every key of the file other than the interactive OAuth credential itself.

**Delivery is not the request path.** The `host-interactive-file` delivery MUST NOT carry, relay or observe inference traffic. An enrolled host's sessions MUST authenticate directly to the provider with the delivered token. Delivering one credential to one authenticated enrolled host over the network is provisioning, not the pooling of subscription credentials behind a shared network endpoint that **Direct provisioning** forbids, and that prohibition MUST continue to apply to every inference path.

**Deliver before expiry.** A delivered access token cannot be refreshed on the enrolled host. The service MUST therefore deliver a replacement before the delivered token's expiry. An enrolled host whose token expires before a replacement arrives MUST be reported as such in the operator-facing status, and MUST NOT be silently left on a dead credential. The service MUST NOT itself invoke the OAuth token endpoint: it MUST obtain fresh access tokens only from the role holder's existing delegated refresh, the agent's own renewal and idle-profile keep-warm, as §"Account rotation and quota supervision" **Never refresh** requires.

**Coexistence on the role holder.** Until per-host account management is deprecated, the role holder MAY keep its full live credential, and the rotation operation's behaviour there MUST remain unchanged.

In SPECIFICATION/contracts.md §"The LLM credential-provider operation", add the contract for `host-interactive-file`:

- A `host-interactive-file` assignment MUST name the selected account by both the profile name and the stable account identifier, as the account-publication record does. It MUST carry an assignment GENERATION that increases on every new assignment, and the access token's expiry.
- The client MUST apply an assignment only when its generation is greater than the generation last applied, so a delayed or replayed delivery can never move a host back to an earlier account.
- The client MUST write the credential file to a temporary file in the same directory with mode 0600, then rename it into place. It MUST preserve every top-level key other than `claudeAiOauth`, and MUST NOT include a `refreshToken` field.
- The protected-path list defined for target writes MUST continue to refuse every adapter other than `host-interactive-file` writing the effective user's `.claude/.credentials.json`. `host-interactive-file` is the one adapter whose target IS that file, and only on an enrolled host that does not hold the credential-rotation role. On the role holder it MUST refuse, because that host's live credential belongs to the rotation operation.

In SPECIFICATION/scenarios.md, add:

## Scenario: An enrolled host receives an access token and never a refresh token

Given an enrolled host that does not hold the credential-rotation role

When the service delivers the selected account to it

Then the host's interactive credential file holds that account's access token and its expiry

And the file holds no refresh token

And every other top-level key the file held before the delivery is unchanged

And the host's agent configuration names the same account

## Scenario: A stale assignment cannot move a host back

Given an enrolled host has applied assignment generation 7

When a delivery carrying generation 6 arrives

Then the host's credential file and account identity are unchanged

## Scenario: The role holder refuses the host-interactive-file target

Given the machine holding the credential-rotation role

When a host-interactive-file delivery is attempted against its own credential file

Then the manager refuses it and no credential bytes change

## Proposal: Enrolment, least privilege and the central status view

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Defines what an ENROLLED host is and how far a compromise can reach: a per-host revocable enrolment, checked together with the network identity of the caller, with each host able to read only its own assignment. Adds the central status view: every managed account's limits, each enrolled host's assigned account and last report, and silent hosts reported as stale.

### Motivation

Plan Definition of Done assertions 3 and 7 (session-derived and still awaiting the maintainer's correction, recorded on overseer-iyfjbo): "One central view shows every managed account's limits, the account each enrolled host is using, and when each host last reported, and it reports a silent host as stale", and "A compromised enrolled host's credentials cannot read the central store or another host's credential material." Measured (research note 002 §2.2): `tailscale-admin/policy.hujson` grants every member full access to every member, phones included, and the tag apparatus is retired. So reaching the service's port proves nothing about which host is asking, and the service needs its own per-host identity. The inherited constraint from llm-provider-manager is "least privilege everywhere".

### Proposed Changes

In SPECIFICATION/spec.md §"LLM provider credential management", add:

**Enrolment.** An ENROLLED host is one holding a per-host enrolment credential issued for it by the role holder. The service MUST authenticate every request from an enrolled host by BOTH that enrolment credential AND the network identity of the requesting device, and MUST refuse a request where either is missing, unknown or revoked. Enrolment MUST be revocable per host, without affecting any other host. The enrolment credential MUST be stored on the host readable only by the user that runs its client, or in the host's OS keyring.

**Least privilege.** An enrolled host MUST be able to read only its OWN current assignment. It MUST NOT be able to read the service's credential store, any refresh token, or any other host's assignment or credential material. Every issued assignment MUST be recorded in an append-only audit log that names the host, the account and the generation, and that contains no credential material.

**Central status view.** The service MUST expose one status view that contains no credential material. It MUST show every managed account's limits as §"Account rotation and quota supervision" reports them, and, for each enrolled host: the account assigned, the generation it last applied, when it last reported, and whether its delivered token has expired. A host that has not reported within the configured staleness interval MUST be shown as STALE, and MUST NOT be shown as current.

In SPECIFICATION/scenarios.md, add:

## Scenario: An enrolled host cannot read another host's credential

Given two enrolled hosts A and B

When host A presents its own enrolment credential and asks for host B's assignment, the credential store, or any refresh token

Then the service refuses

And the audit log records no assignment issued to host A for that request

## Scenario: A request with a valid enrolment from the wrong device is refused

Given host A's enrolment credential

When it is presented from a device whose network identity is not host A

Then the service refuses the request and issues nothing

## Scenario: A silent enrolled host is reported as stale

Given an enrolled host that has not reported within the configured staleness interval

When the operator reads the central status view

Then that host is shown as stale with the time of its last report

And the view contains no credential material
