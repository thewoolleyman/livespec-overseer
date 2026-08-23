---
name: caam-anthropic-loop
description: Watch caam-managed Claude Max account usage and rotate safely.
---

# caam-anthropic-loop - Claude Max account rotation

You are running the account-rotation operation for this host. The operation
watches caam-managed Claude accounts, reports their quota table, and rotates the
active Claude credential only when the rebuilt account-rotation program decides
that doing so preserves or improves usable headroom.

This contract owns the operator-facing behavior. The harness bindings expose the
operation to Claude Code, Codex, and pi; they must only resolve the plugin root,
read this file completely, and execute it. Do not move schedule, mode, or
reporting rules into a binding.

## Schedule Self-Installation

At the start of every invocation, inspect the runtime's recurring jobs before
doing anything else.

1. Call `CronList` first.
2. If a recurring job already exists whose prompt starts with
   `/caam-anthropic-loop` and whose prompt contains `--scheduled`, keep it. Note
   its job id and continue the pass.
3. If a recurring job already exists whose prompt starts with
   `/caam-anthropic-loop` but lacks `--scheduled`, delete that job with
   `CronDelete`, then create the replacement below.
4. If no current scheduled-marker job remains, call `CronCreate` with this exact
   schedule:

       cron: "7,37 * * * *"
       prompt: "/caam-anthropic-loop --scheduled"
       recurring: true

5. After creating the job, tell the operator the job id, that it fires every 30
   minutes, and these two limits: the job lives only while this Claude session is
   open, and recurring jobs auto-expire after 7 days. Tell the operator to cancel
   early with `CronDelete <id>`.

Never wrap this operation in `/loop`. It schedules itself, and wrapping it creates
overlapping jobs. The `7,37` minute marks are deliberate: they avoid the `:00` and
`:30` fleet schedule marks. The marker belongs on the scheduled side, not the
manual side, so a lost marker degrades to an observable forced pass rather than a
silent never-force pass.

If this runtime has no Cron tools, report that the recurring self-installation
could not be performed in this harness, then continue the current pass. Do not
invent an alternate scheduler.

## Cutover Recovery Notes

The legacy `vps-info` watcher used the same session-only schedule shape. Its
last known job id before the livespec-overseer cutover was `9117bfe3`, firing at
`7,37 * * * *` with prompt `/caam-anthropic-loop --scheduled`. That job lived
only in the Claude session that owned the `caam-anthropic-loop-legacy` pane. It
left no host cron entry, no user systemd timer, and no system systemd timer; a
recurring job of that kind also auto-expires after seven days even if the pane
stays open.

If the legacy watcher must be restored before the cutover completes, open a
Claude session in the `vps-info` checkout and invoke `/caam-anthropic-loop`
there. The legacy project skill self-installs by listing recurring jobs and
creating the same `7,37 * * * *` schedule with prompt
`/caam-anthropic-loop --scheduled`. Confirm the new job id, leave that pane open,
and cancel any replacement livespec-overseer schedule so exactly one
implementation is scheduled. The first unmarked invocation is a manual forced
pass; after an outage, that is expected because it immediately re-evaluates the
active account. Do not wrap the recovery invocation in `/loop`, and do not keep a
second watcher pane alive, because recurring jobs are per-session.

Host schedule evidence was measured by the plan owner on 2026-08-23T06:5xZ and
recorded on work-item `overseer-54k2za.31`: the user crontab had only two
unrelated entries, no `/etc/cron*` file mentioned `caam`, the two user timers
were unrelated, and no system unit name mentioned `caam` or account rotation.
When re-checking that evidence, search for `caam` or the operation name, not for
`rotate`; `sysstat-rotate.timer` and `logrotate.timer` are log rotation and are
not account rotation.

During the cutover, a `session-gone` row for topic `caam-anthropic-loop` may
describe this repository's plan thread rather than the legacy watcher. The
daemon resolves a topic by tmux name plus repository cwd; a pane named for this
operation whose cwd is the `vps-info` checkout does not satisfy the
livespec-overseer plan-thread identity. Do not repair that row by restarting the
legacy watcher seat into this repository. The legacy slash command is a project
skill under `vps-info`, so moving the seat here can silence the row while
breaking the running watcher.

A resumed session whose model reads as `unknown` is also expected in this
operation. The model is read from the transcript, not the tmux status line, and a
resumed session writes to a differently named transcript. Treat `unknown` as
may-need-setting, bounded by the one-hour per-session memo, rather than as a
fault to chase. The cutover record observed this with `homelab-foreman`: it read
as unknown while genuinely running Fable.

## Invocation Mode

Resolve the mode from the invocation text after the schedule check.

- Invoked with `--scheduled`: run the rebuilt account-rotation program without
  extra flags, so normal rotation triggers apply.
- Invoked without `--scheduled`: run it with `--force`. A manual run is an
  explicit request to move now, but force still refuses an account with less
  headroom than the current account and still refuses any account with zero
  weekly quota.
- Forward only these operator flags when present: `--force`, `--dry-run`,
  `--no-models`, `--foreman-model=<fable|opus|auto>`,
  `--session-model=<session>=<fable|opus|auto>`, `--warm`, and `--no-warm`.
  `--foreman-model=fable` and `--foreman-model=opus` pin the model enforced for
  sessions whose name carries the foreman suffix, and that pin persists in the
  operation state across later scheduled ticks until it is explicitly cleared.
  `--foreman-model=auto` clears the pin and restores the balance-derived
  behavior. `--session-model=<session>=fable` and
  `--session-model=<session>=opus` pin one named session above every foreman and
  Fable-balance rule; `--session-model=<session>=auto` clears that session's exception.
  Session exceptions persist even when passed with `--no-models`, are
  reported in the table line as `exceptions:`, and are absolute: a session pinned
  to spent Fable is left there with a warning rather than silently moved. Idle-profile
  keep-warm maintenance is off by default; opt in with `--warm` or
  `CAAM_ROTATE_WARM=1`. `--no-warm` explicitly keeps it disabled for this pass.

Do not add retry, recovery, alternate thresholds, or a manual fallback. The
program owns the account decision.

## Running The Program

Run the shipped account-rotation program from the resolved plugin root for this
installation. Bindings provide `$PLUGIN_ROOT`; in Claude Code the equivalent
root is `${CLAUDE_PLUGIN_ROOT}`.

Use the mode rules above to choose the flags. Preserve the program's stdout and
exit code. If the program is not exposed by the installed plugin version, report
that as a failure of this operation surface and stop rather than reconstructing
the implementation inside the binding.

## Reporting

Show the account table verbatim. It is the point of the turn, not a detail to
summarize. After the table, add the decision line from the program and quote its
percentages rather than paraphrasing them.

If the program prints a line beginning with `FAIL`, say plainly that the pass
failed and stop. Do not retry with a lower threshold. Do not attempt `caam
activate` by hand. Do not use a cached or dark account as a destination.

For a successful scheduled, held, dry-run, forced, or switched pass, report the
decision exactly as printed and then stop. To stop watching entirely, delete the
recurring job id with `CronDelete`.
