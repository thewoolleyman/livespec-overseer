---
topic: caam-identity-only-switch-write
author: claude-opus-5-5
created_at: 2026-10-26T07:43:23Z
---

## Proposal: Account install swaps identity only, atomically, and fails closed

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

### Summary

Specifies that the caam account-rotation switch keeps every non-identity key of the host agent's global state file (onboarding, per-repository trust) and the settings file (except the effort floor), writes the merged file atomically under the switch lock, and on an unreadable or unparseable file or a failed write restores the pre-switch state, reports a distinct failure and keeps the previous account. Carves the write out of constraints.md §"Atomicity and single instance", which currently scopes caam out, and adds two scenarios.

### Motivation

Measured 2026-10-26: `caam activate` restores the whole `~/.claude.json` and `settings.json` from the destination vault copy, and anthropic-6's copy was never onboarded (no hasCompletedOnboarding, 0 trusted projects), so restarted seats came up on first-run onboarding and the live file shrank from about 65 projects to 3. Work item overseer-hc7j implements the identity-only swap; petri run 01M5VAHW7FJR landed part of it and then the coordinator (R20) held the item on a spec gap: no governing heading states the swap, its atomic write or its failure path, and constraints.md §"Atomicity and single instance" explicitly excludes the caam operation.

### Proposed Changes

Add one paragraph to `SPECIFICATION/spec.md` §"Account rotation and quota supervision", placed immediately after the **Effort MUST be re-asserted as a floor** paragraph, reading exactly:

```markdown
**Installing an account MUST swap identity only.** The account manager's restore replaces the host agent's whole global state file (`~/.claude.json`) and settings file with the copies the destination profile was backed up from. A profile backed up before onboarding, or before a repository was trusted, would therefore silently return every session started afterwards to first-run onboarding. After the account manager installs the destination, the operation MUST leave the live global state file holding every key it held before the switch, with its pre-switch value, except the account-identity keys (`oauthAccount`, and any other key the host agent scopes to the signed-in account), which MUST take the destination profile's values. It MUST leave the live settings file byte-identical to its pre-switch content except where **Effort MUST be re-asserted as a floor** rewrites it. The merged global state file MUST be written atomically, as a temporary file in the same directory renamed into place with owner-only permissions, while the switch lock is held. When the merged write cannot be completed, because the live or the destination profile's global state file is unreadable or unparseable or the write itself fails, the operation MUST restore the pre-switch live global state file, settings file and credential. It MUST then report the switch as failed with a reason distinct from every other switch failure, and leave the pre-switch account active.
```

Add one paragraph to `SPECIFICATION/constraints.md` §"Atomicity and single instance", placed immediately after its first paragraph (the one that scopes the section to the supervision daemon's stores), reading exactly:

```markdown
The ONE exception within the caam operation is its identity-only merged write of the host agent's global state file (spec.md §"Account rotation and quota supervision", **Installing an account MUST swap identity only**). That write MUST meet the whole-file atomic-replacement guarantee of the next paragraph, and it is serialized by the operation's switch lock rather than by this section's advisory locks. It does NOT inherit the warning-only fallback: a failed write restores the pre-switch state and fails the switch loudly, as that clause defines.
```

Append two scenarios to `SPECIFICATION/scenarios.md`, reading exactly:

```markdown
## Scenario: A switch to a never-onboarded profile keeps the host's onboarding and trust

Given the live `~/.claude.json` records completed onboarding and trust for `/data/projects/example`

And the destination profile's stored `~/.claude.json` records no onboarding and trusts no repository

When the account-rotation operation switches to the destination profile

Then the live `~/.claude.json` carries the destination profile's account identity

And it still records completed onboarding and trust for `/data/projects/example`

And the live settings file is byte-identical to its pre-switch content except for a reasoning-effort value the effort floor raised

And the merged file was written by renaming a same-directory temporary file with owner-only permissions while the switch lock was held

## Scenario: An unreadable global state file fails the switch and keeps the previous account

Given the destination profile's stored `~/.claude.json` cannot be parsed

When the account-rotation operation switches to the destination profile

Then the live `~/.claude.json`, settings file and credential equal their pre-switch content

And the previous account is still active

And the operation emits a clearly-marked failure line naming a reason distinct from every other switch failure and exits non-zero
```

At revise time, `tests/heading-coverage.json` MUST gain one row per new scenario heading with `test: "TODO"`, `work_item: "overseer-hc7j"` and a reason naming the owed integration-tier test, and `tests/heading-coverage-debt.json` MUST register both as spec-first debt, co-edited in the same commit.
