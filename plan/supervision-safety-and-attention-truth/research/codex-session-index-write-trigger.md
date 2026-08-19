# When does `~/.codex/session_index.jsonl` get written?

Measured 2026-08-19 on the developer host, `codex-cli 0.147.0`. Written because
`overseer-6eo` made this question a blocking acceptance leg ("Establish and
record the index write trigger as part of the fix"), and because the answer
turned out to constrain more than that one item: the index is the ONLY surface
that maps a live Codex process to a plan topic, so anything that depends on
adoption depends on this.

The per-item disposition lives on `overseer-6eo`'s ledger comments. This note is
the durable measurement and, more importantly, the METHOD — so the next reader
can re-measure rather than trust a dated claim.

## Why it matters

The daemon joins a live Codex process to a plan topic through this chain:

    pane pid -> codex process -> open rollout fd -> session id
      --session_index.jsonl--> thread_name == THE PLAN TOPIC

If the session id is absent from the index there is no `thread_name`, so
`map_codex_sessions` resolves no topic and drops the process. A dropped process
gets no wrap-up and no restart. That is the whole harm in `overseer-6eo`.

## What the daemon does and does not do here

**The overseer NEVER writes this file.** It only reads it
(`overseer/codex_session_index.py`, `overseer/codex_sessions.py`). Codex owns
every write, so the trigger is a Codex behavior and no fleet change can make the
index more complete. Worth stating explicitly because the natural first guess is
that some fleet tool maintains it.

## The measurements

State at the time of measuring: 228 index rows; newest row `updated_at`
`2026-08-17T14:12:14Z`, matching the file's own mtime exactly; **about 42 hours
stale**, with ten rollouts newer than it, five of them created that day.

### It is NOT written at session end

The last indexed session started `16:11:26` local and its rollout kept being
written until `16:41`. Its index entry is stamped `16:12:14` — about 48 seconds
**after it started** and 29 minutes **before it ended** — and the file was never
rewritten at that end.

So a session can be indexed while LIVE, and its entry is not re-touched when it
dies. An end-of-session model predicts both the opposite stamp and a later file
mtime.

### It is NOT a periodic timer

42 hours elapsed with ten sessions and zero writes.

### It is NOT a Codex version change

`cli_version` is `0.147.0` on the last indexed session, on every unindexed
session sampled, and on the installed CLI.

### It is NOT `history_mode`

A four-sample reading suggested indexed=`paginated` / unindexed=`legacy`. The
full-corpus join refutes it — both modes appear on both sides:

| | `legacy` | `paginated` | absent |
|---|---|---|---|
| indexed | 270 | 42 | 18 |
| unindexed | 133 | 4 | 135 |

Recorded because it is a live example of a small sample producing a clean,
wrong-looking answer.

### `thread_name` is NOT an explanation

Every one of the 228 rows has a non-empty `thread_name`, and it is tempting to
conclude that a session "acquires" one and is then recorded. That reasoning is
**circular**: the index IS an id-to-`thread_name` map, so the property holds by
construction and predicts nothing. The rollout's own `session_meta` payload
carries no name field at all.

### What DOES hold: no `codex_exec` session is ever indexed

Joining every rollout under `~/.codex/sessions` against the index by
`session_id` — 330 indexed, 272 unindexed:

| originator | indexed | unindexed |
|---|---|---|
| `codex_exec` | **0** | **139** |
| `codex-tui` | 250 | 133 |
| `Claude Code` | 80 | 0 |

`codex_exec` is never indexed, in either direction, with no exceptions. Being
non-`exec` is **necessary but not sufficient**: `codex-tui` appears on both
sides, so a further gate applies to interactive sessions.

**NOT ASSERTED:** what that further gate is. That is the open question, and it is
the right next measurement.

## The consequence that changes remedies

`overseer-6eo` framed the stakes itself: "if indexing only happens at session
END, then EVERY freshly started codex track is invisible for its whole working
life, and that is a much larger defect than a lag."

The measured reality is **worse than the end-of-session case**, because that case
would at least resolve when the session died. For an `exec`-originated session
the entry never appears at any point. So:

- A fix must NOT wait for, retry against, or poll the index.
- Any acceptance criterion resting on the session eventually appearing there is
  **unsatisfiable**, and should be rewritten rather than attempted.
- A topic binding has to come from evidence the daemon already holds —
  `map_unindexed_codex_sessions` already yields the tmux session name, the cwd
  and the rollout id.

Note `overseer/_supervisor_unindexed_codex.py` already surfaces a
`codex-unindexed` diagnostic row for exactly this condition, so the REPORTING
half exists. What does not exist is supervision: that module deliberately
declines to guess a topic, so the track still gets no wrap-up and no restart.

## How to re-measure

Everything above is reproducible read-only, in a couple of minutes:

1. Compare the index's newest `updated_at` against the file mtime, and both
   against `find ~/.codex/sessions -name 'rollout-*.jsonl' -newer` the index.
2. For any session id, read the first line of its rollout — a `session_meta`
   record carrying `originator`, `cli_version`, `history_mode`, `source`,
   `thread_source`, `cwd`.
3. Join all rollouts against the index by `session_id` and tally by whichever
   field you are testing. **Tally the whole corpus.** The `history_mode` result
   above is the cautionary example: four samples gave a clean answer that the
   full join destroyed.

Re-measure before relying on any of this. A conclusion about another program's
undocumented behavior is a claim with a timestamp, and this one is dated
2026-08-19.
