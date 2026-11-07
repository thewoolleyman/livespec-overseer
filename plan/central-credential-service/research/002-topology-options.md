# 002: topology options and recommendation

Written 2026-11-07 by the seat `central-credential-service`, for the maintainer's decision (coordinator-duties section 9). No
reviewer has read this note yet. Marking: **MEASURED** means observed by a named command or record. **INFERRED** means derived
and not exercised. **UNMEASURED** means nobody has checked it.

## 1. The fact that decides the design

A Claude interactive credential holds a refresh token that rotates on every refresh. `vps-info` plan `caam-snapshot-orphaning`
section 6 explains how copies die: a holder presenting a retired refresh token gets the whole token family revoked. The same
note's section 6a later weakened "the switch causes it", and section 8 records that the server-side rule is inferred from
behaviour, not documented. The practical rule is unchanged: **two machines must not both hold and use one refresh token.** So
"copy the vault credential to each host" is not an available design. Every option below is a different answer to this.

## 2. Measurements taken for this note

### 2.1 Claude Code runs on a credential with no refresh token (MEASURED 2026-11-07, VPS, one run each)

Sandbox `CLAUDE_CONFIG_DIR`, Haiku, the active account's access token, `refreshToken` removed, sandbox deleted afterwards. With
no refresh token in the sandbox, no OAuth family could be touched.

| Case | Result |
|---|---|
| Valid access token, no refresh token | Exit 0, normal reply |
| Same token with `expiresAt` set in the past, no refresh token | Exit 0, normal reply, 17 s API time against about 2 s for the first case |
| One live process, server-rejected token | Turn fails: `Failed to authenticate. API Error: 401 Invalid bearer token`, after 2 retries, 4.9 s |
| Same process, file atomically replaced with the valid token | Next turn succeeds in 1.7 s with no restart, and the turn after it too |

What this does not show, which the P0 proof must cover:

- It ran headless (`claude -p`, stream-json), not in an interactive TUI session.
- The replacement was the same account, not a different one.
- Nothing tested a token that genuinely expired server-side.
- The turn that hits the 401 is lost, so an unattended seat could stall. Delivery must happen BEFORE expiry, not after.
- A separate headless process, started expired and then replaced with the valid token, took 56.6 s on its second turn, and I
  did not explain that.

### 2.2 Other measurements

- **MEASURED, `hetzner-xubuntu`** (reported by seat `bootstrap-credentials-and-onboarding`, 2026-11-07): no `claude` binary, no
  credentials, no caam, 0 sessions. Seat migration starts at 2 sessions, and up to about 30 if the herdr tabs follow. Host changes
  come only from that repo's committed Ansible.
- **MEASURED, `hxi-tyzxmh` DoD**, verbatim from that seat: "The seats' Claude interactive accounts on hetzner-xubuntu are managed
  by the one central credential service, as a client of it, never by a per-host caam copy, an SSM token grant or a plain login."
- **MEASURED, VPS:** caam vault and loop seat live here; 7 accounts, `anthropic-0` to `-6`; 32 `claude` processes; load about 21
  to 24 on 18 cores. The incident observer stays here by maintainer ruling ("Keep vps", hetzner note 017), and the VPS host
  outlives the coordinator move (hetzner note 020, assertion 12).
- **MEASURED, flat tailnet:** `tailscale-admin/policy.hujson` grants every member full access to every member, and the tag
  apparatus is retired by maintainer ruling. Phones are members. **Reaching a port on the tailnet proves nothing about which host
  is asking**, so the service needs its own per-host identity.
- **MEASURED, the loop is host-bound on three inputs:** refusal records come from tracked sessions' transcripts
  (`overseer/caam_refusal_sessions.py`), model enforcement reaches tmux panes (`overseer/_caam_session_enforce.py`), and active
  identity reads the local credential (`overseer/caam_profiles.py`). The usage reading is account-wide, so it already counts every
  host's spend.
- **MEASURED, the loop is not a service:** it is a Claude session with a session-only cron that expires after 7 days
  (`.claude-plugin/prose/caam-anthropic-loop.md`).
- **MEASURED, spec:** the rotation operation MUST NOT publish or export credential material; `llm-provider-manager` is the
  distinct operation that provisions credentials, and `isolated-run` is its only enabled target (`SPECIFICATION/spec.md`,
  `.claude-plugin/prose/llm-provider-manager.md`). So credential transport belongs in the manager, and selection stays with the
  loop's identity-only record.
- **UNMEASURED:**
  - whether a refresh invalidates the previous access token;
  - whether two logins of one account create independent token families;
  - how macOS clients store the credential (expected to be the Keychain, not a file; not checked on these laptops);
  - whether the provider treats one access token used from several IPs as a signal.

## 3. The options

All three keep one selection brain, `caam-anthropic-loop` with its rules unchanged, and no process in the request path. All three
have a host client that pulls over HTTPS and applies changes atomically. They differ in who holds what.

### Option A: central brain, per-host logins (identity-only)

- **Holds:** each host keeps its own vault, with its own browser login per account, so each has its own token family. Central
  publishes only "activate this account"; the host client runs the swap locally.
- **Transport:** no credential ever crosses the network.
- **Cost:** accounts times hosts logins, 7 times 6 is about 42, repeated on every re-login. Each host also needs its own keep-warm
  and its own copy of the holder race.
- **Fails:** the `hxi-tyzxmh` DoD as worded ("never by a per-host caam copy ... or a plain login"), and the maintainer's standing
  objection to manual token upkeep (llm-provider-manager transcript).
- **Outage:** the best of the three. Hosts run indefinitely.

### Option B: central custodian, hosts receive access tokens only (RECOMMENDED)

- **Holds:** central alone holds refresh tokens. Each host receives only the selected account's access token, valid for at most
  8 h, and cannot refresh.
- **Why it fits:** no client host can trigger the race in section 1. One browser login per account, in one place. A stolen
  host credential is worth one account for at most 8 h.
- **Open risk:** section 2.1's gaps, and the unmeasured refresh behaviour.
- **Outage:** hosts keep working until the token expires, then fail at most 8 h after central goes down. Break-glass is a local
  `claude /login`, which the client reports as a detached host.

### Option C: central custodian, exclusive per-host lease of the full credential

- **Holds:** central leases the full credential, refresh token included, to one host at a time. An account is on one host only.
- **Why not:** two hosts cannot share an account, so hosts need different accounts, which is per-host account selection. That
  changes the selection rules this plan may not change. A sleeping laptop holds its lease hostage, and refresh tokens spread to
  every host. Each host's own session fleet keeps the holder race.
- **When to reconsider:** if the maintainer later wants hosts spread across accounts.

| | A | B | C |
|---|---|---|---|
| Browser logins | about 42, plus re-logins | 7, plus re-logins | 7, plus re-logins |
| Secret on a client host | Every account's refresh token | One access token, 8 h at most | One refresh token |
| Selection rules | Unchanged | Unchanged | Must change |
| Central down | Fine indefinitely | Fine for up to 8 h | Fine until lease needs moving |
| `hxi-tyzxmh` DoD as worded | Conflicts | Fits | Fits |
| Main unknown | Whether logins are independent | Client behaviour at refresh and expiry | Sleeping holders |

## 4. Recommended topology in detail

**Where it runs: the VPS.** The vault and loop are already there, so one instance exists on day one and nothing about caam moves.
The VPS outlives the coordinator move, and `incident_observer` is a working precedent for a tailnet-only service role with
1Password-projected secrets (livespec-dev-tooling `ansible/roles/incident_observer`). Its load should fall as seats leave.
Alternatives rejected: `hetzner-xubuntu` is scoped not to become a control plane (its note 002); `gmktec-xubuntu` carries the
factories, so an outage there would take both down together. The client reads the service URL from config, so moving the service
later is a config change.

**How hosts swap in place.** A small stdlib client, a systemd user unit on Linux. It polls often and also wakes on a
central change, then atomically merges `claudeAiOauth` into `.credentials.json`, leaving other keys such as `mcpOAuth` intact
(`caam-snapshot-orphaning` section 7.6), and updates the identity in `.claude.json`. Macs get a separate target adapter in P3.

**Coexistence on the VPS during P1.** The VPS stays exactly as it is, holding the full live credential, because the loop must stay
untouched. The service reads the active account's freshest access token from the live file, not the vault snapshot, which can
be up to 30 minutes old. Only `hetzner-xubuntu` runs access-token-only in P1. The VPS converts in P5.

**Refresh timing.** Delivery must beat expiry (section 2.1). The August refresh probe forced `expiresAt` into the past in a sandbox
to refresh early (`caam-snapshot-orphaning` section 5a). That needs re-measuring on the current client, and it needs to stay
delegated, because the spec forbids the operation from calling the OAuth endpoint itself.

**Least privilege.**

- A per-host enrolment secret, held 0600 or in the OS keyring, issued through 1Password or, for hetzner, its existing sealed
  credential path. The server checks it AND the Tailscale `whois` node identity, because the tailnet is flat.
- A host can fetch only its own current assignment. Enrolment is revocable per host. Every issue goes to an append-only, secret-free
  audit log.
- Interactive refresh tokens stay in the 0600 on-disk vault. They rotate every 8 h, and 1Password service accounts are rate-limited,
  so 1Password is not a hot store. Long-lived setup tokens and provider logins stay behind the `SecretStore` port, so AWS remains a
  later backend change.
- No `hxi-tyzxmh` SSM token grant. The hold condition rules it out.

**Monitoring.** One secret-free status endpoint: the existing account table plus, per host, assignment, generation applied, last
report, session count and refusals. Silent hosts show as stale. It feeds the overseerd attention surface and the existing caam OTel
spans, so there is no second dashboard to keep in step.

**How `llm-provider-manager` folds in.** The service is the manager's boundary with a network front, not a third system. Selection
stays with the loop's identity record. Transport is the manager's provisioning, with new target adapters beside `isolated-run`:
`host-interactive-file` and later `host-keychain`. Its provider, kind, purpose, signal and strategy axes then cover P2 and P4
unchanged, and purpose stays a policy partition over shared account usage. Its acquisition work is not needed for P1, because the
vault already exists. Its open children (`overseer-v3tutb`, `overseer-psqcmg`, `overseer-p6pod4`) become P2's dependency, and
need the coordinator to lift its 2026-11-02 hold when P2 starts.

## 5. Decisions only the maintainer can make

1. **The topology:** A, B or C. Recommendation: B on the VPS.
2. **One additive input to the loop.** Remote refusals never reach the loop, because it reads refusals from local transcripts. Once
   the coordinator moves, most refusals would happen where the loop cannot see them, and refusals are the trigger that catches a
   wrong usage reading (2026-10-13: 45 percent remaining nine minutes before refusal). The hard constraint says leave the loop
   untouched. Recommendation: allow one additive seam that feeds forwarded refusal records into the existing store, with no rule
   changing, and do the same for model enforcement on remote sessions. The alternative is to accept the blind spot in P1.
3. **One account across all hosts at a time.** This follows from "do not change selection", and it concentrates all hosts on one
   account. Recommendation: accept it for P1. Spreading hosts across accounts is a rule change, deferred until the maintainer asks.
4. **Fingerprint risk.** One access token in use from several IPs at once is a new shape. It is much milder than a proxy, but it is
   not what a human does with separate logins. It is unmeasured. Recommendation: accept it, watch for it in P1's soak, and fall back to
   Option A's separate logins if a provider reacts.

## 6. Refined phases

- **P0, the gate (host proofs before any build).**
  - Run an access-token-only client through a live interactive session on a sacrificial seat.
  - Swap to a different account in place.
  - Check whether refresh invalidates the prior access token.
  - Re-measure early refresh on the current client.
  - A failure sends the decision back to the maintainer, with Option A as the fallback.
  - Route the spec change through `/livespec:propose-change`: enrolled hosts in the rotation scope, the new target adapter, and the
    refusal seam if ruled in. Spec and code are separate children, so neither blocks dispatch.
- **P1, the blocking slice.** Central service, host client and status view, enrolled on the VPS (as the coexisting source) and on
  `hetzner-xubuntu`. Ready when `livespec-dev-tooling-bqnzcm` (`expedited-incident-response-flag`) is archived. Deployment roles land
  in livespec-dev-tooling (the service) and hetzner-xubuntu-info (the client and Claude Code install). P1 is proved by a real rotation
  observed on both hosts with sessions continuing.
- **P2, factory.** Long-lived injected credentials, central across every factory in `/etc/livespec/fabro-factories.json` (`petri`,
  `candidate`, `mi-homelab`) and the homelab workers, under a strategy independent of interactive rotation. Runs the manager's open
  children and the `llm-provider-manager-consumer` hook. Factory runs keep their token for the run, so this rotates between runs.
- **P3, laptops.** `chads-macbook-pro`, `macbook-m4-max`, `macbook-air`: `host-keychain` adapter, launchd unit, wake-time reconcile,
  detached-host detection. Measure macOS storage first. Claude Desktop is unmeasured and out of scope until measured.
- **P4, providers.** Codex first: `livespec-codex-cred-refresh.timer` and the factory's Codex overlay leg already exist. caam's vault
  holds no Codex accounts today (`caam-quota-resets` note 002). Then other providers through the same axes.
- **P5, deprecation.** Convert the VPS to a plain client, replace the session cron with a service schedule, then deprecate per-host
  caam, using the manager's own proof gate.

Sequence: P0 and P1 first, because hetzner waits on them. P2 to P5 order is for the coordinator to place once the maintainer sets the
track's rank.
