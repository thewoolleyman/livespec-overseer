# Why a voided `ready` deadlocks certification

Reasoning note for the `ready-certification-deadlock` plan thread (repo:
`livespec-overseer`). No prior ledger record exists for this defect; the
thread's epic is the anchor. Read ids' live state from the ledger.

> **PREMISE CORRECTED 2026-08-04, from code and from `daemon.log`.** This note
> originally said the deadlock's third edge was BAND EXHAUSTION — that
> foreman's coalesced injection "spent ALL of them" and no band could fire
> again. That is measurably false. The void CLEARS THE WHOLE ROUND KEY, `at`
> and `bands` together, so bands reset on every void and were never exhausted.
> The superseded text is preserved verbatim in §"Superseded: the original
> band-exhaustion mechanism" rather than deleted, because the fact that the
> deadlock READS from the outside as band exhaustion is itself evidence about
> how it presents — and the next reader will arrive with the same intuition.

## The observed failure (foreman track, 2026-08-03/04, daemon 0.27.1)

The track ran a healthy inject → declare → resume-work → void LOOP for about
two hours, then stopped dead. Measured over `tmp/overseer/daemon.log`:

- **41** `injected wrap-up into …::foreman` lines and **39**
  `voided stale ready declaration for …::foreman` lines, alternating on a
  ~2.5-minute period from 06:57:00Z to 08:52:59Z.
- **ZERO** restarts for the `foreman` track, over the entire log. (The two
  `restarted …::foreman-supervisor` lines are the paired SUPERVISOR track, a
  different entity — do not read them as this track's.)
- The last event of the loop is the void at **2026-08-03T08:52:59Z**
  (`age 130s > 120s grace; session resumed work`). Nothing acts on the track
  again, ever.
- Hours later the session wrote `ready` a final time, sincerely, and sat idle
  on it. At **20:19:04Z** the daemon emitted
  `ready cannot certify (15m): no supervision round open`, and again at
  **00:04:06Z** as `(4h)`. The 15m is exactly `CONDITION_CONTINUITY_GAP`
  (900s), so the declaration was written at ≈20:04Z. It stayed in `NEEDS YOU`
  at 17% context until the maintainer asked why the overseer was "letting it
  sit". The daemon was reporting the whole time; reporting is all the ratified
  machinery allows it.

**The control that kills the band-exhaustion premise.** Across those 41
injections the reported band sets do not grow monotonically — they SHRINK:

| band set | count |
|---|---|
| `[50, 40, 30]` | 23 |
| `[50, 40, 30, 20]` | 8 |
| `[50, 40]` | 6 |
| `[50]` | 4 |

A band set cannot shrink within one round; `bands` is append-only per round
(`add_notified_band`). So the key was demonstrably deleted and re-accumulated
dozens of times. Bands were never the constraint.

## What actually clears the round — the third path, named

`_supervisor_state.void_if_stale` → `clear_state` → `clear_injection_stamp`:

| # | Site | What it does |
|---|---|---|
| 1 | `overseer/_supervisor_state.py:63-64` | `void_if_stale`: `age > MARKER_VOID_GRACE` (120s) → calls `clear_state` |
| 2 | `overseer/_supervisor_state.py:45` | `clear_state`: calls `registry.clear_injection_stamp` after unlinking the state file |
| 3 | `overseer/_registry_stamps.py:174-194` | `clear_injection_stamp`: deletes the WHOLE sidecar key — `at` AND `bands` |

Reached from the busy leg (`overseer/_supervisor_busy.py:100`) and the blocked
leg (`overseer/_supervisor_blocked.py:73`). The log line proving it ran is
emitted at `_supervisor_state.py:65-68`.

`clear_injection_stamp`'s own docstring says it is "Called by the daemon when
it restarts a track", and `contracts.md:186-188` ratifies that deleting the key
IS closing the round. So the void reaches a round-closing operation documented
and ratified as restart-only — a divergence from the function's own contract as
well as from the spec.

## The three blockers, and which are ratified

Clearing the stamp is necessary but not sufficient for the deadlock: the round
could simply re-open on the next wrap-up. Three separate things stop it, and
the distinction between them is the whole finding.

**(A) Attention suppresses the wrap-up — a DIVERGENCE.**
`overseer/_supervisor_evaluate_idle.py:97-100` places the `ready-uncertifiable`
branch ABOVE the below-threshold branch at `:121-132` that calls
`_supervisor_threshold.threshold()` → `_supervisor_restart.maybe_inject()`.
Once the surface is due — declaration age ≥ `CONDITION_CONTINUITY_GAP` (900s,
`_supervisor_config.py:143`) — the wrap-up branch is structurally unreachable,
and the age only grows. This contradicts `spec.md:546-550` verbatim: those
attention memberships "do not suppress an independently qualified
escalation-band wrap-up under §'The supervision round'; that wrap-up is
authorized by its own complete predicate, never by the attention condition."
`scenarios.md:204` carries the same rule for the danger member. **A ratified
MUST NOT is being violated by branch ordering.** It arrived with the v004
surfacing work (`5c54cb7`) — the change that was meant to REPORT the dead end
is what made it PERMANENT.

**(B) Shell-only + a raw `ready` cancels the wrap-up — RATIFIED, and correct.**
Inside the first 900s the row does reach `threshold()`, but
`overseer/_supervisor_threshold.py:98-100` computes
`ready = fresh.ready or (shell_only and fresh.declared.token == STATE_READY)` —
the RAW token, not `ready_valid` — and `:112` returns `None` on it, yielding
`settling` with no injection. This is `contracts.md:121-123` and `:133-134`
implemented faithfully: the pane MUST NOT be "carrying … `ready`", and "an
uncertifiable `ready` remains report-only and is not pasted into." Foreman
carried background-shell evidence throughout (`16:53:22Z … background shell
prolonged (8h)`; `21:02:15Z … background shell 17m`). **Do not "fix" this.**
Never keystroking over a standing declaration is a real invariant.

**(C) The non-shell escape is itself unratified — and it is load-bearing.**
For a track with NO shell evidence, `fresh.ready` is `ready_valid` (False with
no stamp) and the raw token is ignored, so within the 900s window the wrap-up
DOES fire, wakes the session, and it re-declares against the new stamp and
restarts. That is why this deadlock is rare rather than universal. But that
permissiveness contradicts the same `contracts.md:133-134` sentence that (B)
obeys — the code is stricter than the contract when shell evidence is present
and looser than it when it is absent. **Tightening (C) to match the ratified
letter would make the deadlock UNIVERSAL instead of shell-specific.** Any
proposal that touches this sentence must say which way it is moving and why.

So: (A) and the void's stamp clearing are defects against already-ratified
text. (B) is correct ratified behavior. With (A) fixed and (B) intact, a track
carrying an uncertifiable `ready` still cannot be pasted into, so no round can
open for it — and THAT residue is the genuine contract gap this thread exists
to close.

## Why each edge exists — the intent the fix must preserve

- **One declaration never authorizes two kills** (the v003 restart
  preservation guarantee, `contracts.md:93-94`): certification-against-a-round
  exists so a STALE `ready` cannot be replayed into a second kill.
- **The 120s void grace**: a `ready` the session works past is not a safe
  point; voiding the DECLARATION is correct and is not in question.
- **Spam-proof bands**: re-firing spent bands would re-nag a session that
  already heard every escalation.
- **Fail-closed authorization** (`spec.md:525-526`): an uncertifiable
  declaration must never be "benefit-of-the-doubt" restarted.

The deadlock is an emergent interaction of individually-correct rules with two
implementation divergences — which is why the remedy is partly a defect fix and
partly a contract decision, and why saying which is which matters more than the
patch.

## What v004 already did, and where it stops

The v004 `uncertifiable-declaration-attention` change (see
`SPECIFICATION/history/v004/proposed_changes/uncertifiable-declaration-attention.md`
and its `-revision.md`) added the report-only surfacing — the
`ready-uncertifiable` status and `NEEDS YOU` membership. (The remedy sentence
"a human must clear the declaration or open a sanctioned round" is the SHIPPED
PROSE's, in `.claude-plugin/prose/overseer.md` — not v004's own text.) No
mechanical path to "open a sanctioned round" exists, so the remedy is always a
maintainer intervention. v004 in fact went further: it RECORDED, as an
explicitly unratified design question, whether a session should have a
sanctioned way to request its own restart outside a round — deferring any such
affordance to "its own future proposed change". That deferral is the mandate
this thread executes. Meanwhile the `supervisor-wrapup-citizenship` narrowing
(epic `overseer-blccme`, closed 2026-08-03) makes wrap-ups land more often —
more rounds, more voids, more exposure.

## Two arguments available FROM the ratified letter

- **Certification is already a TIMESTAMP COMPARISON, not an abstract "is a
  round open".** `scenarios.md:164` turns on a declaration "whose modification
  time predates this round's injection stamp". So "written after the void" is
  the same KIND of test the interlock already performs.
- **`spec.md:530-541` already anticipates the SHAPE of this state** — a track
  that "can sit in a state in which no supervision round can open" — and
  requires it be surfaced. But it ENUMERATES the causes it foresaw: "a busy
  classification that never ends, a standing `blocked:` declaration, an
  alternation between the two". This cause is not among them, and the
  asymmetry is the argument: all three listed causes are states a session can
  LEAVE by its own action, whereas this one it cannot — it has already done
  the only thing the cardinal rule accepts.

## Candidate fix directions, reassessed against the measurement

a. **A post-void fresh `ready` re-opens a certification window.** A NEW
   declaration written AFTER the void, observed at a verified settled idle
   prompt, is not a replay of the voided one — the two-kills hazard the
   interlock guards against is REUSE of one declaration, not a newer sincere
   one. Closest to the ratified letter (see the timestamp argument above).
   **Still viable, and now the leading candidate.**
b. **Band exhaustion re-arms one final band.** **REJECTED — it addresses a
   cause that does not exist.** Bands reset on every void; foreman's were
   never exhausted. Re-arming a band that is already armed changes nothing.
c. **Voiding a declaration does not close the round.** **NOT a no-op** — the
   void demonstrably does close the round — but the WRONG cut. Leaving the
   stamp in place makes `at` arbitrarily old, degrading the interlock to
   "newer than the FIRST-EVER injection", which is exactly the hazard
   `clear_injection_stamp`'s docstring records as blocker B4, and it leaves
   the bands notified so no re-warn can ever follow. Its correct residue is
   narrower: the void should stop closing the ROUND while still clearing the
   DECLARATION, which is what `scenarios.md:188` and `contracts.md:39-41`
   already say it does.

## Relations

- **Epic `overseer-blccme`** (closed) — raises this deadlock's frequency by
  design (more wrap-ups → more rounds).
- **`overseer-mgg`** (restart-leg confirm race) — same family: defects in the
  wrap-up → ready → restart automation's integrity; different legs of it.
- **The ratified surfaces swept at proposed-change time**: `spec.md` §§ 89,
  110, 142, 162, 189, 218, 289, 382, 433, 480, 504; `contracts.md` §§ 9, 58,
  110, 154, 167, 250; `scenarios.md` §§ 148, 162, 170, 182, 192, 206, 304;
  and the shipped prose (`overseer/marker-protocol.md`,
  `.claude-plugin/prose/overseer.md`).

---

## Superseded: the original band-exhaustion mechanism

Preserved verbatim as filed 2026-08-04, before the code re-derivation. It is
WRONG about the mechanism — kept because four readers found it plausible, which
is data about how this failure presents.

> ## The deadlock triangle
>
> - Certifying a `ready` requires an **open supervision round** for it to
>   answer (the restart interlock).
> - A round opens when the wrap-up **injects a band**; each band fires at most
>   once per round (the durable stamp sidecar — deliberately spam-proof), and
>   foreman's coalesced injection spent ALL of them.
> - The round (and its bands) resets only on a **restart** — which requires a
>   certified `ready`.
>
> After a void with bands exhausted, every edge of that triangle is closed:
> the session can re-declare forever and never be certifiable, the daemon can
> never re-warn, and the restart is unreachable without a human.

The corrected reading: the round key is deleted on every void, so the second
and third bullets are both false. What closes the triangle is the branch
ordering in (A) plus the ratified no-paste-over-a-declaration rule in (B).
