# 007 — Sourcing the shared livespec secrets from AWS Parameter Store (options, 2026-11-13)

Ownership: legacy-coordinator-agent assigned this design to this plan on 2026-11-13, recorded in the scope event of that day on
`overseer-iyfjbo`. The maintainer's ruling it serves is that every hetzner-xubuntu credential comes from AWS only (scope event on
`livespec-dev-tooling-6tgd2z`, 17:22:31Z). This note does not gate the Hetzner migration and carries no plan assertion. It only
proposes; every secrets act it implies is reserved to the maintainer (see "Reserved to the maintainer" below).

Revised 2026-11-14 for the coordinator's PASS-WITH-FIXES grade of #3012. Every claim below is either measured, with its source
named, or labelled as an estimate.

## What is measured

The wrapper `with-livespec-env.sh` injects 33 secret names from the livespec 1Password Environment. It also adds its own two
settings, `OP_CACHE` and `OP_ENV_WRAPPER_CACHE_TTL`. These are names only, listed on the VPS from inside Python by `os.environ`
keys (this plan's session, 2026-11-13). No value was read for this note.

| Family | Names |
|---|---|
| Claude factory slots | `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_0` … `_6` (7) |
| Claude stray copies | `CLAUDE_CODE_OAUTH_TOKEN` (equals the anthropic-1 slot, research 005), `CLAUDE_CODE_OAUTH_TOKEN_0` (unread by any code, research 005), `CLAUDE_CODE_OAUTH_TOKEN_1` (anthropic-1 again in this Environment, research 006) |
| Fabro dev tokens | `FABRO_DEV_TOKEN__petri`, `FABRO_DEV_TOKEN__hp`, `FABRO_DEV_TOKEN__vps` |
| GitHub factory bot | `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` |
| GitHub E2E and recovery | `GITHUB_APP_ID_E2E`, `GITHUB_APP_INSTALLATION_ID_E2E`, `GITHUB_PRIVATE_KEY_E2E`, `LIVESPEC_E2E_GITHUB_TOKEN`, `LIVESPEC_RECOVERY_APP_ID`, `LIVESPEC_RECOVERY_APP_PRIVATE_KEY` |
| Anthropic E2E | `ANTHROPIC_API_KEY_LIVESPEC_E2E` |
| Ledger | `BEADS_DOLT_PASSWORD` |
| Honeycomb | `HONEYCOMB_CONFIG_KEY_LIVESPEC`, `HONEYCOMB_GITHUB_CI_INGEST_KEY_LIVESPEC`, `HONEYCOMB_INGEST_KEY_LIVESPEC`, `HONEYCOMB_MCP_API_KEY_LIVESPEC` |
| Incident service | `LIVESPEC_INCIDENT_CONTROL_SECRET`, `LIVESPEC_INCIDENT_OBSERVER_QUERY_TOKEN`, `LIVESPEC_INCIDENT_QUERY_SECRET`, `LIVESPEC_INCIDENT_WEBHOOK_SECRET` |

The committed AWS identity on hetzner. bootstrap-credentials-and-onboarding reported it from `hetzner-xubuntu-info`
`config/credential-runtime.hetzner.json`. This plan read the host's `/etc/hetzner-xubuntu-credentials/hxi-hetzner.json` (names
and ARNs only) on 2026-11-14.

- Account: homelab-gitops `672283019497`, region `us-west-2`, namespace `/gitops/v1`.
- Bootstrap user `hxi-hetzner-bootstrap`, with its key sealed by systemd-creds as `hxi-hetzner-aws-bootstrap`.
- Reader role `hxi-hetzner-reader`, and KMS key `de723c63-…`.
- Today's manifest consumers are `hxi-backup` and `hxi-runtime`, and BOTH bind `hxi-hetzner-reader`.
- Path prefixes:
  - `/gitops/v1/hosts/hxi-hetzner/`, host-scoped;
  - `/gitops/v1/repos/<repo>/`, repo-scoped;
  - `/gitops/v1/shared/providers/`, shared.
- The launcher is homelab's `shared-credentials` (`launch --manifest … --consumer <name>`). Its repeat-launch cache is homelab
  `hl-db7nul`.
- It costs about 7 AWS CLI calls per launch, with no cache (measured by dev-host-disk-retention, 2026-11-13).

No other host has a reader identity. A search of every repository under `/data/projects` on 2026-11-14 found no `hxi-vps`
or other per-host reader role. The VPS, gmktec, poweredge, hp and gamingpc would each need a new one.

Already in Parameter Store under that namespace:

- the factory bot's `app-id` and `private-key` under `/gitops/v1/shared/providers/github/thewoolleyman-factory-bot/`;
- `/gitops/v1/repos/hetzner-xubuntu-info/beads/password`, bound as `BEADS_DOLT_PASSWORD` for consumer `hxi-runtime`.

The beads password is most likely the same credential stored twice, but its VALUE is not verified. The fleet runs one shared
`BEADS_DOLT_PASSWORD`, and isolates tenants by a per-tenant SQL user and a database-scoped grant, not by distinct passwords. That
is recorded in `livespec-overseer/.beads/config.yaml`, verified 2026-07-20. `hetzner-xubuntu-info`'s tenant is SQL user
`hetzner-xubuntu-info` on the same dolt-server port, 3307.

So the hxi parameter is very likely a second stored copy of that one shared password, and under either option it becomes the
single record. Equality is NOT verified, because no value was read. A value-free check is owed: one process on hetzner hashes
both values and prints only equal or unequal. That check is reserved to the maintainer.

The single shared Claude Code token lives cross-account in homelab `888508923089`. It is NOT the same value as the livespec
Environment's bare `CLAUDE_CODE_OAUTH_TOKEN` (research 006), so a name match is not an identity match.

What calls the wrapper on hetzner. This was measured read-only over ssh on 2026-11-14, by name search, and no file was changed:

- the `credential_wrapper` key of `.livespec.jsonc` in 12 of the 14 repositories under `~/workspace`, which is every `bd`,
  dispatcher and plugin call those repositories make;
- the justfiles of `hetzner-xubuntu-info` (1 reference), `livespec-console-beads-fabro` (2), `livespec-dev-tooling` (1) and
  `livespec-orchestrator-beads-fabro` (4);
- scripts:
  - `livespec-overseer/scripts/check-pre-push.sh`;
  - `livespec-dev-tooling/scripts/coordinator/{top5,fleet-utilization.sh}`;
  - `hetzner-xubuntu-info/scripts/honeycomb-triggers.sh`;
  - three `dolt-server` scripts: `with-dolt-server-env.sh`, `provision-dolt-server-credentials.sh` and
    `verify-dolt-server-dispatch-identity.sh`;
- the systemd unit `hxi-otel-ingest-env.service`;
- the plugin caches of `livespec`, `livespec-orchestrator-beads-fabro` and `livespec-overseer`.

Retiring the wrapper on hetzner therefore means replacing what those call sites reach, and then removing:

- `/usr/local/bin/with-livespec-env.sh` (root:livespec 0750);
- `/etc/credstore.encrypted/1password-env-wrapper-livespec`;
- `/etc/sudoers.d/with-livespec-env`;
- the `livespec` group grant.

The interactive 1Password app and CLI stay (`/etc/sudoers.d/1password-desktop`). `hetzner-xubuntu-info`
`SPECIFICATION/spec.md` requires "the 1Password application and CLI functionality needed for interactive AI work".

## Prune before moving anything

Five of the 33 names should not move, because nothing should read them. Four can go at once; the fifth needs a code change
first.

- **At once:**
  - `CLAUDE_CODE_OAUTH_TOKEN_0` is unread by any code (research 005).
  - `CLAUDE_CODE_OAUTH_TOKEN_1` is a second copy of the anthropic-1 slot (research 006).
  - `FABRO_DEV_TOKEN__hp` and `FABRO_DEV_TOKEN__vps` name factories that `/etc/livespec/fabro-factories.json` no longer
    registers (measured 2026-11-13: petri, mi-homelab, candidate, homelab-worker-arm64 only).
- **After a dispatcher change:** the bare `CLAUDE_CODE_OAUTH_TOKEN`. `livespec-orchestrator-beads-fabro`'s
  `resolve_factory_credential_env_name` (`_dispatcher_factory_account_selector.py`) names it whenever session-headroom admission
  picks no slot AND either caam has published no account selection or the selected profile's slot is not injected. It logs
  "factory credential slot fallback". With the name gone, that path would project no credential at all. So that repository must
  first change the fallback to REFUSE the dispatch with the fallback reason, rather than name a token that no longer exists. Until
  it does, the bare name stays, and the parameter count is 29, falling to 28 when the change ships.

Confirm each prune with a names-only reader search before dropping it. Assertion 11 of this plan (one stored copy per credential)
and the maintainer's 2026-11-09 DRY ruling both point the same way.

## Option (a) — fleet-wide move off the 1Password Environment

Every listed host and the role holder read the 28 names from Parameter Store through `shared-credentials`. The livespec
Environment and its service account are retired.

- **Store.**
  - Shared names go under `/gitops/v1/shared/providers/<provider>/<name>`, reusing the factory-bot paths that already exist.
  - livespec-only names go under `/gitops/v1/repos/livespec/<name>`. These are the incident, E2E, recovery and Honeycomb
    livespec keys, and the beads password.
  - All of them are SecureString under KMS `de723c63-…`. The path of every name is fixed in "Parameter paths" below.
- **Reader identity.** Each host needs its own bootstrap user, reader role and seal, on the hxi pattern. Hetzner has one
  (`hxi-hetzner-reader`). The VPS, gmktec, poweredge, hp and gamingpc each need a new one, provisioned by committed automation.
- **Rotation.** The maintainer, or a future rotation job, writes a new parameter version. A consumer sees it on its next launch,
  or after the launcher's cache TTL once `hl-db7nul` lands. There is one place to rotate.
- **Retirement.**
  - On every host: the wrapper, its seal, its sudoers grant and the `livespec` group.
  - Once the last host has converted: the 1Password service-account token is revoked and the Environment deleted.
- **Blast radius.** Every host. Every seat, hook, dispatcher and `bd` call that reads the Environment today moves. Those are the
  12 `.livespec.jsonc` wrappers per host, and the justfile and script call sites above.
- **Rollback.** Per host, as long as that host's wrapper and seal have not yet been removed: point the call sites back at the
  wrapper. The Environment stays populated until the last host converts, so a host can return to it at any point before then.
  After the Environment is deleted there is no rollback short of recreating it from Parameter Store.
- **Cost.**
  - Every launch on every host pays the launcher's per-launch AWS calls until `hl-db7nul` lands.
  - The added load on the VPS, the host that launches the most seats, has not been measured for this note.
  - AWS charges are in "Cost and effort" below.

## Option (b) — a hetzner-scoped Parameter Store source fed from the same records

Only hetzner reads Parameter Store. The other hosts keep the 1Password Environment for now. Each parameter is written from the same
record the Environment holds.

- **Store.** The same paths as (a).
- **Per-consumer scoping on hetzner** (the AWS-only carrier `hxi-y56i6q`). Each consumer is a separate `--consumer` entry in
  `hxi-hetzner.json`, given only the names it reads. The first-cut matrix is grouped by family and must be MEASURED per consumer
  before it is bound; that measurement is `hxi-y56i6q`'s consumer-to-authority matrix.

  | Consumer | First-cut names |
  |---|---|
  | `livespec-dispatcher` | the 7 `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_n`, `FABRO_DEV_TOKEN__petri`, `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `BEADS_DOLT_PASSWORD`, `HONEYCOMB_INGEST_KEY_LIVESPEC` |
  | `livespec-reconcile` | `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `BEADS_DOLT_PASSWORD`, `FABRO_DEV_TOKEN__petri`, `HONEYCOMB_INGEST_KEY_LIVESPEC` |
  | `livespec-seat` (interactive sessions, their hooks, and every `.livespec.jsonc` `credential_wrapper` call) | `BEADS_DOLT_PASSWORD`, `HONEYCOMB_MCP_API_KEY_LIVESPEC`, `HONEYCOMB_CONFIG_KEY_LIVESPEC`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` |
  | not on hetzner unless a measured reader needs it | the E2E, recovery, incident and CI-ingest names |

- **Where the deny is enforced: the launcher manifest, not IAM.** Today every hxi consumer binds the one role
  `hxi-hetzner-reader`, through the one bootstrap key, and every consumer runs as the same Unix user, `ubuntu`. So a consumer's
  "deny" holds only because the launcher reads its own manifest entry. Any process that can run the launcher can name another
  consumer and get that consumer's names.

  Making the deny an IAM fact would take a reader role per consumer, each with a policy allowing `ssm:GetParameter` and
  `kms:Decrypt` on that consumer's paths only. It would ALSO take a bootstrap identity per consumer, readable only by a separate
  Unix user per consumer. Separate roles alone change nothing while one bootstrap key can assume all of them.

  Recommendation: state the deny as manifest-enforced for stage 1, and make it a property of the reader proof (each consumer
  receives exactly its names). Defer per-consumer IAM, with separate Unix users, to a named follow-up if the maintainer wants
  the deny to hold against a hostile local process.
- **What replaces `/usr/local/bin/with-livespec-env.sh` on hetzner: a shim at the same path.** The 24 measured files listed above read
  that path, plus the plugin defaults, so a shim keeps every one of them working with no edit. The shim is committed in
  `hetzner-xubuntu-info`, takes the same `-- <command>` form, and runs
  `shared-credentials launch --manifest /etc/hetzner-xubuntu-credentials/hxi-hetzner.json --consumer livespec-seat -- <command>`.

  The two service units, the dispatcher and reconcile, call the launcher directly with their own consumer names, not through the
  shim. The three `dolt-server` scripts belong to dolt-server's own credential route (#106, item 2) and are checked separately.
- **Rotation.** Two stores hold each value until (a) completes, so a rotation must write both, Parameter Store first. That is a
  real drift risk for exactly the credentials this plan rotates. See step 2 of the recommendation for who changes each writer.
- **Retirement on hetzner, gated per consumer.** The wrapper and its seal STAY on hetzner until EVERY consumer has passed its
  reader proof on the shim: allow for its names, deny for the rest, by the manifest. Only then does `hetzner-xubuntu-info`'s
  committed automation remove `/etc/credstore.encrypted/1password-env-wrapper-livespec`, `/etc/sudoers.d/with-livespec-env` and
  the `livespec` group grant. The original wrapper's file is replaced by the shim.

  The service-account token stays alive, because other hosts still use it. So "revoke the retired token" cannot be met under
  (b) alone.
- **Blast radius.** Hetzner only. No other host, and nothing on the VPS, changes.
- **Rollback.** Until retirement, restore the original wrapper at the shim's path. Its seal is still present and still decrypts,
  so every call site is back on the Environment at once. After retirement, rollback needs the maintainer to re-seal a 1Password
  service-account token on hetzner.
- **Cost.** Hetzner's launches only. AWS charges are in "Cost and effort" below.

## Parameter paths

The consumer matrix fixes which NAMES each consumer reads. This table fixes WHERE each one lives. All are SecureString under KMS
`de723c63-…` in `672283019497`.

| Names | Path |
|---|---|
| `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY` | `/gitops/v1/shared/providers/github/thewoolleyman-factory-bot/{app-id,private-key}` (exist) |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | `/gitops/v1/shared/providers/github/thewoolleyman-factory-bot/{client-id,client-secret}` |
| `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_n` (7) | `/gitops/v1/shared/providers/anthropic/claude-code/setup-token/anthropic-<n>` |
| `FABRO_DEV_TOKEN__petri` | `/gitops/v1/shared/providers/fabro/dev-token/petri` |
| `BEADS_DOLT_PASSWORD` | `/gitops/v1/repos/hetzner-xubuntu-info/beads/password` if the equality check above passes, so it is not stored twice; otherwise `/gitops/v1/repos/livespec/beads/password` |
| the 4 Honeycomb names | `/gitops/v1/repos/livespec/honeycomb/<config-key,ci-ingest-key,ingest-key,mcp-api-key>` |
| the 4 incident names | `/gitops/v1/repos/livespec/incident/<control-secret,observer-query-token,query-secret,webhook-secret>` |
| the 6 GitHub E2E and recovery names | `/gitops/v1/repos/livespec/github/<e2e-app-id,e2e-installation-id,e2e-private-key,e2e-token,recovery-app-id,recovery-private-key>` |
| `ANTHROPIC_API_KEY_LIVESPEC_E2E` | `/gitops/v1/repos/livespec/anthropic/e2e-api-key` |
| bare `CLAUDE_CODE_OAUTH_TOKEN` (until the dispatcher change) | not created: a consumer still on the fallback keeps reading it from the Environment |

## Recommendation: (b) now, as stage 1 of (a), with Parameter Store as the record from day one

1. Prune the four names that can go at once, and file the dispatcher fallback change in `livespec-orchestrator-beads-fabro` so
   the fifth can follow.
2. The maintainer creates the parameters once. From then on, Parameter Store is written FIRST and the 1Password Environment is a
   downstream copy that shrinks host by host. Two writers are automated, or due to be, and each needs a named owner for that
   change:
   - **Fabro dev tokens.** `fabro_server` regenerates them. `overseer-iyfjbo.1` owns their storage, and its text currently names
     1Password as the source. It must be revised to name Parameter Store as the source, with `server.env` and the Environment
     rendered from it.
   - **The factory slots.** Today each `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_n` is a `claude setup-token` value, which is minted by
     an interactive login. So the writer is the maintainer, by hand: no committed code in this plan writes a slot, and
     `overseer/llm_provider_manager.py` stores none. `overseer-3evlnu` (parked), which gives homelab and hetzner per-account slots,
     is where an automated slot writer would land. Its text must name Parameter Store as the record when it resumes.
3. Hetzner converts first, under (b)'s per-consumer manifest and the shim. This meets the AWS-only ruling where it applies today.
4. Each further host converts under (a) as it gets its reader role and seal, after `hl-db7nul` lands, so no host pays uncached
   launches.
5. When the last host converts:
   - the Environment's remaining entries are deleted;
   - the service-account token is revoked;
   - the DRY end state, one stored copy per credential, holds.

The duplication in step 2 is bounded by a plan with a named end, rather than standing indefinitely. Converting the role holder's
own sessions stays deferred, as this plan already records.

## hetzner-xubuntu-info#106 and the AWS-only ruling

#106 (merged) prepares the dispatcher seat's tenant launchers on hetzner. Its "What the maintainer must supply" asks for three
things:

1. a new 1Password service account `hetzner-xubuntu-homelab`, with read access to the **homelab** Environment;
2. dolt-server credentials sealed on hetzner (`dolt-server-beads-password`, `dolt-server-claude-oauth-token` and others);
3. a homelab AWS owner decision.

Option (b) covers only the **livespec** Environment's names, so it does NOT replace ask 1 or ask 2:

- **Ask 1** is a separate interim. Read literally, the AWS-only ruling ("every hetzner-xubuntu credential comes from AWS only")
  also rules out a hetzner 1Password service account for the homelab Environment. Whether ask 1 stands as a dated interim, or
  is replaced by homelab names in Parameter Store read through the same launcher, is a call for the coordinator and the
  maintainer. This note flags the conflict but does not decide it.
- **Ask 2** seals copies of credentials that this note also sources: a beads password, a Claude OAuth token and the GitHub app.
  Under the DRY end state, dolt-server's wrapper should read the same Parameter Store records rather than hold its own sealed
  copies. That is a dolt-server owner change, outside this note.
- **Ask 3** is homelab's, and unchanged.

## Cost and effort (estimates)

- **AWS charges.** These come from AWS's published list prices as this plan knows them; re-check them on the AWS pricing pages
  before relying on them.
  - Standard-tier parameters cost nothing to store or to read at standard throughput. All 28 fit the 4 KB standard limit. The
    largest are the GitHub App private keys: RSA PEM files of about 1.7 KB at 2048 bits, or 3.2 KB at 4096.
  - The KMS key already exists, so it adds no monthly key charge.
  - Each SecureString read is one KMS decrypt, at about $0.03 per 10,000 requests.
  - Example: 1,000 launches a day, each reading the dispatcher's 12 names, is about 360,000 decrypts a month, or about $1 a
    month. Launch counts per host are not measured. `hl-db7nul`'s cache would cut reads further.
- **Effort**, an estimate from the hxi pattern, not measured:
  - Hetzner under (b): about one working day. That covers the shim, the three consumer entries, the reader proofs, and the
    gated retirement.
  - Each further host under (a): about half a day for its bootstrap user, reader role, seal, manifest and proof. That is
    roughly two and a half days for the five remaining hosts (VPS, gmktec, poweredge, hp, gamingpc), on committed automation.
  - Plus the dispatcher fallback change, and the `overseer-iyfjbo.1` revision.

## Reserved to the maintainer

Every one of these is a secrets act or an account act, and none is performed by this plan. They are routed through
legacy-coordinator-agent once the coordinator accepts an option:

- creating the parameters (28, or 29 while the bare token stays) at the paths above;
- the value-free equality check of the two beads passwords;
- minting the bootstrap users and access keys, and sealing them, for the five hosts other than hetzner, as each converts;
- deleting the five pruned names from the 1Password Environment (four at once, the bare token after the dispatcher change);
- revoking the livespec 1Password service-account token, once the last host converts;
- deleting the livespec Environment;
- deciding #106 ask 1 against the AWS-only ruling.
