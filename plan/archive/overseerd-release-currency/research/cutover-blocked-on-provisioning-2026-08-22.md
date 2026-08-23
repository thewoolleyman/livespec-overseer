# The cutover cannot succeed — the prefix will not provision on this host

ledger anchor `overseer-6s3pk6`

Every child that builds the self-update path is merged. This note records why
that still buys nothing on this machine, and why the obvious way to find out
would have taken the fleet's supervisor down.

Measured 2026-08-22T18:25–18:27Z, with the acting daemon deliberately left
running.

## The measurement

`runtime_prefix.ensure_current_runtime()` returns `None`:

```
The virtual environment was not created successfully because ensurepip is not
available.  On Debian/Ubuntu systems, you need to install the python3-venv
package using the following command.
    apt install python3.13-venv
```

The prefix has never existed here. Before this measurement,
`~/.local/share/livespec-overseer/runtime/` held exactly one file —
`rollback-state.json` — and no version directory at all.

**Both steps fail, not one.** `ensure_runtime` creates a venv and then pip-installs
into it. Step 1 fails as above. Step 2 would fail independently: probed against a
stdlib venv on this host, `<venv>/bin/python -m pip --version` answers
`No module named pip`. An implementer who fixes only the creation call will meet
the same wall one line further down.

## Why this is a blocker and not a footnote

`start.py`'s `main()` calls `ensure_runtime()` and, on `None`:

```
"failed to prepare the daemon-owned runtime prefix; overseerd was not launched
 from the working tree."
return 1
```

**The bootstrap refuses to launch any daemon.** The natural reading of `.10` —
stop the acting daemon, then run the bootstrap — would therefore have left every
tracked session in this repo with no supervisor: the old daemon dead, no new one
started, and a `return 1` as the only notice.

It was avoided only by installing the prefix **first**, while the old daemon kept
running.

> **Provision and verify the prefix executable exists before stopping anything.**
> It costs one command and converts a potential fleet outage into a failed
> command.

That belongs in the cutover procedure permanently. The ordering constraint already
carried onto `.10` said the prefix must be installed at the intended release
before the start; what was missing is that the install can **fail**, and that the
bootstrap's answer to a failed install is to launch nothing at all.

## The two-way control, which names the remedy

This host provisions Python environments with `uv`, not with the stdlib module.
The repo's own `.venv` — the one the acting daemon runs from — records it:
`uv = 0.9.26`, CPython 3.10.16.

| command | result |
|---|---|
| `python3 -m venv <dir>` | **fails**, ensurepip unavailable, no pip produced |
| `uv venv <dir>` | **succeeds**, CPython 3.10.16 |
| `uv pip install --python <venv>/bin/python --no-deps packaging` | **succeeds**, `packaging==26.3` in 63ms |

**A uv-made venv also has no `pip` binary of its own.** So the remedy is not
merely swapping the creation call — the install step must go through `uv` as
well, or the venv must be seeded. This is the trap that makes a half-fix look
plausible.

Filed as `overseer-6s3pk6.12`.

## A second hazard in the same bootstrap, which `.6` does not fix

`main()` decides whether to launch by looking for a pane **titled**
`overseer-daemon`, and `_start_daemon_pane` **always** calls `split_window_top` —
it never adopts an existing pane.

The acting daemon's pane is not titled that. `tmux` reports session
`livespec-overseer` holding `%166` at `pane_top=0` titled `vmi3006760` — the
hostname default — and `%32` at `pane_top=33`. So `pane_by_title` returns `None`,
and running the bootstrap against that window today would **split a third pane and
start a second daemon** beside the running one.

`.6` correctly tightened the early-return so a titled pane is accepted only when it
is genuinely the top of two. It did not teach the bootstrap to recognise an
*untitled* daemon pane, and the acting pane predates the titling. Both readings of
the layout are correct; they simply do not meet.

**So the cutover needs a pane step as well as a prefix step.** A candidate
sequence is recorded on `.10` and is explicitly marked as not ratified, because
`.12` may change the provisioning half of it.

## What this changes about the epic's shape

It is no longer "nine done, one cutover left". `.10` is **blocked**, not merely
sequenced, and its blocker is that the mechanism this epic built has never been
executable on the host it was built for.

That is the sharp form of `.10`'s own phrase, *in force nowhere*. The row reads as
though the only thing missing is that nobody performed the transition. The
transition **cannot currently succeed**.

## Method note

The finding came from refusing to trust the safe-looking order of operations.
Installing the prefix first was chosen only to de-risk a restart — it was not
expected to discover anything. It is worth stating as a general rule for this
thread: **when a procedure has an irreversible step and a step that can fail,
run the failing-capable step first**, even when you expect it to pass. The cost is
one command; the alternative cost here was the fleet's supervisor.
