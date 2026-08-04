# Why a voided `ready` plus spent wrap-up bands deadlocks certification

Reasoning note for the `ready-certification-deadlock` plan thread (repo:
`livespec-overseer`). No prior ledger record exists for this defect; the
thread's epic is the anchor. Read ids' live state from the ledger.

## The observed failure (foreman track, 2026-08-04, daemon 0.27.1)

1. 2026-08-03T08:50:35Z — the daemon injected the wrap-up into
   `/data/projects/livespec-overseer::foreman` at 18% context; all
   remaining bands coalesced into it (`bands [50, 40, 30, 20]`),
   opening the supervision round.
2. The session wrote `ready`, then resumed working, so at 08:52:59Z the
   daemon voided the declaration (age 130s > the 120s grace — correct:
   a `ready` followed by more work is not a safe stopping point).
3. Hours later the session wrote `ready` again — sincerely; it then sat
   idle on that declaration. The daemon classified it
   `ready-uncertifiable — ready cannot certify: no supervision round
   open` and put it in `NEEDS YOU`, where it stayed for **7+ hours** at
   17% context until the maintainer asked why the overseer was "letting
   it sit". The daemon was reporting the whole time; reporting is all
   the ratified machinery allows it.

## The deadlock triangle

- Certifying a `ready` requires an **open supervision round** for it to
  answer (the restart interlock).
- A round opens when the wrap-up **injects a band**; each band fires at
  most once per round (the durable stamp sidecar — deliberately
  spam-proof), and foreman's coalesced injection spent ALL of them.
- The round (and its bands) resets only on a **restart** — which
  requires a certified `ready`.

After a void with bands exhausted, every edge of that triangle is
closed: the session can re-declare forever and never be certifiable,
the daemon can never re-warn, and the restart is unreachable without a
human. The daemon's own status string names the resulting state —
`ready cannot certify: no supervision round open`, emitted by
`overseer/_supervisor_liveness.py` when the observation carries no
injection stamp. The executor of this thread MUST re-derive from code
which step actually cleared the stamp after the void, with this known
discrepancy as the lead: `overseer/_supervisor_restart.py` documents
round-close as happening "ONLY when the resume line actually SUBMITS",
and `SPECIFICATION/spec.md` §"The supervision round" says the round
closes on restart — yet foreman's stamp was cleared with NO restart
ever logged for the track. A third path is clearing it (candidate: the
void handling); identify it before drafting the spec change.

## Why each edge exists — the intent the fix must preserve

- **One declaration never authorizes two kills** (the v003 restart
  preservation guarantee): certification-against-a-round exists so a
  STALE `ready` cannot be replayed into a second kill.
- **The 120s void grace**: a `ready` the session works past is not a
  safe point; voiding it is correct.
- **Spam-proof bands**: re-firing spent bands would re-nag a session
  that already heard every escalation.
- **Fail-closed authorization**: an uncertifiable declaration must
  never be "benefit-of-the-doubt" restarted.

The deadlock is an emergent interaction of four individually-correct
rules — none of them is simply wrong, which is why the fix is a
contract decision rather than a code patch.

## What v004 already did, and where it stops

The v004 `uncertifiable-declaration-attention` change (see
`SPECIFICATION/history/v004/proposed_changes/uncertifiable-declaration-attention.md`
and its `-revision.md`) added the report-only surfacing — the
`ready-uncertifiable` status and `NEEDS YOU` membership. (The remedy
sentence "a human must clear the declaration or open a sanctioned
round" is the SHIPPED PROSE's, in `.claude-plugin/prose/overseer.md` —
not v004's own text.) NO mechanical path to "open a sanctioned round"
exists, so the remedy is always a maintainer intervention. v004 in fact
went further: it RECORDED, as an explicitly unratified design question,
whether a session should have a sanctioned way to request its own
restart outside a round — deferring any such affordance to "its own
future proposed change". That deferral is the mandate this thread
executes. Meanwhile the `supervisor-wrapup-citizenship` narrowing
(epic `overseer-blccme`, closed 2026-08-03) makes wrap-ups land more
often — more rounds, more voids, more exhaustions.

## Candidate fix directions (contract-bearing; decide in the proposed change)

a. **A post-void fresh `ready` re-opens a certification window.** A NEW
   declaration written AFTER the void, observed at a verified settled
   idle prompt, is not a replay of the voided one — the two-kills
   hazard the interlock guards against is REUSE of one declaration,
   not a newer sincere one. Certification could accept
   `declaration written after the void timestamp` + settled-idle as the
   round-equivalent.
b. **Band exhaustion without restart re-arms one final band.** After a
   bounded cool-down, a single "last call" wrap-up MAY fire again,
   re-opening a genuine round. Bounded (once per cool-down), so
   spam-proofing survives in spirit.
c. **Voiding a declaration does not close the round.** The round stays
   open for a later `ready` to answer; only a restart closes it. If the
   round-closing step turns out to be the void itself, this is the
   minimal cut — but verify it cannot let a session oscillate
   (declare → work → declare) into a kill at an unsafe moment; the
   settled-idle check at restart time is the guard.

Any of these keeps: THE CARDINAL RULE (only a session-written `ready`
ever authorizes a restart), no timer-based restarts, fail-closed
certification, one-declaration-one-kill.

## Relations

- **Epic `overseer-blccme`** (closed) — raises this deadlock's
  frequency by design (more wrap-ups → more rounds).
- **`overseer-mgg`** (restart-leg confirm race) — same family: defects
  in the wrap-up → ready → restart automation's integrity; different
  legs of it.
- **The ratified surfaces to sweep at proposed-change time**: the
  restart interlock and round language in `SPECIFICATION/spec.md`
  (§"The restart", §"The escalating wrap-up"), any parallel clauses in
  `SPECIFICATION/contracts.md` / `SPECIFICATION/scenarios.md`, the v004
  uncertifiable-attention language, and the shipped prose
  (`.claude-plugin/prose/overseer.md`, `overseer/marker-protocol.md`).
