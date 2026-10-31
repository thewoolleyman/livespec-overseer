# Live verification: read the running daemon, and prove a fix on it

Read this on every resume of a plan that changes `overseer/`, and after every
release that ships an `overseer/` change. It exists because a merged, released
and test-green change is not evidence that the fleet works.

## What went wrong (measured 2026-10-13/14, plan `herdr-overseer`)

A plan session resumed from its ledger handoff, filed and dispatched a fix, and
drove a PR to merge across a day of releases. It never once read the live
`overseerd` output. Meanwhile the running daemon reported four `session-gone`
tracks and two `ready-uncertifiable` tracks in its own attention block. The
maintainer had to point at the daemon twice before the session looked.

When it did look, five minutes of reading found three things the ledger did
not say:

- The handoff had attributed `factory-test-first-enforcement` to the
  renumbered-pane fix. It was a different bug: a Codex track with a dead tmux
  locator and no held-open rollout file (`overseer-iffpgw`).
- Two more tracks the handoff did list were live sessions misreported as gone,
  which only checking each recorded pid and start time against `/proc` proved.
- An untracked daemon defect: a certified herdr `ready` lost its round before
  binding and expired unhonored (`overseer-6wcyg2`).

The cause was a definition of done that never touched the running system. The
plan's next action said "the item reaches `closed`", which is a ledger state.
Nothing in the loop required looking at the daemon after shipping.

## The rule

1. **On resume, read the live daemon before acting on any handoff.** A
   handoff's diagnosis, and especially its list of affected tracks, is a claim
   to re-measure. It is not a fact (see `.ai/record-versus-world.md`).
2. **Reconcile every attention row.** Each row the daemon reports needing
   attention maps to an open work item, or to a stated session-side cause, or
   it gets filed now. An unexplained row is the finding.
3. **After a release that ships an `overseer/` change, prove it on the fleet
   daemon.** Confirm the running version, observe the specific behavior the
   change promised on a real track, and re-read the attention block for
   anything new. A daemon that has not re-executed into the release has not
   shipped it.
4. **Close only on observed behavior.** An item whose deliverable is daemon
   behavior closes after that observation, and the close reason quotes it: the
   log line, the row status, the version. A merged PR or a green CI run is not
   the observation.
5. **Prove on a sacrificial seat, and know what that rule does NOT cover.** A
   live proof that renames, misnames, restarts, sends keys to, closes or
   re-briefs a supervised session runs against a sacrificial seat, never an
   active operator session (`SPECIFICATION/non-functional-requirements.md`
   §"Scenarios"). That rule is about PROOFS. It does not forbid a coordinator
   from typing into a session's pane: a coordinator MUST unblock a session stuck
   at a decision picker it cannot otherwise answer, by typing what the picker
   needs, and then MUST send the same answer in words by cross-session message.
   Outside unblocking, a session does not type into another session's input
   field, because that collides with the operator's own typing. The over-broad
   reading of this rule froze a seat for hours on 2026-10-31 (`overseer-wcsd`).

## How to read the live daemon

Use these read-only reads. None of them mutates the store or touches a pane.

- **Status snapshot**, rewritten every tick: `~/.livespec-overseer-status.json`.
  `daemon_package.version` is the running release. `rows[]` carries each
  track's `status`, `tmux` coordinate and a truncated `note`. Check
  `written_at` to confirm the daemon is ticking.
- **History**: `tmp/overseer/daemon.log` in this repository, one JSON record per
  line. A rotated history continues in `daemon.log.1` and older (see
  `overseer/AGENTS.md`). Filter by `topic` and `event`. Collapse identical
  lines before counting, because the daemon re-renders every tick (the same
  file covers the full-line collapsing rule).
- **Mapping store**: `~/.livespec-overseer.jsonl`. A track's recorded `tmux`
  coordinate and `observed_session_identity` (`claude:<pid>:<starttime>:<name>`
  or `codex:<uuid>`).
- **Process truth**: for a `claude:` identity, compare `/proc/<pid>/stat`
  field 22 with the recorded start time. A match means the session is alive,
  whatever the row says.

`supervisor.py list --json` runs the read-only classification on the code at
the checkout's HEAD, not on the running daemon's release. Use it to preview a
fix. Never use it as evidence about what the fleet is running.
