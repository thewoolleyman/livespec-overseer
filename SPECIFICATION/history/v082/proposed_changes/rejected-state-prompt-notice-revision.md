---
proposal: rejected-state-prompt-notice.md
decision: modify
revised_at: 2026-11-02T07:16:57Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5 (herdr-overseer)
---

## Decision and Rationale

Ratified under the repository's delegated revise_decision_mode. This carries overseer-uzvcbn.11, filed at the maintainer's direction on 2026-11-02 and handed to plan herdr-overseer by overseerd. All four proposals state operator-observable behaviour: a BCP14 clause in contracts.md §'The state file', two Given/When/Then scenarios, and the lockstep membership change in spec.md §'The keep-going nudge' and constraints.md §'Acting safety' (five to six informational acts, including the 'sixth member' renumbering). The notice follows §'Notify, never block' (edge-triggered, a non-blocking relay) and authorizes no act. No design record is contradicted. The independent read-only Sonnet reviewer first returned two BLOCKERS. (1) The notice's retry of an UNCONFIRMED delivery contradicted the channel section's hold rule, and a held notice had no release. (2) The scenario named only the paste path. Both were repaired as modifications, and the same reviewer returned NO BLOCKERS over the exact final bytes. Its remaining notes are non-blocking: the held notice delays the 24h re-notice until release, and the 'within one cycle' title is kept as the maintainer's DoD wording, with the busy case in the scenario. tests/heading-coverage.json rows for the two new scenarios land in the same commit, owned by the code-half item overseer-uzvcbn.12.

## Modifications

Made over the filed text after the independent review. (a) Notice delivery: only a FAILED delivery is retried. An UNCONFIRMED delivery is never re-sent by either path; it is recorded as that value's notice and surfaced, and an UNCONFIRMED channel delivery is held. (b) contracts.md §'Daemon message delivery channel' gains a release rule for a held rejected-state notice: the named rejected copy is deleted or replaced by a different value, or the session writes a valid declaration. Its 'Choosing the channel' bullet names the notice's trigger, guards, cancellation and durable delivered record. (c) The dedup digest is pinned to the rendered (sanitized, truncated) rejected-value line. (d) The notice is added to the daemon-authored declaration-text list in §'The state file'. (e) The first scenario's Then-line allows the guarded paste or a supported direct channel under the same guards. (f) The rule's prose was compacted and reflowed against the filed wording, with the same meaning.

## Resulting Changes

- constraints.md
- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-02T07:16:56Z
verdict: NO BLOCKERS
proposal_stem: rejected-state-prompt-notice
content_digest: 4c3241897315c8fc7734381c03219a048a1239da1aca53dd0c321455f276a1b0
