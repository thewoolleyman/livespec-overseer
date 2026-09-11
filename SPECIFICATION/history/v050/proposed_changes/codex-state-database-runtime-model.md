---
topic: codex-state-database-runtime-model
author: gpt-5.6-sol
created_at: 2026-09-11T08:34:10Z
---

## Proposal: Codex state database expresses the current runtime model without exposing rollout bodies

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Admit the exact live Codex session row in Codex's active state database as an additional permitted launch-profile model source, with identity, fail-soft, model-precedence, and no-rollout-body boundaries that preserve the existing launch-token and verification rules.

### Motivation

A Codex model can change after process launch, but argv and environment continue to name the launched model. Codex's own state database updates the exact thread row's model when a turn changes it, including after resume, while the stable thread summary surface does not expose that field. Live validation against Codex 0.154.0 observed one isolated thread row move from gpt-5.6-terra to gpt-5.6-luna across two real turn overrides without reading its rollout body. The daemon therefore needs a permitted current-model source that does not violate the existing rollout-content prohibition or mistake a stale or unrelated row for the supervised session.

### Proposed Changes

Amend `SPECIFICATION/spec.md` section `The launch profile` after the Claude-transcript source rules with the following requirements.

1. For a Codex-harness track, Codex's own active state database MAY be an additional permitted source for the profile's model. The daemon MUST identify the live Codex session from the supervised process's open rollout filename without reading the rollout file body, then accept a database model token only from a `threads` row keyed by that exact session identifier whose recorded `cwd` resolves to the supervised repository. The database MUST be queried read-only. The daemon MUST NOT inspect any rollout body, infer a token from a rendered display name, or weaken the rule that the statusline is verification-only.
2. A usable database token MUST follow the same base-model precedence as the permitted Claude transcript token: where its base model differs from the argv/environment launch source, the daemon MUST prefer the database token so a mid-session model change survives restart; where the base model is the same, the daemon MUST retain the launch-source token so a context-window or other launch-token variant is not silently discarded.
3. The database source MUST be fail-soft. An absent, unreadable, locked, or unsupported-version database; a schema without the required table or fields; a missing session row; a row whose `cwd` does not identify the supervised repository; or an empty, synthetic, or otherwise unusable model token MUST fall back to argv, else environment, exactly as before and MUST NOT be treated as a mismatch. The Claude transcript behavior remains unchanged.

Add these contract-covering Given/When/Then scenarios to `SPECIFICATION/scenarios.md`, and add their exact heading-to-test links to `tests/heading-coverage.json` atomically when the proposal is revised.

- `## Scenario: The Codex launch profile captures a mid-session model change from its state database`: Given a live Codex track launched under one model token, its exact current session row names a different usable base-model token and matching repository cwd, and the model changed after launch, when the daemon re-captures the launch profile, then it records the database token and a restart reasserts the current model.
- `## Scenario: A same-base Codex database model preserves the launch-token variant`: Given a launch token with a trailing context-window or other variant and the exact matching session row names the same base model without that variant, when the daemon captures the profile, then it retains the launch token.
- `## Scenario: An unavailable or mismatched Codex state row fails soft`: exercise at least an unavailable or unsupported database and an exact-id row whose cwd belongs to another repository; in each case capture falls back to argv/environment and does not block supervision.
- `## Scenario: Codex runtime-model capture never reads a rollout body`: Given a real live-session identity obtainable from the open rollout filename and a rollout body that would fail the test if opened, when the daemon captures the state-database model, then it obtains the token from the exact database row without opening the rollout body.
