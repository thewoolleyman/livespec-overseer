# 003 — Sonnet + Fable review findings and resulting revisions (2026-09-10)

Two independent adversarial reviewers (one Sonnet, one Fable) checked `001` against the
verbatim intent in `002`. This note records their load-bearing findings, the revisions
they drive into the design, and the decisions that are the MAINTAINER's (not the agent's)
to make. Where this note and `001` conflict, THIS note wins; `001` will be reconciled when
the plan is groomed into children.

## Revisions now folded into the design (agent-decided, from the reviews)

### Security (the highest-value findings)
- **Avoid the lethal trifecta.** Do NOT put (secrets) + (untrusted web content) + (an
  exfil channel) in one agent context — a provider page or web-search result read while
  "figuring out the flow" can prompt-inject the agent into pasting a password elsewhere.
  Split roles: a **research agent** (web search, NO secrets) writes flow notes; an
  **execution agent** (secrets, NO web search) drives the browser. The execution agent
  **never sees the password value** — a LOCAL tool reads the vault and types into the
  Playwright page, returning only success/failure. Token WRITES go through a local tool
  whose value is never echoed into agent context. (Both reviewers.)
- **Two stores / least privilege, not one blanket grant.** A **secrets** store (provider
  passwords + Gmail OAuth) reachable only by the acquisition execution agent; a **tokens**
  store that the rotation brain reads **read-only** and acquisition **writes**. The brain
  must never hold the credential that can read passwords/Gmail. State where the store's own
  service-account token lives (OS keyring, like the existing wrapper). Enforce SecretStore
  writes in acquisition go THROUGH the port (so AWS-later doesn't rewrite acquisition).
- **Leak paths.** Minted tokens shown once will land in agent transcripts
  (`~/.claude/projects`), Playwright traces/screenshots, VNC recordings, daemon logs.
  Require: a redaction policy, a local append-only audit of every vault write, VNC bound to
  localhost/SSH tunnel only, and the brain CACHING (1Password service accounts are
  rate-limited — do not poll).

### Constraint corrections
- **Restore the dropped acceptance criterion.** `001` lost the maintainer's concrete goal:
  seed the vault by copying the EXISTING `CLAUDE_CODE_OAUTH_TOKEN*` setup-tokens out of
  1Password (agent reads them via the wrapper env, probe-validates each, writes to the
  vault, mints the missing one), and the plan EXIT criterion is "maintainer can delete ALL
  `CLAUDE_CODE_OAUTH_TOKEN*` items." This is also the fastest outage fix (Slice 1).
- **"caam — KILLED" does NOT mean uninstall the binary.** The `caam-anthropic-loop` skill
  and the caam binary STAY installed and running until the new skill is proven for the
  factory. Phase it: factory purpose first; interactive purpose stays on caam until later.
  ("Proven" must be DEFINED — success criteria + soak — it currently isn't.)
- **Constraint (d) boundary:** "no pre-scripted per-provider flows" covers UI flows
  (agent-discovered). It does NOT forbid per-credential-kind **API validation probes** —
  those are APIs (the 403/200 table), they don't rot, and they're the ONLY success signal
  the agent has. Code the probes per kind; discover the UI.
- **In-place swap ≠ safe, and ≠ picked up by a live process.** (a) N sandboxes on N
  accounts from one egress IP is still a *usage* fingerprint (the header one is gone) —
  make the factory strategy default **consume-first** (drain one account, then the next),
  with "spread" opt-in, and record the trade-off. (b) An env-var swap is not seen by an
  already-running process — interactive provisioning needs a credential-file re-read or the
  overseerd ready/restart interlock (`marker-protocol.md`); name that dependency.

### Soundness
- **Shared per-account quota is the real constraint, not the tag.** An account's
  setup-token and interactive token bill the SAME 5-hour window. Independent *algorithms*
  per purpose is right; independent *signals* is impossible. Define **purpose-tag as a
  partition/policy** (accounts assigned to purposes, OR a per-account shared-usage ledger
  both strategies consult) so interactive and factory don't co-exhaust one account (the
  original bug). Each Anthropic vault item is a **pair** {setup-token, interactive
  token+refresh}; the factory needs the interactive token to read `/usage`. Add an
  **interactive-token-refresh** component (caam's `warm`/`overseer/caam_warm.py` does this
  today; it must be owned once caam is gone).
- **Observation channel + credential state machine.** With no proxy, signals come from
  (i) consumer failure reports (fabro's `errorKind: rate_limit` envelope; a 401 from a
  revoked token) via an explicit "consumer reports failure" API, and (ii) periodic
  revalidation probes. Model each credential as a state machine
  (acquiring→valid→suspect→revalidating→dead→reacquiring) with a **lock** so two agents
  never re-acquire the same account. Add a **circuit-breaker** for whole-purpose-pool
  exhaustion (fail/queue/backoff — decide which).
- **Vault item schema is the contract** between acquisition and brain — fix it in Slice 1:
  `{provider, account_id, kind, purpose, value(ref), acquired_at, expires_at,
  last_validated, status, previous_value}` + a name convention.
- **Where it runs:** decide daemon-loop (like the caam pane) vs on-demand.

### Cross-repo + SPEC (must be handled first)
- **v049 conflict — real.** `SPECIFICATION/spec.md:~1055` (ratified 2026-09-08) says the
  rotation operation MUST NOT publish/copy/export/expose credential material, and a
  consumer MUST NOT be expected to obtain a credential from it. The new manager's whole
  point is to PROVIDE a credential. Resolution: a **spec-change child FIRST** — the new
  operation is a *credential provider*, a distinct operator surface; v049's rule stays true
  of `caam-anthropic-loop`. Note the v049 published-selection-record becomes **vestigial**
  once the factory follows this manager — nobody should build on it. Also reconcile the
  CLAUDE.md "fixed operator-surface count" (a new surface is a maintainer ruling, as
  `drain-backlog` was).
- **Named cross-repo child:** the per-run sandbox credential selection lands in
  `livespec-orchestrator-beads-fabro` (`_dispatcher_credentials.py`; the review adapter
  uses the same token). Split spec-tier vs code-tier at FILING (mixed-tier deadlocks
  dispatch here).

### Browser-acquisition realism
- **Do NOT let Playwright launch its bundled Chromium** — Google sign-in and claude.ai
  (Cloudflare Turnstile) fingerprint it (`navigator.webdriver`, CDP artifacts) and block it
  before any CAPTCHA. Instead launch a REAL Chrome normally in the VNC session with
  `--remote-debugging-port` and **attach** Playwright over CDP (`--cdp-endpoint`), with a
  **persistent user-data-dir PER ACCOUNT** (one profile for five accounts is itself a
  fingerprint and makes `claude setup-token` ambiguous — it authorizes whoever the browser
  is logged in as). Persistent profiles hold session cookies = credentials OUTSIDE the
  vault — bound it (disk perms; or clear+re-login per acquisition).
- **Human handoff mechanics** (design them, don't let an implementer invent them badly):
  how the agent detects a CAPTCHA/2FA wall; notify via the daemon attention surface
  (`_supervisor_attention`); wait/timeout/resume; 3am behavior. A **step/time budget +
  give-up path** so provider-UI drift yields an attention item, not an infinite
  login-hammer (lockout risk). Note `claude setup-token` is CLI+browser (prints a URL,
  expects a pasted code) — the agent needs a terminal AND the browser.

### Scope — the risk-ordered slices (both reviewers converge)
- **Slice 1 — fixes the outage, ZERO browser work:** the two stores + service account(s);
  `OnePasswordSecretStore` (through the port); the vault item schema; **seed from the
  existing `CLAUDE_CODE_OAUTH_TOKEN*` tokens** (probe-validate, write, mint the missing
  one); the per-credential-kind validation probe; a consume-first factory strategy; the
  fabro per-run credential hook. **Proof:** two concurrent factory runs authenticate as two
  different accounts; the `CLAUDE_CODE_OAUTH_TOKEN*` pool is deletable.
- **Slice 2 — proves the risky core:** ONE provider, ONE account — execution agent attaches
  to real Chrome over CDP, logs in (maintainer does email/2FA by hand this once), obtains a
  setup-token, probe-validates, writes the schema item to the vault. **Proof:** probe 200 +
  a vault item matching the schema.
- **Deferrals (record per `.ai/deferral-successor-records.md`):** Gmail automation,
  multi-provider, interactive-purpose migration off caam, AWS SecretStore backends, local
  inference pools.

### Also missing (fold into grooming)
- The "general instructions" document for the acquisition agents is itself a DELIVERABLE
  and needs an eval (run against Anthropic + one other provider).
- Test strategy: a fake SecretStore for the brain; acquisition tested as a live-exercise
  per `overseer/AGENTS.md` conventions. No burning real provider quota to test rotation.
- Record ToS-on-automated-login as an explicitly ACCEPTED risk with a maintainer ruling —
  not `001`'s "milder than a proxy" softening.

## MAINTAINER DECISIONS — RESOLVED 2026-09-10
1. **v049 spec change + new operator surface — APPROVED.** Route a `propose-change` adding
   a credential-PROVIDER operation (reconciling v049, which stays true of the rotation
   loop) and ruling in a new shipped surface (as `drain-backlog` was ruled in). This is the
   FIRST step (gates Slice 1's fabro consumer hook).
2. **Gmail scope — PRIMARY account, read-only (accepted risk).** The maintainer will NOT
   set up a dedicated/forwarding mailbox; everything is forwarded to his primary account.
   `gmail.readonly` therefore reads the whole primary inbox — accepted, recorded as risk.
3. **Per-account login method — AGENT-DISCOVERED, do not pre-decide.** Maintainer: "you do
   whatever you have to do for the given provider; the agents will figure it out." So there
   is NO per-provider login-method decision to make — this is constraint (d). The agent
   handles whatever the provider presents (password / SSO / magic-link / whatever 2FA); the
   maintainer solves CAPTCHA/2FA walls via VNC. Remove this from open questions.
4. **Confirmed:** `/2FA` in the manual steps, the consume-first default, and the Slice 1 /
   Slice 2 ordering + the deferral set.
5. **Security suggestions — ACCEPTED, with one exception:** the role-split (research vs
   execution agent), the two-store least-privilege split, out-of-band secret injection
   (execution agent never sees the password value), leak-path controls (redaction, audit,
   localhost-bound VNC, brain caching) all stand. The ONE exception is the dedicated
   mailbox (see #2) — primary account is used instead.
6. **Chrome — REAL INSTALLED Google Chrome via Playwright, NOT bundled Chromium, NOT the
   Claude extension.** (Recorded in 001; re-confirmed here as a hard requirement — attach
   Playwright over CDP to the real installed Chrome, persistent user-data-dir per account.)
