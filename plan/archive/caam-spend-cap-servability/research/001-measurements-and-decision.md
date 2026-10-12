# caam-spend-cap-servability — measurements and decision (2026-10-10)

## What went wrong

`caam-anthropic-loop` excluded `anthropic-0` from selection for three days after
that account had regained its included quota, and kept `anthropic-1` (the account
in use, shared by the interactive sessions and the factory) running from 98%
weekly down to 8% while `anthropic-0` sat idle at 98–100%.

Three defects, one cause each:

| # | Defect | Where |
|---|---|---|
| 1 | A capped account is treated as unservable forever; included quota is never re-checked | `overseer/caam_extra_usage.py` `spend_capped` |
| 2 | The ALERT claims the account "can serve no request" every pass, and the operator contract relays ALERTs verbatim | `overseer/caam_spend_report.py` (~line 78) |
| 3 | The no-candidate hold names the headroom margin as the reason when the spend cap was the gate | `overseer/caam_candidate_diagnosis.py` `no_candidate_cause` |

Defect 3 made the failure look like a normal hold. "none of the live-verified
candidates (anthropic-0) clears the >=10.00 point seven_day headroom margin over
anthropic-1" is false for a candidate at 98% against an active account at 8%.

## Measurements

All 2026-10-10, host `hp`, no token material printed.

- `extra_usage.spend_limit_reached` true: $200.31 of $200.00, unchanged since
  2026-10-08.
- `anthropic-0` included windows after the 2026-10-09 weekly reset: 5-hour
  98–100%, weekly 98–99%, Fable 99–100%.
- Live credential fingerprint equals vault `anthropic-0` (`4f4626570c`); no
  `CLAUDE_CODE_OAUTH_TOKEN*` or `ANTHROPIC_API_KEY` in the shell, so the credential
  file was what the CLI used.
- `claude -p` answered `ok` on `claude-sonnet-4-6`, `claude-sonnet-5-5` and
  `claude-opus-5-5`.
- Raw `/v1/messages` with the `oauth-2025-04-20` beta header returned 200 for Haiku
  and 429 `rate_limit_error` with an empty message for every other model, on BOTH
  `anthropic-0` and `anthropic-1`. `anthropic-1` was the healthy control, so that 429
  is an artifact of raw calls without the Claude Code client identity and is
  **not** evidence about either account. Do not repeat the mistake of reading it as
  one.

## The countervailing evidence

Commit `11d1b13b` (2026-09-08, `overseer-t04c`) introduced `spend_capped` after an
incident that "stranded the whole interactive fleet on a capped account while three
accounts with included quota sat idle". The test
`test_a_spend_capped_active_account_rotates_to_an_included_quota_account` is
docstringed "THE INCIDENT. Healthy percentages everywhere, and the account cannot
serve."

That is a direct observation that a capped account with healthy percentages
could not serve. It was never isolated: not whether the percentages were stale, not
whether a model class was blocked, not whether the cap had been reached mid-window.
It is not reproducible today, since the measurements above show the opposite.

## Decision

Narrow the rule rather than delete it. An account counts as spend-capped for
selection only when the cap is reached **and** an included allowance is exhausted.
That keeps the case the original docstring actually describes (cap reached AND
included quota gone) and stops excluding an account that demonstrably serves.

This reverses the observable behavior pinned by the 2026-09-08 test. The reversal
is deliberate and is recorded in the rewritten test's docstring (item
`overseer-vc4nza`), not smuggled in.

## Residual risk, owned by the host-side item

If the 2026-09-08 failure mode is real and recurs, the first selection of a
capped-but-healthy account will strand a session on an account that cannot serve.
`overseer-ucb3aj` makes that first selection a watched event with a stated revert.
The loop itself has no serve-probe, so it cannot detect this on its own; adding
one is out of scope here and should be filed if the revert fires.

## Not in this plan

- The `overseerd busy(fable->opus)` line that persisted across many passes while
  Fable sat at 0%. It may be by design (a busy session is not interrupted), and it
  was not investigated.
- The factory selector's fallback warning when no per-profile slot exists. Slots
  `__ANTHROPIC_0` and `__ANTHROPIC_1` now exist; `_2`/`_3` do not.
- The `llm-provider-manager` plan, which will eventually replace this loop.
