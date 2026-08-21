# Ratification — the daemon runs from an isolated daemon-owned runtime prefix

ledger anchor `overseer-6s3pk6`, deciding child `overseer-6s3pk6.2`

The opening research left exactly one question open and named the plan as its
owner: whether `overseerd` runs from a **daemon-owned runtime prefix** or from
the **primary checkout pinned to `origin/release`**. This note ratifies the
first and records why, so an implementer does not re-litigate it.

## Decision

**The isolated daemon-owned runtime prefix.** The primary checkout is never
again the source of the running daemon's code.

## The premises, re-measured 2026-08-22 rather than inherited

Every fact this decision rests on was checked against the live host today, not
carried forward from the opening note:

| premise | measurement |
|---|---|
| the daemon imports the working tree | `~/.livespec-overseer-status.json` publishes `daemon_package.package_dir = /data/projects/livespec-overseer/overseer` |
| the install is editable | `.venv/lib/python3*/site-packages/__editable__.livespec_overseer-1.21.0.pth` |
| `refs/heads/release` is a real, CI-maintained anchor | `git ls-remote origin refs/heads/release` = `2f47f01` = `refs/tags/v1.21.0` |
| the daemon is not stale right now | it reports `1.21.0`, which IS the release ref; started 00:14:12Z |

That last row matters to how this note should be read. The plan was opened on a
stale daemon, and today's daemon is current — so the defect being fixed is not
"the daemon is stale", it is "**nothing structurally prevents it from being
stale, or from being edited out from under itself**". A currently-correct
daemon is not evidence against the requirement.

## Why pinning the checkout was rejected

**It does not satisfy the requirement as stated.** The maintainer's requirement
is that local primary changes cannot break the daemon. Pinning `HEAD` to
`origin/release` constrains only the COMMIT; the daemon still imports a mutable
directory. An uncommitted edit, a `git stash pop`, a half-applied rebase, or a
pack hydration all reach the live fleet supervisor with no commit involved at
all. The measured incident that opened this plan was about commits, but the
root cause recorded in the opening research is the editable import — and
pinning does not touch it.

**It puts the daemon in direct conflict with the human using that tree.** The
primary checkout is the maintainer's working surface. A daemon that requires it
to sit at `origin/release` makes every ordinary `git checkout`, `git pull`, or
branch switch an act that de-currents or breaks the supervisor. The two uses of
that directory are incompatible, and the pin resolves the conflict against the
human.

**It makes rollback destructive.** Child `.5` requires reverting a release that
fails before its first successful tick. With a versioned prefix that is a
re-exec into the retained previous prefix — an operation entirely inside the
daemon's own storage. With a pinned checkout it means moving a shared working
tree's `HEAD` underneath whatever the maintainer is doing, which is exactly the
class of act this repo gates per-instance.

**It leaves provenance unverifiable.** `AGENTS.md` prescribes reading
`daemon_package.version` to learn what the daemon is running. That field is
*more* honest than it first looks, and the exact mechanism matters, so it is
recorded here rather than assumed: `daemon_package_payload` in
`overseer/_supervisor_snapshot.py` reports `APP_VERSION`, and
`overseer/version.py` reads that literal out of `overseer/version.json` **in the
imported tree** at start — deliberately, as data rather than distribution
metadata, so the module works from both the installed console script and the
in-tree executables. So the field is not stale install metadata. It genuinely
names the release the imported tree was sitting at.

**That is precisely why pinning does not rescue it.** The field is faithful about
`version.json` and blind to every other module. A tree carrying a hand-edited
`_supervisor_restart.py` reports a clean release version, because the edit did
not touch the one file the version is read from. Pinning `HEAD` to
`origin/release` pins that file and buys nothing for the rest. A version-named
prefix makes the answer structural instead: the path the process runs from names
the release, and no edit inside it can be both present and unnamed.

## The objection that turned out to be empty

The strongest argument for the pin is that an isolated prefix introduces
**version skew between the daemon and the separate command entrypoints**
(`overseer-declare`, `foreman-*`), which are fresh subprocesses per call and
would resolve from somewhere else.

Measured, that skew already exists and is wider than anything the prefix adds:

```
$ which overseerd
/home/ubuntu/.local/bin/overseerd          # shebang: /data/projects/livespec-overseer/.venv/bin/python3
$ which overseer-declare
/home/ubuntu/.claude/plugins/cache/livespec-overseer/livespec-overseer/1304b1cb0065/bin/overseer-declare
```

The daemon runs from the working tree via the project venv; `overseer-declare`
runs from a **plugin cache build**. They are already two different sources with
independent update cadences. So the prefix does not create daemon/command skew;
it replaces one unknowable source with a version-stamped one, and leaves the
pre-existing skew exactly as it was. Narrowing that skew is a separate concern
and is NOT adopted into this plan's scope — see the deferral below.

## What this obliges the implementation to do

Consequences that follow from the decision and belong to the named children:

- The prefix is built from the **adopted commit**, never from the working tree.
  An install step that reaches into `/data/projects/livespec-overseer` for
  sources reintroduces the whole defect while appearing to satisfy the design.
- Retain at least the previous prefix on disk, since child `.5`'s rollback is
  a re-exec into it.
- `os.execv` into the new prefix's interpreter keeps the pane, the terminal and
  the file descriptors by construction, which is the argument child `.6` asks
  to have recorded: prefer exec over stop-then-start precisely because a
  stop-then-start is what closes the pane.
- The proposed location stands as written on child `.2`:
  `~/.local/share/livespec-overseer/runtime/<version>/`.

## Deferral recorded by this decision

**Unifying the daemon's runtime with the command entrypoints' plugin-cache
build is deferred.** It is a real gap — the two halves can disagree, and
`AGENTS.md` already records an incident where a command told a session the
truth while the daemon stranded it anyway — but it is a different requirement
from the one this plan carries, it touches the plugin distribution surface
rather than the daemon, and folding it in would widen a six-child plan into the
packaging lane. It will be reconsidered as its own thread once the daemon owns
a versioned runtime, which is what makes the comparison expressible at all.
