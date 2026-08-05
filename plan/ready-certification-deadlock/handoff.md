# ready-certification-deadlock — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path in §6.
> Do not treat chat history as a source of truth. Rewritten 2026-08-05.

## 1. The primary goal

Give an uncertifiable `ready` a MECHANICAL recovery path, so a session that
sincerely declares itself ready after a voided declaration can be restarted by
the daemon instead of waiting hours for a maintainer. Observed on the `foreman`
track 2026-08-03: 7+ hours in `NEEDS YOU` at 17% context with a sincere `ready`
on disk. v004 recorded, as an explicitly unratified design question, whether a
session may have a sanctioned way to request its own restart outside a round,
deferring it to "its own future proposed change" — this thread authors it.

The thread is CONTRACT-BEARING: the spec change is ratified FIRST, and the
daemon implementation is filed afterwards as a child of the ledger anchor and
run through the FACTORY path. **Do not edit `overseer/*.py` on this thread.**

## 2. Where this stands — measured 2026-08-05T04:00Z; re-measure before acting

**Ledger anchor:** epic **`overseer-er6ikw`** (this repo's beads tenant). Read
live status from the ledger (`bd show overseer-er6ikw`), never from this file.
It is `status=backlog` with ZERO children — correct, because nothing is ratified
yet and the implementation item must not be filed before it is.

The proposal `SPECIFICATION/proposed_changes/post-void-ready-certification.md`
is on master, PENDING, and carries every correction made so far. Six PRs merged:
#701 (proposal), #704 (sequencing constraint), #707/#709 (supervisor corrections
T2/T3), #708 (ten adversarial-review corrections), #718 (identity anchor, fixing
both ratification blockers).

**One ratification attempt has already FAILED, and that is the live fact.** The
amendments were drafted, a fresh read-only Fable reviewer returned **BLOCKERS**,
and per the maintainer NO version was cut and the spec tree was left unmutated.
Both blockers were then fixed IN THE PROPOSAL by #718. **The AMENDMENTS were
never corrected to match** — that is the next action.

**The history head is v009 and it is NOT ours.** Another session ratified
`codex-yolo-structured-question-protocol` while this thread worked; ours was not
swept and still pends. **The next revise cuts v010.** Every artifact named
`v009-amendments-*` predates that and is misnamed.

## 3. The next action (exactly one)

**Re-derive the amendments from the corrected proposal, against CURRENT master,
then re-run a FRESH ratification review.**

A held patch sits at
`tmp/overseer/ready-certification-deadlock/v009-amendments-BLOCKED.patch` with a
README beside it. **It does NOT apply to current master** — `tests/heading-coverage.json`
conflicts, because v009 touched it — and it is STALE IN CONTENT: authored before
#718, so it still carries the ambiguous identity text, lacks the
replace-before-void scenario, and lacks the Attention-surface co-amendment. Use
it as a reference draft for the ~230 lines of unchanged prose; do not apply it.
An uncommitted worktree at
`~/.worktrees/livespec-overseer/spec/post-void-ready-certification` holds the
same stale content on the old base. Its amendments must NOT be committed to a
branch as-is: they modify active spec files without cutting a version, which is
exactly what `doctor-out-of-band-edits` detects.

What the amendments must carry — all mandated by the proposal; read it, do not
work from this list alone:

- `spec.md` — cardinal-rule non-weakening sentence; round-close plus the
  un-opening carve-out for a round whose OPENING paste failed; the floor may
  rise within a round; Fail-soft posture evaluation-ordering binding plus the
  never-in-a-round residual.
- `contracts.md` — state file: void clears the DECLARATION only, ordered
  record-then-delete, blocked-void raises no floor; interlock preconditions 1-4
  including the ROUND-OPEN identity; the honest two-path statement of
  one-declaration-one-kill; Durable stores including the write-once identity;
  the uniform `ready` paste exclusion; **Attention surface co-amendment** (three
  new report-only members).
- `scenarios.md` — **11** mandated scenarios.
- `tests/heading-coverage.json` — one entry per new scenario, `"test": "TODO"`
  with a reason naming the deferred implementing slice. This file CANNOT go in
  `resulting_files[]` (those paths are relative to the spec target); it lands in
  the same commit, outside the CLI.

Then: fresh reviewer → `/livespec:revise` (maintainer-attended; the maintainer
has already authorized running it and accepted the directory scope) → and only
after ratification, file the implementation child of the ledger anchor and
dispatch it through the FACTORY path (`drive --action impl:<id>`), never the
in-session `implement` operation. Check master CI is green first: a red master
blocks every dispatch and the refusal names your item rather than the cause.

## 4. The regression boundary

The fix must NOT create: a restart from a stale or replayed declaration (one
declaration, one kill); a timer-based or idleness-inferred restart (THE CARDINAL
RULE — only a session-written `ready` ever authorizes a restart); band re-spam;
or a benefit-of-the-doubt certification. A session oscillating declare → work →
declare must still never be killed mid-work, so whatever re-opens certification
must require a verified settled idle prompt at restart time.

**The sharpest hazard found so far is worse than the deadlock itself.** An
identity anchor recording at BOTH round-open and void, into one stored slot,
lets a session be killed that never received a wrap-up: a round opens for A → A
is replaced out of band by B → A's inherited `ready` is voided and the LIVE
identity B is recorded → B declares and is killed. The deadlock leaves a session
STUCK; this DESTROYS one. Pre-amendment text forbade it only incidentally (the
void closed the round), and this proposal removes that protection. The anchor is
therefore the ROUND-OPEN identity, write-once. Do not "simplify" it back.

## 5. Facts already paid for — do NOT re-derive these

- **The mechanism.** The void clears the round via `_supervisor_state.py:63-64
  → :45 → _registry_stamps.py:174-194`, which deletes the whole key, `at` AND
  `bands`. Band exhaustion is NOT the cause and never was.
- **The two code blockers.** `_supervisor_evaluate_idle.py:97-100` precedes
  `:121-132`, making the wrap-up unreachable — violating `spec.md` §"Fail-soft
  posture" verbatim. `_supervisor_threshold.py:98-100` disqualifies a raw
  `ready` only under shell-only evidence — looser than `contracts.md`, and that
  looseness is currently the ONLY reason the deadlock is rare rather than
  universal. Tightening it before the certification floor lands would generalize
  the bug rather than fix it.
- **`/livespec:revise` mechanics.** Decisions are per FILE, not per proposal
  section. Verbs are accept/modify/reject — there is NO defer, and
  `proposed_changes/` must end empty. Every accept requires independent
  ratification evidence: reviewer identity and model, `separate_reviewer`,
  `read_only`, UTC-seconds timestamp, literal `NO BLOCKERS`, proposal stem, and
  a content digest. The digest is SHA-256 over uint64-BE length-prefixed
  proposal bytes then each `(path, content)` sorted by path — mirror
  `_revise_ratification._canonical_ratification_digest`; do not hand-roll it.
  **Never hand-write that evidence.** If a review blocks, that is a real result.
- **`LIVESPEC_CORE_PLUGIN_ROOT` must be set** to the livespec core cache root.
  The resolver's rule 2 falsely matches this repo's own `.claude-plugin/prose/`
  and resolves core to `.claude-plugin`, which ships no `propose_change.py`.
- **The worktree lib is POSIX `sh`; this shell is zsh.** Source it under
  `bash -c`, or `worktree_provision_pack_from_primary` sees one four-name string,
  prints `BLOCKED`, and silently yields a pack-less worktree that can neither
  commit nor push. Re-run `just install-worktree-pack` in any worktree created
  across a pin bump, then discard the `worktree_discipline` key it writes.
- **Auto-merge is armed and races you.** Push every commit before opening a PR;
  never plan to amend after one. Verify against the forge, never the local tree.
- **The TODO lever** (`LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST`) is set
  only in `release-readiness.yml` / `release-tag.yml`, not PR CI. Ratifying with
  TODO placeholders is precedented (18 already on master) but blocks cutting a
  RELEASE until the implementation lands.

**THE METHOD RULE — three recurrences in this thread in three disguises (a
band-shrink lemma, two line-wrapped grep probes, and a scenario count): WHEN THE
THING BEING CHECKED IS A SET, COMPARE THE SET. A count is a weak control and
agrees with the wrong answer.** Nine equalled nine and was still wrong. To check
scenario fidelity, extract the mandated set from the proposal
(`grep -E '^    ## Scenario:'`) and diff it against `scenarios.md` and
`tests/heading-coverage.json`.

## 6. Read-first chain

1. `plan/ready-certification-deadlock/deadlock-mechanism.md` — the corrected
   mechanism, the three blockers and which of them are ratified behavior, and
   the candidate cuts reassessed. Its superseded band-exhaustion text is
   preserved deliberately, because that is how this failure reads from outside.
2. `SPECIFICATION/proposed_changes/post-void-ready-certification.md` — the
   artifact being ratified: three proposals, 11 mandated scenarios, and two
   BINDING sequencing constraints (the round-close and certification-floor
   findings MUST land together; the round-close half alone is a regression).
3. `plan/ready-certification-deadlock/supervisor-handoff.md` — the supervision
   charter: valves V1-V7 and thread corrections T1-T3.
4. `SPECIFICATION/spec.md` §§ "The cardinal rule", "The supervision round",
   "The escalating wrap-up", "The restart", "Fail-soft posture";
   `SPECIFICATION/contracts.md` §§ "The state file", "The restart interlock",
   "The wrap-up injection", "Durable stores", "Attention surface";
   `SPECIFICATION/scenarios.md` §§ 148, 162, 170, 182.
5. `tmp/overseer/ready-certification-deadlock/worker-status.log` — the milestone
   trail; `.supervisor-state` — the supervisor marker.

Ledger ids read live, never stored here: `overseer-er6ikw` (this thread's epic),
`overseer-mgg` (sibling restart-leg defect), `overseer-blccme` (the closed
narrowing epic that raises this deadlock's frequency by design).

Every repo artifact of this thread rides worktree → PR → rebase-merge.
