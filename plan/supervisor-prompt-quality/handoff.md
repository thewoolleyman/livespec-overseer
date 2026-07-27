# Plan — supervisor-prompt-quality

**Owning repo:** `livespec-overseer`. **Status: read it from the ledger**
(`list-work-items` / `next`; nothing here stores status). Created
2026-07-26 at maintainer direction, out of the homelab
supervisor-handoff build-out (homelab PR #37, commit `862b4d0`).

**Ledger anchor:** epic **`overseer-byvxlp`** (this repo's beads
tenant) — the full quality bar for what `supervise-plan` GENERATES,
carried in that epic's description. This thread TIES TOGETHER the
existing generated-prompt items so the maintainer can execute them in
order; it does not fork their content. After the groom the anchor is
the filed replacement-slice set rather than the epic id, since the
groom closes the epic as regroomed-out.

## The item map (ids cited read-only)

- **`overseer-byvxlp`** (epic, this thread's anchor) — the eight-family
  quality bar: iteration-stable generic form; anti-drift layering +
  Corrections preservation on regeneration; the cold-open generation
  gate; placeholder discipline; classified-remedy preconditions
  (parameterized spawn posture); wait-channel bootstrap; adopter
  parameterization; the full anti-stall playbook beyond the two stall
  modes. Will be CLOSED as regroomed-out by its own groom, replaced by
  the filed slices; this thread remains the single tie-together.
- **`overseer-hbr.16`** (S7, P1) — **CLOSED 2026-07-26.** The FLOOR:
  both stall modes (no-idle/no-silent-block AND
  never-end-a-turn-without-an-armed-re-entry) with fixtures that tell
  them apart, asserted over GENERATED output, each demonstrated RED.
  NOTE: beads forbids task-blocks-epic edges, so `overseer-byvxlp`'s
  dependency on this item and on `overseer-hbr.4` was PROSE-ONLY and
  encodable nowhere. That re-check was run 2026-07-26 and the floor is
  discharged — but this sentence is itself a claim with a timestamp, so
  re-run it rather than trusting it.
- **`overseer-hbr.4`** (bug) — **CLOSED 2026-07-26.**
  Executable-commands bar. Both clauses discharged; the second by
  PR #120 + PR #123.
- **`overseer-hbr.15`** (S6, P1) — **CLOSED 2026-07-26.** Goal-1
  acceptance outside this repo. This thread strengthens the bar it
  tests but did NOT gate it.
- **`overseer-fitvmo`** — CLOSED 2026-07-26 as superseded (stall mode 1
  restated in `overseer-hbr.16`; broader bar in `overseer-byvxlp`);
  the close reason carries the full mapping.

## Execution order (the reason this thread exists)

**Re-measured against the ledger 2026-07-26.** The prose-only floor is
DISCHARGED — `overseer-hbr.4` (executable-commands bar) and
`overseer-hbr.16` (both stall modes + tell-them-apart fixtures) are
both CLOSED, and `overseer-hbr.15` (goal-1 acceptance) is CLOSED too.
beads forbids task-blocks-epic edges, so those dependencies were never
encodable and had to be re-checked by hand; this line records that
re-check, and a future reader should re-run it rather than trusting
this sentence. The three steps this section used to list first, second
and fourth were all already discharged when it still described them as
pending — a filed item is a claim with a timestamp.

1. **Groom `overseer-byvxlp`** (the maintainer owns the cut), folding
   `overseer-7lv`'s R1–R5 residue in as replacement slices — one
   anchor, no duplication.
2. **Drain the approved slices by dependency layer.**

Note that the groom operation CLOSES `overseer-byvxlp` itself as
regroomed-out at filing time (`file_approved_slices` ends with
`close_regroomed_out`, whose reason string is machine-generated and
cannot carry narrative). So the epic closing is NOT the archive trigger
it used to be — see Discipline.

## Reference material (all verifiable, none of it status)

- **Reference implementation:** homelab @ `862b4d0` —
  `.ai/supervisor-protocol.md` (shared role-level layer) +
  `plan/<slug>/supervisor-handoff.md` ×6 (thin iteration-stable
  binders), synthesized from this repo's charters plus `livespec`,
  `livespec-orchestrator-beads-fabro`, and `livespec-dev-tooling`.
- **The generic form's prior art:** `livespec-dev-tooling`
  `plan/worktree-location-enforcement/supervisor-handoff.md`.
- **The six defect classes the cold-open dry-runs caught** in a prompt
  that already looked complete — the empirical case for the generation
  gate: an unsubstitutable `<workdir>` placeholder (three shell errors
  in one line); a Monitor wait channel whose file was never created nor
  fed; a boot brief that was a comment, not a command; an unbounded
  wait for the agent UI; a HALT precondition with no remedy (a
  guaranteed stall); a false "only placeholder" claim.

## Discipline

Fleet-standard: worktree → PR → rebase-merge; `mise exec -- git …`;
never `--no-verify`; status only from the ledger via the fleet
credential wrapper; this thread archives when the LAST replacement
slice from `overseer-byvxlp`'s groom closes — not when the epic itself
closes, because the groom closes it as regroomed-out at filing time.

---

## WORKER RESUME STATE — appended 2026-07-27 by the `supervisor-prompt-quality` worker

**Appended, deliberately touching nothing above.** The supervisor owns this
file's execution order and item map and has an unmerged branch editing them
(`origin/docs/handoff-execution-order-correction`). This section is additive and
self-contained so the two do not collide; if a conflict does arise, **theirs
wins** — nothing here is load-bearing for their correction.

### Where the work actually is

The groom of `overseer-byvxlp` is **drafted, accepted, and NOT filed.** All
durable artifacts are in `tmp/overseer/supervisor-prompt-quality/` (gitignored,
present in the working tree):

| file | what it is |
|---|---|
| `groom-decision-packet.md` | the accepted packet (v3 content) — the 9-slice cut, placement, `overseer-7lv` disposition, D1–D6 |
| `NEW-VALVE-tmux-in-ci.md` | **THE ONE OPEN BLOCKER** — read this first |
| `REVISED-S1-S2-acceptance.md` | S1/S2 acceptance rewritten for real tmux (D4) |
| `evidence/` | runnable proof: `test_emitted_commands_discriminate.py` (9 tests, RED-demonstrated), `red-green-harness.sh` (24 legs), `gate_red_suite.py` (6/6), `adopter_validator.py`, `coldopen_gate.py`, `proposed-contract-text-v2.md` |

### Maintainer decisions already given — do not relitigate

D1 canonical groom (byvxlp closes regroomed-out, 9 flat slices) · D2 defects
first (S1, S2, then S3) · D3 `tmp/overseer/<topic>/.supervisor-state` ·
**D4 REQUIRE REAL TMUX IN CI** (overturned both the worker's and the
supervisor's stub recommendation) · D5 one visible-only capture.

### THE NEXT ACTION, and it is blocked

**Filing is HELD on one maintainer valve**, raised and not yet answered:
`tmux is absent from CI` — established three ways (zero mentions in
`.github/workflows/`; the sandbox image chain installs only `libatomic1`;
`docker run … command -v tmux` → absent). D4's acceptance cannot execute
without it.

Recommendation in the valve doc: add tmux to the **shared sandbox base image**
in `livespec-dev-tooling`, not to `ci.yml` — a CI-only install would make S1/S2
pass in CI and fail in the Fabro sandbox they get dispatched into, which is the
exact drift that image was factored to remove. Cost: cross-repo change (another
track's lane), a release + pin bump, and it makes S1/S2 — layer 1, first under
D2 — blocked on that release.

**When the valve is answered:** `file_approved_slices` with the 9 slices (S1/S2
carrying the revised acceptance) → `overseer-byvxlp` auto-closes regroomed-out →
hand-close `overseer-7lv` with the R→id mapping. Report every id created.

### Boundaries that still hold

Supervisor owns `handoff.md` and the archiving of
`plan/supervise-plan-residual-gaps/`. Do not touch branches
`docs/supervisor-charter-hardening`, `docs/regenerate-supervisor-prompt-quality-charter`,
or `docs/handoff-execution-order-correction`. Worktrees via
`just worktree-create`, never raw `git worktree add`.
