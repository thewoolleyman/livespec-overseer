# Anthropic credentials — consequences for probing and dispatch

Moved verbatim from `AGENTS.md` §"The fleet has SEVERAL Anthropic credentials", whose table of the two credentials stays there.

Consequences to hold onto:

- **A probe on the E2E key, or on interactive `claude -p`, is NOT evidence
  about the factory.** Both are documented false positives (2026-07-29
  15:00Z: probe green, adapter hard-blocked).
- **These credentials have SEPARATE limits and may belong to different
  accounts.** At least two limit kinds have been seen — an org monthly spend
  cap and a rolling window. Raising one clears neither the other nor a
  different account, so name WHICH credential you measured.
- **The Dispatcher's Claude check WAS presence-only. IT IS NOT ANY MORE, and the
  remedy this entry used to prescribe is retired.** Observed directly on
  2026-08-07 while dispatching `overseer-1gig`: the dispatch was refused **before
  sandbox launch**, at stage `run-config-overlay`, with

      C-mode dispatch refused before sandbox launch: CLAUDE_CODE_OAUTH_TOKEN is
      exhausted or rate-limited (HTTP 429, rate_limit_error).
      Observed condition: exhausted.

  That is a real usability gate, and `bd-ib-3mbj` — the item that added it —
  reads `acceptance` in the orchestrator tenant. **It is NOT symmetric to the
  Codex side** (the sentence that stood here until 2026-08-20 said it was, and
  had the direction inverted): Codex-mode dispatch still has NO usability
  preflight, so an exhausted Codex usage window launches a doomed sandbox per
  dispatch and surfaces only as an ACP protocol error — carrier `bd-ib-oj71`,
  re-measured 2026-08-19 when four runs burned into a window known-exhausted
  for hours. **So a present-but-exhausted token no longer passes pre-flight, and a
  run no longer dies mid-review from this cause.** Do NOT reach for the host-side
  probe in `plan/archive/background-shell-supervision-liveness/handoff.md`
  §"Gate 4" as "the only valid signal": the dispatcher now reports the condition
  itself, names the credential, and consumes no spend doing it.

  **THE DESCRIPTION IS RETIRED; THE MECHANICS ARE NOT.** Three things still hold,
  and they are why this entry keeps its length. The refusal is a **wait, not a
  question** — a rolling limit clears on its own and must never be escalated as a
  maintainer decision, though an org *spend* cap genuinely is theirs. The refusal
  still leaves the work-item `active` with assignee `fabro` even though
  `fabro_run_id` is `null` and no run exists, so **release the claim by hand after
  any refused dispatch**. And the credential it names is `CLAUDE_CODE_OAUTH_TOKEN`,
  the factory path — a probe against `ANTHROPIC_API_KEY_LIVESPEC_E2E` or
  interactive `claude -p` remains a documented false positive.
- **Never print token material.** Presence, prefix and length are enough to
  identify which credential you are holding.
