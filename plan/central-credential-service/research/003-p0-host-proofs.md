# 003: P0 host proofs for topology B

Written 2026-11-08 by the seat `central-credential-service`, after the maintainer chose topology B ("OK go with B", recorded as a
scope event on `overseer-iyfjbo` at 2026-11-08T14:24:00Z). Markings as in note 002: **MEASURED**, **INFERRED**, **UNMEASURED**.
Every run below was on the VPS, once each, with Claude Code 2.1.319. No credential value was printed. Each sandbox was deleted
after its run.

## 1. Interactive client on an access token alone, then a swap to another account in place (MEASURED, PASSED)

Sacrificial seat: an interactive `claude --model haiku` TUI on a private tmux socket (`tmux -L ccs-p0`), so overseerd never
tracked it. It used a throwaway `CLAUDE_CONFIG_DIR` with session-level `ANTHROPIC_*`/`CLAUDE_CODE_*` variables unset. The
credential file held `claudeAiOauth` with `refreshToken` removed, so no token family could be touched. `oauthAccount` was copied
from the vault's `.claude.json`. Both files were written by atomic rename.

| Turn | Credential on disk | Result |
|---|---|---|
| 1 | `anthropic-0` access token | Replied `ALPHA`, 2 s model time |
| 2 | Atomically replaced with `anthropic-2` access token and `oauthAccount`, session still running | Client printed "Claude can't use thinking from another organization", then replied `BRAVO` |
| 3 | Unchanged | Replied `CHARLIE`, 1 s |

What this settles:

- The interactive TUI, not only `claude -p`, runs on an access token with no refresh token. This closes note 002 §2.1's
  "headless only" gap.
- **A different-account swap takes effect in place, on the next turn, with no restart.** The other-organization notice is the
  server's own evidence that turn 2 authenticated as the new account, not a token cached in memory. This closes §2.1's
  "same account only" gap, and with it the question of whether the client re-reads the file.
- The client did not rewrite either file. After turn 3, `.credentials.json` still had no refresh token and `oauthAccount` still
  named `anthropic-2`, although the client had written `.claude.json` itself in the meantime.

The cost to carry into the design (MEASURED): a cross-account swap drops the session's preserved thinking. The client warns that
the next responses "may be slower and use more tokens because it has to reread this session". Every caam rotation today pays the
same cost, so B adds no new one. It is a reason not to swap more often than selection requires.

## 2. Does a refresh invalidate the previous access token? (IN FLIGHT, passive)

Measured without performing any refresh. A copy of the live (`anthropic-5`) access token was taken at 14:30Z, with no refresh
token. The baseline call succeeded. A watcher waits for the host's own sessions to refresh the live credential, as they do near
expiry, then calls the provider once with the old copy and once with the new token as a control. Ten minutes later it calls once
more with the old copy. The result is appended below when it lands. Script: the seat's scratchpad `p0/refresh_watch.py`
(not committed; it handles live tokens).

If the old token keeps working until its own expiry, hosts can run on their delivered token through a central refresh. If it
dies, the central service must deliver a new token BEFORE it refreshes, or a host loses a turn to a 401 (note 002 §2.1).

## 3. Role binding (MEASURED; needs a maintainer ruling)

The requirement: clients reach the service through a name bound to the credential-rotation role, and moving the role changes
nothing on any client (DoD assertions 9 and 10).

- **Tailscale Services are the designed fit, but they need a tag.** The VPS runs Tailscale 1.104.4, which has `tailscale serve
  --service` and `advertise`. The docs (kb/1552, validated 2026-10-07) say a Service "keeps the same address when you move it to
  another host" and gets an HTTPS certificate for its own name. They also say: "Any device you want to use as a Service host must
  use a tag-based identity. You cannot use a device authenticated with a user account as a Service host."
- **That collides with a standing ruling.** `tailscale-admin/AGENTS.md`, maintainer-approved posture 2026-08-17: "No persistent
  machine tag is approved — not `tag:nix-controller`, not `tag:hetzner`, not any role tag." `policy.hujson` has
  `"tagOwners": {}`. Tagging a host also removes it from every `autogroup:member` grant, the pitfall that file warns about. On the
  VPS, that would cut its other services off unless explicit grants were added.
- **MagicDNS cannot carry it.** kb/1054: "It's not possible to add arbitrary records to MagicDNS."
- **The tag-free alternative is a public DNS record.** For example, a CNAME from a role name in a domain the maintainer controls
  to the role holder's `*.perch-rudd.ts.net` name, repointed when the role moves. (INFERRED, not exercised.) The node's Tailscale
  certificate does not name the role, so the service would run plain HTTP inside the tailnet's WireGuard, or carry its own
  certificate. Either way, both ends authenticate at the application layer: the per-host enrolment secret plus Tailscale `whois`
  on the server side, and a pinned server key on the client side. That last part is needed because the tailnet is flat.
- **A value rendered onto each client does not qualify** (note 002 §4).

Recommendation: the public DNS record. It leaves the tag ruling untouched, and the move is one record change. Choosing Tailscale
Services instead needs an explicit exception to the 2026-08-17 posture for the role holder.

## 4. Still open in P0

- **Early refresh on the current client** (note 002 §4): this needs a real refresh against a live account. The coordinator
  carries it as an explicit maintainer go-ahead. P1 does not depend on it (INFERRED): during coexistence the
  service reads the active account's token from the live file, which the VPS's own sessions already refresh. It becomes necessary
  once the role holder converts to a plain client (P5).
- **A token that genuinely expired server-side**, and the unexplained 56.6 s second turn from note 002 §2.1: both UNMEASURED.
- **Decision 2** (the refusal and model-enforcement seam into the loop): unruled. It is needed before P1 carriers are filed.
