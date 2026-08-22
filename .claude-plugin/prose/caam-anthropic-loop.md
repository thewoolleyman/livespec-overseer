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

## Invocation Mode

Resolve the mode from the invocation text after the schedule check.

- Invoked with `--scheduled`: run the rebuilt account-rotation program without
  extra flags, so normal rotation triggers apply.
- Invoked without `--scheduled`: run it with `--force`. A manual run is an
  explicit request to move now, but force still refuses an account with less
  headroom than the current account and still refuses any account with zero
  weekly quota.
- Forward only these operator flags when present: `--force`, `--dry-run`,
  `--no-models`, `--foreman-model=<fable|opus|auto>`, and `--no-warm`.
  `--foreman-model=fable` and `--foreman-model=opus` pin the model enforced for
  sessions whose name carries the foreman suffix, and that pin persists in the
  operation state across later scheduled ticks until it is explicitly cleared.
  `--foreman-model=auto` clears the pin and restores the balance-derived
  behavior. `--no-warm` skips the idle-profile keep-warm maintenance for this
  pass.

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
