# 001 — The factory token path, measured, and the design shape it forces (2026-09-08)

Maintainer request, 2026-09-08, verbatim in the parts that bind:

> Currently fabro uses a CLAUDE_CODE_OAUTH_TOKEN to use claude quota. This env
> var is stored in 1password livespec env, and when it expires, I have to
> rotate it manually. I want to modify the caam-anthropic-loop skill to
> automatically switch this to whatever the currently selected anthropic
> account is. I.e., it will get automatically managed and injected for the
> factory, via a standard means (fabro config file or whatever) instead of
> read via 1password wrapper. AFAIK there is NO fable usage in the factory, or
> if it is, it falls back to opus.

Authorization: the 2026-09-06 two-bucket ruling (recorded in
`plan/archive/deprecate-unused-seats-simplify-to-overseerd-and-caam/research/001-bucket-inventory.md`)
keeps the caam-anthropic-loop as bucket-1 production and reserves improvement
of it to the maintainer — "I may still improve those". This plan is that
improvement, maintainer-directed.

Nothing in this note turns a valve, writes a credential, or prints token
material. Every token is identified below by name, prefix, length, or a
10-character SHA-256 prefix.

## 1. What the factory token IS today (measured)

| fact | measurement |
|---|---|
| Source | `/usr/local/bin/with-livespec-env.sh` (generated artifact of `1password-env-wrapper`, "DO NOT EDIT") runs `op run --no-masking --environment fufpvkvatwkmqjzvilvfnemsue`; it reads a 1Password **Environment**, never a vault item (`:210-212`, `:418`, `:463`, `:508`) |
| Cache | wrapper-level kernel-keyring TTL, default 300 s (`:288`) — a new Environment value is observed up to 5 min late |
| Consumer | `livespec-orchestrator-beads-fabro/.claude-plugin/scripts/livespec_orchestrator_beads_fabro/commands/_dispatcher_credentials.py:298-310` reads `os.environ["CLAUDE_CODE_OAUTH_TOKEN"]` at dispatch time and renders it into a per-run mode-600 overlay (`_dispatcher_overlay.py:268-278`: `[environments.<id>.env]\nCLAUDE_CODE_OAUTH_TOKEN = …`), deleted when the run returns |
| Long-lived readers | **none.** `fabro server` (pids 4172174, 303293), `overseerd` (561658): zero `CLAUDE_CODE_OAUTH_TOKEN` entries in `/proc/<pid>/environ`. `~/.fabro/environments/livespec-ci.toml:1-9` forbids an `[env]` table (workers run under a fail-closed env allowlist). Every reader is per-invocation: `dispatcher.py loop`, `reconcile-runs.service`, `dispatch_acceptance_guard.py` |
| Usability gate | `_dispatcher_claude_credential_io.py:32` probes `POST /v1/messages` (haiku, `max_tokens=1`); `401`→`revoked`, `402/429`→`exhausted`; remedy text `:83-86`: "Run `claude setup-token` under an account with capacity, then rotate CLAUDE_CODE_OAUTH_TOKEN in the credential wrapper." A running `loop` re-probes every `dispatcher.credential_reprobe_interval_seconds` (300 s; contracts.md:3832) rather than exiting |
| Models | `implement/fix/review_fix` adapters pin `claude-opus-5`, `review` pins `claude-opus-4-8[1m]` (`workflow.toml:165-167, :217`); probe is haiku; **no factory node uses Fable**. The maintainer's premise holds |
| The other key | `ANTHROPIC_API_KEY_LIVESPEC_E2E` (`sk-ant-api03…`) is the containerized-image LLM key only; it never enters the overlay. Unaffected |

So a rotation needs **no daemon restart**: the next dispatch after the keyring
TTL sees the new value, and an already-waiting `loop` picks it up on its next
re-probe.

**The Environment already holds a pool.** Under the wrapper the process env
carries `CLAUDE_CODE_OAUTH_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN_0`…`_3`, all
`sk-ant-oat01…`, length 108. Nothing in any of the three fleet repos reads the
numbered names. Measured by SHA-256 prefix:

| name | sha-10 | equals |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | `9223c8ccc9` | `_1` |
| `_0` | `f1b145b2d2` | — |
| `_1` | `9223c8ccc9` | the live unnumbered token |
| `_2` | `3cd6d968a5` | — |
| `_3` | `15a432bcaf` | — |

The manual rotation the maintainer performs is therefore, mechanically, "copy
slot N into the unnumbered name". The pool is the maintainer's own staging of
per-account tokens; the plan's job is the SELECTOR.

## 2. What "the currently selected account" IS (measured)

- caam 0.1.16 swaps auth FILES: `caam activate claude <profile>` restores
  `~/.claude/.credentials.json` + `~/.claude.json` + `settings.json` from
  `~/.local/share/caam/vault/claude/<profile>/`. Five real profiles,
  `anthropic-0`…`anthropic-4`; active today `anthropic-3` (`caam status --json`
  → `tools[].active_profile`, read by `overseer/caam_profiles.py:61-92`).
- The live credential's `claudeAiOauth.accessToken` is `sk-ant-oat01…`, length
  108 — the SAME shape as the factory token — but it is the interactive
  **short-lived access token**: `expiresAt` 5.5 h from now, `refreshToken`
  (`sk-ant-ort01…`) 11.8 days. `caam ls claude` shows 2h28m–7h3m left per
  profile. Claude Code itself refreshes it (~8 h, per the docstring at
  `caam_profiles.py:70-74`).
- The loop already has this token in hand at the instant a switch completes:
  `caam_switch._switch_did_not_stick` (`caam_switch.py:223-228`) reads both the
  target snapshot's and the live token to verify the switch, via
  `caam_usage.read_creds` (`caam_usage.py:69-84`).
- Per-profile identity is on disk: each vault `.claude.json` carries
  `oauthAccount.{accountUuid, organizationUuid, emailAddress}`; all five are
  distinct organizations.

## 3. The premise that needed correcting, and the probe that settled it

The request reads as "copy the selected account's token to the factory". The
selected account's token is the SHORT-LIVED access token above. Handing it to
a sandbox is the wrong currency on two counts:

1. Factory runs last 1–4 h (`overseer-lixhd3.1` ran four hours) against a
   token with ≤8 h of life and no refresh path in the sandbox — contracts.md:5510
   makes the host "the sole owner and refresher of each long-lived provider
   refresh credential", and spec.md §"Account rotation" "Never refresh" forbids
   the loop from touching the token endpoint. A meaningful fraction of runs
   would die mid-review with `401`.
2. It is not what the factory holds today. The pool tokens match **no** vault
   access or refresh token (table in §1 vs. the five vault hashes
   `013242c41d, 896f97332b, 7e98d7703b, e62efe847d, f6bd2954d2`); they are
   separately minted `claude setup-token` credentials, the long-lived kind the
   dispatcher's own remedy text names.

**Can a pool slot be mapped to its caam profile automatically? No.** Read-only
probe, 2026-09-08 08:30Z, both `GET /api/oauth/profile` and
`GET /api/oauth/usage` with `anthropic-beta: oauth-2025-04-20`:

| credential | `/profile` | `/usage` |
|---|---|---|
| live interactive access token | 200 (`account`, `organization`, …) | 200 (`five_hour`, `limits`, …) |
| pool `_0`, `_2`, `_3` | 403 | 403 |
| pool `_1` (= live factory token) | 403 | **429** |

Setup-tokens carry the inference scope only; they cannot name their own
account. The mapping must be DECLARED, not inferred. And the `429` on `_1` is
the live factory account rate-limited at the moment of measurement — the exact
condition (`Observed condition: exhausted`, `.ai/anthropic-credentials.md:19-21`)
this plan exists to stop needing a human for.

## 4. Design shape (decided; objection invited)

Rejected outright:

- **Fabro config file** — the maintainer's own `livespec-ci.toml:1-9` note and
  the fail-closed worker allowlist rule it out; the overlay is the channel.
- **Exporting the short-lived access token** — §3 point 1.
- **Loop writes into the 1Password Environment via `op`** — a credential WRITE
  by the loop, through a wrapper that is a generated artifact of another repo,
  behind a 300 s cache, with service-account write ability unverified. Three
  new failure surfaces to buy a latency floor the selector design makes zero.

Adopted: **pool + declared mapping + published selection.**

1. **The pool stays where it is, keyed by caam profile.** One-time maintainer
   act (host-only, `needs-privileged-host`): rename or add Environment slots so
   each is named for the profile it was minted from —
   `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_0` … `__ANTHROPIC_4` — and mint the
   missing one(s) with `claude setup-token` (there are four slots and five
   profiles). The declaration IS the mapping; §3 proves nothing else can be.
2. **The loop publishes its selection, and only its selection.** After a
   switch verified by `SwitchResult.switched` — and idempotently on every pass,
   so a hand-run `caam activate` is caught within one cadence — the loop writes
   the active profile's NAME (no secret) to an owner-only file in its existing
   state directory, `~/.local/state/caam-usage-rotate/factory-profile`,
   atomically, the same way `state.json` is written (contracts.md
   §"The account-rotation operation" "Durable store"). A profile the loop
   cannot verify live is never published (spec.md "Only a live-verified account
   MAY be switched onto" already governs the switch; publication follows it).
3. **The Dispatcher selects.** Where `_dispatcher_credentials.py` reads
   `os.environ["CLAUDE_CODE_OAUTH_TOKEN"]`, it first reads the published
   profile name and prefers `CLAUDE_CODE_OAUTH_TOKEN__<PROFILE>` when that
   slot is present in the wrapper-injected env, falling back to the unnumbered
   name (so an absent file or unmapped profile degrades to today's behaviour,
   loudly logged). The wrapper still injects the full credential set
   (contracts.md:2242 unchanged); the secret never leaves 1Password; the
   300 s keyring TTL is irrelevant because every slot is always injected.

Why this ordering of trust: quota is per ACCOUNT, and the loop already reads
each profile's quota with that profile's interactive token, so the account the
loop selects for interactive sessions is by construction one with headroom for
its setup-token too. The loop is the right sensor; it should not become a
credential store.

## 5. Tier split and routing

- **Spec change, this repo** (`SPECIFICATION/spec.md:1009` §"Account rotation
  and quota supervision" — Scope, Durable store): the pass gains one more
  durable write, the published selection. That is new observable behaviour the
  Scope clause does not admit today → `propose-change`, supervised, never
  factory (`check-no-factory-spec-edits.sh`).
- **Implementation, this repo** (dispatch-safe, `impl:<id>`): publish step in
  `overseer/caam_anthropic_pass.py` / `caam_switch.py`, seam-injected on
  `home=`; mirrored byte-identically into `.claude-plugin/overseer/`
  (`tests/test_plugin_carrier_lockstep.py`); new state key under the
  underscore convention (`tests/test_caam_anthropic_loop.py:731`); prose
  contract `.claude-plugin/prose/caam-anthropic-loop.md` gains the publication
  paragraph; manifests bump in lockstep.
- **Implementation, orchestrator repo** (dispatch-safe there, its own plan
  child): the selector in `_dispatcher_credentials.py`. contracts.md:5516
  leaves the projection MECHANISM implementation-owned and :2242 is untouched,
  so this is not a spec change there — a reviewer may disagree; record it if so.
- **Host-only, maintainer** (`needs-privileged-host`): the Environment rename
  + the fifth mint (§4.1). Filed as a post-merge obligation, never as an
  in-sandbox acceptance criterion.
- **Out of scope, named deferral:** yearly `setup-token` expiry (`401`,
  `revoked`) still needs a human mint; the plan makes that per-account and
  annual instead of per-exhaustion and unscheduled. Where reconsidered: a
  later loop pass could surface "slot missing/revoked for profile X" as an
  attention row; not this plan.

## 6. Open items (none block the propose-change)

- Whether four slots ↔ five profiles means one profile deliberately has no
  factory token (e.g. `anthropic-0`, the maintainer's personal org) — the
  declared mapping answers it; the selector's fallback tolerates it either way.
- Whether the orchestrator repo wants the selector file path configurable via
  `.livespec.jsonc` rather than a fixed host path. Default: fixed path under
  the caam loop's state directory; configurable only if a second host needs it.
