# foreman — terminal handoff

## Status: COMPLETE AND ARCHIVED

This thread has no pending implementation, verification, ledger, or archive
work. Do not reopen or redispatch it from this handoff.

**You were handed this path by a respawn prompt, and that prompt is stale by
design.** The daemon builds it as `<repo>/plan/<topic>/handoff.md`
(`overseer/_supervisor_prompts.py:142` — `return str(Path(repo) / "plan" / topic
/ "handoff.md")`), a FIXED live path computed from the topic, which knows nothing
about `plan/archive/`. This file exists so that prompt resolves to something true
instead of a missing file. That failure is filed as `overseer-y26`, still OPEN:
the mapping store `~/.livespec-overseer.jsonl` holds this thread's row with
`handoff: …/plan/foreman/handoff.md` and a matching `resume` line, and **nothing
updates it on archive**. A tombstone is the mitigation, not the fix.

The authoritative completed records are `plan/archive/foreman/handoff.md` and
`plan/archive/foreman/supervisor-handoff.md`. The research inputs the thread was
built on — `research/seed-prompt.md`, `research/brainstorm.md`,
`research/review-findings.md` — moved with them.

## What it shipped

**v1 = phases A+B**, the maintainer's decision of 2026-08-02, recorded on the
epic itself. Phase A is the OBSERVE half, Phase B the mechanical-ACT half.

The epic `overseer-z5fo4y` is CLOSED with all **eleven** children closed: Phase A
`overseer-z5fo4y.1`–`.5` (snapshot export, `list --json`, foreman-gather,
heartbeat surfacing, the `-foreman` reserved suffix) and Phase B
`overseer-by6hrx` (deterministic singleton wrapper + scheduler),
`overseer-eqbk4h` (fail-closed session classifier), `overseer-4opppx`
(session-lifecycle `foreman-act`), `overseer-wykyth` (typed filing + journal
triage), `overseer-vts4lo` (bounded one-shot work-item sessions) and
`overseer-qp3vpb` (the foreman skill and end-to-end v1 binding).

**Phases C–E — consensus panels, gate-driving, federation — were never in v1 and
remain separate future scope.** Nothing here covers them.

## The deployment was verified by BEHAVIOUR, and that distinction is the point

The thread's final acceptance step was "verify the released plugin is deployed
fleet-wide". **A version check passes over the real gap**, and this thread proved
it rather than asserting it.

The acting daemon had been up 16h50m and was SEVEN releases behind — its own
rendered header said `0.20.2` while master was `0.27.0`. It loads `overseer` from
the repo checkout through an EDITABLE install, **not** from the plugin cache, so
updating the cache to 0.27.0 could never have reached it. Only a restart could,
and restarting the acting daemon is the one rule whose blast radius is the whole
fleet, so it was done on explicit maintainer authorization: the checkout was
fast-forwarded to the released commit FIRST (it was one behind — restarting
before that would have loaded a commit still lagging the release), the entry
point was smoke-tested so a failed relaunch could not strand the fleet, and the
pane was respawned in place. **53 tracked rows before, 53 after.**

Then three controls, because the obvious test says the wrong thing: after the
restart the snapshot still contained no `heartbeat` string, and that is CORRECT —
the surfacing fires only on a heartbeat file that is PRESENT and stale, and no
foreman runtime is running. A stale (2h) heartbeat produced the
`foreman-heartbeat-stale` row (53 → 54 rows); a fresh one did not (53), proving
the staleness RULE rather than mere file presence; removing the file restored
baseline.

**Only DAEMON-side code can be shipped-but-not-running.** CLI surfaces get a
fresh process per invocation and are live on merge; `.1` was live because it
landed before that daemon started. Any future daemon-side slice inherits this
problem, and a release version will not reveal it.

## If a fresh session receives this file

Its only action is to confirm on a freshly fetched `origin/master` that
`plan/archive/foreman/` exists. There is no work to resume. Re-measure rather
than trusting any claim above — every one is a claim with a timestamp, including
this sentence.
