---
proposal: foreman-blocking-picker-removal.md
decision: accept
revised_at: 2026-08-23T00:28:34Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5-1m
---

## Decision and Rationale

ACCEPTED as proposed, on the maintainer's explicit decision of 2026-08-22 and with independent ratification-review evidence for these exact bytes. The proposal replaces the foreman escalation paragraph's blocking-question permission -- a last-resort bounded wait with a defined timeout -- with a prohibition plus the obligation to surface the decision on the non-blocking mechanical attention path and return idle with any required recurring schedule still armed. The permission was not merely permissive but UNIMPLEMENTABLE: an open picker suppresses the scheduled fires of the session that raised it and missed occurrences are dropped, so the timeout that was supposed to bound the wait could never fire. Measured 2026-08-21 under overseer-lixhd3.1. Both sides of the new rule are enacted in scenarios.md: the existing scenario is retitled from 'A foreman's own blocking question does not freeze supervision of other tracks', whose title presupposed the blocking question happens and merely needed containing, to 'A foreman's own unresolved decision escalates without blocking'; and a new scenario proves the violation side, that a tick ending with its own blocking prompt outstanding is a reportable violation rather than a permitted bounded wait. The violation scenario's heading is covered by an owned TODO entry in tests/heading-coverage.json naming overseer-afaj, which owns writing the integration-tier test that will replace it -- the documented compliant path for ratifying a heading ahead of its test, and one this repo's registry already uses sixteen times. Restart authority is unchanged: the cardinal rule stands untouched and both foreman scenarios carry an explicit no-restart-authorization clause. Three independent read-only reviews were taken; the first two returned BLOCKERS and both were acted on rather than overruled.

## Resulting Changes

- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-23T00:27:39Z
verdict: NO BLOCKERS
proposal_stem: foreman-blocking-picker-removal
content_digest: 45e498adee0c203013098581ec34c869b5b14cbbba1edf9c229fc5fd1156256d
