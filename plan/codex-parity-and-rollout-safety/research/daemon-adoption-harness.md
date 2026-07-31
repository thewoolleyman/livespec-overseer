# The scratch-store harness that proved A4's daemon half

**Why this file exists.** A4's adopt-a-track clause was recorded as *"NOT PROVABLE
HERE"* on a dilemma that turned out to be false. The proof took a harness that a
future reader would otherwise have to re-derive — including two gotchas that make
the naive version silently prove nothing. Recorded here so the remaining exercise
(see §"The window") can be run in minutes rather than re-discovered.

**This is thread research, not package documentation.** The corresponding gap in
`overseer/AGENTS.md` §"Isolation tip" is filed as **`overseer-0pc`** and is not
fixed here — fixing it is that item's job, behind its own admission.

## The idea in one sentence

`acquire_singleton_lock` keys the daemon's lock to the **store path**, so a daemon
on a scratch store is neither "the acting daemon killed" nor "a second daemon over
the real fleet" — it is a third thing the code was explicitly built for:

> *"Keyed to the store path so a scratch-store live-exercise run never contends with
> the real daemon."* — `_supervisor_lifecycle.acquire_singleton_lock`

All three state roots are `Path.home()`-anchored — store, stamps and watch-set
(`_registry_core.py:91`, `:92`, `:101`) — so **one `HOME` override redirects all of
them at once**.

## Gotcha 1 — a PURE scratch `$HOME` proves nothing, and looks like it worked

Session discovery is `$HOME`-anchored too:

```
claude_sessions.default_sessions_dir()  -> ~/.claude/sessions   (claude_sessions.py:70)
codex_sessions.default_codex_home()     -> ~/.codex             (codex_sessions.py:110)
```

Under a pure scratch `HOME` the daemon sees **zero** sessions, adopts nothing, and
renders every plan `unassigned` — which is **indistinguishable from correct
isolation**, and is exactly what `AGENTS.md`'s worked example celebrates. Symlink
the real registries in. That is safe: adoption is bounded by the **watch-set**, not
by the registry (`adopt_sessions:131-134` builds its topic map from
`discover_plans(watch_repos=resolve_watch(...))`).

## Gotcha 2 — `mise exec` / `uv run` break under an overridden `HOME`

`mise` reads its config from `$HOME` and fails with *"Config files in
/home/ubuntu/mise.toml are not trusted"* before your code runs. Invoke the venv
interpreter directly: `.venv/bin/python3`.

## The harness

```bash
P=<scratch>/ovprobe
mkdir -p "$P/home" "$P/repo/plan/adoption-probe" "$P/repo/tmp/overseer"
ln -s ~/.claude "$P/home/.claude"      # real registries — see Gotcha 1
ln -s ~/.codex  "$P/home/.codex"
ln -s ~/.cache  "$P/home/.cache"       # uv warmth; an empty HOME cold-rebuilds and HANGS
printf '{"repos": ["%s/repo"]}\n' "$P" > "$P/home/.livespec-overseer-repos.json"
printf 'tmp/\n' > "$P/repo/.gitignore" # the daemon REFUSES to start if tmp/overseer/ is not ignored
echo '# probe' > "$P/repo/plan/adoption-probe/handoff.md"
git -C "$P/repo" init -q && git -C "$P/repo" add -A && git -C "$P/repo" commit -qm init
```

Then a live agent session **named for the topic, with its cwd in the scratch repo**:

```bash
tmux new-session -d -s adoption-probe -c "$P/repo"
tmux send-keys -t adoption-probe -l 'claude --dangerously-skip-permissions -n adoption-probe'
tmux send-keys -t adoption-probe Enter
# it stops on the trust-folder picker; read the pane, confirm `❯ 1.`, then send Enter
```

## Prove the blast radius is EMPTY before arming anything

Resolve every path under the scratch `HOME`, then run the would-adopt computation
against **both** watch-sets — the real one is the positive control, and without it an
empty scratch result is worthless:

```
LOCK  -> <scratch>/home/.livespec-overseer.jsonl.daemon.lock     (NOT the real one)
STORE -> <scratch>/home/.livespec-overseer.jsonl

live named agent sessions on this host : 26
WOULD-ADOPT, scratch watch-set         : 0     <- before the probe exists
WOULD-ADOPT, REAL watch-set            : 6     <- same code, the six real tracks
```

With the probe live it becomes **1 (the probe alone)** while the real control stays
at **6**. Two provably disjoint sets. **Do not arm the daemon until you have seen
both numbers.**

## The act=True tick

`adopt_sessions` is unreachable from the read-only `list` path — `build_rows` does
`if not act: return registry.join(...)` **above** it — so only a real `act=True` run
proves adoption. Mirror `run_daemon()` exactly, but with `once=True` so the loop
cannot run unattended:

```python
sup = build_supervisor()
sup.warn_percent = registry.DEFAULT_CTX_THRESHOLD
sup.run(interval=1, once=True, recover=False)
```

Observed:

```
overseer: adopted session adoption-probe → <scratch>/repo::adoption-probe
overseer — 1 track(s) - 0.15.0
idle    adoption-probe  adoption-probe (claude)  —  repo
```

Real store md5 **byte-identical** before and after; the real daemon's lock file
untouched. Check both — they are the whole safety claim.

## What this does NOT prove

- The adopted track was a **Claude** session. The **Codex** arm's *join* is proven
  live and separately (4 named sessions resolved via
  `pid → /proc/fd → rollout → index → thread_name`, against 23 on the Claude arm),
  but no Codex session was adopted here.
- One tick, not a sustained loop.
- Not the full bar re-run as **one** continuous exercise from a Codex session.

**A Codex probe is harder than it looks:** a codex TUI holds **no rollout fd until
it takes a turn**, so a freshly-started one is not adoptable — and taking that turn
spends codex quota, which was near a limit when this was written. See
**`overseer-mir`** (P3) for the measurement.

## The window

The full bar **cannot** be satisfied while any daemon runs — the lock is an
exclusive `flock` on a per-store file, so every real-`$HOME` invocation refuses.
That is invariant B6, not a host limitation.

But it **is** satisfiable whenever no daemon holds the lock, and those windows occur
routinely: `AGENTS.md` requires a daemon restart after landing any overseer code
change, and a reboot does the same. **Take the next such window** — the launch half
already passes from a real Codex session, so all it adds is watching the daemon come
up and *adopt* instead of *refuse*.
