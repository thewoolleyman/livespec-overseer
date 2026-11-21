---
topic: session-window-rotation
author: claude-sonnet-5-5
created_at: 2026-11-21T00:26:11Z
---

## Proposal: Rotate before the 5-hour session window runs out, and never onto a protected account

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Amend '## Account rotation and quota supervision' so the operation rotates when the active account's 5-hour session window remaining falls to about 20% or below (CAAM_ROTATE_FIVE_HOUR_REMAINING default changes from 15 to 20), to a verified account with headroom compared on the short-window dimension, never selecting a protected account under that trigger; a dry-run reports the account it would select and why; protection applies only to operator-marked accounts and the committed configuration marks only anthropic-0.

### Motivation

Maintainer ruling, recorded on livespec-dev-tooling-6tgd2z (verbatim): "Yes do that. Just get things working the way they're supposed to so they rotate automatically to whatever is available and manage it correctly". Required end state: caam rotates automatically before any account's 5-hour session window or weekly allowance runs out, to whichever verified account has headroom, and protects ONLY anthropic-0, the maintainer's personal account. Incident: anthropic-4 (protected, 100% floor in host state, never drainable) went live at 2026-11-21 00:08:42Z and ran out its 5-hour window, killing a seat, because rotation keyed only on weekly-left. Work item overseer-xwfyxy.

### Proposed Changes

In spec.md section 'Account rotation and quota supervision':

1. **Rotation triggers.** Replace the short-window clause so it states the session-window trigger: the operation MUST rotate when the active account's current reading carries a short-window (5-hour session) limit whose remaining allowance is at or below a configurable threshold, default 20% remaining (env CAAM_ROTATE_FIVE_HOUR_REMAINING; this CHANGES the default from 15 to 20 and is stated as a change), moving to a verified account with headroom compared on the short-window dimension. Keep the weekly-reserve and scoped-model clauses.
2. Add a paragraph: under the session-window trigger the operation MUST NEVER select a protected account; there is no fallback onto the protected set, and if no unprotected verified candidate has short-window headroom the operation MUST hold and report why. This STRENGTHENS, for this trigger, the existing 'A protected account MUST NOT be selected while any unprotected account is eligible' (which permits a protected fallback when none is eligible); no existing MUST is weakened, and that sentence is unchanged for the other triggers.
3. **Trigger precedence.** State that the session-window trigger is an ordinary threshold trigger governed as 'every other trigger in this section except the drain', the drain remains lowest, and the protection ordering applies under it.
4. Add a paragraph: a dry run (the existing --dry-run flag) MUST report the account the operation would select and the reason (trigger, dimension, headroom of the candidate), and MUST NOT switch accounts.
5. In the protection clause: protection MUST apply only to operator-marked accounts; the committed configuration marks only anthropic-0 (the committed default protected set, applied at the default floor on every pass); a stale stored mark for any other account is cleared by the operator with --protected-account=<acct>=none.

In scenarios.md add two scenarios: 'An active account at 20 percent of its 5-hour window is rotated to an unprotected account with session headroom' and 'A protected account is never selected under the session-window trigger and a dry run reports the would-be selection', with TODO coverage rows and debt rows owned by overseer-xwfyxy (v120 precedent).
