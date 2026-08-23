# Strand 1 root cause: one seam, reproduced

Measured 2026-08-19 by the `test-and-gate-integrity` worker session while
executing the opening handoff's named next action. This note exists because the
three Strand-1 hermeticity items (`overseer-rvpehf`, `overseer-y2252y`,
`overseer-xogp6d`) were filed from three independent observation posts on three
different days, and the opening handoff only *conjectured* that they were one
defect. They are. The conjecture is now a measurement, and the seam is one line.

## The defect

`overseer/test_supervisor_builders.py:141` constructs the shared test
`Supervisor` with `store_path` and `stamp_path` scoped to `tmp_path` — and does
**not** pass `status_path`. `Supervisor.status_path` defaults to `None`
(`overseer/_supervisor_core.py:142`), and `write_status_snapshot`
(`overseer/_supervisor_snapshot.py:128-136`) resolves that fallthrough to the
module-level `DEFAULT_STATUS_PATH`, which is
`Path.home() / ".livespec-overseer-status.json"` computed at import
(`_supervisor_snapshot.py:40`).

So **every** test built through `make_supervisor` that reaches a snapshot write
publishes to the operator's real status file. The same builder also defaults
`now=lambda: 1000.0` (line 125), which is precisely where the epoch-1000
`written_at` in `overseer-xogp6d`'s evidence comes from.

Seven further direct `supervisor.Supervisor(...)` constructions in test code omit
`status_path` the same way: `overseer/test_supervisor_voiding_stale_blocked2.py`
(2), `tests/test_overseer_declare.py` (1),
`tests/integration/test_ready_arm_until_idle_live_tmux.py` (2), and
`tests/integration/test_startup_refusals_and_runtime.py` (2).

## Reproduction

Run one file with `HOME` redirected to a scratch directory:

```
HOME=<scratch> uv run --no-sync pytest \
  tests/integration/test_startup_refusals_and_runtime.py -q -p no:randomly
```

Eight tests pass, and `<scratch>/.livespec-overseer-status.json` appears,
containing:

```json
{
  "daemon_instance_id": "b6ee46fd7bc14b738325871331f41125",
  "rows": [{ "repo": "/tmp/pytest-of-ubuntu/pytest-8725/test_scenario_a_second_daemon_0/repo",
             "topic": "topic", "tmux": "topic", "status": "warned", "ctx": 40, ... }],
  "schema_version": 1,
  "tick_generation": 1,
  "written_at": "1970-01-01T00:16:40Z"
}
```

That single document carries **all three** filed signatures at once: the
epoch-1000 `written_at` of `overseer-xogp6d`, the `topic`/pytest-tmp-repo
placeholder row of `overseer-y2252y`, and the fresh `daemon_instance_id` +
`tick_generation: 1` + tiny fixture row count of `overseer-rvpehf`. The three
items are one defect observed three times, exactly as the opening handoff
conjectured.

Redirecting `HOME` is also why this reproduction is safe to run beside a live
daemon: the real snapshot is never touched.

## What this means for sizing

The item texts read as an investigation. The investigation is done. What remains
is a fix with three parts:

1. Inject a `tmp_path`-scoped `status_path` in `make_supervisor` and in the
   seven direct constructions. Patch the DEFINING module
   (`_supervisor_snapshot`), never a facade re-export, per `overseer/AGENTS.md`.
2. Add a suite-level guard (an autouse fixture, or a `conftest.py` check) that
   turns any write to the real `~/.livespec-overseer-status.json` into a test
   failure, so the seam cannot silently reopen. `tests/conftest.py` and
   `overseer/conftest.py` are both bootstrap-only today and are the natural
   homes.
3. Optionally, the daemon-side defence both `overseer-rvpehf` and
   `overseer-xogp6d` raise as "consider": refuse a publish whose `written_at`
   regresses hugely against the file it replaces, or guard the rewrite by
   instance id. This is the only part that touches daemon behavior, and the
   thread's scope event defers behavior changes to
   `plan/supervision-safety-and-attention-truth`. Treat it as out of scope here
   unless the implementer finds the gate cannot be made honest without it.

## The one part the factory cannot do

`overseer-rvpehf`'s acceptance carries a GATING live-verification exit criterion:
run the full suite on the host while the real daemon is up, and record verbatim
continuity evidence **in a ledger comment**. The fabro sandbox has no `bd` on
PATH and no live daemon, so that leg is structurally host-side — see this repo's
`CLAUDE.md` on ledger-edit items being undispatchable. It must be performed by a
host session after the repo change merges, and the dispatched item must say so,
or the run will reach acceptance and park at `blocked(human_input_required)`.

## Incidental finding, not part of this fix

`overseer/conftest.py`'s docstring still tells the reader to run the beside-tests
as `uv run pytest .claude/skills/overseer/ -q` — a path that no longer exists in
this repo. Same rotted-citation family as `overseer-zuhv` (Strand 2). Recorded
here rather than fixed, so it is not lost and does not widen this change.
