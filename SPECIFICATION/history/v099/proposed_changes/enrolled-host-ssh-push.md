---
topic: enrolled-host-ssh-push
author: claude-opus-5-5
created_at: 2026-11-13T09:35:51Z
---

## Proposal: Enrolled-host delivery by ssh push

### Target specification files

- SPECIFICATION/spec.md

### Summary

Replace the pull design (HTTPS delivery service, enrolment credentials, a client on every host, report store, audit log) with a delivery service that pushes each delivery over ssh to every host in a role-holder-held host list; add Remote Control re-issue after an account switch, on listed hosts and on the role holder; reduce the central status view to a status command; defer its login-age, factory-probe and alert rows, forwarded refusals and remote sessions. The service delivers only the role holder's live login, never the published selection, and the status command shows and flags a divergence between them.

### Motivation

This is the RE-CUT of the enrolled-host-ssh-push proposal that #2960 ratified as v096 on its own branch, where it collided with master's own v096 (f2e83487). It is re-filed against master at v098 with the text the earlier revise and its two graded amendments produced, so it carries those modifications as proposed text rather than as revise-time edits. Implementations already merged against it: #2962 (push over ssh and the status command) and #2979 (the delivered account is confirmed, with retry on a failed confirmation). Maintainer ruling 2026-11-12 on plan central-credential-service (epic overseer-iyfjbo): topology B (one central custodian of each account's login, hosts receive access tokens only), delivered by ssh push for speed, with no host-installed client and no enrolment. The pull design's transport, enrolment and client work (P1-B2..D) failed twice in the factory and is superseded. Claude Code stops Remote Control on an account change, so the maintainer chose automatic re-issue. The coordinator measured caam's live login diverging from its published selection three times on 2026-11-11 and 2026-11-12, so the delivery source is pinned to the live credential.

### Proposed Changes

In spec.md §"Enrolled-host credential delivery", replace the 5 consecutive paragraphs from the one beginning "**Components.** Enrolled-host delivery is a component of the account-rotation operation. I" through the one beginning "**The one source.** The delivery service MUST read credential material from exactly one pl" with:

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


In spec.md §"Enrolled-host credential delivery", replace the 5 consecutive paragraphs from the one beginning "**Delivery follows the live credential.** The service MUST observe the live credential con" through the one beginning "**Applying a delivery swaps the credential and identity only.** When the client applies a " with:

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


In spec.md §"Enrolled-host credential delivery", replace the 2 consecutive paragraphs from the one beginning "**Deliveries never move backwards.** Every delivery MUST carry a DELIVERY SEQUENCE number " through the one beginning "**Delivery is not the request path.** The delivery service and the client MUST NOT carry, " with:

**Deliveries never move backwards.** Every delivery MUST carry a DELIVERY SEQUENCE number strictly greater than the number of every delivery the service issued before it. The sequence MUST continue across a move of the role. The apply step MUST apply a delivery only when its delivery sequence is greater than the one the host last applied, so a delayed or retried push cannot move a host back to an earlier account or an earlier token.

**Remote Control follows an account switch.** Claude Code stops a session's Remote Control when the signed-in account changes. After a following host applies a delivery that names a different account from the one it last applied, the service MUST re-issue Remote Control on that host in every agent session whose terminal shows Claude Code's account-changed notice (in Claude Code 2.1.323, `signed-in claude.ai account or organization changed on this machine — run /remote-control` in the transcript, or `/rc failed` in the footer) and whose input box holds no unsubmitted text, as contracts.md §"Enrolled-host delivery" defines. The service MUST apply the same re-issue to the role holder's own agent sessions after the rotation operation switches the live credential to a different account. It MUST NOT start Remote Control in any other session. The re-issue is advisory and best-effort: its failure MUST be reported and MUST NOT undo the delivery or fail a rotation pass.

**Delivery is not the request path.** The delivery service and the apply step MUST NOT carry, relay or observe inference traffic. Each following host's sessions MUST authenticate directly to the provider with the delivered access token.


In spec.md §"Enrolled-host credential delivery", replace the 6 consecutive paragraphs from the one beginning "**Enrolment.** A host's ENROLMENT is an enrolment credential that the role holder issued f" through the one beginning "A host that has not reported within `delivery.stale_after` MUST NOT be shown as `current`." with:

**The host list is held only on the role holder.** Adding a host to delivery MUST be one entry in the host list. A listed host MUST NOT hold the role holder's address, the role name, or any credential for the role holder: the role holder reaches the host, and the host never reaches the role holder. The push authenticates to each host with the ROLE KEY, which moves with the role, so moving the role MUST NOT require any change on a listed host.

**Least privilege.** A listed host MUST NOT be able to read anything on the role holder, including the account manager's stored snapshots, any refresh token, or the service stores. The host list and the service stores MUST contain no credential material. The role key MUST be readable only by the role holder's operating user.

**Status command.** The delivery service MUST provide one operator command on the role holder that shows delivery state and contains no credential material. It MUST show whether the live credential has expired without replacement; the account the live credential holds and the account the operation's published selection record names, flagging when they differ; and, for each listed host, the fields and STATE that contracts.md §"Enrolled-host delivery" defines. A host that has had no successful push within `delivery.stale_after` MUST NOT be shown as `current`. It MUST be shown as `stale` unless a state listed before `stale` applies.

**Deferred to a later revision.** This revision does not define rows in the status command for account limits, login age and lifetime-cap warnings, factory credential probes or undelivered push alerts; the rotation operation's clauses on these are unchanged. Refusals forwarded from listed hosts, and tracking and model enforcement of sessions on listed hosts, are deferred as §"Account rotation and quota supervision" **Forwarded refusals** and **Remote sessions** state, until the follow-up plan opened once push runs on every reachable Linux host.


## Proposal: Account rotation clauses follow the push design

### Target specification files

- SPECIFICATION/spec.md

### Summary

Replace the role name and enrolment clauses of the account-rotation section with the host-list equivalents, defer forwarded refusals and remote-session tracking to a later revision, and bind push alerts and factory credential probes to the report only, since the central status view no longer carries those rows.

### Motivation

Under ssh push no host reaches the role holder, so the DNS role name and enrolment have no referent, and without a host client there are no host reports to carry forwarded refusals or remote sessions. The maintainer deferred those two features (F and G) to the follow-up plan opened once push runs on every reachable Linux host, which reopens them. The status command replaces the central status view and carries no alert or probe rows.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", replace the paragraph beginning "**Scope.** `caam-anthropic-loop` is the account-rotation operation governed by this sectio" with:

**Scope.** `caam-anthropic-loop` is the account-rotation operation governed by this section. It is identity-only, except for the delivery defined in §"Enrolled-host credential delivery".
- The ROLE HOLDER is the machine that holds the CREDENTIAL-ROTATION ROLE: the one machine currently assigned that role, which holds the managed accounts' logins, runs the rotation operation and pushes deliveries. Where no host list is configured on it, there are no listed hosts, which is the single-host behaviour this section had before delivery.
- The operation MUST observe every account that the coding-agent account manager tracks on the role holder, and MUST report those accounts' remaining quota.
- When the active account's allowance is nearly spent, the operation MUST rotate the role holder's host-wide active credential.
- Every FOLLOWING HOST, as defined in §"Enrolled-host credential delivery", receives that rotation through the delivery defined there.


In spec.md §"Account rotation and quota supervision", replace the 3 consecutive paragraphs from the one beginning "**One decision, on the role holder.** Only an instance of the operation running on the rol" through the one beginning "**Enrolment does not change the selection rules.** Enrolling or removing a host MUST NOT c" with:

**One decision, on the role holder.** Only an instance of the operation running on the role holder MAY make a rotation decision that a listed host follows, and the decision lock defined under **Switching** serializes those decisions. A listed host MUST NOT make a rotation decision of its own. Every delivery MUST name the account that is active on the role holder, so every following host uses that account. Delivering different accounts to different hosts would change the selection rules, and this section does NOT authorize it.

**The role, never a hostname.** Every provisioning artifact MUST name the credential-rotation role, never a machine's hostname, as the place the rotation runs.
- A listed host's configuration MUST NOT name the role holder at all, because the role holder pushes to the host and the host never reaches the role holder.
- Moving the role to another machine MUST NOT require any change on a listed host.

**Listing a host does not change the selection rules.** Adding or removing a listed host MUST NOT change any rule by which the operation ranks, selects, holds or rotates accounts, and MUST NOT be treated as a reason to alter any threshold, reserve or margin: the usage figures the operation reads are account-wide and already count every host's use. In this revision, listing a host does not widen the set of sessions whose refusals and models those rules observe; **Forwarded refusals** and **Remote sessions** state that deferral.


In spec.md §"Account rotation and quota supervision", replace the 3 consecutive paragraphs from the one beginning "The operation MUST attribute a refusal to the active account only when ALL of these hold: " through the one beginning "**Forwarded refusals.** A FORWARDED refusal is a refusal record that an enrolled-host clie" with:

The operation MUST attribute a refusal to the active account only when ALL of these hold: it was recorded by a tracked session of the same provider as the active account; that session authenticates with the role holder's live credential, as **Which credential a refusing session used** below establishes; where the record names an account identity, that identity is the active account's stable identifier; it was recorded after the moment the operation last observed that account become active, which the operation MUST keep in its durable store; and its reported reset time does not match, within the one-minute tolerance, the reset time of the same window as last read on any DEPARTED ACCOUNT, since concurrent sessions MAY still be spending a departed account's credential for a while after a switch, and their refusals belong to it. Whenever the operation records an activation time, whatever trigger the departure was made on and whether or not the operation made the switch itself, it MUST store in its durable store a DEPARTED ENTRY holding the short-window and weekly reset times last read on the account the previous activation time named, MUST keep that entry until the later of its stored reset times has passed, and MUST drop an account's entry when that account becomes active again. A DEPARTED ACCOUNT is any account with a kept departed entry other than the active account, so an account returned to is never compared with its own reset times. A refusal that reported no reset time never matches. Two residuals are accepted and not corrected: a lagging session's rate-limit refusal, whose reset is derived from its own retry-after interval, cannot match and MAY be attributed to the new account, bounded by its own short hold; and a genuine refusal of the new account whose reset coincides within a minute with a departed account's is not attributed, which fails safe because every other trigger still applies. Where no activation time is stored, or the stored one names a different account from the active account, the operation MUST record the current pass's time as the active account's activation time and MUST attribute no refusal on that pass rather than guess. A refusal recorded by a credential consumer outside the tracked sessions is outside what the operation can observe and MUST NOT be inferred.

**Which credential a refusing session used.** The operation MUST establish the credential conjunct above as follows, so that neither a separately provisioned credential nor the operation's own refresh-maintenance sandbox, whose sessions exercise other accounts' stored credentials and MUST NOT be read for refusals, can contribute:
- For a session on the role holder, the session's agent configuration directory MUST be the role holder's default directory, the one holding the live credential.
- A session on a listed host is not a tracked session in this revision, so no refusal it records is attributed.

**Forwarded refusals.** Deferred to a later revision, reopened by the follow-up plan opened once push runs on every reachable Linux host. In this revision no refusal is forwarded from a listed host, and the operation observes refusals only from tracked sessions on the role holder. Until then, a refusal on a listed host reaches the operation only through the account-wide usage readings.


In spec.md §"Account rotation and quota supervision", replace the paragraph beginning "**A dark active login MUST be left at once.** An account's login is DARK when the provider" with:

**A dark active login MUST be left at once.** An account's login is DARK when the provider will no longer accept it and no refresh can restore it. The operation MUST judge the active account's login dark when either of these holds on a pass: (a) a tracked session's transcript records the provider refusing that account's login as unrenewable or revoked, such as the refusal stating that the login reached its time limit and cannot be renewed, where that record is attributed to the account by every condition the usage-limit refusal clause above requires of an attributed refusal, AND, where the account's current login's mint time under **Login records** is `recorded`, was recorded after that mint time; or (b) the operation's own read-only reading of the active account is refused as unauthenticated while the live credential's access token has not reached its expiry, the operation then re-reads the live credential and finds it byte-identical to the one that was refused, and the reading on the next pass is refused the same way with that same credential still unchanged. A single refused reading MUST NOT judge a login dark under (b), because a refresh on the role holder revokes the previous access token at once and can race the reading. An access token that has merely reached its expiry is NOT a dark login, because the agent's own refresh may restore it. Detecting a dark login under (a) MUST NOT send any request of its own, and under (b) MUST use only the reading **Observation** already makes. A dark login MUST be treated as a rotation trigger on its own, alongside every trigger in **Rotation triggers**, whatever the account's usage figures report: on the next pass that judges it, the operation MUST rotate to a candidate that survives every rule of **Eligibility**, chosen by **Ranking**. Candidates MUST be compared on the weekly dimension, and the dark account's headroom MUST be taken as zero on every dimension. For the weekly reserve's release, a login-held active account MUST NOT count as a usable account above the reserve, and a login-held account MUST NOT count as able to serve now. The capacity test's release, which applies only where the active account is refusal-held, is NOT extended to a dark login: where every candidate fails the capacity test, the operation MUST hold, and the hold report MUST say so. A dark login MUST NOT be a ground for claiming a reset, because no reset restores a login. The trigger MUST NOT relax any per-account protection floor, the zero-weekly disqualifier, the cannot-serve-immediately disqualifier or the live-verification rule. Where no candidate survives, the operation MUST hold and MUST report that the active account's login is dark and that no account could be selected. A switch made under this trigger MUST be reported as such: the switch line MUST name the dark login as the reason, MUST state which of (a) or (b) judged it, and MUST state when.


In spec.md §"Account rotation and quota supervision", replace the paragraph beginning "**Remote sessions are tracked sessions.** A session that an enrolled-host client reports i" with:

**Remote sessions.** Deferred to a later revision, reopened by the follow-up plan opened once push runs on every reachable Linux host. In this revision a session on a listed host is not a tracked session: it arms no trigger through its observed model, and enforcement drives only sessions on the role holder.


In spec.md §"Account rotation and quota supervision", replace the 2 consecutive paragraphs from the one beginning "**Push alerts.** The operation MUST deliver an alert to the maintainer through an operator" through the one beginning "**Factory credential probes.** The operation MUST probe every factory credential named in " with:

**Push alerts.** The operation MUST deliver an alert to the maintainer through an operator-configured PUSH CHANNEL, separate from its report and the status command, at the onset of each of these conditions: a login is judged dark; a lifetime-cap warning starts for a login under **Login age and the lifetime cap**; the operation holds because a dark login left no surviving candidate; and a probed factory credential becomes unusable under **Factory credential probes**. It MUST also deliver one recovery alert when such a condition ends. While a condition persists, it MUST repeat the alert once per configurable repeat interval, whose default MUST be six hours, and not more often. An alert MUST name the condition, the account label or the probed credential's label and owning tenant, and when the condition started, and MUST NOT contain any credential material. Delivering an alert MUST NOT depend on any provider login. A failed delivery MUST be reported as a failure in the report and retried on the next pass; it MUST NOT block, delay or undo a rotation. Where no push channel is configured, the report MUST state that alerts cannot be delivered.

**Factory credential probes.** The operation MUST probe every factory credential named in a configured PROBE LIST. Each entry names a label, its owning tenant, and a location the role holder can read it from; the list MUST NOT hold credential values. On the first scheduled pass after a configurable probe interval has elapsed since its last probe, whose default MUST be one hour, the operation MUST exercise each listed credential with one read-only authenticated reading of the kind **Observation** already makes. It MUST judge the credential UNUSABLE when that reading is refused as unauthenticated, when the reading itself shows its weekly or short-window remaining at zero, or when the credential cannot be read from its location. A rate-limited or failed request MUST be judged INCONCLUSIVE, reported, and not alerted, because the usage endpoint backs off a repeatedly read token and its refusal is not evidence that the credential is exhausted. A probe is observation only: it MUST NOT refresh, rewrite or rotate the probed credential, MUST NOT change any credential record's lifecycle state that §"LLM provider credential management" owns, and MUST NOT influence the selection of the interactive account. The report MUST show each probed credential's label, tenant, last probe time and verdict.


## Proposal: Enrolled-host delivery wire contract for ssh push

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Replace contracts.md §"Enrolled-host delivery" with the host list, ssh transport with the role key and verified host keys, the stdin apply step and its result line, the macOS inbox, launch agent and result file, retry and timeouts, Remote Control re-issue over tmux, push-state stores, the status command and its STATE values, configuration, and the move-the-role order. The Remote Control re-issue names Claude Code 2.1.323's two observed forms of the account-changed notice and identifies a Claude Code pane by its executable.

### Motivation

The wire contract must match the ssh-push design ratified in the spec.md finding. The Remote Control clause is corrected against a real account switch captured on 2026-11-13 under Claude Code 2.1.323 (maintainer-approved, relayed by caam-anthropic-loop-runner; recorded on epic overseer-iyfjbo at 05:25Z): the transcript line reads '● Remote Control disconnected — signed-in claude.ai account or organization changed on this machine — run /remote-control to start a session for the current account, or /login to switch back, then /remote-control', the footer shows only '/rc failed', and tmux reports the pane's current command as '2.1.323', not 'claude'. The previous text's footer form ('Remote Control failed · ' plus the notice, taken from 2.1.322) and its current-command pane filter both missed that real output, which is the recorded drift the clause itself says is corrected by revision.

### Proposed Changes

In contracts.md §"Enrolled-host delivery", replace the 2 consecutive paragraphs from the one beginning "**Transport.**" through the one beginning "**Authentication in both directions.**" with:

**Host list.** The host list is a file in the operation's host state directory on the role holder, created owner-only and written atomically. Each entry names:
- a LABEL, unique in the list;
- an SSH DESTINATION of the form `user@host`;
- a PLATFORM, `linux` or `macos`.

The host list MUST NOT hold credential material. Removing an entry stops delivery to that host on the next push.

**Transport.** The service MUST push over ssh to each entry's ssh destination, authenticating with the ROLE KEY: an ssh key pair held owner-only on the role holder that moves with the role. Each listed host MUST authorize the role key for its listed user. The service MUST verify each host's ssh host key against the role holder's known-hosts record and MUST NOT push to a host whose host key it cannot verify. The delivery MUST travel on the ssh session's standard input, never in a command-line argument, an environment variable or any file on the role holder; the service holds the delivery only in memory.


In contracts.md §"Enrolled-host delivery", replace the 25 consecutive paragraphs from the one beginning "**Operations.** The service MUST expose exactly three operations to an enrolled host:" through the one beginning "Step 4 MUST complete before step 5, so no two machines ever use the role holder's refresh " with:

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

**Remote Control re-issue.** After a push whose result is `applied` and whose account differs from the one that host last applied, the service MUST, over the same ssh destination, read the visible text, with wrapped lines joined, of every tmux pane on the host whose foreground process is Claude Code and which is not in a tmux mode such as copy mode. A pane MUST be identified as Claude Code by the executable its foreground process runs, never by tmux's current-command name alone: Claude Code 2.1.323 reports its version number, such as `2.1.323`, as that name. The trigger is the ACCOUNT-CHANGED NOTICE: what Claude Code renders when the signed-in account changes under a running session on a pushed credential. In Claude Code 2.1.323, the version a real account switch was captured from on 2026-11-13, it takes either of two forms. In the transcript, a line carries `Remote Control disconnected — ` followed by the notice text `signed-in claude.ai account or organization changed on this machine — run /remote-control`, behind the transcript's leading status mark. In the footer below the input box, the Remote Control status reads `/rc failed`, without the notice text. The service MUST match the transcript notice text as part of a line, never as a whole line, and MUST accept the footer status in place of the transcript line, because the transcript line can scroll out of the visible text. Neither form may be matched by its leading mark or glyph. In each such pane where the notice appears, no submitted `/remote-control` prompt line follows it, and the input box holds no unsubmitted text, it MUST send `/remote-control` followed by Enter, once for that delivery. A pane whose input box holds unsubmitted text MUST be skipped, never typed into. It MUST send nothing to any other pane, including a pane that merely displays the notice text in a shell, a pager or another program. A Claude Code release that changes either form is a recorded drift from the version named here, corrected by revising this clause, never a silent miss: the re-issue's test evidence MUST include at least one fixture that is a real `tmux capture-pane -p -J` capture of a pane taken after a real account switch, naming the Claude Code version it was captured from. After it issues a delivery naming a different account from the previous delivery, the service MUST apply the same re-issue, locally, to the role holder's own tmux panes. A session that does not run in tmux is outside what the service can reach, which is accepted and unfixed.

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

Rewrite the enrolled-host scenario block for push: remove the 21 enrolment, client, forwarded-refusal, remote-session and enforcement-instruction scenarios, add 8 (an unverifiable host key, a failed apply, a host's own login, a returning host, a live login diverging from the selected account, Remote Control re-issue on listed hosts and on the role holder, and a macOS inbox apply), and re-word the rest for push. Drop the central status view from the no-push-channel scenario. Update the platform dependencies and atomic-write exceptions in constraints.md.

### Motivation

Every load-bearing behaviour of the push design needs a Given/When/Then scenario, and the removed features must not leave scenarios behind. tests/heading-coverage.json and tests/heading-coverage-debt.json are co-edited: the 21 removed headings' rows are deleted; the 8 added headings are owed by the open carriers overseer-aj577z, overseer-fdwat6 and overseer-7m6wu6; every surviving row keeps the open test-owner item master's 2026-11-13 coverage sweep (56eb7b4b) assigned it.

### Proposed Changes

Delete scenarios.md §"Scenario: A failed client write leaves the host on its previous delivery" (heading and body).

Delete scenarios.md §"Scenario: The client refuses to overwrite a host's own login" (heading and body).

Delete scenarios.md §"Scenario: An enrolled host cannot read another host's delivery" (heading and body).

Delete scenarios.md §"Scenario: A valid enrolment presented from the wrong device is refused" (heading and body).

Delete scenarios.md §"Scenario: Revoking one host's enrolment leaves every other host served" (heading and body).

Delete scenarios.md §"Scenario: Enrolling a host under a label already in use is refused" (heading and body).

Delete scenarios.md §"Scenario: A revoked device can be enrolled again" (heading and body).

Delete scenarios.md §"Scenario: A revoked host's label cannot be reused for another device" (heading and body).

Delete scenarios.md §"Scenario: The client refuses a service it cannot authenticate" (heading and body).

Delete scenarios.md §"Scenario: A refusal on a following host rotates the active account" (heading and body).

Delete scenarios.md §"Scenario: A forwarded refusal under another account's delivery is not attributed" (heading and body).

Delete scenarios.md §"Scenario: A forwarded refusal from outside the host's default directory is not attributed" (heading and body).

Delete scenarios.md §"Scenario: A remote enforcement is recorded only once the client applies it" (heading and body).

Delete scenarios.md §"Scenario: A remote session on the scoped model arms the scoped-model trigger" (heading and body).

Delete scenarios.md §"Scenario: A silent host whose token has expired arms no trigger" (heading and body).

Delete scenarios.md §"Scenario: A refusal forwarded before a host falls silent is still attributed" (heading and body).

Delete scenarios.md §"Scenario: An enforcement instruction is applied at most once" (heading and body).

Delete scenarios.md §"Scenario: A client restarted after recording an instruction does not act on it again" (heading and body).

Delete scenarios.md §"Scenario: An instruction whose outcome was reported is never served again" (heading and body).

Delete scenarios.md §"Scenario: A superseded enforcement instruction is never served" (heading and body).

Delete scenarios.md §"Scenario: An instruction decided before a host returns from silence is not served" (heading and body).

Replace the whole body of scenarios.md §"Scenario: A rotation on the role holder reaches every following host" (heading kept verbatim) with:

Given the role holder runs the rotation operation and the delivery service

And two other hosts are listed and converted

When the operation rotates the active account from one account to another

Then within two minutes each of those hosts' interactive credential holds the newly selected account's access token

And each of those hosts' global state file's account-identity keys name the newly selected account

And neither of those hosts made a rotation decision of its own


Replace the whole body of scenarios.md §"Scenario: Moving the credential-rotation role changes nothing on an enrolled host" (heading kept verbatim) with:

Given a listed host that has applied a delivery from the role holder

When the role is moved to another machine as contracts.md §"Enrolled-host delivery" **Moving the role** defines

Then the new holder's first push is applied by that host with no change to that host's configuration

And that host's configuration names neither role holder's hostname nor its address


Replace the whole body of scenarios.md §"Scenario: A following host receives an access token and never a refresh token" (heading kept verbatim) with:

Given a listed host whose interactive credential holds no refresh token

When the delivery service pushes a delivery to it

Then the host's interactive OAuth object is the delivered object and holds no refresh token

And every other top-level key the credential held before the delivery is unchanged

And the host's global state file's account-identity keys name the delivered account, with every other key unchanged


Replace the whole body of scenarios.md §"Scenario: A refresh on the role holder is delivered and its exposure is measured" (heading kept verbatim) with:

Given every following host is `current`

When an agent session on the role holder refreshes the live credential

Then the delivery service issues a delivery with a greater delivery sequence carrying the new access token and pushes it to every listed host

And the service did not invoke the token endpoint

And the status command shows each following host as `lagging` until its push is applied, and then shows when it was applied


Add a new section `## Scenario: The service refuses to push to a host whose host key it cannot verify` immediately after §"Scenario: A refresh on the role holder is delivered and its exposure is measured" in scenarios.md, with body:

Given a listed host whose ssh host key does not match the role holder's known-hosts record

When the delivery service issues a delivery

Then it pushes nothing to that host and records a push error naming the host-key failure

And every other listed host receives the delivery


Replace the whole body of scenarios.md §"Scenario: A stale delivery cannot move a host back" (heading kept verbatim) with:

Given a listed host has applied delivery sequence 7

When a push carrying delivery sequence 6 reaches it

Then the host's credential and global state file are unchanged

And the apply step reports `stale-sequence`


Add a new section `## Scenario: A failed apply leaves the host on its previous delivery` immediately after §"Scenario: A stale delivery cannot move a host back" in scenarios.md, with body:

Given a listed host has applied a delivery naming one account

When a push of a delivery naming another account reaches it and the global state file write fails

Then the credential and the global state file both hold their previous contents

And the apply step reports the delivery as `failed`


Add a new section `## Scenario: A push refuses to overwrite a host's own login` immediately after §"Scenario: A failed apply leaves the host on its previous delivery" in scenarios.md, with body:

Given a listed host whose interactive credential holds a refresh token

When the delivery service pushes a delivery to it

Then the host's credential is unchanged

And the status command shows that host as `not-converted`


Replace the whole body of scenarios.md §"Scenario: An unreachable enrolled host does not affect a rotation pass" (heading kept verbatim) with:

Given a listed host that is powered off

When the rotation operation runs a pass that switches accounts

Then the pass completes and reports exactly as it would with no listed host

And every other listed host receives the new delivery without waiting for the powered-off host

And the status command shows the powered-off host as `stale` once `delivery.stale_after` has passed since its last successful push


Add a new section `## Scenario: A host that was unreachable receives the current delivery when it returns` immediately after §"Scenario: An unreachable enrolled host does not affect a rotation pass" in scenarios.md, with body:

Given a listed host that was powered off while the service issued deliveries 8 and 9

When the host becomes reachable again

Then within two minutes it holds delivery 9

And it never applies delivery 8


Replace the whole body of scenarios.md §"Scenario: A stopped delivery service does not affect a rotation pass" (heading kept verbatim) with:

Given the delivery service on the role holder is stopped

When the rotation operation runs a pass that switches accounts

Then the pass completes and reports exactly as it would with no listed host


Replace the whole body of scenarios.md §"Scenario: An expired live credential is reported, not refreshed" (heading kept verbatim) with:

Given the live credential's access token reaches its expiry and no agent session on the role holder refreshes it

When the operator runs the status command

Then it reports that the live credential has expired without replacement

And every following host whose last-applied delivery carried that token is shown as `expired`

And the delivery service has not invoked the token endpoint


Add a new section `## Scenario: The live login is delivered when it diverges from the selected account` immediately after §"Scenario: An expired live credential is reported, not refreshed" in scenarios.md, with body:

Given the role holder's live credential and global state file both name account A

And the operation's published selection record names account B

When the delivery service issues a delivery

Then the delivery names account A and carries account A's access token

And the status command shows account A as live and account B as selected, marked `diverged`


Add a new section `## Scenario: An account switch re-issues Remote Control only where it stopped` immediately after §"Scenario: The delivery sequence continues across a move of the role" in scenarios.md, with body:

Given a following host runs two agent sessions in tmux panes, one using Remote Control and one not

When a pushed delivery naming a different account is applied and the first pane shows Claude Code's account-changed notice `signed-in claude.ai account or organization changed on this machine — run /remote-control` inside its `Remote Control disconnected — ` transcript line, or only the `/rc failed` footer status

Then the service sends `/remote-control` to the first pane once

And it sends nothing to the second pane

And it sends nothing to a pane showing that notice whose input box holds unsubmitted text


Add a new section `## Scenario: An account switch re-issues Remote Control on the role holder's own sessions` immediately after §"Scenario: An account switch re-issues Remote Control only where it stopped" in scenarios.md, with body:

Given the role holder runs an agent session in a tmux pane that was using Remote Control

When the rotation operation switches the role holder's live login to a different account and that pane shows Claude Code's account-changed notice `signed-in claude.ai account or organization changed on this machine — run /remote-control`

Then the service sends `/remote-control` to that pane once

And it sends nothing to a role-holder pane that does not show that notice


Add a new section `## Scenario: A macOS host applies a delivery from its inbox and its result is recorded` immediately after §"Scenario: An account switch re-issues Remote Control on the role holder's own sessions" in scenarios.md, with body:

Given a listed `macos` host whose launch agent is installed

When the service pushes a delivery to that host

Then the delivery is written to the host's owner-only inbox file as a mode-0600 temporary file in the same directory that is then renamed into place

And the launch agent applies it to the login Keychain, deletes the inbox file and writes a result line to its owner-only result file

And on its next push or retry to that host the service records that result as the host's last result

And neither the result file nor the status command's output contains credential material


Replace the whole body of scenarios.md §"Scenario: A silent enrolled host is reported as stale" (heading kept verbatim) with:

Given a converted listed host whose last-applied delivery has not expired and which has had no successful push within `delivery.stale_after`

When the operator runs the status command

Then that host is shown as `stale` with the time of its last successful push and its last push error

And the output contains no credential material


Replace the whole body of scenarios.md §"Scenario: No push channel configured is reported" (heading kept verbatim) with:

Given no push channel is configured

When the operation produces its report

Then the report MUST state that alerts cannot be delivered


Replace the whole body of constraints.md §"Runtime requirements" (heading kept verbatim) with:

The overseer MUST support Linux with either tmux or herdr. Linux remains
required because session ownership and runtime identity use the process
filesystem. The two supported terminal backends MUST preserve the same
supervision guarantees; a backend boundary is permitted for their differing
terminal operations. This deliberately replaces the former tmux-only decision
and its prohibition on a terminal-multiplexer abstraction; it does not authorize
another operating-system backend or weaken the standard-library-only rule.

Backend selection MUST follow the nearest positively verified owning terminal
in the invoking process's ancestry. Verification MUST bind that ancestry to
the exact live backend instance and pane. Instance identity MUST include the
live server generation, proven by its process identity and start time or an
equivalent non-reusable identity; a socket path alone is insufficient because
server restarts may reuse that path and pane ids. An inherited environment variable,
process name alone, active tab, or focused pane MUST NOT establish ownership.
Nested terminals MUST select the nearest verified owner rather than an outer
terminal named by stale environment variables. If ownership is absent,
ambiguous, or unreadable, bootstrap MUST refuse before terminal mutation and
name the missing evidence; it MUST NOT guess or silently fall back to the other
backend. A selected backend whose required capabilities are unavailable MUST
fail closed before the dependent action, naming the failed capability.

On an unsupported host the daemon REFUSES to start and names exactly which
precondition failed. That check runs BEFORE every other startup gate, so an
unsupported host is never first reported as some downstream failure.

`llm-provider-manager` is likewise Linux-only. Its architecture depends on the
Linux process model, enforceable local ownership and modes, a user-scoped
kernel keyring, a host identity suitable for secret-store namespace binding,
the configured local SecretStore executable, an authenticated local agent CLI,
and a headed browser in a graphical session. The exact paths, permissions,
capability probes and failure mappings are defined once in contracts.md. The
manager MUST validate each prerequisite before its dependent action and MUST
NOT fall back to another operating system, plaintext secret storage, another
agent credential source, a bundled or cloud browser, or network-exposed browser
control.

Enrolled-host delivery runs on a Linux role holder and pushes to Linux and macOS listed hosts.
- The delivery service depends on: the role holder's account manager and live credential; the operation's host state directory; a per-user service manager; an ssh client, the role key and a known-hosts record; and the host list.
- A listed host depends on: an ssh server that authorizes the role key for the listed user; `python3`; its interactive credential and global state file; and, on macOS, the once-installed per-user launch agent and the login Keychain.

Each part MUST validate its prerequisites before the dependent action. Each part MUST NOT fall back to an unverified host key, a credential carrying a refresh token, or a refresh of its own.


Replace the whole body of constraints.md §"Atomicity and single instance" (heading kept verbatim) with:

This section governs only the supervision daemon's stores. The caam operation's
last-writer-wins publication and fail-loudly exit semantics are defined in
contracts.md §"The account-rotation operation"; the manager's fail-closed store,
audit and provisioning semantics are defined in contracts.md §"The LLM
credential-provider operation". Neither operation inherits the warning-only
fallback below.

The first of three exceptions within the caam operation is, on the role holder, its own writes of the host agent's global state file and settings file, and its restore of the credential, (spec.md §"Account rotation and quota supervision", **Installing an account MUST swap identity only**). Those writes and that restore MUST meet the whole-file atomic-replacement guarantee of the next paragraph, and they are serialized by the operation's switch lock rather than by this section's advisory locks. They do NOT inherit the warning-only fallback: a failed write restores the pre-switch state and fails the switch loudly, as that clause defines.

Writes to the overseer's own stores replace the whole file atomically: a
reader observes the previous or the new complete content, never a partial
write, even across a crash mid-write. Concurrent writers — the daemon and
one-shot operator commands — serialize through advisory locks. At most ONE
daemon instance runs per mapping store, enforced by a singleton lock taken
for the daemon's whole lifetime. Storage failures on the overseer's own
files degrade with a warning; they never crash the supervision loop.

The second and third exceptions within the caam operation are:
- the apply step's writes of a listed host's interactive credential, global state file and applied-sequence record, and, on a macOS host, the push's write of the inbox file and the launch agent's write of the result file;
- on the role holder, the delivery service's writes of its delivery-sequence counter, its push state and the host list.

Both MUST meet the whole-file atomic-replacement guarantee of the paragraph beginning "Writes to the overseer's own stores". Neither inherits the warning-only fallback. A failed apply-step write of the interactive credential or the global state file restores the previous contents of both and is reported, as contracts.md §"Enrolled-host delivery" defines.

