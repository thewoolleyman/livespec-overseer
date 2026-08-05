# Why a wind-down intent must expire when its rationale does

Reasoning note for the `winddown-rationale-expiry` plan thread (repo:
`livespec-overseer`). No prior ledger record exists for this class (a
compaction sweep of the ledger on 2026-08-05 returned zero hits); the
thread's epic is the anchor.

## The observed failure (governed-repo-bootstrap-supervisor, repo dolt-server, 2026-08-06)

1. The supervisor session, low on context, wound down by the book in
   SPIRIT: it updated
   `plan/governed-repo-bootstrap/supervisor-handoff.md` with a precise
   restart checkpoint and announced "Only that file changed. Ready for
   restart." in its pane.
2. It never wrote its `.overseer-state` file — the announcement was
   pane text, which the marker protocol deliberately never trusts. From
   the daemon's side, the session never declared anything.
3. The runtime then AUTO-COMPACTED the session, recovering it to ~94%
   context — which invalidated the entire rationale for a restart.
4. The session sat idle, waiting for a restart that could never come:
   no declaration existed to certify, and even a certified one would
   have described a context problem that no longer existed.
5. It un-stuck only when the maintainer intervened in its pane — at
   which point the session itself articulated the missing rule
   correctly: "Automatic compaction already made the old 94% reading
   irrelevant; waiting for a manual restart would now be wrong. I'm
   resuming the governed track from the checkpoint immediately."

That rule currently lives nowhere except that one chastened session's
transcript. This thread codifies it.

## The failure class

A wind-down is a RESPONSE TO A RATIONALE (low remaining context). The
runtime's auto-compaction can remove the rationale at any moment after
the intent forms — after the wrap-up is received, after the handoff is
refreshed, after `winding-down` or even `ready` is written. Nothing in
the marker protocol, the wrap-up prose, or the generated
charters/supervisor-handoffs says what a session should do when that
happens, so the default behavior is the worst one: hold the intent and
wait.

Three component gaps:

1. **Protocol gap (the core).** The marker protocol needs an expiry
   rule: after an auto-compaction (or any event that restores context
   above the wind-down threshold), a session holding a wind-down
   intent MUST clear it — delete/overwrite its `.overseer-state` if one
   is written — and RESUME from its checkpoint without waiting for any
   external actor. The handoff/checkpoint it prepared is not wasted; it
   is simply a better checkpoint. DETECTION must anchor on DISK, not
   recollection: compaction is exactly the event that can erase the
   session's memory of being mid-wind-down, and what survives is the
   session's own `.overseer-state` (if declared) and its just-updated
   handoff/checkpoint — the drafted rule keys on a post-compaction
   session READING those. The session-observable trigger is the
   compaction event plus that disk evidence; the wind-down threshold
   number is daemon-side config the wrap-up text does not interpolate,
   so the rule must not require the session to compare against a number
   it was never told (adding the threshold to the wrap-up text is an
   optional drafting decision).
2. **Charter gap.** Generated charters and supervisor-handoffs describe
   the wind-down leg but not the expiry leg; and this instance also
   re-demonstrates the declaration-mechanics gap (announcing readiness
   in pane text instead of writing the ONE state file) — the same
   under-specification family as `overseer-daj` (Codex-adoptable
   restarts). The charter amendment should state both: declarations
   are the file, never pane prose; and the post-compaction resume rule.
3. **Daemon-side verification.** The daemon already carries the shape
   that SHOULD catch the stalled end-state: `idle-with-context-left`
   (idle above threshold, not waiting on a human, undeclared) sends ONE
   keep-going nudge. Whether it fired here is UNVERIFIED — the daemon's
   stderr→log redirect has been broken since 2026-08-04T01:24Z (the
   running daemon was launched without it), so the alert history for
   this window does not exist. The executor must (a) verify the nudge
   logic against this shape with a test, (b) consider whether the nudge
   text should name compaction recovery explicitly ("your context
   recovered; resume from your checkpoint"), and (c) check the case
   where a STALE `winding-down`/`ready` declaration survives compaction
   — a declared session is not "undeclared", so the standing
   declaration would suppress the keep-going nudge, which is exactly
   backwards after recovery. (In THIS instance no declaration existed;
   the suppression case is the latent sibling.)

## What does NOT change

- THE CARDINAL RULE — nothing here creates a new restart path; this
  thread is about NOT waiting for one.
- The daemon's own void machinery (a `ready` followed by resumed work
  is voided after the 120s grace) — the expiry rule is the
  SESSION-side complement, not a replacement.
- The wrap-up escalation and its bands.

## Relations

- **`overseer-er6ikw`** (ready-certification-deadlock — CLOSED; fix
  landed): a sincere declaration that cannot be certified at genuinely
  LOW context. This thread is the mirror: an intent outliving its
  rationale at RECOVERED context. Together with delivery
  (`overseer-xkrwm3` / `plan/resume-submit-integrity/`), the
  restart-leg family is: authorization, delivery, expiry.
- **`overseer-daj`**: the charter under-specification family this
  thread's charter amendment extends.
- **Sweep surfaces at proposed-change time**: `overseer/marker-protocol.md`
  (the wind-down/declaration contract), `.claude-plugin/prose/overseer.md`,
  `SPECIFICATION/spec.md` (the wrap-up / round / keep-going-nudge
  sections), `SPECIFICATION/contracts.md`, `SPECIFICATION/scenarios.md`,
  and the charter/supervisor-handoff generator surfaces.
