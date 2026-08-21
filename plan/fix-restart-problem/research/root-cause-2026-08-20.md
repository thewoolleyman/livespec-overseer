# fix-restart-problem — root cause of the 2026-08-20 foreman restart failure

> **STATUS AS OF 2026-08-21T07:00Z — READ THIS BEFORE THE ROOT-CAUSE SECTIONS
> BELOW.** This document is dated, and every measurement in it was correct when
> taken; two of the four causes it describes as live defects are now FIXED and
> merged. Nothing below has been rewritten — the measurements are the evidence
> and they stay as recorded — but a reader arriving today would otherwise take
> RC1 and RC2 for open problems, which is exactly the stale-premise failure this
> repository keeps paying for.
>
> This plan's ledger anchor is `overseer-vr3ym4`, and it — not this file — holds
> the thread's current state as timestamped handoff entries. **Read the newest
> entries there for anything time-sensitive; this file is a root-cause record,
> not a status board.**
>
> | cause | where it stands | evidence |
> |---|---|---|
> | RC1 detector blindness | **FIXED, merged** as `b75ad94`. The acting daemon runs it; the thirteen "resume not submitted" rows and four settling rows went to zero. | `overseer-gdwkdf`, pending-approval |
> | RC2 round survives session replacement | **FIXED, merged** as `fa851bd` (PR 1342). Round close generalised past `PlanTrack` to all three seat kinds; the identity refusal is preserved. | `overseer-5serwd`, acceptance |
> | RC3 seat-epic clobber | Unchanged, and deliberately not taken here — owned by `track-record-type-safety`. | scope event on the epic |
> | RC4 foreman behaviour | Contract change not yet landed; the item is assessed as needing a split before dispatch (two of its five criteria need a maintainer answer and a live tick). | `overseer-7pqr3p`, ready |
>
> Item 3 of "What this plan should hold" (settling past a bound is an attention
> condition) landed as `overseer-srogg6`; item 5 (the live-shape canary) landed
> as `overseer-62qver`, whose fixture pair is proven discriminating. The host
> drain landed as `overseer-znwv4r`.
>
> **A FIFTH CAUSE WAS FOUND AFTER THIS NOTE WAS WRITTEN, and it is the largest
> one still open.** A session that winds down CORRECTLY and declares `ready`
> **outside** a daemon-opened round can never certify, is never restarted, and
> the daemon says nothing at all — the row renders as plain idle with no log
> line and no attention condition. It is independent of RC2: a verified daemon
> bounce onto the merged RC2 fix did not clear the tracks stranded by it. Three
> sessions stranded this way in a single sixteen-session sweep, each having been
> told "restart armed" by the declare command. Tracked as `overseer-vr3ym4.1`.
> The mechanism, read from the code rather than guessed, is recorded on that
> item together with a real-world stale-`ready` specimen taken from this host.


Opened 2026-08-20 by the `debug-restart-problem` session under a direct
maintainer order ("find the root cause bug(s)" behind the
`livespec-overseer-foreman` seat sitting at 14% context, never restarted by
`overseerd`, arguing about restart-vs-tick instead of restarting). Everything
below was MEASURED against the live host, the daemon log
(`tmp/overseer/daemon.log`), the sidecars under `$HOME`, the running
processes, and the tree — not inferred from the foreman's own narration.

Four causes stack. Two are new and untracked (RC1, RC2); one is tracked in
`track-record-type-safety` (RC3); one is the foreman's own behaviour under
the first three (RC4).

## RC1 — Claude Code 2.1.237 changed the idle input-box border; the daemon's idle detector is blind to every session on that build

`overseer/signals.py` `_BORDER_RE = ^[─—━]{3,}.*[─—━]{2,}$` requires at
least TWO trailing rule characters on a box border. Sessions launched with
`claude -n <topic>` carry the topic in the top border. On Claude Code
**2.1.235** (sessions started 2026-08-19) that border ends `… <topic> ──`;
on **2.1.237** (installed 2026-08-20T01:04Z; every session started after
that, including every daemon respawn) it ends `… <topic> ─` — ONE trailing
rule. So `signals._is_border` is False for the top border,
`_input_box_present` never finds an empty `❯` between two borders,
`is_idle_input` is False, and `_supervisor_observe.observe` reports
`idle=False` for a pane that is visibly at an empty prompt.

Measured with the daemon's own predicate over all 45 live claude panes
(2026-08-20T21:20Z): every 2.1.237 pane → `idle=False box=False busy=False
gate=False` with an empty prompt visible and `above_is_border=False`; every
2.1.235 pane → `idle=True`. Cross-checked against `/proc/<pid>/exe`:
pid 2407774 (the foreman) → `versions/2.1.237`; pids 3291270 and 443085
(two `──` panes) → `versions/2.1.235 (deleted)`. Current installed binary
is 2.1.238; the shape is unchanged from 2.1.237 (this session renders `─`).
`_BORDER_RE` itself is unchanged since the repo scaffold (`ceaca74`,
2026-07-21) — this is an upstream TUI change, not a regression in the tree.

Consequences, all through `_supervisor_evaluate_idle.idle_decision`
("pane present but not a verified idle-input state and not busy — wait;
never act"):

- the row reads `settling` forever, and `settling` is rendered GREEN
  ("actively working") — no attention condition, no log line. The foreman
  produced zero daemon-log lines between 12:36Z and 21:12Z while falling
  from ~50% to 14%.
- no wrap-up at 50/40/30/20/10 (`_fresh_guarded_paste_observation` requires
  `fresh.idle`), no keep-going nudge, and NO RESTART EVEN ON A VALID
  `ready` — the `elif request.ready` branch is below the `settling` return.
- `signals.input_box_ready` shares `_input_box_present`, so a completed
  resume submit is never confirmed, `resume_pending` never clears, and
  `_supervisor_resume_retry.resume_retry` calls `resend_enter` — up to
  `SUBMIT_MAX_ENTERS` (8) keystrokes per tick, every tick, indefinitely —
  into 13 live panes (`restarting (resume not submitted — daemon retrying
  Enter)` on the live table; 42 `STILL not submitted` alerts on 2026-08-20).
  `overseer-ulyv` (supervision-safety-and-attention-truth) files that
  symptom with a different hypothesised cause ("no empty box rendered
  mid-turn"); its own comment records that no live pane was captured. The
  box IS rendered and empty; the regex is what fails. ulyv's proposed
  `input_box_text` keying also depends on `_is_border` and would not
  restore idle detection.

## RC2 — a wrap-up round survives an out-of-band session replacement, and entity seats never recover it

`~/.livespec-overseer-stamps.json` key `/data/projects/livespec-overseer\t
livespec-overseer-foreman` still holds the PREDECESSOR's round as of
21:12Z: `at=2026-08-20T03:17:30Z`, `bands=[50]`,
`session_identity=claude:1521187:354055360:livespec-overseer-foreman`,
`expired_at=04:15:02Z`, `expiry_notice_sent=true`. The maintainer recreated
the tmux session by hand at 04:28:23Z (pane `%13` → `%114`, claude pid
2407774). The sidecar key is cleared only by the daemon's own restart path
(`_supervisor_state.clear_state`) or by
`_supervisor_round_recovery.close_recovered_round`, which is gated
`isinstance(track, registry.PlanTrack)` — so for a ForemanSeat,
GroomingSeat or SupervisorSeat the round is never closed.

Effect on the replacement session, independent of RC1: band 50 is already
consumed (no first wrap-up at 50%); any `ready` it writes is refused
"session identity differs from round-open identity" (exactly what the
daemon logged at 04:28:45Z and 04:29:51Z against the predecessor's leftover
declaration); `_fresh_ready_without_round` cannot apply because
`round_record.at is not None`; and `expire_aged_ready` refuses to raise the
floor ("ready expiry observed under a different session identity; floor
not raised", 04:46:34Z). The state file still reads `ready-expired: …`
(mtime 04:46:34Z). Nothing short of a hand-clear of the sidecar key makes
this seat restartable again. The identity REFUSAL is correct by design
(`overseer-f7ogs2`); what is missing is a round RESET when the live
identity changes under an open round for a non-plan seat.

## RC3 — the predecessor's `ready` was refused for 67 minutes: "ready cannot respawn: no foreman epic recorded" (tracked)

Daemon log, 2026-08-20: 03:17:32Z wrap-up injected into the predecessor at
50% → ~03:21Z it declared `ready` → 03:21:40Z through 04:28:10Z roughly 110
refusals at ~35 s cadence → 04:15:20Z the declaration expired (1817 s) →
04:15:56Z expiry notice injected → the predecessor re-declared (04:16:29Z
by arithmetic) → still refused → 04:28:23Z hand relaunch. The seat row's
epic had been clobbered back to `legacy-unresolved:livespec-overseer-foreman`
(residual carrier `overseer-ooro`: running foreman sessions on pre-fix
plugin builds still run the remove-then-append register clobber hourly),
and since `32a8892` (02:21Z) `_track_ready_to_restart` no longer
re-derives a ForemanSeat epic, so an unresolved foreman epic is a hard
refusal. The replacement session rewrote `overseer-z5fo4y` through the
supported writer at 05:44Z. Three seats still carry `legacy-unresolved:`
in the live store (livespec-driver-pi-foreman,
livespec-orchestrator-beads-fabro-foreman, livespec-overseer-grooming) and
will hit the same refusal on their next `ready`. Owned by
`track-record-type-safety` (`overseer-y3xhlh.6` blocked, `overseer-ooro`
P1, `overseer-axql66` and `overseer-25fnu2` pending-approval). Not
re-filed here.

## RC4 — the foreman's model of the situation was wrong and it never acted on it

At 13:17Z the foreman read the daemon log correctly up to a point ("the
epic was the sentinel … the ready on disk belonged to a predecessor … the
stamps entry still carries bands: [50] keyed to 1521187") and concluded
"the daemon isn't stuck; it's waiting on me — complete this round and
declare ready". That premise was false twice over: under RC1 it is never
verified idle, and under RC2 its own `ready` would be refused. It then
asked "say restart and I'll declare ready" at 13:19Z, 15:16Z, 16:15Z and
21:02Z instead of declaring (the decision-authority stall shape), and at
21:02Z argued that ticking and restarting were equivalent. The foreman
contract (`.claude-plugin/prose/foreman.md`) carries no self-initiated
wind-down rule; it relies on the daemon's wrap-up, which RC1/RC2 suppressed.

## Side facts worth keeping

- The acting `overseerd` (pid 420767, started 10:29:02Z from checkout
  `6dbba17`, package 1.3.0) predates release 1.5.0; not a cause (RC1 is
  upstream), but the fix needs the ruled ff + bounce-into-top-pane
  procedure.
- Fleet table at 21:11Z: 13 rows `restarting (retrying Enter)`, 4 rows
  `settling` (three foremen + the grooming seat), 2 `picker-stalled`.
- `just worktree-create` works again in this repo (2026-08-20; the
  recipe now delegates to `dev-tooling/worktree-lib.sh`), contrary to the
  AGENTS.md note measured 2026-08-04.

## What this plan should hold (first cut; the scope event records it)

1. RC1: accept the 2.1.237 border shape in `signals._BORDER_RE` with a
   fixture captured from a live 2.1.237 pane AND a 2.1.235 pane as the
   discriminating pair; prove `is_idle_input` / `input_box_ready` /
   `input_box_text` on both; bound the resend-Enter exposure so a blind
   detector can never keystroke a pane indefinitely.
2. RC2: reset an open round (stamp, bands, expiry, notice, identity) when
   the live session identity differs from the round-open identity for a
   non-plan seat, and generalise `close_recovered_round` past PlanTrack.
3. A below-threshold track stuck in `settling` (not idle, not busy, no
   gate) for longer than a bound is an attention condition, not a green
   row.
4. `prose/foreman.md`: a self-initiated wind-down at a named remaining-
   context floor (append handoff, then `overseer-declare ready`) that does
   not wait for the wrap-up, and does not ask.
5. A live-shape canary: a test or check that captures the installed Claude
   Code build's idle prompt shape and fails loudly when the detector
   cannot see it.
