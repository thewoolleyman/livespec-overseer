# Why narrow wrap-up-injection suppression from "busy" to "generating"

Reasoning note for the `supervisor-wrapup-citizenship` plan thread
(repo: `livespec-overseer`). This records why the currently ratified
contract is wrong for supervisor sessions and what the replacement
contract is, so the spec proposed change and the implementation can both
be derived from it without re-litigating.

## The maintainer's ruling (2026-08-02)

> Supervisors will ALWAYS have a shell going if they are monitoring
> their worker, that shouldn't be a reason not to tell them to restart
> on low context.

This is a re-decision of a previously settled contract, made on new
evidence. It does not weaken any restart rule — see §"What does not
change".

## The currently ratified contract, and where it lives

`SPECIFICATION/spec.md` §"Fail-soft posture" (this repo), ratified in
the v003 background-shell-liveness revision from the maintainer's
2026-07-28 rulings:

- "Busy detection deliberately over-fires: a false 'busy' merely
  suppresses action … That suppression is **unbounded for ACTION** and
  bounded for ATTENTION."
- On shell-busy evidence: "Surfacing is the ENTIRE response … the
  daemon MUST NOT inject a wrap-up, send a keystroke, terminate the
  command, write a declaration, or restart the session."

The daemon conforms to this today: `overseer/_supervisor_evaluate.py`
classifies any busy pane `working` and the threshold branch
(`overseer/_supervisor_threshold.py` — wrap-up injection AND the
`danger` classification) never runs while busy. The bounded ATTENTION
floors that the same revision added (`winddown-starved` ~2h,
`shell-prolonged` ~8h+, both in
`overseer/_supervisor_attention.py`) exclude actively-generating panes
and are report-only.

The settled lineage: archived thread
`plan/archive/background-shell-supervision-liveness/` (epic
`overseer-4xfmez`, closed 7/7); work-item `overseer-vyjkzw`
(pending-approval) whose acceptance criteria EXPLICITLY preserve
injection suppression while shell evidence is live; work-item
`overseer-x6d` (2026-08-02) extending report-only surfacing to
generating panes below the danger floor.

## The structural defect the ruling names

A supervisor session's steady state is a live background monitor shell
watching its worker. Under "suppress action while ANY busy evidence is
present", a supervisor is therefore **permanently uninjectable**: it
can reach its wind-down threshold, then the danger floor, then the
context floor, and the daemon will never once tell it to wrap up. Its
only path to a clean restart is a human noticing.

That contradicts the SAME v003 revision's "full supervisor-pair
citizenship under the identical marker protocol and restart
interlock" (verbatim in
`SPECIFICATION/history/v003/proposed_changes/background-shell-liveness-attention-revision.md`) —
a citizen that can never receive the protocol's one communication is
not under the protocol.

## Evidence (all 2026-08-02, `tmp/overseer/daemon.log` + live table reads)

1. `rop-railway-enforcement-supervisor` (repo `livespec-dev-tooling`):
   below threshold with shell-only busy evidence; no injection possible
   all round; carried `winddown-starved` in `NEEDS YOU` for hours
   (episodes since 2026-07-31T16:42:16Z); ~21% when the maintainer
   asked why. The surfacing worked; nothing else could.
2. `beads-v1-1-2-upgrade-supervisor` (repo
   `livespec-orchestrator-beads-fabro`, Codex): 24% at 04:11Z → 7% at
   05:54Z, `working`, undeclared, uninjectable, and invisible even to
   the attention floors while generating.
3. `console-happy-path-mvp` (repo `livespec-console-beads-fabro`,
   worker, sub-agent busy): full → 15% with zero injections — the
   generating case, which stays suppressed under this thread's change
   (that visibility gap is `overseer-x6d`'s report-only fix).
4. Prior root incident (from `overseer-vyjkzw`): worker
   `04-convergence-loop` sat at an EMPTY prompt below the 30% band for
   ~39h behind a failed background poller. Under the narrowed contract
   that session would have been injected at the first settled tick.
5. `06-resilience-acceptance` (repo `homelab`, Codex WORKER — found
   while this thread was being opened, ~06:55Z): idle at its prompt
   with its task summary visibly complete, 8% context, undeclared,
   classified `working (background shell)` on shell evidence alone —
   uninjectable under the old letter, and not yet surfaced because its
   `winddown-starved` floor's ~2h bound had not elapsed (auto-linked
   05:29:34Z). Its paired supervisor was separately (and correctly)
   in `NEEDS YOU` as `blocked:human`. Confirms the narrowing keys on
   busy-evidence KIND, not session role: workers with shell-only busy
   evidence are equally starved.

## The replacement contract (the delta this thread exists to ratify)

Narrow unbounded ACTION suppression from **"any busy evidence"** to
**"generating"**. The daemon MAY inject the escalating wrap-up when ALL
of:

- the track's known remaining context is at/below its wind-down
  threshold (band machinery unchanged, including coalescing and the
  durable injection-stamp sidecar);
- no fresh `winding-down` ACK stands (unchanged);
- the pane's input prompt is verifiably idle AND settled (the existing
  two-capture settle check — never into a changing pane);
- every piece of busy evidence is background-shell evidence (Claude
  registry `status=shell` / Codex descendant-shell fallback); the
  session is NOT observed generating and no sub-agent-busy evidence is
  present.

Generating/changing panes keep unbounded action suppression exactly as
today; the bounded attention floors remain as the fallback surface for
them.

**Why this is safe.** Mechanically: with only a background shell live,
the input prompt is free; a paste lands as the session's next input and
nothing is interleaved into streamed output. Semantically: the wrap-up
is information, not force — the receiving session's own LLM still
weighs it (it can answer `winding-down`, `blocked: <reason>`, or keep
finishing its shell-gated step and declare afterwards), which is
precisely the judgment split the marker protocol already codifies. The
band escalation stays spam-proof via the existing stamp sidecar.

The ratified spec already carries this narrowing's own precedent:
`SPECIFICATION/spec.md` §"The keep-going nudge" sanctions the
pair-nudge paste "while the supervisor's only busy evidence is a
background command at its prompt" — at a verified empty and settled
input prompt, never while generating, never over a gate or a declared
block. The delta generalizes that already-accepted safety judgment
from the pair-nudge to the wrap-up injection; it introduces no new
class of act.

## What does NOT change

- THE CARDINAL RULE: a restart happens ONLY on a session-written
  `ready`. This thread touches when the daemon may *speak*, never when
  it may *act on the session's life*.
- No auto-spawn, no force-kill, no keystrokes into generating or
  unsettled panes, `danger` stays report-only.
- The bounded attention floors (`winddown-starved`, `shell-prolonged`)
  remain — they become the fallback for the generating case rather
  than the only response to the shell-only case.

## Consequences for existing records

- `overseer-vyjkzw` acceptance criterion 3 ("the daemon continues
  suppressing injection/restart" while shell evidence is live) was
  written under the old contract and must be re-derived at
  ratification: its intent (protect GENUINE background work) survives;
  its letter (shell evidence alone suppresses injection) does not.
  Criterion 2's no-paste clause binds the ATTENTION path only and
  stays true.
- `overseer-x6d` is complementary (report-only, generating panes) and
  unaffected.
- The spec drift sweep at proposed-change time must cover every
  statement of the old letter:
  - `SPECIFICATION/spec.md` §"Fail-soft posture" (the primary target);
  - `SPECIFICATION/spec.md` §"The keep-going nudge", whose pair-nudge
    clause reads "This nudge is the ONE bounded exception to busy
    classification suppressing acts … and only then" — the wrap-up
    becoming a second such exception falsifies that count, so the
    clause MUST be re-derived (enumerate both exceptions, or restate
    the rule as "acts are suppressed while generating" and let both
    follow from it);
  - any parallel clause in `SPECIFICATION/contracts.md` and
    `SPECIFICATION/scenarios.md`;
  - the shipped prose (`.claude-plugin/prose/overseer.md` and
    `overseer/marker-protocol.md`);
  - module docstrings that state "never inject while busy" as contract
    rather than as the generating-only rule.
