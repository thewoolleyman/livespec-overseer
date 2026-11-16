---
topic: caam-protection-from-committed-slot-declaration
author: claude-opus-5-5:central-credential-service
created_at: 2026-11-16T03:58:04Z
---

## Proposal: caam protects the committed slot declaration's accounts with no operator flag

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Account rotation reads the governing repository's committed dispatcher.claude_credential_policy on every pass and protects each account bound to a declared numbered slot with a whole-allowance floor, so the factory's slots are never selected for interactive spend without anyone typing --protected-account. A flag cannot lower or clear that protection. Every other protection floor, anthropic-0's included, keeps working exactly as today. A missing or unreadable declaration fails closed onto the stored floors and says so on the protected-accounts summary line.

### Motivation

On 2026-11-16 the maintainer asked why protecting accounts needed a hand-typed flag: 'Why do I need to do that? What is wrong with its default rules?' caam's defaults protect only anthropic-0 at a 10% floor, and caam knows nothing about the factory's setup-token slots. So its weekly-reserve rotation moved interactive spend onto anthropic-4 at 01:04:35Z, the one account the factory depends on. The fleet's account partition is now declared once, as livespec core's fleet-manifest claude_credential_partition, with each repository's dispatcher.claude_credential_policy as a conformance-enforced consumer copy. Rotation must read the same declaration the factory reads, rather than a separate set of operator flags that can disagree with it (plan central-credential-service, overseer-shojan).

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", insert this clause immediately after the paragraph that begins **A protection floor MUST NOT be released by the weekly reserve's release.**:

**Accounts the committed slot declaration reserves MUST be protected without an operator flag.** On every pass the operation MUST read the committed `dispatcher.claude_credential_policy` of the repository it runs from. Under mode `numbered-slots`, each declared slot `CLAUDE_CODE_OAUTH_TOKEN__<SLOT>` names the managed account whose profile is `<SLOT>` lower-cased with each underscore replaced by a hyphen (for example `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_4` names `anthropic-4`). The operation MUST protect each such account with a floor equal to its whole weekly allowance, so that it is never selected or retained for interactive spend. An operator protection flag MUST NOT lower or clear the protection of a declared account; an operator flag MAY add or change protection for any other account. Where the declaration is absent, is not mode `numbered-slots`, or does not parse, the operation MUST keep every stored protection floor, MUST NOT treat any account as unprotected on that ground, and MUST report on the protected-accounts summary line that the declaration was not applied and why. The protected-accounts summary line MUST distinguish an account protected by the declaration from an account protected by an operator flag or the default floor. Protection taken from the declaration MUST NOT be released by the weekly reserve's release, exactly as for any other protection floor.

In SPECIFICATION/scenarios.md, add these three scenarios after "## Scenario: A release on serveability grounds does not release a protection floor":

## Scenario: A declared factory slot is protected with no operator flag

```gherkin
Given the repository's committed dispatcher.claude_credential_policy declares mode numbered-slots with slots CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_4 and CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_5
And no operator protection flag has ever been passed
And anthropic-4 holds the most weekly headroom of any managed account
When a scheduled pass runs and a rotation trigger has fired on the active account
Then the operation MUST NOT select anthropic-4 or anthropic-5
And the protected-accounts summary line names anthropic-4 and anthropic-5 as protected by the declaration
```

## Scenario: An operator flag cannot clear a declared account's protection

```gherkin
Given the repository's committed dispatcher.claude_credential_policy declares slot CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_4
When an operator runs a pass with --protected-account=anthropic-4=off
Then anthropic-4 MUST remain protected with a whole-allowance floor
And the pass reports that the flag did not apply to a declared account
```

## Scenario: A missing slot declaration keeps the stored floors and says why

```gherkin
Given the stored protection floors are anthropic-0 at 10 percent and anthropic-4 at 100 percent
And the repository's committed dispatcher.claude_credential_policy is absent
When a scheduled pass runs
Then anthropic-4 MUST remain protected at its stored floor of 100 percent
And anthropic-0 keeps its stored floor of 10 percent
And the protected-accounts summary line reports that the slot declaration was not applied because it is absent
```
