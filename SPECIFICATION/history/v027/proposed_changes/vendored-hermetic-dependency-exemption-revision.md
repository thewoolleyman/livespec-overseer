---
proposal: vendored-hermetic-dependency-exemption.md
decision: modify
revised_at: 2026-08-21T08:38:15Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Ratifies the maintainer's 2026-08-20 ruling on the livespec-overseer stdlib-vs-railway contract conflict. The repo's ratified stdlib-only clause and livespec core's ROP railway requirement could not both be satisfied — proved by running the gate, not by reading it: with the railway conversion applied, test_the_package_imports_only_the_standard_library fails on `returns` in foreman_gather_collect.py and foreman_gather_sources.py. The maintainer chose vendoring, narrowed to vendored + standalone + fully hermetic with zero impact on other livespec libraries. The amendment preserves the property the original clause protected — executables still run dependency-free under an isolated interpreter, because the dependency is in the tree rather than the environment — and non-vendored runtime dependencies remain contract changes. Condition (b) was corrected before merge so it is satisfiable by its own first user: `returns` needs `typing_extensions` vendored alongside and contrib/ pruned. Independent read-only review returned NO BLOCKERS for these exact bytes.

## Modifications

ONE CLAUSE ADDED BEYOND THE PROPOSAL'S STATED TARGET FILE, to resolve a blocker raised by independent ratification review. The proposal targeted constraints.md alone. Round-1 review found that SPECIFICATION/non-functional-requirements.md, section 'Constraints', asserts the stdlib-only rule 'is enforced at review and by the executables' isolated launch mode, which would fail on any third-party import'. The amended constraints.md permits a conforming vendored import AND states executables still run dependency-free, so that NFR sentence becomes FALSE the moment the exemption's declared first user lands: constraints.md would permit a state non-functional-requirements.md declares impossible. Ratifying constraints.md alone would therefore land a NEW intra-repo contradiction inside an amendment whose whole purpose is removing one. The modification rewords that single NFR bullet to scope the failure claim to imports FROM AN INSTALLED ENVIRONMENT, and states that a library vendored in-tree under the constraints.md exemption is by construction not such an import. No other file is touched, and the modification narrows nothing in the ratified exemption itself.

## Resulting Changes

- constraints.md
- non-functional-requirements.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-21T08:35:54Z
verdict: NO BLOCKERS
proposal_stem: vendored-hermetic-dependency-exemption
content_digest: 88e0cf5c25cc087d23ee20f26c6825e971fe028cface8885847c1c2c70cd2ada
