# 002 — How each provider exposes and applies quota resets (measured 2026-10-14)

This note discharges the plan's first step: measure, per provider, how an
account's available resets are discovered and how one is applied, before any
design. Everything below was MEASURED against live accounts with read-only GETs,
or read from the shipped client binaries. **No reset was claimed.** Claiming one
is irreversible and spends a limited grant, so the apply path is documented from
the client code and has not been exercised.

Sources:

- Claude Code `2.1.296` (`~/.local/share/claude/versions/2.1.296`), the
  `cedar-ember` and `juniper-tide` modules.
- Codex CLI `0.162.1` (`~/.codex/packages/app-server-daemon/releases/0.162.1-*/bin/codex`).
- Live reads: caam vault profiles `anthropic-0..3` (`anthropic-4`'s token is
  expired), and the host's single Codex ChatGPT login.

## Anthropic — two separate reset programs

Both programs live in the SAME endpoint the loop already polls,
`GET https://api.anthropic.com/api/oauth/usage`. They are top-level keys of the
response that the loop currently ignores (`cedar_ember`, `juniper_tide`). Both
are null on a plain read.

### Trap 1: the blocks only fill in when you ask for them

| Read | `cedar_ember` | `juniper_tide` |
|---|---|---|
| `/api/oauth/usage` (what the loop reads today) | `null` | `null` |
| `/api/oauth/usage?cedar_ember=1&skip_spend=1` | populated | `null` |
| `/api/oauth/usage?at_wall=1&skip_spend=1` | populated | populated |

So `?at_wall=1&skip_spend=1` returns both blocks in one read.
`skip_spend=1` leaves the `spend` block out of the response, and the loop's
spend-cap rule reads that block (`caam_extra_usage`). The design has to choose
between a second read and dropping `skip_spend`. That was not measured.

### Trap 2: eligibility is gated on the client's User-Agent

Without Claude Code's User-Agent, EVERY account answers
`{"eligible": false, "ineligible_reason": "surface", "grants": []}`. With
`User-Agent: claude-cli/2.1.296 (external, cli)` the same accounts answer
`eligible: true` with their grants. A reader who probes this the obvious way
concludes "no resets exist". That is the same failure shape as the
wrong-credential probe in `.ai/anthropic-credentials.md`: an HTTP 200 that
silently lies. The loop's `caam_usage.fetch_usage` sends no User-Agent today.

### Program `cedar_ember` — granted, multi-window, EXPIRING resets

Status block (the client's zod schema, confirmed against live data):

- `eligible`, `ineligible_reason`, `at_limit`, `exhausted[]` (the window keys
  currently at 100%), `next_grant_id`, `weekly_resets_at`, `cooldown_until`.
- `grants[]`, each with: `id`, `label`, `resets_total`, `resets_left`,
  `starts_at`, `ends_at` (**the reset itself expires**), `clears[]` (the windows
  one use refills), `paused`, `usable_now`, `use_requires_limit`,
  `percent_used{window: pct}`, `blocking[]`.
- Window keys `clears` may name: `five_hour`, `seven_day`,
  `seven_day_overage_included`, `seven_day_opus`, `seven_day_sonnet`,
  `seven_day_cowork`, `seven_day_omelette`, `seven_day_oauth_apps`.

Apply: `POST https://api.anthropic.com/api/organizations/{organizationUuid}/reset_rate_limits`
with body `{"program": "cedar_ember", "grant_id": <next_grant_id>, "request_id": <uuid>}`.
`request_id` makes the claim idempotent. The response is
`result ∈ {reset, already_used, not_limited, cooldown, ineligible, unavailable}`
plus `reason`, `resets_left`, `cleared[]`, `weekly_resets_at`, `cooldown_until`.
The client distinguishes 429 (rate-limited) from 401/403 (auth).

Measured 2026-10-14, every live account:

| Profile | Tier | Grant | Left | `usable_now` | `use_requires_limit` | `ends_at` | `percent_used` |
|---|---|---|---|---|---|---|---|
| anthropic-0 | max_20x | `opus55-launch-promax-20260921` | 1/1 | true | false | 2026-10-22T16:00Z | 5h 0, 7d 93, overage_incl 13 |
| anthropic-1 | max_20x | same | 1/1 | true | false | 2026-10-22T16:00Z | 5h 7, 7d 93, overage_incl **100** (`at_limit`) |
| anthropic-2 | max_20x | same | 1/1 | true | false | 2026-10-22T16:00Z | 5h 13, 7d 56, overage_incl 8 |
| anthropic-3 | pro | same | 1/1 | true | false | 2026-10-22T16:00Z | 5h **100** (`at_limit`), 7d 38 |

`clears` is `[five_hour, seven_day, seven_day_overage_included]` on all four.
**One grant refills the five-hour AND the weekly windows together.** It is not a
"weekly reset" or a "five-hour reset". A provider-agnostic column therefore has
to show what a reset CLEARS, not assume it has one scope.

`seven_day_overage_included` tracks the Fable-scoped weekly limit in these
figures: 13/100/8 against the plain read's `weekly_scoped` Fable percents of
13/100/—. So this grant also refills the Fable scoped allowance. The loop's
scoped-model rule cares about that.

**Time-sensitive:** all four grants lapse unused at **2026-10-22T16:00Z**. That
is exactly the plan's "expiring and would otherwise be lost" case, and it is
live now. It will very likely arrive before the code path ships.

### Program `juniper_tide` — the session (five-hour) reset

Status block fields: `eligible`, `ineligible_reason` (including `not_at_wall`,
`weekly_limit`, `no_weekly_limit`, `tier`, `tenure`), `in_experiment`, `arm`,
`available`, `next_available_at`, `weekly_resets_at`, and `resets_per_week`
(default 1). It is a recurring weekly allowance, not an expiring grant.

Apply: the same `POST .../reset_rate_limits` with body `{"program": "juniper_tide"}`.
The response is `result ∈ {reset, already_used, not_limited, ineligible, unavailable}`
plus `next_available_at`, `weekly_resets_at`. The client's success line reads
"Session limit reset · next reset available {date} · your weekly limit still
applies". It refills ONLY the five-hour window.

Measured: anthropic-0/1/2 answered `ineligible_reason: not_at_wall`.
anthropic-3, at 5h 100%, answered `eligible: true, available: true,
resets_per_week: 1`. **This program only reports availability when the account
is at the five-hour wall.** It cannot be displayed ahead of time the way
`cedar_ember` can.

## Codex — reset credits

Base `https://chatgpt.com/backend-api`, with the ChatGPT login's bearer token
and a `ChatGPT-Account-Id` header.

- Discover: `GET /wham/rate-limit-reset-credits` returns `credits[]`,
  `available_count`, `total_earned_count`, `immediate_reset_purchase_eligible`,
  `history_enabled`. Each credit (the binary's `RateLimitResetCreditDetails`,
  7 fields) carries `reset_type`, `granted_at`, and `expires_at`. **Codex reset
  credits expire too.** `GET /wham/usage` also carries a summary,
  `rate_limit_reset_credits{available_count, applicable_available_count}`, next
  to `rate_limit.primary_window` / `secondary_window`.
- Apply: `POST /wham/rate-limit-reset-credits/consume`. The app-server exposes it
  as `account/rateLimitResetCredit/consume`. The outcome is one of
  `reset | no_credit | nothingToReset | alreadyRedeemed`, with `windows_reset`.

Measured: the host's one Codex login (`plan_type: promax`) has `credits: []`,
`available_count: 0`. Its `primary_window` is the 7-day window at 6% used, and
`secondary_window` is null. So no per-credit record was observable live, and the
`reset_type` value set is known only from the binary. That is unmeasured, not
measured-empty.

## Scope finding for the design

caam's vault holds ONLY `claude` profiles; it manages no Codex accounts. The loop
is `caam-anthropic-loop` and polls Anthropic alone. The Codex half of
"detect, display and spend" has no account set to run against through this loop
today. **Recommendation (decided for objection, not a maintainer question):**
build the reset model provider-agnostic (`program`, `clears`, `left/total`,
`expires_at`, `usable_now`, `requires_limit`), ship the Anthropic adapter (both
programs), and record the Codex adapter as an explicit deferral. Reconsider it
when caam manages Codex profiles, which is the same trigger as any Codex
rotation. Carry this as a deferral in the plan's scoping event.

## Design inputs the measurements force

1. One read (`?at_wall=1`) with the claude-cli User-Agent yields both programs.
   The spend block versus `skip_spend` needs a deliberate choice.
2. A reset is shown by what it CLEARS (5h, 7d, scoped) and by WHEN IT LAPSES.
   `juniper_tide` is shown as "available at wall" only.
3. "Expiring and would otherwise be lost" is a `cedar_ember` / Codex-credit
   property (`ends_at` / `expires_at`). `juniper_tide` does not lapse in that
   sense: it recurs weekly.
4. `use_requires_limit: false` on the measured grant means it CAN be spent
   before the wall. The "nearly exhausted" rule is a policy choice, not a
   server constraint.
5. Do not spend a grant on an account whose own weekly window resets before the
   grant would be needed. Example: anthropic-0 is at 7d 93%, but its week rolls
   over at 2026-10-16T05:00Z, six days before the grant lapses.
6. A claim is idempotent per `request_id`. The loop must persist the id it used
   so that a retried pass cannot double-spend a grant.
