# 002 — The measured cut, and why the spec goes first (2026-09-06)

Source: factory run `01M1V1E2YSXWKCPYMR95G21Y6B` for `overseer-5ugiuj.1`
(claude-sonnet-4-6 implement node, 6 min), which measured the repository and
terminated at `needs_human` with no tree change. Its refusal is the finding.

## Why a code-only cut cannot land

Two gates in this repo's `just check` aggregate make the bucket-2 removal
spec-first:

1. `scripts/check-no-factory-spec-edits.sh` (justfile:269) rejects any commit
   authored by the sandbox identity (`<noreply@fabro.sh>`) that touches
   `SPECIFICATION/`. It is a self-declared no-escape-hatch gate. Foreman
   mentions in the spec: 101 in `scenarios.md`, 92 in `spec.md`, 17 in
   `contracts.md`, 5 in `constraints.md`.
2. `check-heading-coverage` (justfile:192) requires that every entry in
   `tests/heading-coverage.json` resolves to an existing test node id AND that
   every spec H2 scenario heading has an entry. 49 entries (44 `scenarios.md`,
   2 `contracts.md`, 3 `constraints.md`) bind spec headings to integration
   tests that exercise the foreman modules. Deleting the modules and tests
   without deleting the headings goes red; deleting the headings is the
   forbidden spec edit.

Every remaining route — rewriting the commit author, marking the 49 entries
TODO, weakening either gate — is detector evasion. So the ORDER is:

1. `overseer-5ugiuj.6` — one supervised spec revision (propose-change, then
   revise by the maintainer) removes the foreman, grooming and supervisor
   seats from `SPECIFICATION/` and deletes the 49 heading-coverage entries
   whose headings go. Tests may outlive their entries; entries may not outlive
   their headings or their tests.
2. `.1`, `.2`, `.3` — pure code cuts, factory-safe, each behind `.6`.

## The foreman cut, measured

- **73 modules / 10,734 lines** are foreman-exclusive and cleanly deletable.
- **Keep despite the name pattern** (live bucket-1 consumers):
  `_foreman_vendor_path` (consumer `jsonio`), `foreman_gather_sources`
  (consumers `_registry_epic`, `grooming_*`, `ledger_comments`),
  `caam_foreman_override` (consumer caam — bucket 1).
- **Ten daemon modules carry a foreman half** that needs surgery, not deletion.
- The skill directory, its Codex/Pi counterparts, `prose/foreman.md`, `bin/`
  entry points and manifest references go with the modules.

Note 001's regex sizing (89 modules) over-counted by the keep-list and the
daemon halves; this note's numbers supersede it for `.1`.

## Open point for `.2` and `.3`

`foreman_gather_sources` is consumed by `grooming_*`; once `.2` deletes the
grooming modules, re-check whether that consumer set collapses to
`_registry_epic` and `ledger_comments` only. The b4 panel-workflow carrier
depends on two bucket-2 items (the foreman panel prose and the
supervise-plan prose), so its by-name transfer in `.5` cites both.
