---
topic: central-credential-service-login-health
author: claude-opus-5-5 (central-credential-service)
created_at: 2026-11-10T20:33:28Z
---

## Proposal: A dark active login is a rotation trigger, and the pass that detects it does not depend on any login

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Add a dead-login rotation trigger to section Account rotation and quota supervision: when the active account's login is dark (refused as unrenewable or revoked, or its unexpired credential refused as unauthenticated), the operation rotates to a live-verified account at once, holds the dark account out of selection until a new login is recorded for it, and the scheduled pass that makes this decision is started without needing any provider login. Eligibility and ranking are unchanged. contracts.md gains a host-started schedule on the role holder.

### Motivation

Maintainer ruling 2026-11-10 (plan central-credential-service, DoD assertion 12): an expired or dark login is an automatic rotation trigger. Evidence, 2026-11-10 (caam-anthropic-loop-runner and legacy-coordinator-agent, account labels only): anthropic-3, the ACTIVE account, reached its login lifetime cap at about 15:14Z (provider message: the login reached its time limit and cannot be renewed). About 25 local seats stalled for about 4.5 h while anthropic-4 stayed healthy and usable throughout. The first pass to see the dark login ran at 19:38:48Z, because the scheduled passes did not run between about 14:42Z and 19:38Z: the session that drives them was itself on the dark login. anthropic-2 had reached the same cap at about 2026-11-09T14:12Z. The rotation trigger list has no trigger for a dead login: a dark account still reads as having allowance, so no usage trigger fires. This adds a TRIGGER and a HOLD; it changes no eligibility or ranking rule, so the hold that keeps caam selection rules unchanged until the central instance is proven stands.

### Proposed Changes

In SPECIFICATION/spec.md section "Account rotation and quota supervision", insert the following two paragraphs immediately AFTER the paragraph that begins "**An account that is refusing requests MUST be left, and MUST NOT be returned to until its refusal has lapsed.**" and its two continuation paragraphs (the ones beginning "The operation MUST remember each attributed refusal" and "The refusal trigger fires only while the active account is refusal-held"), and BEFORE the paragraph that begins "**Which credential a refusing session used.**":

**A dark active login MUST be left at once.** An account's login is DARK when the provider will no longer accept it and no refresh can restore it. The operation MUST judge the active account's login dark when either of these holds on a pass: (a) a tracked session's transcript, local or forwarded from an enrolled host under **Forwarded refusals**, records the provider refusing that account's login as unrenewable or revoked, such as the refusal stating that the login reached its time limit and cannot be renewed, where that record is attributed to the account by every condition the usage-limit refusal clause above requires of an attributed refusal, AND, where the account's current login's mint time under **Login records** is `recorded`, was recorded after that mint time; or (b) the operation's own read-only reading of the active account is refused as unauthenticated while the live credential's access token has not reached its expiry, the operation then re-reads the live credential and finds it byte-identical to the one that was refused, and the reading on the next pass is refused the same way with that same credential still unchanged. A single refused reading MUST NOT judge a login dark under (b), because a refresh on the role holder revokes the previous access token at once and can race the reading. An access token that has merely reached its expiry is NOT a dark login, because the agent's own refresh may restore it. Detecting a dark login under (a) MUST NOT send any request of its own, and under (b) MUST use only the reading **Observation** already makes. A dark login MUST be treated as a rotation trigger on its own, alongside every trigger in **Rotation triggers**, whatever the account's usage figures report: on the next pass that judges it, the operation MUST rotate to a candidate that survives every rule of **Eligibility**, chosen by **Ranking**. Candidates MUST be compared on the weekly dimension, and the dark account's headroom MUST be taken as zero on every dimension. For the weekly reserve's release, a login-held active account MUST NOT count as a usable account above the reserve, and a login-held account MUST NOT count as able to serve now. The capacity test's release, which applies only where the active account is refusal-held, is NOT extended to a dark login: where every candidate fails the capacity test, the operation MUST hold, and the hold report MUST say so. A dark login MUST NOT be a ground for claiming a reset, because no reset restores a login. The trigger MUST NOT relax any per-account protection floor, the zero-weekly disqualifier, the cannot-serve-immediately disqualifier or the live-verification rule. Where no candidate survives, the operation MUST hold and MUST report that the active account's login is dark and that no account could be selected. A switch made under this trigger MUST be reported as such: the switch line MUST name the dark login as the reason, MUST state which of (a) or (b) judged it, and MUST state when.

An account whose login has been judged dark is LOGIN-HELD: it MUST NOT be selected as a candidate, on any pass, until a new login is recorded for it under **Login records**, and MUST NOT count as live-verified meanwhile. A reading or a reset claim MUST NOT release a login hold. The operation MUST remember the hold in its durable store, so that a restart does not return the fleet to a dark login.

Also in that section, in the paragraph that begins "**Trigger precedence.**", replace the words "Where several triggers fire on one pass, the refusal trigger and its dimension MUST govern;" with "Where several triggers fire on one pass, the dark-login trigger MUST govern; otherwise the refusal trigger and its dimension MUST govern;".

Also in that section, insert the following paragraph immediately BEFORE the paragraph that begins "**Fail loudly.**":

**On the role holder, the scheduled pass MUST NOT depend on a provider login.** On the machine holding the credential-rotation role, scheduled passes MUST be started as contracts.md §"The account-rotation operation" **A host-started schedule** requires, by a host scheduler or supervised process that needs no provider login, so that a dark active login cannot stop the pass that would rotate away from it. Such a pass MUST NOT be started by, or wait to be started by, an agent session that authenticates with any managed account. The refresh-maintenance sandbox that **The set of verifiable accounts MUST be actively maintained, not merely reported on.** requires is not such a dependency, because it exercises a stored credential rather than the live one, and its failure MUST NOT stop the pass.

In SPECIFICATION/contracts.md section "The account-rotation operation", in the paragraph that begins "**Schedule.**", replace the words "The operation MUST establish its own recurring schedule" with "Except as **A host-started schedule** provides, the operation MUST establish its own recurring schedule". Then insert this paragraph immediately AFTER that paragraph:

**A host-started schedule.** On the machine holding the credential-rotation role, the scheduled passes MUST be started by a host scheduler or by a supervised process that needs no provider login, invoking the operation with the scheduled marker as an argument, at the interval **Schedule** names. There the operation MUST NOT also establish the session schedule that **Schedule** describes, and its check for an existing schedule MUST find the host-started one, so that passes never overlap. **Schedule**'s session-held form remains in force only on a host that does not hold the role, until per-host operation is deprecated. A host-started pass has no agent caller: it MUST write its account table, and any failure line, where the operator-facing report and the central status view read them, and **Reporting** applies to whichever operator session presents them.

In SPECIFICATION/scenarios.md, append these scenarios at the end of the file:

## Scenario: A dark active login is left on the next pass

Given the active account's login has reached its lifetime cap, and a tracked session's transcript records the provider refusing it as unrenewable

And another managed account is live-verified and survives every eligibility rule

When the next scheduled pass runs

Then the operation MUST switch to that other account

And the switch line MUST name the dark login as the reason

And the dark account MUST NOT be selected again until a new login is recorded for it

## Scenario: An expired access token alone does not trigger a dark-login rotation

Given the active account's live access token has reached its expiry

And no transcript records a refusal of that login as unrenewable or revoked

When the next scheduled pass runs

Then the operation MUST NOT judge the login dark

## Scenario: A dark active login with no surviving candidate holds and reports

Given the active account's login is judged dark

And no other managed account survives the eligibility rules

When the scheduled pass runs

Then the operation MUST hold

And it MUST report that the active login is dark and that no account could be selected

## Scenario: One refused reading does not judge a login dark

Given the operation's reading of the active account is refused as unauthenticated while its access token is unexpired

And the live credential has changed by the time the operation re-reads it

When the pass completes

Then the operation MUST NOT judge the login dark

## Scenario: A login hold survives a restart

Given an account's login has been judged dark and no new login has been recorded for it

When the operation restarts and runs a pass

Then that account MUST NOT be selected

## Scenario: The rotation pass runs while every agent session's login is dark

Given the role holder's scheduled passes are host-started

And every agent session on the role holder authenticates with the active account, whose login is dark

When the scheduled time for a pass arrives

Then the pass MUST run

And it MUST rotate to a surviving live-verified account


## Proposal: Login records: mint time, age, death, and a warning ahead of the lifetime cap

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

The operation keeps a durable login record per account (mint time, how it is known, death time and cause), records a mint time through an explicit operator command at each new login, shows login age in its report and the central status view, and warns ahead of a configurable lifetime cap that is unset until measured.

### Motivation

Maintainer ruling 2026-11-10 (plan central-credential-service, DoD assertion 13): track each account's login age and warn AHEAD of the lifetime cap; because the cap's length is unknown, first record when each login is minted and when it dies. caam-anthropic-loop-runner reports that caam records no login mint time: its vault meta holds only a backup time that moves on every re-snapshot, and its listing shows access-token expiry, not login age. So no account currently has a known login age. The first known mint times are the maintainer's re-logins of anthropic-4 (about 19:46:38Z), anthropic-3 (about 19:49:05Z) and anthropic-2 (about 19:50-19:51Z) on 2026-11-10. Logins seen to die: anthropic-2 at about 2026-11-09T14:12Z and anthropic-3 at about 2026-11-10T15:14Z, both by the lifetime cap; their mint times are unknown. A token refresh rewrites the credential file just as a login does, so a new login cannot be told apart by watching the file: it has to be recorded at the moment the operator logs in.

### Proposed Changes

In SPECIFICATION/spec.md section "Account rotation and quota supervision", insert the following paragraphs immediately BEFORE the paragraph that begins "**Switching.**":

**Login records.** A LOGIN is one provider sign-in for an account, from the moment the operator completes it until the provider stops accepting it or a later login for that account replaces it. The operation MUST keep in its durable store, for every managed account, a record of its current login and of each past login, each carrying: its MINT TIME and how that time is known (`recorded` when taken at the login, `first-seen` when an account that has NEVER had a login record is given one, with the mint time set to that pass's time, which is a lower bound only); and, once it ends, its END TIME and END CAUSE (`dark`, with the evidence that judged it under the dark-login trigger, or `replaced`). The operation MUST provide an operator command that takes the credential from the configuration directory in which the operator has just completed a login for a named account, stores it as that account's stored credential through the store the operation already uses for stored credentials, and records that login with mint time `recorded`, taken as that credential file's write time where readable and otherwise the time the command ran, stating which. The command MUST NOT write the live credential; where the named account is the active one, the live credential changes only by the operator's own login or by **Switching**. That command MUST end the account's previous login as `replaced` unless it already ended, and MUST release any login hold on the account. Only this command releases a login hold; an account whose login has ended MUST NOT be given a `first-seen` record. A refresh of an existing login MUST NOT be recorded as a new login. Past login records MUST be kept for at least 365 days.

**Login age and the lifetime cap.** The operator-facing report MUST show, for every managed account, its current login's age and mint time, marked as a lower bound when the mint time is `first-seen`. The lifetime cap is a configurable duration that MUST be unset by default, because no cap length has been measured. While it is unset the report MUST state that the lifetime cap is not yet measured and MUST NOT warn. Once it is set, the report MUST warn for every account whose current login's age has reached the cap minus a configurable warning lead, whose default MUST be 48 hours. An age that is only a lower bound MUST still warn, because the true age is at least that. The login records MUST NOT influence eligibility or ranking: only the dark-login hold acts on selection.

In the same file, section "Enrolled-host credential delivery", in the paragraph that begins "**Central status view.**", add this item to the list after the item "every managed account's limits, as §\"Account rotation and quota supervision\" reports them;":

- every managed account's current login age, mint time and any lifetime-cap warning, as §"Account rotation and quota supervision" reports them;

In SPECIFICATION/scenarios.md, append these scenarios at the end of the file:

## Scenario: A recorded login shows its age in the report

Given the operator has completed a login for an account and run the record-login command

When the operation produces its report a day later

Then the report MUST show that account's login age as one day and its mint time as recorded

## Scenario: A refresh does not start a new login record

Given an account's login is recorded with a known mint time

When the agent refreshes that login's access token

Then the account's login record MUST keep its original mint time

## Scenario: Recording a new login replaces the old one and releases a login hold

Given an account is login-held after its login was judged dark

When the operator completes a new login for it and runs the record-login command

Then the previous login's record MUST end with cause dark or replaced

And the account MUST no longer be login-held

## Scenario: A first-seen login age is shown as a lower bound and still warns

Given the lifetime cap is set to 28 days and the warning lead is 48 hours

And an account's current login has mint time first-seen 27 days ago

When the operation produces its report

Then the report MUST mark that login's age as a lower bound

And it MUST warn that the login is approaching its lifetime cap

## Scenario: No lifetime-cap warning before the cap is measured

Given the lifetime cap setting is unset

When the operation produces its report

Then it MUST state that the lifetime cap is not yet measured

And it MUST NOT warn for any account's login age

## Scenario: A login approaching the measured cap is warned

Given the lifetime cap is set to 28 days and the warning lead is 48 hours

And an account's current login was minted 26 days and 1 hour ago

When the operation produces its report

Then it MUST warn that this account's login is approaching its lifetime cap


## Proposal: Push alerts to the maintainer for dark or near-cap logins and unusable factory credentials

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

The operation delivers push alerts through an operator-configured channel when a login nears its lifetime cap or goes dark, when a dark-login hold finds no candidate, and when a factory credential in a configured probe list probes unusable (judged from the reading, with rate limits inconclusive), with onset, repeat and recovery alerts, no credential material, observation-only probes, and reported delivery failures shown in the central status view.

### Motivation

Maintainer ruling 2026-11-10 (plan central-credential-service, DoD assertion 14): a PUSH ALERT to the maintainer, not only the central view, when an account nears dark, or when any tenant's factory credential probes unusable. On 2026-11-10 the shared SSM token used by homelab and hetzner-xubuntu-info (/homelab/v1/providers/anthropic/claude-code/oauth-token) probed 429 exhausted, and that surfaced only through a dispatcher survey. The same day's dark login stalled about 25 seats for about 4.5 h with no alert at all. A status view only helps someone who is already looking.

### Proposed Changes

In SPECIFICATION/spec.md section "Account rotation and quota supervision", insert the following paragraphs immediately BEFORE the paragraph that begins "**Fail loudly.**" (and after the paragraph "**On the role holder, the scheduled pass MUST NOT depend on a provider login.**" where that proposal is also accepted):

**Push alerts.** The operation MUST deliver an alert to the maintainer through an operator-configured PUSH CHANNEL, separate from its report and the central status view, at the onset of each of these conditions: a login is judged dark; a lifetime-cap warning starts for a login under **Login age and the lifetime cap**; the operation holds because a dark login left no surviving candidate; and a probed factory credential becomes unusable under **Factory credential probes**. It MUST also deliver one recovery alert when such a condition ends. While a condition persists, it MUST repeat the alert once per configurable repeat interval, whose default MUST be six hours, and not more often. An alert MUST name the condition, the account label or the probed credential's label and owning tenant, and when the condition started, and MUST NOT contain any credential material. Delivering an alert MUST NOT depend on any provider login. A failed delivery MUST be reported as a failure in the report and the central status view and retried on the next pass; it MUST NOT block, delay or undo a rotation. Where no push channel is configured, the report and the central status view MUST state that alerts cannot be delivered.

**Factory credential probes.** The operation MUST probe every factory credential named in a configured PROBE LIST. Each entry names a label, its owning tenant, and a location the role holder can read it from; the list MUST NOT hold credential values. On the first scheduled pass after a configurable probe interval has elapsed since its last probe, whose default MUST be one hour, the operation MUST exercise each listed credential with one read-only authenticated reading of the kind **Observation** already makes. It MUST judge the credential UNUSABLE when that reading is refused as unauthenticated, when the reading itself shows its weekly or short-window remaining at zero, or when the credential cannot be read from its location. A rate-limited or failed request MUST be judged INCONCLUSIVE, reported, and not alerted, because the usage endpoint backs off a repeatedly read token and its refusal is not evidence that the credential is exhausted. A probe is observation only: it MUST NOT refresh, rewrite or rotate the probed credential, MUST NOT change any credential record's lifecycle state that §"LLM provider credential management" owns, and MUST NOT influence the selection of the interactive account. The report and the central status view MUST show each probed credential's label, tenant, last probe time and verdict.

In the same file, section "Enrolled-host credential delivery", in the paragraph that begins "**Central status view.**", add these items to the list, after the login-record item where that proposal is also accepted:

- each probed factory credential's label, owning tenant, last probe time and verdict;
- every push alert that could not be delivered, and a statement that alerts cannot be delivered while no push channel is configured;

In SPECIFICATION/scenarios.md, append these scenarios at the end of the file:

## Scenario: A dark login raises one push alert at onset

Given a push channel is configured

When the operation judges the active account's login dark

Then it MUST deliver one push alert naming that account and the dark login

And the alert MUST NOT contain any credential material

## Scenario: An exhausted factory credential raises a push alert

Given the probe list names a tenant's factory credential

And that credential's probe reading shows its weekly remaining at zero

When the probe runs

Then the operation MUST deliver a push alert naming that credential's label and tenant

And the report MUST show that credential as unusable

## Scenario: A failed alert delivery is reported and does not block rotation

Given the push channel is unreachable

And the active account's login is judged dark while another account is live-verified and eligible

When the scheduled pass runs

Then the operation MUST rotate to the other account

And it MUST report that the alert could not be delivered

## Scenario: A persisting condition is not re-alerted before the repeat interval

Given a probed factory credential has been unusable since an alert was delivered one hour ago

And the repeat interval is six hours

When the next probe again finds it unusable

Then the operation MUST NOT deliver another alert for that condition

## Scenario: A rate-limited probe is inconclusive and not alerted

Given the probe list names a factory credential

And its probe request is rate limited

When the probe runs

Then the operation MUST report that credential's verdict as inconclusive

And it MUST NOT deliver a push alert for it

## Scenario: A credential that cannot be read from its location is unusable

Given the probe list names a factory credential whose location the role holder cannot read

When the probe runs

Then the operation MUST judge it unusable and deliver a push alert naming its label and tenant

## Scenario: A recovered condition sends one recovery alert

Given a push alert was delivered because a probed factory credential was unusable

When a later probe finds that credential usable

Then the operation MUST deliver one recovery alert for that credential

## Scenario: No push channel configured is reported

Given no push channel is configured

When the operation produces its report

Then the report and the central status view MUST state that alerts cannot be delivered

