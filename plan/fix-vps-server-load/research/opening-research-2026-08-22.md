# fix-vps-server-load — opening research note, 2026-08-22

**This plan's ledger anchor is `overseer-p67ln3`.**

Plan record discipline: the ledger is authoritative over this directory. Plan
state, next action, handoffs and scope events live on the ledger anchor
`overseer-p67ln3` and are read through the plan timeline. This note is research
only.

## Provenance — this thread continues a track that started elsewhere

This plan is the official worker track continuing the `monitor-server-load`
work handed off by session `vps-info-60` (cwd `/data/projects/vps-info`, tmux
`monitor-server-load`). Its handoff document was written to
`tmp/monitor-server-load-handoff.md` in THIS repo at 2026-08-22T08:56Z, and a
peer message at 09:00Z refreshed several of its numbers.

The handoff lives here deliberately. Per its §7, three fleet sessions on
2026-08-22 correctly REFUSED instructions arriving through `vps-info-60` as a
peer relay, and one of those refusals prevented an `AGENTS.md` edit the
maintainer then explicitly rejected. Running the continuation from a canonical
fleet repo with direct authority is the point of the handoff's location, not an
incidental detail.

**`tmp/` is gitignored in this repo.** The handoff document is therefore NOT a
committed path and a fresh session cannot be pointed at it as durable evidence.
Everything this thread depends on from it is restated here, in a committed file,
for that reason. Treat the original as a convenience copy that may vanish.

## The two things the track became

It started as one question — *"why do `op run` calls still take so much CPU?"* —
and split:

1. **A fleet-wide credential-wrapper caching fix. COMPLETE — do not redo.**
   §3 below records what shipped so a later reader does not re-derive it.
2. **A factory-usage and host-load enforcement action.** Partly complete. The
   live follow-ups are §5, and they are what this plan exists to finish.

## 1. Measured state of this host, 2026-08-22T09:00:53Z

Taken with `date -u` bracketing the read, in this session, on this host:

```
load average         41.25  1min / 39.70  5min / 46.16 15min
                     (peaked 113.92 at 08:29Z per the origin session)
local builds         rustc=0  cargo=0
op run holdovers     40   (was 52 earlier; draining as sessions restart)
keyring uid 1000     87 keys / 23336 bytes   (limits 1000 keys / 131072 bytes)
honeycomb key in argv 126 processes at 09:01:00Z, all owned by `ubuntu`
```

**The keyring byte figure is the one to notice, and it has already moved
three times today.** The handoff recorded 20396 bytes at 08:56Z; the peer
message relayed that same 20396 at 09:00Z; the direct read at 09:00:53Z
returned **23336**. All three are correct for when they were taken. The
load-bearing fact survives all of them: 23336 is **past the stock 20000-byte
per-uid ceiling**, so without the `services/keyring-quota/` sysctl change that
shipped on this track (§3) the wrapper cache would be returning `EDQUOT` right
now. The quota raise is not headroom-for-later; it is already the only reason
the cache works on this host.

**The peer relay carried a stale number that was true when written.** That is
worth recording as a live instance of the trap in §6.2 rather than as a
criticism — it is exactly how these numbers rot.

## 2. What is NOT the load source, and why the obvious sweep is wrong

The origin session's first process sweep flagged **45 sessions** as running
local builds. More than 40 of those were `pretooluse_background_guard`, a
PreToolUse hook present in every session, matched by a loose `uv run` regex.
Only **3** sessions were doing real compile or test work. Acting on the first
sweep would have interrupted roughly 40 workers, most of them foremen, over a
fabrication.

At 09:00Z there are **zero** `rustc` and **zero** `cargo` processes on this
host. Local builds are not the current load source.

The 40 `op run` holdovers are pre-deploy honeycomb-mcp servers, one per Claude
session, inert: no CPU, no 1Password quota draw, roughly 9.8 GB RSS including
children. They drain as sessions restart. They are not the load source either.

**Scope a sweep before it names anyone.** Any child of this plan that proposes
to act on a process inventory must state the discriminator it used to separate
real work from hook noise.

## 3. COMPLETED on this track — do not redo

### The wrapper caching fix

**Root cause.** `with-*-env.sh` gated its TTL cache on
`keyctl get_persistent @s`. `/etc/pam.d/sshd` carries
`pam_keyinit.so force revoke`, which revokes the SSH session keyring at logout.
The tmux server is reparented to init, so every pane and every agent beneath it
inherits a **revoked** keyring. The check failed, and because it was an `&&`
guard it fell through **silently** to the full `op run` path — where `op run`
wraps the real command and stays resident for its whole life. Measured 8.565s
versus 0.236s: a 36x penalty on every credential-touching call since
2026-08-17.

| Repo | Ref | What |
|---|---|---|
| `1password-env-wrapper` | `762676c` (PR #10) | recover the cache from a revoked session keyring |
| `1password-env-wrapper` | `fbee51a` (PR #11) | replace the re-exec with in-place `keyctl new_session` |
| `1password-env-wrapper` | issue #12 | `test/integration.bats` silently reinstalls live production wrappers |
| `vps-info` | `693c257` (PR #56) | `services/keyring-quota/` — sysctl drop-in plus idempotent installer |
| `openbrain` | `fab1a02` | re-rendered `scripts/with-openbrain-env.sh` |
| `resume` | `ef86109` | re-rendered `with-resume-env.sh` |

Deployed and verified on 8 wrappers across 3 hosts, each tested from a
deliberately revoked `@s`, asserting stdout is byte-identical under plain
capture and under `2>&1`:

```
vps                6 wrappers   warm 0.19–0.60s
hp-xubuntu         1 wrapper    warm 0.151s   (keyutils installed)
poweredge-xubuntu  1 wrapper    warm 0.092s   (keyutils installed; 0.085s in its systemd context)
```

`with-dolt-server-env.sh` was examined and **correctly excluded** — it is
systemd-creds backed and never calls `op run`.

### Why PR #11 exists — do not undo it

PR #10's design re-exec'd under `keyctl session -`, which prints
`Joined session keyring: N` to **stderr**. That corrupted
`openbrain/scripts/verify-openbrain-env.sh`, which captures with `2>&1` and
parses JSON. PR #11 replaced it with `keyctl new_session` — no exec, no
recursion guard, no probe. **`keyctl new_session` writes a bare keyring ID to
STDOUT**, so the `>/dev/null 2>&1` on that call is load-bearing rather than
cosmetic; unredirected it would corrupt every caller's payload channel.

## 4. Rulings settled by the maintainer — do not relitigate

1. **vps is NOT a factory dispatch target. hp is.** vps's fabro-server showing
   zero running jobs is the **desired** state, not idle capacity. `--factory
   vps` is not a remedy for a closed queue, for an ENOSPC, or for anything else
   absent an explicit instruction from the maintainer. The origin session's
   framing of vps idleness as "underutilization" is retracted and was struck
   from the orchestrator foreman's anchor ledger.
2. **Do NOT amend `livespec-orchestrator-beads-fabro/AGENTS.md:863-880`.** Its
   hand-build exemption for *"outward-facing upstream fabro PRs"* is correct as
   written. The reason is stronger than the clause itself states: **fabro is a
   third-party upstream repo**, and dispatching livespec factory work into it
   would pollute upstream MRs with livespec tooling. Hand-build there is correct
   **permanently** — not a workaround, not a gap.
3. **Do NOT onboard `fabro` as a governed tenant.** It is third-party. Its
   missing `.livespec.jsonc` and `.beads/config.yaml` are **intended**.
4. **The two vps factory runs were left to finish**, not killed. They cost about
   0.1% CPU combined — a policy violation, not a load problem.

A work-item asserting the opposite of #2 (`bd-ib-majsyl`) was filed by the
origin session's wrong analysis, reached **rank a0 — the front of the pick
order** — and is now **CLOSED** with `resolution:no-longer-applicable`. Do not
resurrect it.

## 5. Open work — what this plan is for

### 5.1 The vps routing question is ANSWERED, and the answer is a sticky ledger pin

The handoff's §5.2 asked "find what passes `--factory vps`", on the reasoning
that `.livespec.jsonc` sets `dispatcher.default_factory: "hp"` so vps must have
been chosen explicitly by some caller. **That framing is too narrow. Nothing
needs to pass a flag.**

Measured 2026-08-22 against plugin build `21ee1008de2d`,
`commands/_dispatcher_factory_ledger.py`:

```python
explicit = _explicit_factory(args=args)                       # --factory, else $LIVESPEC_FABRO_FACTORY
recorded = dispatch_factory_for(path=config, work_item_id=work_item_id)
factory  = explicit or _usable_recorded_factory(repo=repo, recorded=recorded)
target   = resolve_fabro_factory(cwd=repo, factory=factory)   # else default_factory
record_dispatch_factory(path=config, work_item_id=work_item_id, factory=target.name)
```

The last line is the finding. **Every dispatch PERSISTS its resolved factory
onto the work item's ledger metadata**, and the next dispatch of that item
prefers the recorded value over `default_factory`. So a single sanctioned
re-route pins the item to that factory **permanently**, and every later
dispatch of it goes to vps with nobody passing anything.

Confirmed on the ledger the same day. Four vps dispatches exist in
`tmp/fabro-dispatch-journal.jsonl`, all on 2026-08-22, keyed on the field
`dispatch_factory` (NOT `factory` — a tally keyed on the wrong name reports
zero and reads as "no vps dispatches ever"):

```
00:53:44Z  overseer-temi26.2
01:32:57Z  overseer-54k2za.11
08:39:54Z  overseer-6l7v.1
08:42:26Z  overseer-v2vs
```

`bd show --json` on those four: `overseer-temi26.2`, `overseer-54k2za.11` and
`overseer-6l7v.1` each carry `metadata.dispatch_factory = "vps"`.
`overseer-v2vs` — the run the maintainer said to let finish — showed no such
key at 09:0xZ while still `active`.

**`overseer-temi26.2` is the live one.** It sits at `backlog`, still pinned to
vps. Its next dispatch will land on vps, under a ruling that says vps is not a
dispatch target, with no operator involved. That is the one condition in this
plan that can still get worse while nobody is looking.

**Where the first pin came from is not a rogue actor — it is this repo's own
documentation.** `AGENTS.md:1021-1029` (`CLAUDE.md` is a symlink to it) instructs `--factory vps` as the
mitigation for the factory-host ENOSPC shape, in these words: *"Re-dispatching
to the second factory is a routing choice inside sanctioned configuration, not
a host mutation, and it needs no approval."* `overseer-temi26.2`'s 00:53Z vps
dispatch is exactly that remedy being followed. `.livespec.jsonc:263-265`
declares `vps` under `dispatcher.factories`, which is what makes it selectable
at all.

So ruling #4-adjacent policy and this repo's own AGENTS.md **contradict each
other**, and the AGENTS.md side is what a diligent session will obey. Bringing
AGENTS.md into line with the settled ruling is a **conformance fix**, not a
re-litigation of the ruling.

**Three separable pieces fall out, and they are not equally safe:**

- Clearing the stale vps pin off any item still carrying it is a ledger
  mutation with no trade-off. Do it.
- Correcting `AGENTS.md:1021-1029` so it stops prescribing a ruled-out remedy is
  a conformance fix. Do it, and say what a session should do INSTEAD when a
  factory host hits ENOSPC — silence there recreates the problem.
- Removing `vps` from `dispatcher.factories` is the one with a real cost: it
  deletes the only fallback for an ENOSPC condition that is **measured,
  intermittent, and fleet-wide while it lasts** (see `AGENTS.md` §"A SEVENTH
  SHAPE"). That is a maintainer trade-off, not a session call, and it should be
  presented with the cost stated rather than performed.

**A caveat on the pin scan.** A `bd list --json` sweep at 09:0xZ returned 50
items with 14 `hp` pins and zero `vps` pins — because the three vps-pinned items
found above are `closed` or `backlog` and fall outside that default listing. Do
not read that sweep as "no vps pins exist"; it does not cover the set where they
live.

**Settled from source already, so do not re-derive it:** `wip_cap` is
**repo-level, not per-factory**. `resolve_wip_cap(*, cwd)` is keyed on repo path
alone and `_dispatcher_admission.py` contains no reference to `factory`. So
`--factory vps` moves where a run executes and buys **no** extra slot. When the
queue is closed at `active_count=10 wip_cap=10`, the levers are the cap value or
the run duration, and both are maintainer calls. Journal evidence at 08:36:57Z
and 08:38:08Z shows both of those items `capacity-deferred` with
`active_count=10 wip_cap=10 free_slots=0` before their vps dispatches, so a
reader will be tempted to conclude the vps route bought a slot. It did not; a
slot freed in between (`overseer-au3pt3.12` reached PR at 08:38–08:41Z).

### 5.2 Honeycomb management API key exposed in `ps` argv — highest value, security

**126 process argv entries** contained the key in plaintext at 09:01:00Z,
readable by any local user. The count is RISING as sessions restart: 120 at
08:56Z, 123 at 09:00Z, 126 at 09:01Z.

`vps-info/AGENTS.md:1158` claims of this wrapper that the key is *"interpolated from
the child environment, never written to a file, git, or an argv visible to the
outer shell."* The same claim is repeated verbatim in the header comment of
`services/honeycomb-mcp/honeycomb-mcp.sh`. **Both are false as deployed**, and
the second is false in the very file that does the exposing.

The mechanism, read at 09:0xZ in
`vps-info/services/honeycomb-mcp/honeycomb-mcp.sh`:

```bash
export AUTH_HEADER="Bearer ${HONEYCOMB_MGMT_API_KEY}"
exec npx -y mcp-remote https://mcp.honeycomb.io/mcp \
  --transport http-only \
  --header "Authorization:${AUTH_HEADER}" \
  --silent
```

The variable IS exported, which is what makes the claim feel true on a skim.
The double quotes then expand it into argv anyway. `services/cloudflare-mcp/
cloudflare-mcp.sh` is the same pattern on `CLOUDFLARE_MCP_TOKEN`; 7 such
processes were live at 09:01Z.

**The fix is feasible and was verified rather than assumed.** The handoff said
"mcp-remote supports env-based headers; verify before relying on it". Verified
in the installed build at
`~/.npm/_npx/705d23756ff7dacc/node_modules/mcp-remote/dist/chunk-LB6BHXHQ.js:20938`:

```js
headers[key] = value.replace(/\$\{([^}]+)}/g, (match, envVarName) => { ... process.env ... })
```

mcp-remote substitutes `${VAR}` inside a header VALUE from its own environment,
logging `Replacing ... with environment value in header` on success and
`Warning: Environment variable '...' not found for header` on failure. Its
README documents exactly the shape these scripts want, `Authorization:${AUTH_HEADER}`
with the note *"no spaces around ':'"*.

So the change is to stop the SHELL expanding that token and let mcp-remote do
it. **There is a quoting trap in the way, and this file already documents it
against itself.** The payload is one single-quoted bash string, so an inner
single quote CLOSES it — the header comment in `honeycomb-mcp.sh` records that
exact failure between `7a688c5` and its fix, where the payload silently shrank
from 569 to 520 characters and lost the `exec` entirely, while `bash -n` still
reported the file valid. The safe form escapes the dollar for the inner shell
instead of re-quoting:

```bash
  --header "Authorization:\${AUTH_HEADER}" \
```

Acceptance for this work must be **behavioural, not textual**: after the change
and a re-install, `ps -eo args=` must show zero argv entries carrying the key
prefix, AND an MCP call must still succeed. A diff review alone cannot
distinguish the fixed form from the broken-payload form above.

Two things ride along and must not be dropped: the false claim in
`vps-info/AGENTS.md` and in the script header has to be corrected in the same
change, and **whether the exposed key warrants rotation is the maintainer's
call** — 126 argv entries readable by any local user is the fact to put in
front of them.

**Routing constraint, measured 09:0xZ: `vps-info` is not a governed tenant.**
It has no `.livespec.jsonc` and no `.beads/config.yaml`. Work whose deliverable
is a `vps-info` repository change therefore cannot be factory-dispatched from
the `livespec-overseer` tenant and has no tenant of its own to be filed in.
**That measurement is NOT a finding that vps-info should be onboarded.** The
identical inference — missing config therefore gap to close — is what produced
the rejected rank-a0 work-item described in §6.1. It is recorded here only so a
child that needs a vps-info edit is routed by hand from a session with that
repo checked out, rather than filed as a dispatchable item that can never run.

### 5.3 Four hosts never verified

Not reachable from the origin session; wrapper status unknown, and **not
re-measured by this session** — these rows are inherited, not confirmed.

| host | blocker as recorded 08:56Z |
|---|---|
| `macmini` | Tailscale SSH not enabled; OpenSSH denies publickey for ubuntu/chad/thewoolleyman |
| `nix-controller` | `tailscale ssh` connects then hangs (exit 124 on a bare `id`) |
| `aperture` | port 22 connection refused (no sshd) |
| `agentic-ai-vm` | offline since 2026-06-04 — 78 days as of 2026-08-22; propose dropping from scope |

macOS is uncached by design — the Darwin branch of the wrapper has no keyring
code at all — so `macmini` is very likely a no-op. **That is an inference, not
a measurement**, and it should be labelled as such wherever it is repeated.

### 5.4 Stale primary checkouts — a live tripwire for the next reader

Re-measured 2026-08-22T09:0xZ, and both figures match what the handoff recorded:

```
/data/projects/openbrain   branch main    64 behind origin   clean
/data/projects/resume      branch master  58 behind origin   clean
```

Git has the correct post-cache wrapper content; these working copies still hold
the **old pre-cache files**. They were deliberately not pulled, because dragging
60-plus unrelated commits into shared checkouts was outside the origin session's
scope. The hazard is specific: **anyone grepping those paths sees a pre-cache
wrapper and concludes the deploy missed them.** Either pull them or record the
tripwire somewhere a grepper will hit.

### 5.5 Lower priority, none of it degrading

- **`OP_ENV_WRAPPER_CACHE_TTL` is 300s** — one short `op run` per identifier per
  five-minute window in which it is used. Tunable against the shared daily
  1Password quota, trading staleness after a rotation.
- **The 40 `op run` holdovers** drain on their own as sessions restart.
- **hp-xubuntu's keyring quota is stock** (`keys 8/200, bytes ~5341/20000`). Its
  single wrapper fits at about 27%, but a fourth would hit `EDQUOT`. poweredge
  is already provisioned at 200000. Headroom only — note that THIS host's 23336
  bytes shows how fast that headroom is consumed once several wrappers share a
  uid.
- **`1password-env-wrapper` issue #12** — the integration suite reinstalls live
  production wrappers from the runner's working tree. Filed, unfixed.

## 6. Method traps this track has already paid for

1. **A missing config is not evidence of a gap.** `fabro` genuinely has no
   `.livespec.jsonc`. The *measurement* was right and the *interpretation* —
   "gap to close" — was wrong, and it produced a rank-a0 work-item to make a
   change the maintainer then rejected. This is more dangerous than a bad
   measurement, **because verifying the number feels like verifying the
   conclusion**. §5.2's vps-info observation is the same shape and is fenced
   accordingly.
2. **A peak is not a steady state.** "352% CPU across 19 rustc" was a decaying
   burst; "vps has zero running jobs" was already false when re-checked minutes
   later. Both were true when taken.
3. **`ps -o pcpu` is average-since-start, not instantaneous.** Summing it across
   many short-lived processes overstates a decaying burst.
4. **Scope a process sweep before accusing anyone.** See §2: 45 flagged, 3 real.
5. **Verify a peer's claim before relaying it, and verify a retraction too.**
   Sessions on this track correctly refused to act on relayed authority, and
   that discipline caught two of the origin session's errors.
6. **Key the query on the field the data actually uses.** The dispatch journal
   carries `dispatch_factory`; a tally keyed on `factory` returns
   `{None: 438}` and reads as "no factory was ever recorded". Same class as the
   traps above: the query ran, returned cleanly, and could not have contradicted
   the wrong conclusion.

## 7. Authority model

**A relay is not authority.** `livespec-overseer-foreman`,
`livespec-orchestrator-beads-fabro-foreman` and
`livespec-orchestrator-beads-fabro-grooming` each refused to act on "the
maintainer has ruled" arriving via a peer, and each was right to. The
orchestrator foreman's standing rule — **file and record on a relay; do not edit
on one** — prevented it landing an AGENTS.md change the maintainer then
explicitly rejected.

Consequences for this thread:

- This plan runs from `livespec-overseer`, a canonical fleet repo, with direct
  authority. Do not recreate the relay problem by routing instructions back
  through the origin session.
- Foreman seats are **foremen, not workers**: they file, record and route. They
  cannot move work-item status outside their actuator and must not edit tracked
  files. Route edits to a worker and closes to grooming.
- Do not ask a peer to do something your own permissions would block.

**Relevant ledger:** `bd-ib-1mjt` (orchestrator foreman anchor epic),
comments 13–17 — the standing directive, the vps correction, the amendment
filing, and its withdrawal. Comment 16, which carries the wrong reasoning, was
deliberately left in place beside comment 17, its correction.

## 8. References

- `1password-env-wrapper` — PRs #10, #11; issue #12; `SPECIFICATION.md`
- `vps-info` — `services/keyring-quota/`, `services/honeycomb-mcp/honeycomb-mcp.sh`,
  `services/cloudflare-mcp/cloudflare-mcp.sh`, `AGENTS.md` §"Kernel keyring quota",
  §"Host credentials"
- `livespec-orchestrator-beads-fabro` — `AGENTS.md:863-880`,
  `.ai/cross-tenant-execution-mirror.md`,
  `commands/_dispatcher_factory_ledger.py`
- `livespec-overseer` — `.livespec.jsonc` (`dispatcher.factories`,
  `default_factory: hp`, `wip_cap: 10`), `AGENTS.md:1021-1029`
- Origin handoff — `tmp/monitor-server-load-handoff.md` (gitignored; restated above)
