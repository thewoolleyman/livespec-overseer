---
proposal: daemon-reports-codex-session-to-backend.md
decision: modify
revised_at: 2026-11-02T08:40:30Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5 (herdr-overseer)
---

## Decision and Rationale

Ratified under the delegated revise_decision_mode so overseer-rthizs is spec-backed and passes the dispatch spec-change-tier screen. The change adds one subsection to spec.md §'The restart' for the daemon's own fresh-Codex-successor launch in a guarded replacement. Once the session index confirms a thread created by that launch and named exactly the track's derived session name, the daemon reports it to the terminal backend as the agent session of its own replacement record's pane only, and never of a pane read from a process environment. It accepts the successor as proven without an open rollout file, keeping every other successor-proof condition. An unconfirmed rename reports nothing and leaves the successor unproven, with the ready declaration retained. The text stays backend-neutral, mirroring v083's sanctioned relaunch report. No acting rule is widened: the backend report is not a keystroke-bearing act, and /rename stays inside the existing herdr successor-launch exception. No design record is contradicted. The independent read-only Sonnet reviewer first returned two BLOCKERS. One was a MUST about a rejected report that had no scenario. The other was an ambiguous proof condition for a backend that accepts no report. Both were repaired, along with two non-blocking notes, and the same reviewer returned NO BLOCKERS over the exact final bytes. One non-blocking note remains for the implementation: the no-report-backend parenthetical has no scenario of its own. Heading-coverage and debt rows for the three new scenarios land in the same branch, owned by overseer-rthizs.

## Modifications

Made over the filed proposal after the independent review. (a) The proof condition now reads 'the session identity the daemon binds to the successor (and reports to the backend, where the backend accepts such a report)', so proof does not depend on a report a backend cannot accept. (b) A third scenario was added, 'A rejected backend report is surfaced and does not void a fresh Codex successor's proof', covering the rejected-report MUST. (c) Scenario 1's rollout line now matches the clause: no reliance on write time or recency, and no rollout body opened. (d) The body of the existing scenario 'A Codex herdr replacement delivers the resume line after an unconfirmable rename' now uses the derived session name <name> and 'a thread created by this launch named exactly <name>'; its heading is unchanged.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-02T08:40:27Z
verdict: NO BLOCKERS
proposal_stem: daemon-reports-codex-session-to-backend
content_digest: 5fc2abaaeaab6cc788999e00b1738f1373eb304b7f65f3baaea7c7eb3f6f56f2
