---
topic: central-factory-selection
author: claude-opus-5-5:central-credential-service
created_at: 2026-11-16T07:29:04Z
---

## Proposal: The central rotation publishes a separate factory account selection under the same rules and floors

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

On every pass that publishes the interactive selection, account rotation also decides and publishes a FACTORY SELECTION: the managed account that factory credential consumers bill against until the next pass. It is chosen with the same eligibility, protection floors, weekly reserve and ranking as the interactive decision. It is never the interactive account, it keeps its incumbent while that incumbent stays eligible, and it is decided only after the interactive decision, which it cannot change. When no account qualifies, the record says so instead of naming a stale account. The record carries identity only, lives beside the interactive record, and the enrolled-host delivery service writes it onto every listed host.

### Motivation

Plan central-credential-service line 6 requires factory runs to choose among the managed accounts' setup tokens at dispatch, so one account at its limit does not stop a factory while another has headroom. The maintainer's original wording requires factory credentials to rotate centrally 'under a strategy independent of the interactive rotation' (research 005). Nothing central decides the factory account today. Each dispatcher ranks its own injected slots by short-window headroom, ignoring the protection floors this operation keeps. Between 2026-10-31 and 2026-11-14 that local ranking chose the anthropic-0 slot 1520 times, up to 99% weekly utilization, past the account's 10% protection floor and into the maintainer's paid extra usage (overseer-kzmmn7). Since 2026-11-14 a seat-side workaround has pinned every factory to anthropic-4, so factories do not switch at all. The maintainer's direction on 2026-11-16 was to keep caam's single-host approach across hosts and to switch the factories automatically. This proposal makes the central operation decide the factory account with the same rules that protect the interactive accounts, and publish it for every factory (overseer-shojan). The matching consumer change, that a dispatcher reads this record at run start in place of local ranking, belongs to livespec-orchestrator-beads-fabro's specification.

### Proposed Changes

1. In SPECIFICATION/spec.md §"Account rotation and quota supervision", insert these paragraphs immediately after the paragraph that begins **An identity the pass could not fully resolve MUST suppress publication rather than degrade it.**:

**The operation MUST decide and publish a separate FACTORY SELECTION.** A FACTORY CREDENTIAL CONSUMER is a credential consumer that runs unattended factory work against the managed accounts under separately-provisioned per-account credentials. On every pass that publishes the interactive selection, the operation MUST also decide one FACTORY ACCOUNT and publish it as a FACTORY SELECTION RECORD, whose shape and location are fixed by contracts.md §"The account-rotation operation". The factory decision MUST be made only after the interactive decision of that pass is final, and it MUST NOT change, delay or re-order any step of the interactive decision. A pass MUST select the same interactive account whether or not a factory selection is decided.

**The factory account MUST satisfy every rule that protects the accounts, and MUST NOT be the interactive account.** A managed account MAY be the factory account only when it is live-verified on that pass, it is not refusal-held, the zero-weekly disqualifier does not exclude it, its short-window remaining is above the short-window floor, its weekly remaining is above the weekly reserve, and, where it is protected, its usable headroom net of its own protection floor is above zero. The account selected for interactive use at the end of the pass MUST NOT be the factory account. A protection floor MUST NOT be released for the factory decision under any condition, including where no other account qualifies.

**The factory account MUST be kept while it qualifies, and replaced as soon as it does not.** Where the factory account published by the previous pass still satisfies every rule above, the operation MUST publish it again unchanged, so that factory consumers do not move between accounts on every pass. Where it no longer satisfies them, including where it has become the interactive account or has reached its protection floor, the operation MUST choose a new factory account among those that qualify, ranked by **Ranking** unchanged, so that the most perishable balance is spent first.

**Where no account qualifies, the factory selection MUST say so rather than name an account.** The operation MUST publish a factory selection record that names no account and states the reason, and MUST NOT leave a previously published factory account in place. A factory consumer that kept billing a stale factory account after it reached its floor would spend exactly the balance the floor exists to keep. This is the deliberate opposite of the interactive record's stale-but-complete rule. An identity the pass could not fully resolve for the interactive account MUST still suppress both publications, as stated above.

**The factory selection MUST carry identity only and MUST reach every listed host.** The factory selection record MUST carry no credential material, under **Publication MUST carry identity only**. The enrolled-host delivery service MUST write the current factory selection record onto every listed host at the fixed location contracts.md defines. It MUST do so on each push and whenever the factory selection changes, so that a factory consumer on any listed host reads the same selection the role holder published. Writing an identity-only record is not a sending of credential material, and the delivery service's credential rules are unchanged.

2. In SPECIFICATION/contracts.md §"The account-rotation operation", insert after the **Published selection record.** paragraph:

**Factory selection record.** The record required by spec.md **The operation MUST decide and publish a separate FACTORY SELECTION** MUST live beside the published selection record, at `factory-selected-account.json` in the same host state directory. It MUST be created with owner-only permissions and MUST be written atomically. It MUST carry exactly these fields: `profile` (the factory account's profile name, or `null`); `account_uuid` (its stable account identifier, or `null`); `written_at` (the UTC instant of the write); and `reason` (`null` when an account is named, otherwise a non-empty operator-facing string naming why no account qualifies). `profile` and `account_uuid` MUST be both present or both `null`. On every listed host, the enrolled-host delivery service MUST write the same record, byte for byte, at the same path under the receiving user's home, with the same permission and atomicity rules.

3. In SPECIFICATION/scenarios.md, add these scenarios after "## Scenario: Account rotation publishes identity while credential management provisions separately":

## Scenario: The factory selection never names the interactive account

```gherkin
Given anthropic-4 and anthropic-5 both qualify under every protection rule
And the pass selects anthropic-4 for interactive use
When the pass decides the factory selection
Then the factory selection record names anthropic-5
And it MUST NOT name anthropic-4
```

## Scenario: A factory account at its protection floor is replaced on the next pass

```gherkin
Given anthropic-0 is protected with a floor of 10 percent of its weekly allowance
And the previous pass published anthropic-0 as the factory account
And anthropic-0 now holds 10 percent weekly remaining
And anthropic-6 qualifies under every protection rule and is not the interactive account
When the next pass runs
Then the factory selection record names anthropic-6
And no operator action was taken
```

## Scenario: A qualifying factory account is kept rather than moved

```gherkin
Given the previous pass published anthropic-5 as the factory account
And anthropic-5 still qualifies under every protection rule and is not the interactive account
And anthropic-6 qualifies and resets sooner
When the next pass runs
Then the factory selection record still names anthropic-5
```

## Scenario: No qualifying factory account publishes a reason instead of a stale account

```gherkin
Given the previous pass published anthropic-5 as the factory account
And every managed account other than the interactive account is at or below its protection floor or the weekly reserve
When the next pass runs
Then the factory selection record names no account
And its reason states that no account qualifies
And no protection floor was released
```

## Scenario: The interactive selection is unchanged by the factory decision

```gherkin
Given a set of managed accounts and readings
When one pass runs with the factory decision and another runs on the same readings without it
Then both passes MUST select the same interactive account
```

## Scenario: The factory selection reaches every listed host

```gherkin
Given the role holder publishes a factory selection naming anthropic-5
When the delivery service pushes to a listed host
Then that host holds factory-selected-account.json naming anthropic-5, identical to the role holder's record
And the record carries no credential material
```
