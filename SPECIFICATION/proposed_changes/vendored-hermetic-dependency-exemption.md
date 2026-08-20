---
topic: vendored-hermetic-dependency-exemption
author: claude-opus-5
created_at: 2026-08-20T21:27:23Z
spec_commitments:
  impl_followups:
    - id_hint: vendored-hermetic-import-constraint-test
      description: |
        Update overseer/test_package_constraints.py::test_the_package_imports_only_the_standard_library so it enforces the amended clause instead of a blanket third-party ban. Today it flags every import that is neither stdlib nor first-party, which would reject a conforming vendored import and leave the ratified prose contradicted by its own checker. The updated test must permit an import that satisfies all three conditions and must still fail one that does not: it must verify the library resolves to the in-tree overseer/_vendor/ copy rather than an installed one (a), that the vendored tree's own imports resolve within itself and the standard library (b), and that the vendored top-level name cannot shadow or be shadowed by a module another livespec library resolves (c). Preserve the existing sabotage-verification discipline recorded in the test's docstring: prove each arm has teeth with an installed third-party module, since an uninstalled one fails at collection time before the assertion runs.
    - id_hint: vendor-returns-into-overseer
      description: |
        Vendor dry-python/returns under overseer/_vendor/ with the vendoring artifacts the fleet already uses for this dependency (.vendor.jsonc and NOTICES.md, mirroring the copy livespec carries), then land the authored railway conversion preserved at livespec-dev-tooling:plan/rop-railway-enforcement/research/overseer-railway-blocked.patch — run_json_command and read_journal onto IOResult with a shared overseer/errors.py OverseerSourceError. Re-derive the offender counts before landing rather than trusting the recorded 182 -> 178, and re-sync the byte-identical .claude-plugin/overseer/ mirror, which is a plain copy enforced by check-codex-plugin-runnable-launcher. Keep the conversion's design call: source-unavailable and source-broken stay separated, the skip payloads stay byte-identical on the success track, and only the malformed-output case moves to the failure track.
---

## Proposal: Permit vendored, standalone, hermetic third-party imports in the standard-library-only supervision package

### Target specification files

- SPECIFICATION/constraints.md

### Summary

The stdlib-only rule and livespec's ROP railway requirement cannot both be satisfied by this package today, and the conflict blocks all 178 of its railway offenders. This proposal amends the stdlib-only clause to permit third-party imports under one narrow, cumulative exemption — vendored in-tree, standalone, and fully hermetic with zero impact on any other livespec library — preserving the property the rule exists to protect (executables run dependency-free under an isolated interpreter) while removing the contradiction. Non-vendored runtime dependencies remain contract changes.

### Motivation

TWO RATIFIED SPECIFICATIONS CONTRADICT EACH OTHER TODAY, AND THE CONFLICT IS PROVED
BY RUNNING THE GATE RATHER THAN BY READING IT.

`livespec-overseer/SPECIFICATION/constraints.md` section "Language and
dependencies" requires standard-library-only Python with "no third-party imports
anywhere in the package", and states that introducing a runtime dependency is a
contract change. livespec's own
`SPECIFICATION/non-functional-requirements.md` (the "ROP composition" clause)
requires every governed repo carrying first-party Python to put its product logic
on the `Result` / `IOResult` railway with `dry-python/returns` "vendored under
`_vendor/`", and states there is no thin-repo exemption.

Both cannot be satisfied. With the railway conversion applied,
`overseer/test_package_constraints.py::test_the_package_imports_only_the_standard_library`
fails with:

    third-party imports in a stdlib-only package:
      {'foreman_gather_collect.py': ['returns'], 'foreman_gather_sources.py': ['returns']}

The conversion itself is sound and was proved before this proposal was filed: it
was authored, gate-run, and measured on a throwaway branch, moving offender counts
182 -> 178 and 434 -> 430 (exactly two functions across the primary tree and its
enforced mirror), with the whole suite green and the mirror re-sync working.
ONLY the stdlib-only constraint test fails. The evidence patch is preserved at
`livespec-dev-tooling:plan/rop-railway-enforcement/research/overseer-railway-blocked.patch`
and the analysis is on ledger epic `livespec-dev-tooling-8o8e`.

SCALE: this is not a two-function problem. The conflict blocks all 178 of
`livespec-overseer`'s railway offenders — roughly 41% of the fleet's total — and
it is 100% of the fleet's remaining task-shaped railway work. Every other repo's
remaining convictions are policy questions, not conversions.

WHY THE ROUTING IS RATIFICATION AND NOT AN IMPLEMENTATION DECISION: the current
clause names it. "A change that introduces a runtime dependency is a contract
change, not an implementation detail." The specification asked to be amended
rather than worked around, and this proposal is that amendment.

WHY THIS SHAPE AND NOT THE ALTERNATIVES

Three options were on the table. Declaring `livespec-overseer` exempt from the
railway rule was rejected: it permanently carves the fleet's largest Python
surface out of a central requirement, and trades a real invariant for a paperwork
fix. Relaxing stdlib-only to allow `returns` as an installed dependency was
rejected: it reopens "dependency-free under an isolated interpreter", which is a
genuine operational property of a long-running daemon rather than decoration.
Vendoring keeps that property intact and contradicts only the literal phrase "no
third-party imports anywhere" — and the livespec rule being satisfied itself
specifies vendoring under `_vendor/`, so the two specifications converge on the
same mechanism once this sentence is amended. A fourth option, hand-rolled result
types with no `returns`, satisfies neither specification and is what the package
already does in places.

WHY CONDITION (c) IS PRESENT AND IS THE OPERATIVE ONE

Conditions (a) and (b) describe the vendoring shape. Condition (c) is the one
that does work at fleet scale, and it forbids a failure this fleet has already
recorded rather than a hypothetical: a sibling repo currently carries two copies
of the same vendored package at different versions, where which copy wins is
decided by import order rather than by intent (tracked as
`livespec-dev-tooling-8o8e.24`). Vendoring is only safe while it stays invisible
to everything outside the tree that holds it; a vendored library that other
livespec libraries can observe, shadow, or be shadowed by has reintroduced the
dependency problem it was meant to avoid. Stating (c) as a ratified condition
makes that the standard the next vendoring decision is measured against, rather
than something rediscovered after a version skew.


### Proposed Changes

Replace the whole of `SPECIFICATION/constraints.md` section "Language and dependencies".

CURRENT TEXT:

> The supervision package is standard-library-only Python: no third-party
> imports anywhere in the package, and its executables run dependency-free
> under an isolated interpreter. A change that introduces a runtime dependency
> is a contract change, not an implementation detail.

PROPOSED TEXT:

> The supervision package is standard-library-only Python. Its executables MUST
> run dependency-free under an isolated interpreter, and the package MUST NOT
> import any third-party library from an installed environment.
>
> A third-party library MAY be imported ONLY when it is vendored in-tree and
> satisfies ALL THREE conditions below. A vendored import that fails any one of
> them, and every non-vendored runtime dependency, remains a contract change
> rather than an implementation detail.
>
> (a) **Vendored.** The library's source is committed in-tree under
> `overseer/_vendor/`, and every import of it resolves to that in-tree copy. The
> package MUST NOT import the library from site-packages, a virtualenv, or any
> other installed location, and MUST NOT declare it as an installed runtime
> dependency.
>
> (b) **Standalone.** The vendored tree's own imports MUST resolve entirely
> within itself and the standard library. A library that drags in further
> third-party dependencies MUST NOT be vendored under this exemption.
>
> (c) **Hermetic, with zero cross-library impact.** The package's use of the
> vendored library MUST cause no impact or problem for any other livespec
> library. It MUST NOT shadow, collide with, or change which copy or version of
> any module another livespec library resolves — whether that library is
> vendored alongside it, installed in the environment, or imported by a consumer
> that also imports this package.
>
> The conditions are cumulative. Vendoring under this exemption preserves the
> load-bearing property the stdlib-only rule exists to protect: the executables
> still run dependency-free under an isolated interpreter, because the
> dependency is in the tree rather than in the environment.

WHY THE CLAUSE IS WORDED AS AN EXEMPTION AND NOT AS A CARVE-OUT FOR `returns`

The exemption is stated generally, over any library meeting (a)–(c), rather than
naming `dry-python/returns`. A named carve-out would have to be re-ratified for
the next library, and would invite the reading that the three conditions are
`returns`-specific rather than the actual standard. `returns` is the first user
of the exemption, not its subject.

PLACEMENT AND ENFORCEMENT

The amended rule stays in `constraints.md`, where the current rule already lives:
it is a constraint on the package's construction, not a user-observable behavior,
so it takes a BCP14 clause without a `scenarios.md` Given/When/Then — the same
shape the current clause has. Its mechanical enforcement is the existing
`overseer/test_package_constraints.py::test_the_package_imports_only_the_standard_library`,
which today rejects EVERY non-stdlib, non-first-party import flatly and would
therefore reject a conforming vendored import. Updating that test to enforce
(a)-(c) instead of a blanket ban is declared below as a spec-to-impl commitment,
so the amendment does not land as prose the checker contradicts.

