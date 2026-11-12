---
topic: enrolled-host-ssh-push
author: claude-opus-5-5
created_at: 2026-11-12T18:48:31Z
---

## Proposal: Enrolled-host delivery by ssh push

### Target specification files

- SPECIFICATION/spec.md

### Summary

Replace the pull design (HTTPS delivery service, enrolment credentials, a client on every host, report store, audit log) with a delivery service that pushes each delivery over ssh to every host in a role-holder-held host list; add Remote Control re-issue after an account switch, on listed hosts and on the role holder; reduce the central status view to a status command; defer its login-age, factory-probe and alert rows, forwarded refusals and remote sessions. The service delivers only the role holder's live login, never the published selection, and the status command shows and flags a divergence between them.

### Motivation

Maintainer ruling 2026-11-12 on plan central-credential-service (epic overseer-iyfjbo): topology B (one central custodian of each account's login, hosts receive access tokens only), delivered by ssh push for speed, with no host-installed client and no enrolment. The pull design's transport, enrolment and client work (P1-B2..D) failed twice in the factory and is superseded. Claude Code since v2.1.234 stops Remote Control on an account change, so the maintainer chose automatic re-issue. The coordinator measured caam's live login diverging from its published selection three times on 2026-11-11 and 2026-11-12, so the delivery source is pinned to the live credential.

### Proposed Changes

Replace the whole body of spec.md §"Enrolled-host credential delivery" (heading kept verbatim) with:

**Components.** Enrolled-host delivery is a component of the account-rotation operation. It is a DELIVERY SERVICE that runs on the role holder and PUSHES each delivery over ssh to every host in the role holder's HOST LIST. Nothing that reaches the role holder runs on a listed host.

Three kinds of host are defined:
- A LISTED HOST is a host other than the role holder that has an entry in the host list. "Enrolled host" elsewhere in this specification means a listed host.
- A CONVERTED host is a listed host whose interactive credential holds no refresh token.
- A FOLLOWING HOST is a converted listed host.

Delivery never makes a rotation decision. A failure of the delivery service MUST NOT fail a rotation pass.

**The service is a supervised long-running process.** It MUST run under the role holder's per-user service manager, which restarts it when it stops. **Schedule**, **Mode resolution** and **Exit contract** in contracts.md §"The account-rotation operation" govern rotation passes and do not apply to it. **Fail loudly** applies to it as follows:
- On every failure, the service MUST emit a clearly-marked failure line that contains no credential material, and continue.
- A failure that stops the service MUST exit non-zero.

**The one source.** The delivery service MUST read credential material from exactly one place: the role holder's LIVE credential, the host-wide credential that §"Account rotation and quota supervision" polls as the active account's.
- From that credential, it MUST read only the interactive OAuth object, and MUST remove the refresh token from that object before the object leaves the reading.
- It MUST read the account-identity keys from the role holder's global state file, as that section defines them under **Installing an account MUST swap identity only**, and resolve from them the stable account identifier of **Identity**.
- It MUST NOT transmit any refresh token.
- It MUST NOT read the account manager's stored snapshots or the refresh-maintenance sandbox.
- It MUST NOT write any file the rotation operation writes.
- It MUST deliver only the account of the login the role holder is itself using, as the live credential holds it, and MUST NOT take the account to deliver from the operation's published selection record. Where the published selection names a different account from the live credential, the service MUST still deliver the live credential's account, and the status command MUST show the divergence.

**A delivery names the account its token belongs to.** Before it issues a delivery, the service MUST confirm, with the ONE read-only request contracts.md §"Enrolled-host delivery" names, that the access token it read belongs to the account whose stable identifier the identity keys carry. Where the two differ, the service MUST NOT issue a delivery, and MUST read again on the next change to either the live credential or the global state file. This covers two cases:
- a switch in progress, in which the account manager has installed the new credential before the identity keys are rewritten;
- a session that reinstates or rewrites either file after a switch.

Where the token is locally expired, the service MUST NOT send the request, as **Never refresh** requires.

**Delivery follows the live credential.** The service MUST observe the live credential continuously. Whenever the access token or the account-identity keys change, the service MUST issue a new DELIVERY once the confirmation above succeeds, provided the access token differs from the one in the last delivery issued, whether the change came from an agent session on the role holder refreshing it or from the rotation operation switching accounts.
- The service MUST NOT cause a refresh. It MUST NOT invoke the OAuth token endpoint, and **Never refresh** applies to it unchanged. When to refresh remains a decision for the role holder's sessions.
- No lead time before expiry is promised. A refresh on the role holder revokes the previously delivered access token at once. The window between that revocation and each following host applying the replacement is an ACCEPTED exposure under this revision. The status command records when each host last received a delivery.

**Every delivery is pushed to every listed host.** The service MUST push each delivery it issues to every listed host, and MUST push to each host independently, so that a slow or unreachable host never delays another. A host the push cannot reach, or whose push fails, MUST be retried at the interval contracts.md §"Enrolled-host delivery" defines until it holds the current delivery or a later delivery supersedes the one being retried. Retrying MUST NOT re-confirm or re-read the live credential beyond what **Delivery follows the live credential** requires.

**An expired live credential is reported, never repaired.** Where the live credential's access token reaches its expiry and no change has replaced it, the service MUST report that condition through the status command. Every following host whose last-applied delivery carried that token is then shown as `expired`. The service MUST NOT refresh the credential to prevent this.

**A refresh token never reaches a listed host.** The service MUST NOT send a refresh token to any host. The apply step MUST NOT write a refresh token, and MUST NOT write over an interactive credential that already holds one, whether that token comes from the host's own login or from anywhere else. Where the credential holds one, the apply step MUST leave the host unchanged and report the host as NOT CONVERTED, and the service MUST NOT count it as following.

Converting a host is an explicit operator act that removes the host's own login. Neither the service nor the apply step performs it. A not-converted host's own login is a separate grant from the role holder's. That host holds none of the role holder's refresh tokens.

**Applying a delivery swaps the credential and identity only.** The push runs an APPLY STEP on the listed host. When the apply step applies a delivery:
- it MUST set the interactive OAuth object of the host's interactive credential to the delivered object;
- it MUST set the account-identity keys of the host's agent global state file to the delivered values;
- it MUST preserve every other key of both;
- it MUST verify afterwards that both hold what it wrote, and MUST report as not applied a delivery whose verification fails.

Atomicity, serialization and rollback are defined in contracts.md §"Enrolled-host delivery". Applying a delivery MUST NOT require restarting any session.

**Deliveries never move backwards.** Every delivery MUST carry a DELIVERY SEQUENCE number strictly greater than the number of every delivery the service issued before it. The sequence MUST continue across a move of the role. The apply step MUST apply a delivery only when its delivery sequence is greater than the one the host last applied, so a delayed or retried push cannot move a host back to an earlier account or an earlier token.

**Remote Control follows an account switch.** Claude Code stops a session's Remote Control when the signed-in account changes. After a following host applies a delivery that names a different account from the one it last applied, the service MUST re-issue Remote Control on that host in every agent session whose terminal shows that Remote Control stopped because the signed-in account changed, as contracts.md §"Enrolled-host delivery" defines. The service MUST apply the same re-issue to the role holder's own agent sessions after the rotation operation switches the live credential to a different account. It MUST NOT start Remote Control in any other session. The re-issue is advisory and best-effort: its failure MUST be reported and MUST NOT undo the delivery or fail a rotation pass.

**Delivery is not the request path.** The delivery service and the apply step MUST NOT carry, relay or observe inference traffic. Each following host's sessions MUST authenticate directly to the provider with the delivered access token.

**Not the credential-provider manager.** Enrolled-host delivery is not a provisioning path of `llm-provider-manager`. It MUST NOT read or write that manager's store, records, leases, assignments or tombstones. Apart from the read prohibition that §"LLM provider credential management" **Direct provisioning** states for deliveries, the manager's rules are unchanged.

**Coexistence on the role holder.** The role holder MUST keep its full live credential, and the rotation operation's handling of that credential MUST remain unchanged. Only a later revision of this section may remove the role holder's refresh tokens. An implementation MUST NOT do so on its own.

**The host list is held only on the role holder.** Adding a host to delivery MUST be one entry in the host list. A listed host MUST NOT hold the role holder's address, the role name, or any credential for the role holder: the role holder reaches the host, and the host never reaches the role holder. The push authenticates to each host with the ROLE KEY, which moves with the role, so moving the role MUST NOT require any change on a listed host.

**Least privilege.** A listed host MUST NOT be able to read anything on the role holder, including the account manager's stored snapshots, any refresh token, or the service stores. The host list and the service stores MUST contain no credential material. The role key MUST be readable only by the role holder's operating user.

**Status command.** The delivery service MUST provide one operator command on the role holder that shows delivery state and contains no credential material. This command is the CENTRAL STATUS VIEW that other clauses of this specification name. It MUST show whether the live credential has expired without replacement; the account the live credential holds and the account the operation's published selection record names, flagging when they differ; and, for each listed host, the fields and STATE that contracts.md §"Enrolled-host delivery" defines. A host that has had no successful push within `delivery.stale_after` MUST NOT be shown as `current`. It MUST be shown as `stale` unless a state listed before `stale` applies.

**Deferred to a later revision.** This revision does not define rows in the status command for account limits, login age and lifetime-cap warnings, factory credential probes or undelivered push alerts; the rotation operation's clauses on these are unchanged. Refusals forwarded from listed hosts, and tracking and model enforcement of sessions on listed hosts, are deferred as §"Account rotation and quota supervision" **Forwarded refusals** and **Remote sessions** state, until the follow-up plan opened once push runs on every reachable Linux host.


## Proposal: Account rotation clauses follow the push design

### Target specification files

- SPECIFICATION/spec.md

### Summary

Remove the role name, enrolment, forwarded refusals and remote-session tracking from the account-rotation section, deferring the last two to a later revision.

### Motivation

Under ssh push no host reaches the role holder, so the DNS role name and enrolment have no referent, and without a host client there are no host reports to carry forwarded refusals or remote sessions. The maintainer deferred those two features (F and G) to the follow-up plan opened once push runs on every reachable Linux host, which reopens them.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", replace the enrolled-host clauses as follows:
- **Scope**, role-holder bullet: the role holder is "the one machine currently assigned that role, which holds the managed accounts' logins, runs the rotation operation and pushes deliveries. Where no host list is configured on it, there are no listed hosts, which is the single-host behaviour this section had before delivery."
- **One decision, on the role holder**: "enrolled host" becomes "listed host"; otherwise unchanged.
- **The role is reached by its name, never by a hostname** is replaced by **The role, never a hostname.**: every provisioning artifact names the credential-rotation role, never a machine's hostname; a listed host's configuration MUST NOT name the role holder at all, because the role holder pushes and the host never reaches it; moving the role MUST NOT require any change on a listed host. The DNS ROLE NAME is removed.
- **Enrolment does not change the selection rules** becomes **Listing a host does not change the selection rules**, with the same rule, and states that listing a host widens no observed session set in this revision.
- The refusal-attribution credential conjunct drops "or with a following host's delivered credential"; **Which credential a refusing session used** replaces its enrolled-host bullet with: "A session on a listed host is not a tracked session in this revision, so no refusal it records is attributed."
- **Forwarded refusals** becomes a deferral, reopened by the follow-up plan opened once push runs on every reachable Linux host: no refusal is forwarded from a listed host in this revision; refusals are observed only from tracked sessions on the role holder; until then a refusal on a listed host reaches the operation only through the account-wide usage readings.
- **Remote sessions are tracked sessions** becomes **Remote sessions**, a deferral reopened by the follow-up plan opened once push runs on every reachable Linux host: a session on a listed host is not tracked, arms no trigger, and enforcement drives only role-holder sessions.
- **A dark active login MUST be left at once**, condition (a): "a tracked session's transcript, local or forwarded from an enrolled host under **Forwarded refusals**, records" becomes "a tracked session's transcript records".

## Proposal: Enrolled-host delivery wire contract for ssh push

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Replace contracts.md §"Enrolled-host delivery" with the host list, ssh transport with the role key and verified host keys, the stdin apply step and its result line, the macOS inbox, launch agent and result file, retry and timeouts, Remote Control re-issue over tmux keyed on Claude Code's pinned notice text, push-state stores, the status command and its STATE values, configuration, and the move-the-role order.

### Motivation

The wire contract must match the ssh-push design ratified in the spec.md finding.

### Proposed Changes

Replace the whole body of contracts.md §"Enrolled-host delivery" (heading kept verbatim) with:

**Host list.** The host list is a file in the operation's host state directory on the role holder, created owner-only and written atomically. Each entry names:
- a LABEL, unique in the list;
- an SSH DESTINATION of the form `user@host`;
- a PLATFORM, `linux` or `macos`.

The host list MUST NOT hold credential material. Removing an entry stops delivery to that host on the next push.

**Transport.** The service MUST push over ssh to each entry's ssh destination, authenticating with the ROLE KEY: an ssh key pair held owner-only on the role holder that moves with the role. Each listed host MUST authorize the role key for its listed user. The service MUST verify each host's ssh host key against the role holder's known-hosts record and MUST NOT push to a host whose host key it cannot verify. The delivery MUST travel on the ssh session's standard input, never in a command-line argument, an environment variable or any file on the role holder; the service holds the delivery only in memory.

**The account-confirmation request.** For the Anthropic provider, the request that spec.md **A delivery names the account its token belongs to** requires is the `GET https://api.anthropic.com/api/oauth/profile` read defined under **Capacity class source** in §"The account-rotation operation". It MUST be sent with the live access token, and the service MUST compare the account identifier in the response with the stable account identifier the identity keys carry. It is read-only, and it is the only provider request the service sends.

**The delivery.** A delivery carries the delivery sequence, the selected account's stable account identifier, the account-identity key values `oauthAccount` and `userID`, and the interactive OAuth object with no `refreshToken` field.

**The apply step.** The push sends the apply step to the host as a program on the ssh session's standard input, followed by the delivery, and the host runs it with its own `python3`. Nothing for delivery is installed on a Linux host. On a `macos` host, where Claude Code keeps the interactive credential in the login Keychain and an ssh session cannot write that Keychain, the push MUST instead write the delivery to an owner-only INBOX file in the listed user's home directory, as a mode-0600 temporary file in the same directory that is then renamed into place. A per-user launch agent installed once on that Mac MUST apply it from there under the same rules, delete the inbox, and write its result line to an owner-only RESULT file beside it, atomically in the same way. The service MUST read that result file on its next push or retry to that host and record it as the host's last result; for a `macos` host, every clause below that depends on the apply step's result uses that recorded result.
- The apply step MUST hold an exclusive lock from its sequence check until its writes and verification are complete.
- It MUST compare the delivery's sequence with the APPLIED SEQUENCE recorded on the host in an owner-only file beside the credential file, and MUST change nothing and report `stale-sequence` when the delivery's sequence is not greater.
- It MUST change nothing and report `not-converted` when the host's interactive credential holds a refresh token.
- In the credential, it MUST set `claudeAiOauth` to the delivered object, which MUST NOT contain a `refreshToken` field, and MUST preserve every other top-level key. On Linux the credential is the file `~/.claude/.credentials.json`; on macOS it is the login-Keychain item Claude Code reads.
- In the global state file `~/.claude.json`, it MUST change only `oauthAccount` and `userID`.
- Each file write MUST go to a temporary file in the same directory, with mode 0600, which is then renamed into place. It MUST record the applied sequence the same way, last.
- If either write fails, it MUST restore the captured previous contents of BOTH the credential and the global state file, the credential first, attempting every restore whatever the outcome of an earlier one, and MUST report the delivery as `failed`. A restore that fails MUST be reported as a further, distinct failure naming what was left unrestored.
- It MUST print exactly one result line, containing no credential material, naming one of `applied`, `stale-sequence`, `not-converted` or `failed`, the sequence it applied or refused, and, for `failed`, the reason.

Accepted and unfixed: the host's own agent sessions write the global state file without the apply step's lock, so they can replace the identity keys after its rename. The verification reports that case.

**Retry and timeouts.** A push attempt that has not finished within `delivery.push_timeout`, default 30 seconds, MUST be abandoned and counted as failed. The service MUST retry a host whose last push failed or did not reach it at least once per `delivery.retry_interval`, default 60 seconds.

**Remote Control re-issue.** After a push whose result is `applied` and whose account differs from the one that host last applied, the service MUST, over the same ssh destination, read the visible text of every tmux pane on the host that runs an agent session. In each pane whose visible text contains Claude Code's notice `Remote Control stopped because the signed-in account changed`, it MUST send `/remote-control` followed by Enter, once for that delivery. It MUST send nothing to any other pane. After it issues a delivery naming a different account from the previous delivery, the service MUST apply the same re-issue, locally, to the role holder's own tmux panes. A session that does not run in tmux is outside what the service can reach, which is accepted and unfixed.

**Service stores.** The service MUST keep these stores in the operation's host state directory, each created owner-only and written atomically:
- the DELIVERY-SEQUENCE COUNTER, written before the delivery that consumes the sequence is pushed;
- the PUSH STATE, holding for each listed host the last result its apply step reported, the sequence and stable account identifier it last applied and when, the time of its last successful push, and its last push error, which contains no credential material, with its time.


**Status command.** The status command MUST be readable only on the role holder and MUST contain no credential material. It MUST show whether the live credential has expired without replacement. It MUST show the stable account identifier of the account the live credential holds and of the account the operation's published selection record names, each with its profile name, and MUST mark the pair `diverged` when they differ; the service delivers the live account in that case, as spec.md **The one source** requires. For each listed host, it MUST show:
- its label;
- the stable account identifier its last-applied delivery named, with the profile name the operation's account table gives that identifier;
- that delivery's sequence and when the host applied it;
- the time of its last successful push;
- its last push error and when it occurred;
- its STATE.

STATE MUST be exactly one of the values below. Where more than one applies, the one listed first MUST be shown:
- `not-converted`: the host's last result was `not-converted`;
- `expired`: the host's last-applied delivery's access token has reached its expiry;
- `stale`: the host has had no successful push within `delivery.stale_after`, whose default MUST be 15 minutes;
- `lagging`: the service has issued a later delivery sequence than the one the host last applied;
- `current`: none of the above applies.

**Configuration.** The host list, `delivery.push_timeout`, `delivery.retry_interval` and `delivery.stale_after` MUST be configurable on the role holder. A listed host carries no delivery configuration beyond authorizing the role key, and, on macOS, the launch agent.

**Moving the role.** Moving the role MUST proceed in this order:
1. On the old holder, stop the delivery service, every agent session using the live credential, the rotation operation's schedule, and its refresh maintenance. From this step on, the old holder MUST NOT use the managed accounts' refresh tokens.
2. Copy to the new holder:
   - the account manager's stored snapshots;
   - the live credential;
   - the account-identity keys of the old holder's global state file, and nothing else from that file;
   - the operation's durable store;
   - the service stores and the host list;
   - the role key and the known-hosts record.
3. Remove every managed account's refresh token from the old machine.
4. Start the new holder. From this step, the new machine is the role holder.
5. Confirm with the status command that every listed host receives a delivery.

Step 3 MUST complete before step 4, so no two machines ever use the role holder's refresh tokens. Step 3 does not breach **Coexistence on the role holder**: by then the old machine is no longer the role holder. No listed host changes during a move. Hosts keep their last-applied delivery until the new holder pushes a later one.

Accepted and unfixed: a pushed access token stays usable until the next refresh on the role holder revokes it, or until it expires, whichever comes first. Removing a host from the host list does not invalidate a token already pushed to it. The service MUST NOT force a refresh to shorten that window.


## Proposal: Scenarios and constraints for ssh push

### Target specification files

- SPECIFICATION/scenarios.md
- SPECIFICATION/constraints.md

### Summary

Rewrite the enrolled-host scenario block for push (32 headings to 17: 19 removed, 2 renamed, 4 added). Remove the enrolment, client-authentication, forwarded-refusal, remote-session and enforcement-instruction scenarios. Add scenarios for an unverifiable host key, a returning host, Remote Control re-issue and a live login diverging from the selected account. Drop the central status view from the no-push-channel scenario. Update the platform dependencies and atomic-write exceptions in constraints.md.

### Motivation

Every load-bearing behaviour of the push design needs a Given/When/Then scenario, and the removed features must not leave scenarios behind. tests/heading-coverage.json and the generated tests/heading-coverage-debt.json are co-edited so every remaining or new heading maps to a test or a debt entry owned by an open carrier (overseer-aj577z, overseer-fdwat6, overseer-ky6u2l) or the follow-up overseer-w5h24j.

### Proposed Changes

In scenarios.md, replace every scenario from "## Scenario: A rotation on the role holder reaches every following host" through "## Scenario: An instruction decided before a host returns from silence is not served" with:

## Scenario: A rotation on the role holder reaches every following host

Given the role holder runs the rotation operation and the delivery service

And two other hosts are listed and converted

When the operation rotates the active account from one account to another

Then within two minutes each of those hosts' interactive credential holds the newly selected account's access token

And each of those hosts' global state file's account-identity keys name the newly selected account

And neither of those hosts made a rotation decision of its own

## Scenario: Moving the credential-rotation role changes nothing on an enrolled host

Given a listed host that has applied a delivery from the role holder

When the role is moved to another machine as contracts.md §"Enrolled-host delivery" **Moving the role** defines

Then the new holder's first push is applied by that host with no change to that host's configuration

And that host's configuration names neither role holder's hostname nor its address

## Scenario: A following host receives an access token and never a refresh token

Given a listed host whose interactive credential holds no refresh token

When the delivery service pushes a delivery to it

Then the host's interactive OAuth object is the delivered object and holds no refresh token

And every other top-level key the credential held before the delivery is unchanged

And the host's global state file's account-identity keys name the delivered account, with every other key unchanged

## Scenario: A refresh on the role holder is delivered and its exposure is measured

Given every following host is `current`

When an agent session on the role holder refreshes the live credential

Then the delivery service issues a delivery with a greater delivery sequence carrying the new access token and pushes it to every listed host

And the service did not invoke the token endpoint

And the status command shows each following host as `lagging` until its push is applied, and then shows when it was applied

## Scenario: The service refuses to push to a host whose host key it cannot verify

Given a listed host whose ssh host key does not match the role holder's known-hosts record

When the delivery service issues a delivery

Then it pushes nothing to that host and records a push error naming the host-key failure

And every other listed host receives the delivery

## Scenario: A token and identity that disagree produce no delivery

Given the live credential holds one account's access token while the global state file's account-identity keys name another account

When the delivery service reads them

Then the service issues no delivery

And it issues one once the access token and the identity keys name the same account

## Scenario: A stale delivery cannot move a host back

Given a listed host has applied delivery sequence 7

When a push carrying delivery sequence 6 reaches it

Then the host's credential and global state file are unchanged

And the apply step reports `stale-sequence`

## Scenario: A failed apply leaves the host on its previous delivery

Given a listed host has applied a delivery naming one account

When a push of a delivery naming another account reaches it and the global state file write fails

Then the credential and the global state file both hold their previous contents

And the apply step reports the delivery as `failed`

## Scenario: A push refuses to overwrite a host's own login

Given a listed host whose interactive credential holds a refresh token

When the delivery service pushes a delivery to it

Then the host's credential is unchanged

And the status command shows that host as `not-converted`

## Scenario: An unreachable enrolled host does not affect a rotation pass

Given a listed host that is powered off

When the rotation operation runs a pass that switches accounts

Then the pass completes and reports exactly as it would with no listed host

And every other listed host receives the new delivery without waiting for the powered-off host

And the status command shows the powered-off host as `stale` once `delivery.stale_after` has passed since its last successful push

## Scenario: A host that was unreachable receives the current delivery when it returns

Given a listed host that was powered off while the service issued deliveries 8 and 9

When the host becomes reachable again

Then within two minutes it holds delivery 9

And it never applies delivery 8

## Scenario: A stopped delivery service does not affect a rotation pass

Given the delivery service on the role holder is stopped

When the rotation operation runs a pass that switches accounts

Then the pass completes and reports exactly as it would with no listed host

## Scenario: An expired live credential is reported, not refreshed

Given the live credential's access token reaches its expiry and no agent session on the role holder refreshes it

When the operator runs the status command

Then it reports that the live credential has expired without replacement

And every following host whose last-applied delivery carried that token is shown as `expired`

And the delivery service has not invoked the token endpoint

## Scenario: The live login is delivered when it diverges from the selected account

Given the role holder's live credential and global state file both name account A

And the operation's published selection record names account B

When the delivery service issues a delivery

Then the delivery names account A and carries account A's access token

And the status command shows account A as live and account B as selected, marked `diverged`

## Scenario: The delivery sequence continues across a move of the role

Given the old role holder last issued delivery sequence 40

When the role is moved and the new holder issues its first delivery

Then that delivery carries a sequence greater than 40

And every following host applies it

## Scenario: An account switch re-issues Remote Control only where it stopped

Given a following host runs two agent sessions in tmux panes, one using Remote Control and one not

When a pushed delivery naming a different account is applied and the first pane shows that Remote Control stopped because the signed-in account changed

Then the service sends `/remote-control` to the first pane once

And it sends nothing to the second pane

## Scenario: A silent enrolled host is reported as stale

Given a converted listed host whose last-applied delivery has not expired and which has had no successful push within `delivery.stale_after`

When the operator runs the status command

Then that host is shown as `stale` with the time of its last successful push and its last push error

And the output contains no credential material


In scenarios.md "## Scenario: No push channel configured is reported", "Then the report and the central status view MUST state that alerts cannot be delivered" becomes "Then the report MUST state that alerts cannot be delivered".

In constraints.md, replace the paragraph beginning "Enrolled-host delivery is Linux-only on both ends in this revision." and its bullets and prerequisite sentence with:

Enrolled-host delivery runs on a Linux role holder and pushes to Linux and macOS listed hosts.
- The delivery service depends on: the role holder's account manager and live credential; the operation's host state directory; a per-user service manager; an ssh client, the role key and a known-hosts record; and the host list.
- A listed host depends on: an ssh server that authorizes the role key for the listed user; `python3`; its interactive credential and global state file; and, on macOS, the once-installed per-user launch agent and the login Keychain.

Each part MUST validate its prerequisites before the dependent action. Each part MUST NOT fall back to an unverified host key, a credential carrying a refresh token, or a refresh of its own.

and replace the paragraph beginning "The second and third exceptions within the caam operation are:" through its closing sentence with:

The second and third exceptions within the caam operation are:
- the apply step's writes of a listed host's interactive credential, global state file and applied-sequence record, and, on a macOS host, the push's write of the inbox file and the launch agent's write of the result file;
- on the role holder, the delivery service's writes of its delivery-sequence counter, its push state and the host list.

Both MUST meet the whole-file atomic-replacement guarantee of the paragraph beginning "Writes to the overseer's own stores". Neither inherits the warning-only fallback. A failed apply-step write of the interactive credential or the global state file restores the previous contents of both and is reported, as contracts.md §"Enrolled-host delivery" defines.
