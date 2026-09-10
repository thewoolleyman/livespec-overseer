# llm-provider-manager — design intent and decisions (2026-09-10)

A NEW operator surface that manages the full lifecycle of LLM provider credentials
across MULTIPLE providers and PURPOSES — obtaining them, storing them, and rotating
them in place to avoid rate-limits / quota-exhaustion / outages. It supersedes, over
time, the Anthropic-only `caam-anthropic-loop`.

> READ `002-verbatim-discussion-transcript.md` IN THIS DIRECTORY BEFORE CHANGING SCOPE.
> It is the maintainer's own words. When an implementing agent forgets what it is
> building and starts yak-shaving, that transcript is the authority, not this summary.

## HARD CONSTRAINTS (maintainer-directed — non-negotiable)
1. **NO PROXY. Forbidden.** Anthropic/OpenAI crack down on subscription-gaming by
   inspecting headers/usage; a middleman that injects pooled subscription tokens per
   request is the exact fingerprint they flag. The mechanism is to **swap the REAL
   credential IN PLACE** so every session authenticates directly as ONE legitimately
   logged-in account — exactly what a human does. This RULES OUT LiteLLM / teamclaude /
   ccflare / claude-rotate as ARCHITECTURE (their quota-rotation LOGIC is a reference
   only). LiteLLM is a request-path proxy; its whole value is being in the request path;
   we are not in the request path.
2. **MINIMAL permissions everywhere** (least privilege). See the security section.
3. **NEW skill, built alongside — do NOT rename or surgically modify the working
   `caam-anthropic-loop`.** The two coexist; `caam-anthropic-loop` keeps running,
   untouched, the entire time. Deprecate it ONLY after `llm-provider-manager` is proven
   in production. Never leave a window with a broken skill.
4. **Do NOT pre-script per-provider login/token flows.** They rot. Give agents GENERAL
   instructions + web-search access + browser control and let them figure out each
   provider's CURRENT flow live. Any hardcoded per-provider process is forbidden.

## THE PROBLEM THIS SOLVES
The factory (fabro) kept hitting Anthropic's 5-hour SESSION limit under concurrent
multi-repo load because it was pinned to ONE account, while other accounts sat with
headroom. The prior `add-fabro-rotation-to-caam-skill` plan (now archived) tried to make
the factory follow caam's published account selection via per-profile 1Password env
slots — but that was inert (needed a manual host act to key the slots) AND concentrated
concurrent load on one account. The maintainer's redirection: stop hand-maintaining
tokens in 1Password; have a proper, provider-agnostic manager OBTAIN and ROTATE real
credentials, swapping them in place.

## TWO CREDENTIAL TYPES (proven 2026-09-10, scope not lifetime)
| credential | /api/oauth/usage | /api/oauth/profile | /v1/messages | lifetime | refresh |
|---|---|---|---|---|---|
| `claude setup-token` | 403 | 403 | 200 | long (~yearly) | none / never rotates |
| interactive OAuth token | 200 | 200 | 200 | short (~2.8–5.9h) | refreshed ~8h |
The factory needs INFERENCE only → the setup-token fits (long-lived, no refresh, no
mid-run expiry). Quota-driven rotation needs the interactive token (only it reads
`/usage`). You cannot collapse to one type — the scopes differ.

## ARCHITECTURE — independent axes, each a strategy/adapter seam
- **provider** — anthropic, openai/codex, x.ai, z.ai, LOCAL/self-hosted, …
- **credential-kind** — subscription OAuth, long-lived setup/CLI token, API key, local
  endpoint(+key). A local provider may have no token at all (URL + optional key).
- **purpose-tag** — interactive vs automated/"factory". THE unclaimed differentiator:
  no surveyed tool segregates credential pools by purpose, though Anthropic's own docs
  name the hazard (automation exhausting interactive quota).
- **signal-source** — the rotation trigger GENERALIZES to three kinds; the strategy must
  accept any: (a) subscription quota-% remaining; (b) rate-limit/error/outage
  observations (token-priced providers); (c) liveness/availability (local pools that go
  up/down). Never assume "% remaining" exists.
- **rotation-strategy** — pluggable, per-purpose, INDEPENDENT of the interactive
  algorithm. Copy the converged recipe as a reference (read windows → rotate at
  threshold or on 429 → distinguish pacing-vs-exhaustion → cooldown → consume-first).
- **SecretStore** — WHERE secrets durably live. Pluggable: 1Password today, AWS Secrets
  Manager / Parameter Store later. The rotation brain depends only on this port.
- **provisioning / in-place-swap target** — WHERE the live credential is written for the
  agent to read (env var / credential file / fabro config). Separate axis from
  SecretStore, so "where stored" and "how swapped in place" vary independently.

## SecretStore (make storage agnostic — strategy pattern)
Interface: `get / set / list / delete` + tags/metadata. Backends: `OnePasswordSecretStore`
(today), `AwsSecretsManagerStore`, `AwsParameterStore` (target), optional local encrypted
store. Migration = point config at a new backend + copy the pool once; ZERO brain changes.
(Today's 1Password coupling is only the `credential_wrapper` = `op run --environment` →
env-injection pattern; consumers read env vars, never call 1Password directly.)

## CREDENTIAL ACQUISITION SUBSYSTEM (the big new piece — agent-driven, browser-based)
- A DEDICATED, AGENT-MANAGED 1Password **vault** named `llm-provider-manager` (distinct
  from the locked-down Environments), reached by a service account scoped to ONLY that
  vault, read+write.
- The maintainer puts in it: provider LOGIN username/passwords (per account), and a
  Google OAuth token (Gmail, READ-ONLY) for reading provider verification/handshake
  emails. **MAINTAINER RULING (2026-09-10): use the maintainer's PRIMARY Gmail account**
  — everything is forwarded there and he will not set up a separate mailbox. `gmail.readonly`
  can only read the whole mailbox, so the acquisition agent can read the entire primary
  inbox; this broader scope is an ACCEPTED risk, not an oversight.
- Agents drive a **REAL, INSTALLED Google Chrome** (NOT Playwright's bundled Chromium, and
  NOT the Claude browser extension — the extension binds to the logged-in cloud account)
  running HEADED in a VNC session on the local machine. Playwright **attaches to that real
  Chrome over CDP** (real Chrome launched with `--remote-debugging-port`); it does NOT
  launch its own Chromium, because Google sign-in / Cloudflare Turnstile fingerprint and
  block automation-flagged Chromium before any CAPTCHA appears. Use a **persistent
  user-data-dir PER ACCOUNT**. Agents get GENERAL instructions + web-search + browser
  control and figure out each provider's CURRENT login/token flow THEMSELVES — whatever
  that provider requires (password, SSO, magic-link, whatever 2FA) — no pre-scripted
  per-provider flows. They log in, complete verification (reading Gmail), obtain tokens
  (e.g. `claude setup-token`, API-key creation), write them to the vault through the
  SecretStore port, and RE-ACQUIRE on expiry/revocation.
- The only RECURRING manual steps: (A) maintainer enters provider usernames/passwords once
  per account; (B) maintainer solves in-browser CAPTCHAs/2FA via the VNC session. (A
  one-time BOOTSTRAP is also the maintainer's — create the vault(s) + service account(s),
  the Google OAuth client + Gmail grant, and the VNC/Chrome setup — see note 003.)

## ROTATION BRAIN
Reads the pool from SecretStore + per-account signals, picks the best credential for a
purpose, and swaps it IN PLACE (no proxy). Per-purpose independent strategy. For the
factory under concurrency, each isolated sandbox gets one real account's credential
written into its own env/credential-file — in-place, direct-auth, not a shared proxy.

## caam — KILLED as a dependency
Retire the third-party caam binary. KEEP its in-place-swap MECHANISM (aligned with
no-proxy), owned by us. caam is a crowded-niche tool we cannot extend (third-party signed
Go binary), Anthropic-shaped, and none of the acquisition / SecretStore / purpose-tag
vision lives in it. `caam-anthropic-loop` (the overseer skill) stays running until the new
skill is proven, THEN is deprecated.

## PRIOR ART (5-lane web sweep, 2026-09-10) — adopt LOGIC, not architecture
- Gateways/proxies (LiteLLM, Portkey, Bifrost, new-api; teamclaude/ccflare/claude-rotate):
  quota-rotation LOGIC reference ONLY. All are request-path proxies → forbidden here.
- Local-pool routing (Olla, LiteLLM Router): only if we later want to load-balance our OWN
  machines — separable inference-serving concern, out of scope for the credential manager.
- Secrets managers (Vault, Infisical, 1Password, AWS): none do usage/health-aware
  SELECTION → the brain is ours. Store stays 1Password now, AWS later (agnostic).
- Nobody does purpose-tagging or unified multi-kind browser-acquisition → our
  differentiator.
- Anthropic is building native account-pooling (`anthropicAccountPool.enabled`,
  experimental) — WATCH it; it may subsume the interactive-Claude part.

## COMPONENTS (to groom into children)
1. New `llm-provider-manager` skill scaffold (coexists with `caam-anthropic-loop`).
2. `SecretStore` strategy + `OnePasswordSecretStore` (agent-managed vault); AWS backends later.
3. Provider / credential-kind / purpose-tag / signal-source / rotation-strategy model + brain.
4. In-place provisioning (factory + interactive) — NO proxy.
5. Browser-acquisition subsystem: VNC + headed Chrome + Playwright (not the extension);
   agent-driven with general instructions + web search; Gmail verification.
6. Security: minimal-permission service account scoped to the one vault; Gmail read-only/filtered.
7. Spec change(s) as needed; deprecate `caam-anthropic-loop` after the new skill is proven.

## OPEN QUESTIONS / RISKS
- **Security blast radius** — the vault (all provider passwords + Gmail OAuth, agent-writable)
  is the crown jewels. Least privilege, tight audit, minimal scopes.
- **ToS/detection on automated login** — milder than a proxy (inference stays direct,
  single-account), but many logins from one host can trip new-device/unusual-login checks.
  Email-reading handles the verification challenges; CAPTCHAs stay manual; pace human-like.
- **Reliability of agent-driven browser flows** — resilient BY DESIGN (no brittle scripts)
  but needs good general instructions + web search + retries + human CAPTCHA/2FA handoff.
- **SecretStore first** — 1Password now (confirmed); AWS SM/Parameter Store later.
