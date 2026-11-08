# 004: a refresh revokes the prior access token; spec proposal review

Written 2026-11-08 by the seat `central-credential-service`. Markings as in note 002.

## 1. Maintainer rulings, 2026-11-08

Recorded verbatim on `overseer-iyfjbo`, in a scope event at 14:50:04Z:

- **Decision 2:** the additive refusal and model-enforcement seam into `caam-anthropic-loop` is approved ("Yes.").
- **Role binding:** no Tailscale tags ("they are viral and prevent automatic reaching from default tailnet"). A Tailscale Service
  host must be tagged (note 003 §3), so the binding is a **public DNS record**. The domain is not yet named.
- **The live forced-refresh proof:** "Permission given".
- **The DoD assertions:** the maintainer will review them later, so raise them again.
- **The homelab Environment:** it now holds `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_0..6`. The maintainer imported them from a file this
  seat wrote. The file is deleted, and the projection is verified by name and length.

## 2. Forced-refresh proof (MEASURED 2026-11-08 14:51Z, VPS, one run, Claude Code 2.1.319)

Run on idle `anthropic-3`. It was not the active account; the script refused to run if it was. The method was note 002 §4's
August one:

1. Copy the vault credential into a sandbox, with `expiresAt` set one minute into the past.
2. Run `claude -p --model haiku` there, so that Claude Code itself performs the refresh. The script never calls the OAuth
   endpoint.
3. Write the new credential straight back to the vault, but only if the vault file was byte-identical to its state at the
   start (it was). Every other key in the file was preserved.

| Step | Result |
|---|---|
| Vault before | Token expiring in 441 min |
| Probe on the locally-expired copy | Exit 0, `OK`, 7.8 s. Claude Code refreshed: new access token, **refresh token rotated**, new expiry 480 min |
| **Old access token, used right after the refresh** | **Exit 1: "Failed to authenticate: OAuth token revoked. Please log in again"** |
| New access token (control) | Exit 0, `OK` |

**Findings:**

- **Early refresh works on the current client.** A token with 7.3 h left can be renewed on demand by marking a copy expired,
  with the refresh delegated to the agent as §"Never refresh" requires. This closes note 002's open "early refresh" item.
- **A refresh revokes the previous access token immediately.** This closes note 002 §2.2's first unmeasured item, and it is the
  load-bearing fact for topology B.

**What it means for B (INFERRED):**

- Every refresh of the active account, by anyone, instantly blinds every enrolled host until the new token is pushed to it. A
  turn in that window gets a 401. Note 002 §2.1 measured such a turn failing after 2 retries in about 4.9 s.
- **Central must therefore own the active account's refresh timing.** It forces an early refresh at a moment it chooses and
  pushes immediately: to the enrolled hosts AND to the role holder's own live credential. Otherwise the VPS's sessions would
  refresh on their own near expiry and revoke every host's token unannounced, and a VPS session left holding the retired refresh
  token is exactly the family-revocation race of note 002 §1.
- **That collides with current behaviour.** `overseer/caam_warm.py` treats any change to the live credential by keep-warm as a
  hard failure ("keep-warm altered the LIVE credential -- this must never happen"). Making central drive the live account's
  refresh is a change to caam's live-credential handling, though not to its selection rules. It needs a maintainer ruling before
  P1 is designed. The other choices are to accept a blind window of seconds at each refresh (about once every 8 h for the
  active account), or to fall back to Option A.
- **Unmeasured:** whether Claude Code's own 401 retry re-reads the credential file, which would let a push arriving within a
  couple of seconds save the turn.

**Fleet scope: factory credentials are NOT affected (MEASURED 14:5xZ, same day).** The factory's injected
`CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_3` still authenticated right after `anthropic-3`'s interactive refresh (`claude -p`, exit 0,
`OK`), with `_4` as the control. The revocation hits the previous access token of the same interactive grant, not the
account's separate long-lived token. So factory per-run credentials (`llm-provider-manager-consumer`, the dispatcher's slot
pool) are unaffected by any interactive refresh, central or otherwise. Only holders of an interactive access token are exposed:
under B, the enrolled hosts.

### Options for who refreshes the active account (maintainer decision)

| | R1: central forces the refresh and pushes everywhere | R2: VPS sessions refresh as today; central watches the live file and pushes on change | R3: fall back to Option A (a login per host) |
|---|---|---|---|
| Blind window per refresh | Seconds, at a time central chooses | Seconds (watch plus delivery), at a time the VPS sessions choose | None across hosts |
| caam change | Yes: something other than the agent writes the live credential, which keep-warm forbids today | **None** | None |
| Refresh-token holders | Central, which must also write the VPS live file | The VPS live file only, as today | One per host per account |
| Fits B's ruling | Yes | Yes | No: reverses B |

**Recommendation: R2 for P1, and revisit R1 at P5.**
- R2 leaves caam and the VPS exactly as they are, which P1 already requires (note 002 §4, "Coexistence").
- It adds no new refresh-token holder, so the family-revocation race cannot arise.
- Its cost is a few seconds of 401 exposure on enrolled hosts about once every 8 h. Each rotation pushes a new account too, but a
  rotation revokes nothing.
- P1's soak MUST measure how many enrolled-host turns that actually loses. If it loses turns, the next step is R1, whose live-file
  write is easier to justify once P5 converts the role holder to a plain client.

## 3. Correction to note 003 §2

The passive watcher snapshotted the live credential at 14:30Z believing it held `anthropic-5`. It actually held `anthropic-6`:
its expiry matched `anthropic-6`'s snapshot, and the selection record caught up at 14:41:38Z. The watcher was also unsafe: a
caam rotation would have changed the live token and read as a refresh. It was stopped unfired, and its token copies were deleted.
§2 above replaces it.

## 4. The spec proposal is filed but NOT ready to commit

`/livespec:propose-change` filed `SPECIFICATION/proposed_changes/central-credential-service-enrolled-hosts.md`. It is
uncommitted, in worktree `~/.worktrees/livespec-overseer/spec/central-credential-service-enrolled-hosts`. The static doctor
phases passed. An independent agent ran the LLM-driven post-step, scoped to the clauses the proposal touches, and found
contradictions that block it:

1. **No lawful source for the delivered token.**
   - spec.md §"Account rotation and quota supervision" forbids the rotation operation to "publish, copy, export, or otherwise
     expose credential material".
   - contracts.md lets the manager provision only from its own provisionable-token store.
   - constraints.md forbids the manager reading another agent's credential source.
   The proposal must name the one sanctioned channel from the role holder's credential to the delivery component, and carve it
   out explicitly.
2. **The adapter model is run-bound.** contracts.md (around lines 1403 and 1548-1550) binds every conforming adapter to one
   `consumer_run_id`, forbids the host's live interactive credential as a destination, and refuses host-wide targets.
   `host-interactive-file` needs those rules scoped to run-bound adapters, plus its own relation to `target`, `provision`,
   leases and tombstones.
3. **"Exactly one instance" contradicts** contracts.md's "any number of concurrent callers". Reword as: only the role holder
   MAY decide, and the existing decision lock serializes it.
4. **The manager MUST NOT act proactively** outside a command (spec.md around line 1848), yet delivery is proactive. constraints.md
   also lists none of the delivery service's or client's prerequisites.
5. **Undefined terms and names.**
   - Not defined: "the service", "network identity", the staleness interval (which has no config key), and the account-identity
     fields (`oauthAccount`/`userID`).
   - "assignment generation" collides with an existing lifecycle term; rename it, e.g. "delivery sequence".
   - Dangling names: "account-publication record" should be "published selection record". "idle-profile keep-warm" should be the
     clause **The set of verifiable accounts MUST be actively maintained**. The protected-path list is per credential kind, not
     per target.
6. **Not yet explicit.**
   - "before expiry" has no lead time; §2 above now supplies the mechanism.
   - "until deprecated" has no trigger.
   - Not covered: enrolment migration on a role move, and an unreachable host's effect on a caam pass.
7. **Placement.** Proposal 3 needs a contracts.md wire contract (enrolment, status shape, audit-log location, revocation),
   several clauses lack scenarios, and the "authenticates on its next turn" scenario asserts third-party behaviour.
8. **BCP14.** Write "MUST NOT name" in place of "No ... MAY name", and "a machine other than the role holder MUST NOT hold a
   refresh token".

**Also owed in the redraft:** decision 2 is now ruled yes, so the redraft adds the refusal and model-enforcement seam. It should
wait for the refresh-ownership ruling in §2, which changes what the proposal says about the live credential.
