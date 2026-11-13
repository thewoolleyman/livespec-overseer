---
proposal: enrolled-host-reissue-trigger-and-least-privilege-scenarios.md
decision: modify
revised_at: 2026-11-13T12:59:13Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Follow-ups (a) and (b) of plan central-credential-service (epic overseer-iyfjbo), owed onto the epic by the coordinator at the grading of #2960. (a) aligns the role holder's Remote Control re-issue between spec.md and contracts.md to one trigger and one reach: once per change of the account the role holder's live credential holds, seen first in the live credential or in an issued delivery, whether or not a delivery results, the first account after start only recorded, reaching the sessions contracts.md defines. This is the coordinator's ruling at the #2990 grade and what #2992 (overseer-fdwat6) ships. (b) adds scenarios for spec.md 'Least privilege', which had none. Revise decision taken under coordinator R301 delegation (legacy-coordinator-agent): proposal 1 ACCEPT verbatim, proposal 2 MODIFY.

## Modifications

Proposal 1 is accepted verbatim. Proposal 2 is modified so that the scenarios state no consequence the 'Least privilege' clause and contracts.md do not state: (1) 'The host list and the service stores hold no credential material' drops its line 'a host-list line that carries any field beyond a label, an ssh destination and a platform is rejected and reported, and the service does not push to it', because contracts.md §"Enrolled-host delivery" lists the host-list fields but states no rejection; (2) 'The service does not push with a role key other users can read' is replaced by 'The role key is readable only by the role holder's operating user' (Given the delivery service is installed on the role holder; When it pushes a delivery to a listed host; Then the role key file grants no access to any user but the role holder's operating user; And the status command's output contains no credential material), because contracts.md states the role key is held owner-only but states no refusal. Both scenarios receive TODO heading-coverage rows, integration tier, owned by overseer-aj577z, registered in tests/heading-coverage-debt.json.

## Resulting Changes

- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T12:56:57Z
verdict: NO BLOCKERS
proposal_stem: enrolled-host-reissue-trigger-and-least-privilege-scenarios
content_digest: 4697f85a22e7bf0997ecf5ee33fb6f004144bbd5bebe296b64d5e0807d7b73f3
