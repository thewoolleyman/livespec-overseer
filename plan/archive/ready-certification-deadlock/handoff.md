# ready-certification-deadlock — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path in §6.
> Do not treat chat history as a source of truth. Rewritten 2026-08-05.

## 0. CLOSED — 2026-08-05T21:20Z. Both halves shipped.

This thread is DONE and archived. Nothing below is a live instruction; §3's
"next action" is finished work, kept for the record rather than to be acted on.

- **Contract half:** `SPECIFICATION/history/v010` (PR #721, `816cff7`).
- **Daemon half:** PR #738, from factory run `01KZ84FG43SF` (56m57s, succeeded).
  All 11 v010 scenarios carry integration-tier pinning tests; zero TODO
  placeholders remain for them.
- **The deferred operator-prose obligation was DISCHARGED**, which was the
  condition the ratification review attached to its NO BLOCKERS verdict:
  `overseer/marker-protocol.md` now states the four-precondition interlock over
  a certification floor with the round-open identity, and
  `.claude-plugin/prose/overseer.md` replaced "a human must clear the
  declaration or open a sanctioned round" with the mechanical path, keeping the
  human remedy only for a track that was never in a round, has a malformed
  round record, or shows a differing/undeterminable identity.
- **Ledger:** `overseer-5oap` closed; epic `overseer-er6ikw` closed.
- **Carried forward, and tracked nowhere else:** `overseer-y8n6` (P3) holds the
  two spec-side residuals the review deferred — no named attention member for a
  FAILED un-open, and the non-monotonic divergence between "the void instant MAY
  be raised repeatedly" and "the most recent such void". Both fail closed today.

**One footnote that outlived this thread and is worth the search that finds it:**
`overseer-5oap` sat at `status=active, assignee=fabro` with `fabro ps` not
listing it — the textbook queue-eviction signature — while its work had already
merged and shipped. That is the "succeeded-untransitioned" fourth dispatch trap,
now in the repo `CLAUDE.md`. `fabro ps -a` is the only discriminator: an evicted
run is absent there, a completed one reads `succeeded`. The remedy is to CLOSE
the item, never to re-dispatch.

## 1. The primary goal

Give an uncertifiable `ready` a MECHANICAL recovery path, so a session that
sincerely declares itself ready after a voided declaration can be restarted by
the daemon instead of waiting hours for a maintainer. Observed on the `foreman`
track 2026-08-03: 7+ hours in `NEEDS YOU` at 17% context with a sincere `ready`
on disk. v004 recorded, as an explicitly unratified design question, whether a
session may have a sanctioned way to request its own restart outside a round,
deferring it to "its own future proposed change" — this thread authored it.

The thread is CONTRACT-BEARING: the spec change is ratified FIRST, and the
daemon implementation runs through the FACTORY path afterwards. **Do not edit
`overseer/*.py` on this thread** — that work belongs to the dispatched child.

## 2. Where this stood — measured 2026-08-05T04:45Z, before the daemon half landed

**THE SPEC CHANGE IS RATIFIED.** `SPECIFICATION/history/v010` is on master
(PR #721, merge commit `816cff7`), `proposed_changes/` is empty of this thread's
proposal, and `scenarios.md` carries 59 scenarios. The contract half of this
thread is DONE. What remains is the daemon half and the thread's close-out.

**Ledger anchor:** epic **`overseer-er6ikw`**. It now has ONE child:
**`overseer-5oap`** (P1, the daemon implementation), linked with `--parent` —
a HIERARCHICAL edge, deliberately NOT a `depends_on`, because an anchor link
pointing at an item's own parent epic is circular by construction and makes the
item permanently undispatchable. Read live status from the ledger
(`bd show overseer-5oap`), never from this file.

**The one ratification attempt that FAILED is history, and its lesson is §5.**
The first attempt drew BLOCKERS from a fresh Fable reviewer, no version was cut,
and both blockers were fixed in the proposal by #718. The second attempt — fresh
re-derivation against current master, fresh reviewer, `NO BLOCKERS` — is what
landed as v010.

## 3. The next action as it stood before closure (DONE — see §0)

**Dispatch `overseer-5oap` through the FACTORY path**, then supervise it:

    python3 <current-plugin-build>/scripts/bin/drive.py --action impl:overseer-5oap

Check master CI is green FIRST — a red master blocks every dispatch in the repo
and the refusal names your item rather than the cause. Then confirm the run
actually exists and reaches `running`: **`drive.py` exiting 0 means only that
the request was ACCEPTED**, and a run parked at `runnable` may be evicted
without ever executing, leaving a phantom `active`/`fabro` claim. `ACTIVE` is
never evidence of a run; `fabro ps` is.

Do NOT use the in-session `implement` operation. If the stale-build gate fires,
resolve the current build's `drive.py` by ABSOLUTE path rather than through the
Skill binding — a running session keeps its originally-resolved plugin path.

After it lands, close the thread: archive `plan/ready-certification-deadlock/`
and close `overseer-er6ikw`.

## 4. The regression boundary

The daemon change must NOT create: a restart from a stale or replayed
declaration (one declaration, one kill); a timer-based or idleness-inferred
restart (THE CARDINAL RULE); band re-spam; or a benefit-of-the-doubt
certification. A session oscillating declare → work → declare must still never
be killed mid-work — the settled-idle gate at restart time is what protects it.

**The sharpest hazard is worse than the deadlock itself, and v010's text exists
to refuse it.** An identity recorded at BOTH round-open and void into one stored
slot permits overwrite-at-void: a round opens for A → A is replaced out of band
by B → A's inherited `ready` is voided and the LIVE identity B is recorded → B
declares and is killed, having received no wrap-up. The deadlock leaves a
session STUCK; this DESTROYS one. The ratified anchor is therefore the
ROUND-OPEN identity, **write-once**. Do not "simplify" it back — an adversarial
reviewer caught exactly this and blocked the first ratification.

## 5. Facts already paid for — do NOT re-derive these

- **The mechanism.** The void clears the round via `_supervisor_state.py:63-64
  → :45 → _registry_stamps.py:174-194`, which deletes the whole key, `at` AND
  `bands`. Band exhaustion is NOT the cause and never was.
- **The two code blockers the implementation must fix.**
  `_supervisor_evaluate_idle.py:97-100` precedes `:121-132`, making the wrap-up
  unreachable. `_supervisor_threshold.py:98-100` disqualifies a raw `ready` only
  under shell-only evidence — looser than the contract, and that looseness is
  the ONLY reason the deadlock is rare rather than universal, so tightening it
  before the floor lands would GENERALIZE the bug.
- **THE METHOD RULE — four recurrences in this thread in four disguises (a
  band-shrink lemma, two line-wrapped grep probes, a scenario count, and a
  coverage failure): WHEN THE THING BEING CHECKED IS A SET, COMPARE THE SET; AND
  WHEN YOU SUSPECT A CHANGE CAUSED A FAILURE, RUN THE CONTROL.** Nine equalled
  nine and was still wrong. To check scenario fidelity, extract the mandated set
  (`grep -E '^    ## Scenario:'` over the proposal, now in
  `history/v010/proposed_changes/`) and diff it against `scenarios.md` and
  `tests/heading-coverage.json` — never compare counts.
- **`check-coverage` FAILS LOCALLY IN A FRESH WORKTREE AND IT IS NOT YOUR
  CHANGE.** Measured 2026-08-05: a fresh worktree fails at 99% on four
  timing-dependent lines in `tests/prompts/test_watcher_wake_discriminates.py`,
  which drives REAL tmux and is sensitive to this host's loaded tmux server. The
  identical failure reproduces with the branch's own changes STASHED, and the
  same commit passes `check-coverage` in CI. The PRIMARY checkout appears to
  pass only because `scripts/check-coverage.sh` reports from a pre-existing
  `.coverage` file when one exists (2402 statements) instead of running the
  suite (11132). **A green `check-coverage` in the primary is not evidence.**
  A doc-only branch is unaffected at push time: `scripts/check-pre-push.sh`
  routes zero-`.py` changesets to `check-pre-commit-doc-only`.
- **A FRESH WORKTREE IS BORN FAILING TWO MORE CHECKS HERE.** `worktree_create`
  copies the pack from the PRIMARY, whose copy can be drifted from the package
  source; the symptoms NAME THE WRONG THING —
  `check-primary-checkout-commit-refuse-hook-installed` reports
  `worktree_pack_body_mismatch`, and `check-shell-quality` reports
  `just-interpolation` against recipes named `worktree-create`/`-land`/`-reap`
  that arrive via `import?` and are therefore attributed to the consumer's own
  justfile. Fix: `just install-worktree-pack` INSIDE the worktree (the hint says
  `just bootstrap`, which is the wrong verb in a linked worktree), then discard
  the `worktree_discipline` key it writes into the tracked `.livespec.jsonc`.
- **`just worktree-create` is DEAD in this repo and fails SILENTLY** (exit 141,
  SIGPIPE, size-dependent). Use the bash-with-resolver-override form in the
  supervisor charter §V5 — and it MUST run under bash, not this fleet's zsh,
  or it yields a pack-less worktree that can neither commit nor push.
- **`/livespec:revise` mechanics.** Decisions are per FILE. Verbs are
  accept/modify/reject — no defer, and `proposed_changes/` must end empty.
  **`--spec-target` resolves relative to the shell's CWD, NOT `--project-root`.**
  Measured the hard way: a run issued from the primary checkout with
  `--project-root <worktree>` cut v010 INTO THE PRIMARY, and printed nothing at
  all on that first invocation. Run it with CWD inside the worktree and pass an
  ABSOLUTE `--spec-target`. Ratification evidence requires reviewer identity and
  model — **and the CLI requires `reviewer_identity` to EQUAL `reviewer_model`**
  (`_reviewer_error`), so the reviewing agent's own name belongs in the
  rationale, not that field. The content digest is SHA-256 over uint64-BE
  length-prefixed proposal bytes then each `(path, content)` sorted by path;
  import `_revise_ratification._canonical_ratification_digest` rather than
  hand-rolling it (it needs `structlog returns pydantic jsoncomment click` —
  supply them with `uv run --no-project --with ...`). **Never hand-write that
  evidence.** If a review blocks, that is a real result.
- **`LIVESPEC_CORE_PLUGIN_ROOT` must be set** to the livespec core cache root.
  The resolver's rule 2 falsely matches this repo's own `.claude-plugin/prose/`.
- **Auto-merge is armed and races you.** Push every commit before opening a PR.
- **The TODO lever** (`LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST`) is set
  only in `release-readiness.yml` / `release-tag.yml`, not PR CI. v010 added 11
  TODO placeholders (31 now stand). They block cutting a RELEASE until
  `overseer-5oap` lands and replaces them with real test IDs.
- **A `{{...}}` token anywhere in a work-item's text makes it UNDISPATCHABLE**,
  and quoting a `just` recipe variable is the common way it happens.
  `overseer-5oap` was scanned clean at filing; keep it that way.

## 6. Read-first chain

1. `SPECIFICATION/spec.md` §§ "The cardinal rule", "The supervision round",
   "Fail-soft posture"; `SPECIFICATION/contracts.md` §§ "The state file", "The
   restart interlock", "The wrap-up injection", "Durable stores", "Attention
   surface". **This is the RATIFIED v010 text and it is the authority** — read
   it before the proposal, not after.
2. `SPECIFICATION/history/v010/proposed_changes/post-void-ready-certification.md`
   — the full reasoning behind every clause, including the two BINDING
   sequencing constraints that forbid decomposing the implementation.
   Its `-revision.md` sibling carries the ratification evidence.
3. `plan/archive/ready-certification-deadlock/deadlock-mechanism.md` — the corrected
   mechanism. Its superseded band-exhaustion text is preserved deliberately,
   because that is how this failure reads from outside.
4. `plan/archive/ready-certification-deadlock/supervisor-handoff.md` — the supervision
   charter: valves V1-V7 and thread corrections T1-T3.
5. `tmp/overseer/ready-certification-deadlock/worker-status.log` — the milestone
   trail; `.supervisor-state` — the supervisor marker.

**One obligation is carried ONLY by `overseer-5oap` and by v010's history, and
it will be lost if that item is reworded.** The proposal mandates bringing
`overseer/marker-protocol.md` and `.claude-plugin/prose/overseer.md` into step.
Both were deliberately NOT amended at ratification, because they describe what
the daemon ACTUALLY DOES and amending them ahead of the daemon would have told
operators a mechanical recovery path existed when it did not. The ratification
reviewer judged that deferral legitimate ON CONDITION that the implementation
child name both files in its acceptance criteria. It does. Keep it.

Ledger ids read live, never stored here: `overseer-er6ikw` (this thread's epic),
`overseer-5oap` (the daemon implementation child), `overseer-mgg` (sibling
restart-leg defect), `overseer-blccme` (the closed narrowing epic that raises
this deadlock's frequency by design).

Every repo artifact of this thread rides worktree → PR → rebase-merge.
