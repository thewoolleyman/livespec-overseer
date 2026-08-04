# ready-certification-deadlock — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path in §5.
> Do not treat chat history as a source of truth.

## 1. The primary goal

Give an uncertifiable `ready` a MECHANICAL recovery path, so a session
that sincerely declares itself ready after a voided declaration and
exhausted wrap-up bands can be restarted by the daemon instead of
waiting hours for a maintainer. Today the certification triangle
deadlocks: certifying a `ready` needs an open supervision round; a
round opens only when a wrap-up band injects and every band fires at
most once per round; the round resets only on a restart; a restart
needs a certified `ready`. The v004 remedy — "a human must clear the
declaration or open a sanctioned round" — has no mechanical way to open
that round, so every instance is a maintainer interrupt. Observed on
the `foreman` track 2026-08-04: 7+ hours in `NEEDS YOU` at 17% context
with a sincere `ready` on disk (full timeline in §5 item 1).

Nothing here weakens THE CARDINAL RULE (only a session-written `ready`
ever authorizes a restart), fail-closed certification, spam-proof
bands, or the one-declaration-never-authorizes-two-kills guarantee —
the fix must preserve all four intents while breaking the deadlock.

## 2. Where this thread stands

Created 2026-08-04. The epic anchor is **`overseer-er6ikw`**. Read live
status from the ledger — `list-work-items` / `bd show overseer-er6ikw` —
never from this file; this handoff cites ids read-only and carries no
work queue.

Done so far: the reasoning note (§5 item 1) carries the observed
timeline, the deadlock triangle, the four design intents each edge
protects, and three candidate contract cuts. NOT done: the
code-level re-derivation of which step actually closes the round after
a void, the spec proposed change, its review and ratification, and the
daemon implementation.

## 3. The next action (exactly one)

Author the spec proposed change via the `/livespec:propose-change`
operation against THIS repo's `SPECIFICATION/`, in two steps inside
that one action: FIRST re-derive from the daemon source which step
closes the supervision round after a void (the void itself, or a
separate expiry — start from the round/stamp handling reachable from
`overseer/_supervisor_threshold.py` and the certification path that
emits "ready cannot certify: no supervision round open"), then draft
the change choosing among the three candidate cuts in the reasoning
note (§"Candidate fix directions") — or a better one the code reading
reveals — sweeping every ratified statement of the interlock/round
letter (the sweep list is §5 items 2-3). Then: independent
adversarial review by a separately-spawned Fable-model agent, then
`/livespec:revise` with the maintainer. AFTER ratification: file the
daemon-implementation item as a CHILD of `overseer-er6ikw` via the
`capture-work-item` operation (`depends_on` the epic; autonomy tier
T2), implemented through the FACTORY path — the `drive` operation
(`impl:<id>`) or the Dispatcher drain — never the in-session
`implement` operation.

Every repo artifact of this thread rides this repo's normal
worktree → PR → rebase-merge discipline.

## 4. The regression boundary

The fix must NOT create: a restart from a stale/replayed declaration
(one declaration, one kill — a voided `ready` stays dead), a
timer-based or idleness-inferred restart (the cardinal rule), band
re-spam (any re-armed band is bounded and fires at most once per
cool-down), or a benefit-of-the-doubt certification (ambiguity still
fails closed). A session oscillating declare → work → declare must
still never be killed mid-work: whatever re-opens certification must
require a verified settled idle prompt at restart time.

## 5. Read-first chain (all committed in this repo, livespec-overseer)

1. `plan/ready-certification-deadlock/deadlock-mechanism.md` — the
   observed foreman timeline, the triangle, the intents to preserve,
   the three candidate cuts.
2. `SPECIFICATION/spec.md` §"The escalating wrap-up" and §"The
   restart" — the ratified round/interlock contract being amended.
3. `SPECIFICATION/history/v004/proposed_changes/uncertifiable-declaration-attention.md`
   (and its `-revision.md` beside it) — the change that added the
   report-only surfacing and named the human-only remedy this thread
   mechanizes.
4. `overseer/_supervisor_threshold.py` and `overseer/marker-protocol.md`
   — the wrap-up branch and the shipped marker-protocol prose (sweep
   targets alongside `SPECIFICATION/contracts.md`,
   `SPECIFICATION/scenarios.md`, and `.claude-plugin/prose/overseer.md`).

Ledger ids to read live (never stored here): `overseer-er6ikw` (this
thread's epic), `overseer-mgg` (sibling restart-leg defect),
`overseer-blccme` (the closed narrowing epic that raises this
deadlock's frequency).
