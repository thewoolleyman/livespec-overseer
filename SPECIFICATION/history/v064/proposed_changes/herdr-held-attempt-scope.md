---
topic: herdr-held-attempt-scope
author: claude-opus-5-5:herdr-overseer
created_at: 2026-10-21T10:07:44Z
---

## Proposal: A held unconfirmed delivery holds only the round's wrap-up, never a replacement's naming command or resume line

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Scope the held-UNCONFIRMED-attempt rule in spec.md §"The supervision round" to the round's wrap-up and its expiry notice, which are the deliveries the rule exists to protect. A daemon-authored payload that asks the runtime for no turn, namely the `/rename <topic>` that names a fresh Codex successor, is never held as an unconfirmed delivery: its outcome is proven by its own evidence (the durable session-index record), never by an observed turn start. A held attempt never suppresses the resume line a replacement delivers to its proven successor. Add a scenario pinning the Codex herdr replacement through to a delivered resume line.

### Motivation

On the herdr backend a Codex replacement can never complete. The daemon submits `/rename <topic>` to the fresh Codex successor. A slash command starts no turn, and a Codex composer can never be proven empty, so by the paragraph's own rule that delivery can never be confirmed. The pane router then holds the attempt, and every later payload in the round, including the successor's resume line, is suppressed without being pasted; the replacement stalls at phase `resume-attempted` (factory run 01M5EVBNK0X1 on overseer-uzvcbn.4, reproduced three times against a real herdr instance with the released overseerd; code-confirmed in overseer/pane_router_submit.py `submit_prompt_once`, where a held `PromptState` substitutes its own text for any new payload). The current text reads two ways. 'No later wrap-up is pasted' scopes suppression to wrap-ups, but 'a runtime whose empty input cannot be proven ... is never re-pasted into while its delivery is unconfirmed' can be read as forbidding ANY paste into such a pane while anything is unconfirmed. Under the second reading the herdr router is conformant and the Codex herdr replacement arm is unreachable by construction. The tmux Codex arm already proves naming from the durable session index rather than from a turn start (overseer/AGENTS.md, `fresh_rollout_indexed`). This proposal makes that the rule for both backends and removes the ambiguity, so that the code fix (overseer-uzvcbn.5, plan herdr-overseer, epic overseer-uzvcbn) follows ratified text. It aligns with the in-flight spec/daemon-message-channel-delivery proposal, which keeps the DELIVERED / FAILED / UNCONFIRMED outcome rules unchanged.

### Proposed Changes

### spec.md §"The supervision round"

Replace the sentence

> While an UNCONFIRMED attempt is held for a pane, no later wrap-up is pasted into that pane, and the held attempt stays surfaced.

with:

> While an UNCONFIRMED wrap-up or expiry-notice delivery is held for a pane, no later wrap-up or expiry notice for that pane's round is pasted into that pane, and the held attempt stays surfaced. Only those deliveries are ever held. A daemon-authored payload that asks the runtime for no turn, such as the `/rename <topic>` that names a fresh Codex successor, MUST NOT be held as an UNCONFIRMED delivery and MUST NOT suppress any later paste: the daemon MUST prove its outcome by that payload's own evidence (for a Codex rename, the durable session-index record binding the successor's rollout to the topic), never by an observed turn start. A held attempt MUST NOT suppress the resume line a replacement delivers to its proven successor; that resume line is pasted afresh, and its delivery is confirmed by the successor's observed turn start.

The surrounding sentences are unchanged. In particular, the never-re-paste rule for a runtime whose empty input cannot be proven continues to apply to the SAME payload while that payload's own delivery is unconfirmed, and a held wrap-up is still released when a later observation resolves it DELIVERED or FAILED, or when its round closes.

### scenarios.md

Add, immediately after `## Scenario: A guarded herdr replacement survives daemon loss without a second kill`:

```
## Scenario: A Codex herdr replacement delivers the resume line after an unconfirmable rename

Given a Codex track on the herdr backend whose fresh-session ready declaration authorized a replacement
And the daemon has launched a fresh Codex successor in the recorded pane and submitted /rename <topic> to it
And the rename started no turn, so its delivery cannot be confirmed by a turn start
When the session index records the successor's rollout under the topic
Then the daemon treats the successor as named, without holding the rename as an UNCONFIRMED delivery
And it pastes the replacement's resume line into the successor's pane
And it confirms that delivery only when the successor's turn starts
And the replacement reaches phase completed and consumes the ready declaration
```

The scenario's evidence MUST be integration-tier. Because the pinning test ships with the code change, the `tests/heading-coverage.json` entry for this heading MUST be added in this revision as `"test": "TODO"` with `"work_item": "overseer-uzvcbn.5"`, and overseer-uzvcbn.5 MUST replace it with the pinning test.
