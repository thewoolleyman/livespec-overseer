# Isolated released-backend exercise

`scripts/overseer-live-exercise.sh` is the coordinator entrypoint for the host-captured
Claude, Codex and legacy-tmux proof. It runs a released checkout inside a private
Bubblewrap PID/mount namespace. The namespace mounts fresh contents at the operator's
normal home pathname instead of changing `HOME`, and gives the exercise its own `/tmp`,
`/run/user/<uid>`, checkout, watch declaration, mapping store, terminal instance and
evidence directory. Cleanup addresses only the uniquely named exercise backend and the
validated `mktemp` root.

First inspect the exact namespace plan without starting anything:

```bash
scripts/overseer-live-exercise.sh run --plan-only \
  --backend herdr --agent claude --topic overseer-proof \
  --checkout "$PWD" --evidence /absolute/path/to/evidence -- /bin/true
```

Plan inspection does not prove runtime confinement because it starts neither the
namespace nor a terminal backend. Run the dedicated check with a new empty evidence
directory to start and stop the selected native backend inside the namespace:

```bash
scripts/overseer-live-exercise.sh run --isolation-check \
  --backend herdr --agent claude --topic overseer-proof \
  --checkout "$PWD" --evidence /absolute/path/to/isolation-evidence
```

The check succeeds only when the native backend reached a live state and its scoped
cleanup completed. Compare operator-store and terminal fingerprints around that real
run when capturing confinement proof; `--plan-only` does not prove runtime confinement.

For a real lifecycle run, remove both planning/check modes, pass the normal client's auth file with
`--credential`, and replace `/bin/true` with the foreground controller command. A
Claude run copies only `.claude/.credentials.json`; a Codex run copies only
`.codex/auth.json`. The command is responsible for opening the named backend instance,
starting the authenticated client in the scratch repository, asking that client to run
the shipped `overseer-start`, and appending lifecycle evidence to
`$OVERSEER_EXERCISE_EVIDENCE/lifecycle.jsonl`. That directory is
`/tmp/livespec-overseer-exercise-evidence`, beneath the writable scratch `/tmp`, because
the read-only host root cannot hold a new top-level mount point. Each line is a JSON
object with `stage`, `status`
(`passed` or `failed`) and an optional `detail`. The required stages are `bootstrap`,
`adoption`, `wrap-up`, `declaration`, `replacement` and `continuation`. After the
controller exits, the checked-in verifier reports a malformed record, failed stage or
missing stage as `FAILED` or `INCOMPLETE` with a non-zero status. It receives:

- `OVERSEER_EXERCISE_BACKEND` (`herdr` or `tmux`)
- `OVERSEER_EXERCISE_INSTANCE` (the unique instance name)
- `OVERSEER_EXERCISE_ENDPOINT` (the private tmux socket when applicable)
- `OVERSEER_EXERCISE_TOPIC` (the only watched plan topic)

For Herdr, every controller command must use
`herdr --session "$OVERSEER_EXERCISE_INSTANCE" ...`. For tmux, every command must use
`tmux -S "$OVERSEER_EXERCISE_ENDPOINT" ...`. Never substitute the default server.

The namespace keeps networking for real authentication but scrubs inherited tmux,
Herdr and OTLP selectors. It copies the released checkout to the private writable bind;
all other host paths remain read-only.

**The agent client gets AT MOST TWO read-only operator-home binds and no others.** The
scratch home hides whatever the client executes from under the real home, so the runner
resolves the launcher on PATH to what it actually RUNS — the real path of the program on
its `exec` line, or, when that program lies outside the home, the script file it is
passed — and binds that program's install root, the first directory below the operator
home on that path. On the release host `~/.local/bin/codex` is a bash shim running the
bun global install, so the two binds are the shim at its own path and `~/.bun`. Every
other home path a launcher merely NAMES — a config, cache or state directory, another
install — stays hidden; the bound set does not grow with the launcher. A launcher that
is a self-contained executable, or a script with no `exec` line, needs only the first
bind.

Two conditions REFUSE before any terminal backend starts, so neither can be mistaken for
a failed `bootstrap` stage. The runner refuses, naming the client name or path, when it
cannot make the client runnable at all: absent from PATH, an `exec` line whose program it
cannot resolve, or a program and script file living in two different first-level home
trees. And it refuses, naming the root, when the resolved install root is the operator
home itself or one of `~/.claude`, `~/.codex`, `~/.config` — the home directories this
exercise WRITES inside the namespace, which binding read-only would break. The scratch plan is intentionally not a real
ledger thread, so a run that cannot read a coordinator-provided plan epic must record
that limitation and must not claim end-to-end continuation.

Every mode requires an empty evidence directory. Reusing a directory is refused before
the runner writes anything, so an incomplete run cannot inherit passed lifecycle or
backend records from an earlier attempt. Repeating a required lifecycle stage is also a
failed record; a later `passed` observation can never overwrite an earlier failure.

The current factory sandbox may expose `bwrap` while denying namespace creation. In
that case `--plan-only` remains usable, but a real run must fail; do not fall back to an
unisolated exercise. Authenticated real-client evidence remains a release-host
obligation and is not discharged by fixture or mocked tests.
