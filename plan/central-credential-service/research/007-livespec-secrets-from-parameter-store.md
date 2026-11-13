# 007 — Sourcing the shared livespec secrets from AWS Parameter Store (options, 2026-11-13)

Ownership: legacy-coordinator-agent assigned this design to this plan on 2026-11-13, recorded in the scope event of that day on
`overseer-iyfjbo`. The maintainer's ruling it serves is that every hetzner-xubuntu credential comes from AWS only (scope event on
`livespec-dev-tooling-6tgd2z`, 17:22:31Z). This note does not gate the Hetzner migration and carries no plan assertion. Creating
or changing any parameter is the maintainer's secrets act; this note only proposes.

## What is measured

The wrapper `with-livespec-env.sh` injects 33 secret names from the livespec 1Password Environment. It also adds its own two
settings, `OP_CACHE` and `OP_ENV_WRAPPER_CACHE_TTL`. These are names only, listed on the VPS from inside Python by `os.environ`
keys. No value was read for this note.

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

The committed AWS identity on hetzner, as reported by bootstrap-credentials-and-onboarding from `hetzner-xubuntu-info`
`config/credential-runtime.hetzner.json` and checked against the host's `/etc/hetzner-xubuntu-credentials/hxi-hetzner.json`:

- Account: homelab-gitops `672283019497`, region `us-west-2`, namespace `/gitops/v1`.
- Bootstrap user `hxi-hetzner-bootstrap`, with its key sealed by systemd-creds as `hxi-hetzner-aws-bootstrap`.
- Reader role `hxi-hetzner-reader`, and KMS key `de723c63-…`.
- Path prefixes:
  - `/gitops/v1/hosts/hxi-hetzner/`, host-scoped;
  - `/gitops/v1/repos/<repo>/`, repo-scoped;
  - `/gitops/v1/shared/providers/`, shared.
- The launcher is homelab's `shared-credentials` (`launch --manifest … --consumer <name>`). Its repeat-launch cache is homelab
  `hl-db7nul`.
- Today it costs about 7 AWS CLI calls per launch, with no cache (measured by dev-host-disk-retention, 2026-11-13).

Already in Parameter Store under that namespace:

- the factory bot's `app-id` and `private-key` under `/gitops/v1/shared/providers/github/thewoolleyman-factory-bot/`;
- a beads password under `/gitops/v1/repos/hetzner-xubuntu-info/`.

The single shared Claude Code token lives cross-account in homelab `888508923089`. It is NOT the same value as the livespec
Environment's bare `CLAUDE_CODE_OAUTH_TOKEN`, so a name match is not an identity match.

On hetzner today, retiring the wrapper means removing:

- `/usr/local/bin/with-livespec-env.sh` (root:livespec 0750);
- `/etc/credstore.encrypted/1password-env-wrapper-livespec`;
- `/etc/sudoers.d/with-livespec-env`;
- the `livespec` group grant;
- the 1Password service-account token that seal holds, which must then be revoked.

The interactive 1Password app and CLI stay (`/etc/sudoers.d/1password-desktop`), because the spec requires them.

## Prune before moving anything

Five of the 33 names should not move, under either option, because nothing should read them:

- `CLAUDE_CODE_OAUTH_TOKEN_0` is unread by any code (research 005).
- `CLAUDE_CODE_OAUTH_TOKEN_1` is a second copy of the anthropic-1 slot.
- The bare `CLAUDE_CODE_OAUTH_TOKEN` is the dispatcher's last-resort fallback only, and duplicates anthropic-1.
- `FABRO_DEV_TOKEN__hp` and `FABRO_DEV_TOKEN__vps` name factories that `/etc/livespec/fabro-factories.json` no longer
  registers (measured 2026-11-13: petri, mi-homelab, candidate, homelab-worker-arm64 only).

Confirm each with a names-only reader search before dropping it. Assertion 11 of this plan (one stored copy per credential) and
the maintainer's 2026-11-09 DRY ruling both point the same way. That leaves 28 names to source.

## Option (a) — fleet-wide move off the 1Password Environment

Every listed host and the role holder read the 28 names from Parameter Store through `shared-credentials`. The livespec
Environment and its service account are retired.

- **Store.**
  - Shared names go under `/gitops/v1/shared/providers/<provider>/<name>`, reusing the factory-bot paths that already exist.
  - livespec-only names (incident, E2E, recovery, Honeycomb livespec keys, beads) go under `/gitops/v1/repos/livespec/…`.
  - All of them are SecureString under KMS `de723c63-…`.
- **Reader identity.** Each host has its own bootstrap user and reader role, on the hxi pattern:
  - hetzner: `hxi-hetzner-reader` (exists);
  - vps: `hxi-vps-reader` (exists);
  - gmktec, poweredge, hp, gamingpc: each needs a new reader role, bootstrap user and seal, provisioned by committed
    automation.
- **Rotation.** The maintainer, or a future rotation job, writes a new parameter version. A consumer sees it on its next launch,
  or after the launcher's cache TTL once `hl-db7nul` lands. There is one place to rotate.
- **Retirement.**
  - On every host: the wrapper, its seal, its sudoers grant and the `livespec` group.
  - Once the last host has converted: the 1Password service-account token is revoked and the Environment deleted.
- **Cost.**
  - Every host must be provisioned.
  - Every seat on every host pays the launcher's per-launch AWS cost until `hl-db7nul` lands. On the CPU-saturated VPS that
    is the 41% `aws` reading measured today, multiplied.
  - It has the biggest blast radius: every hook and seat on the VPS reads this Environment today.

## Option (b) — a hetzner-scoped Parameter Store source fed from the same records

Only hetzner reads Parameter Store. The other hosts keep the 1Password Environment for now. Each parameter is written from the same
record the Environment holds.

- **Store.** The same paths as (a).
- **Per-consumer scoping on hetzner** (the AWS-only carrier `hxi-y56i6q`). Each consumer is a separate `--consumer` entry in
  `hxi-hetzner.json`, bound to `hxi-hetzner-reader` and given only the names it reads. The first-cut matrix is grouped by family
  and must be MEASURED per consumer before it is bound; that measurement is `hxi-y56i6q`'s consumer-to-authority matrix.

  | Consumer | First-cut names |
  |---|---|
  | `livespec-dispatcher` | the 7 `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_n`, `FABRO_DEV_TOKEN__petri`, `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `BEADS_DOLT_PASSWORD`, `HONEYCOMB_INGEST_KEY_LIVESPEC` |
  | `livespec-reconcile` | `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `BEADS_DOLT_PASSWORD`, `FABRO_DEV_TOKEN__petri`, `HONEYCOMB_INGEST_KEY_LIVESPEC` |
  | `livespec-seat` (interactive sessions and their hooks) | `BEADS_DOLT_PASSWORD`, `HONEYCOMB_MCP_API_KEY_LIVESPEC`, `HONEYCOMB_CONFIG_KEY_LIVESPEC`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` |
  | not on hetzner unless a measured reader needs it | the E2E, recovery, incident and CI-ingest names |

  Each consumer is a deny for every name it is not bound to, which is the allow/deny reader proof the carrier asks for.
- **Rotation.** Two stores hold each value until (a) completes, so a rotation must write both, Parameter Store first. That is
  a real drift risk for exactly the credentials this plan rotates:
  - the factory slots;
  - the Fabro dev tokens that `fabro_server` regenerates (see `overseer-iyfjbo.1`).
- **Retirement on hetzner.**
  - The wrapper, `/etc/credstore.encrypted/1password-env-wrapper-livespec`, `/etc/sudoers.d/with-livespec-env` and the
    `livespec` group grant are removed by `hetzner-xubuntu-info`'s committed automation.
  - The service-account token stays alive, because other hosts still use it. So "revoke the retired token" cannot be met
    under (b) alone.
- **Cost.** Hetzner only: no other host changes, and the launcher's cost lands on a new, unloaded box.

## Recommendation: (b) now, as stage 1 of (a), with Parameter Store as the record from day one

1. Prune the five names above.
2. The maintainer creates the 28 parameters once. From then on, the maintainer and every rotation write Parameter Store FIRST,
   and the 1Password Environment is a downstream copy that shrinks host by host.
3. Hetzner converts first, under (b)'s per-consumer manifest. This meets the AWS-only ruling where it applies today.
4. Each further host converts under (a) as it gets its reader role and seal, after `hl-db7nul` lands, so the VPS never pays
   uncached launches.
5. When the last host converts:
   - the Environment's remaining entries are deleted;
   - the service-account token is revoked;
   - the DRY end state, one stored copy per credential, holds.

The duplication in step 2 is bounded by a plan with a named end, rather than standing indefinitely. Converting the role holder's
own sessions stays deferred, as this plan already records.

## The maintainer ask this produces (non-blocking)

Create the 28 SecureString parameters under `/gitops/v1` in homelab-gitops `672283019497`, KMS `de723c63-…`, at the paths the
consumer matrix fixes. The values come from the livespec 1Password Environment's records of the same names.

This is a secrets act and the maintainer's alone. It is routed through legacy-coordinator-agent once the coordinator accepts an
option.
