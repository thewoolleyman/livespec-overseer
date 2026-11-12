# 006 — Host route for retiring the stale CLAUDE_CODE_OAUTH_TOKEN_1 copy (overseer-cwnedl, 2026-11-12)

On 2026-11-12, legacy-coordinator-agent (session 72dc4e8c) transferred `overseer-cwnedl` to this plan from homelab plan
secret-writer-stored-key-alias. This plan carries it for assertion 11 (one stored copy per credential). The retirement
itself, removing `CLAUDE_CODE_OAUTH_TOKEN_1` from the homelab 1Password Environment, is the maintainer's act, routed
through the coordinator's FOR THE MAINTAINER list. This note is the host leg the coordinator asked this seat to prepare:
a committed, reversible route to the item's first assertion, "no process on the vps holds fingerprint 6fd1f6914a0c".
No agent reads, rotates, writes or deletes the value. Every measurement below is a sha256 fingerprint (first 12 hex) or
a process count.

## What was measured (2026-11-12, about 03:30Z, on the vps)

- **54 processes hold `6fd1f6914a0c`.** They form 18 Honeycomb MCP trees of three processes each (`sh -c mcp-remote`,
  `npm exec mcp-remote`, `node .../mcp-remote https://mcp.honeycomb.io/mcp`). Research 005 counted about 30; the number
  moves with the number of live sessions. No other process kind holds it.
- **Each tree is spawned by a Claude Code session** as its Honeycomb MCP server. The launch is
  `sudo -n ... /usr/local/bin/with-homelab-env.sh bash -lc '<payload>'`, run as uid 1000. The variable enters at that
  wrapper: the first non-holding ancestor of every holder is the wrapper's `sudo` stage.
- **None of them uses it.** The payload reads only `HONEYCOMB_MGMT_API_KEY` (or the legacy `HONEYCOMB_MCP_KEY`), sets
  `AUTH_HEADER`, and execs `npx -y mcp-remote https://mcp.honeycomb.io/mcp`. `CLAUDE_CODE_OAUTH_TOKEN_1` is present only
  because `with-homelab-env.sh` injects the whole homelab Environment into its child.
- **Nothing reads the name.** A search of the homelab and livespec-overseer trees and `/usr/local/bin` finds
  `CLAUDE_CODE_OAUTH_TOKEN_1` only in prose: homelab's research note and exception register, and research 005 here.
  Claude Code itself reads the bare `CLAUDE_CODE_OAUTH_TOKEN`, not the numbered name.
- **A different value travels under the same name in livespec processes.** 181 processes carry
  `CLAUDE_CODE_OAUTH_TOKEN_1` with fingerprint `9223c8ccc926` (anthropic-1), injected by `with-livespec-env.sh` from the
  livespec Environment. That copy is NOT this item's subject. Every check below matches by fingerprint, never by name.
- **Holders turn over in hours.** A tree lives as long as the session that spawned it. Of the 17 trees whose session
  was resolved, 12 were under 3 hours old, 4 were 5.8 to 11.9 hours old, and the oldest was 25.5 hours.
- The item's context identifies the value as the stale 2026-08-23 copy. The live shared SSM token
  (`/homelab/v1/providers/anthropic/claude-code/oauth-token`) is version 2, re-minted for anthropic-2 on 2026-11-11.

## Correction to the item's caution

The item says that removing the key "before those holders move would break them". The measurement above says
otherwise: the holders inherit the value and never read it, so removing it breaks nothing. The order is in fact
reversed. While the key is still in the Environment, every restarted session spawns a new tree that inherits it again,
so restarting holders first achieves nothing. **The Environment removal must come first; the holders drain after.**

## The route

1. **Pre-check (this seat, read-only).** Run the fingerprint scan below. Record the holder count and confirm that every
   holder is a `mcp-remote` tree under `with-homelab-env.sh`. If any other process kind holds `6fd1f6914a0c`, stop: that
   process may read the value, and the route goes back to the coordinator before step 2.
2. **Removal (the maintainer, in person).** Remove `CLAUDE_CODE_OAUTH_TOKEN_1` from the homelab 1Password Environment.
   *Reversal:* re-add the variable. Before removing it, the maintainer decides whether to keep the value anywhere (for
   example an archived 1Password item) until step 5. Assertion 11 counts any kept copy, so it must be deleted at step 5.
3. **Natural drain (no action).** From the removal onward, every newly spawned Honeycomb tree lacks the key. Re-run the
   scan after 24 hours. Turnover measured above suggests most holders are gone by then.
4. **Residual holders (only with the coordinator's sanction).** For each tree still holding the key after the window,
   ask its owning session by cross-session message to reconnect its Honeycomb MCP server (`/mcp`, reconnect honeycomb).
   The reconnect spawns a fresh tree without the key. Where a session cannot act, the coordinator may sanction sending
   `SIGTERM` to that tree's `node .../mcp-remote` process. Its session then reports the Honeycomb server as failed until
   it reconnects, and nothing else in the session is touched. *Reversal:* `/mcp` reconnect respawns the server. No
   `sudo`, no kill of a Claude Code process, no restart of `overseerd`.
5. **Verification.** The scan reports 0 holders. A names-only listing of the homelab Environment (variable names, never
   values) shows no `CLAUDE_CODE_OAUTH_TOKEN_1`. Then the maintainer attests the removal on the item, and deletes any copy
   kept at step 2.

## Fingerprint scan (run as uid 1000; prints counts and kinds, never a value)

```python
import collections, hashlib, os
NAME, TARGET = b"CLAUDE_CODE_OAUTH_TOKEN_1=", "6fd1f6914a0c"
kinds = collections.Counter()
for pid in filter(str.isdigit, os.listdir("/proc")):
    try:
        env = open(f"/proc/{pid}/environ", "rb").read()
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
    except OSError:
        continue
    for kv in env.split(b"\0"):
        if kv.startswith(NAME) and hashlib.sha256(kv[len(NAME):]).hexdigest()[:12] == TARGET:
            kinds[b" ".join(cmd[:2]).decode(errors="replace")[:80]] += 1
print("holders", sum(kinds.values()))
for kind, count in kinds.most_common():
    print(count, kind)
```

## Out of scope here

- Narrowing `with-homelab-env.sh` so a child gets only the variables it needs. That would stop every session's MCP
  servers inheriting unrelated credentials, but it is the homelab tenant's wrapper. Recorded as an observation for
  homelab, not filed from this seat.
- The `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_0..6` Environment copies and the unread `CLAUDE_CODE_OAUTH_TOKEN_0` exposure.
  Both stay deferred to P2 (research 005, remedy item 4).
