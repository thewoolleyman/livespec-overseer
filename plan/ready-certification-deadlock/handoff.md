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
needs a certified `ready`. The shipped prose's remedy
(`.claude-plugin/prose/overseer.md`) — "a human must clear the
declaration or open a sanctioned round" — has no mechanical way to open
that round, so every instance is a maintainer interrupt. The v004
change itself went further than a remedy: it RECORDED, as an explicitly
unratified design question, whether a session should have a sanctioned
way to request its own restart outside a round, deferring any such
affordance to "its own future proposed change" — this thread authors
exactly that change. Observed on
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
cleared the round's injection stamp after the void. Start from
`overseer/_supervisor_liveness.py` — the OWNER of the certification
refusal: it emits "ready cannot certify: no supervision round open"
when the observation's injection stamp is absent — and from
`overseer/_supervisor_restart.py` (one hop from
`_supervisor_threshold.py`), which handles round-open and round-close.
Known discrepancy to resolve first: `_supervisor_restart.py` documents
the round as closing "ONLY when the resume line actually SUBMITS", and
`SPECIFICATION/spec.md` §"The supervision round" says it closes on
restart — yet foreman's stamp was cleared with NO restart ever logged,
so a third path is clearing it (candidate: the void handling). Then draft
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
2. `SPECIFICATION/spec.md` §"The supervision round" (the round-open /
   round-close sentence that is the deadlock's third edge), §"The
   escalating wrap-up", §"The restart", and §"Fail-soft posture" (where
   the v004 surfacing clause landed) — the ratified round/interlock
   contract being amended.
3. `SPECIFICATION/contracts.md` §"The restart interlock" — the two
   numbered certification preconditions being amended (first-class,
   not a side sweep).
4. `SPECIFICATION/history/v004/proposed_changes/uncertifiable-declaration-attention.md`
   (and its `-revision.md` beside it) — the change that added the
   report-only surfacing and recorded the deferred design question
   this thread answers.
5. `overseer/_supervisor_liveness.py` (the certification refusal),
   `overseer/_supervisor_threshold.py` (the wrap-up branch),
   `overseer/_supervisor_restart.py` (round-open/round-close stamp
   handling), and `overseer/marker-protocol.md` — code + shipped
   marker-protocol prose (sweep targets alongside
   `SPECIFICATION/scenarios.md` and `.claude-plugin/prose/overseer.md`).

Ledger ids to read live (never stored here): `overseer-er6ikw` (this
thread's epic), `overseer-mgg` (sibling restart-leg defect),
`overseer-blccme` (the closed narrowing epic that raises this
deadlock's frequency).
