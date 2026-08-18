# Why the restart's resume submission needs end-to-end integrity

Reasoning note for the `resume-submit-integrity` plan thread (repo:
`livespec-overseer`). The defect record is **`overseer-mgg`** (read its
live state — including the three instance comments — from the ledger;
cite it, do not re-file). This note fixes the thread's scope and the
design constraints; the mechanism analysis lives on the record.

## The defect in one paragraph

`submit_prompt` (`overseer/_supervisor_launch.py`) bracketed-pastes the
resume line into a freshly respawned session, sends Enter, and confirms
submission by observing an EMPTY bordered input box
(`signals.input_box_ready`). During the fresh TUI's startup window the
pasted bytes can be queued but not yet rendered, so the capture sees the
never-typed empty box and confirms a submission that never happened —
while the startup TUI drops the Enter but keeps the paste. The daemon
then logs the clean `restarted`, clears the `ready` marker and stamps,
and never arms the `resume_pending` retry (it gates on `submit_prompt`
returning False). Result: a live, healthy, named session holding its
resume in the composer, doing nothing, invisible to every surface.

## Evidence (all on the `overseer-mgg` record)

1. `rop-railway-enforcement-supervisor` (repo `livespec-dev-tooling`),
   2026-08-03: ~3h stranded after a clean-logged 04:19:52Z restart;
   maintainer submitted by hand.
2. `12-hetzner-ci-critical-path-overseer` (repo `homelab`), 2026-08-04:
   live reproduction in the one-shot `start --force` path — the CLI
   printed success while the paste sat visible; one Enter healed it.
   Confirms the paste renders and survives startup; only the Enter is
   dropped, and the confirm can fire before the render.
3. `spec-side-autonomy-supervisor` (repo `livespec`), found 2026-08-05:
   **~32 hours** stranded after a clean-logged 2026-08-03T19:12:18Z
   restart — a session that never ran a single turn (no `Ctx:` in its
   statusline), with ZERO log lines, alerts, or `NEEDS YOU` membership
   for the whole window. The worst reporting shape the daemon has: a
   success log and a dead lane.

Every restart and every `start` exercises this code path, and the
`ready-certification-deadlock` fix (epic `overseer-er6ikw`) will only
increase restart frequency once it lands.

## The three work fronts (scope of this thread)

1. **Two-phase submit confirm.** Only accept "box is empty" as proof of
   submission after the paste has been SEEN rendered in the box at
   least once (paste-visible → box-cleared), or accept immediately when
   the session transitions to busy/processing. A box never seen holding
   the text cannot prove the text left it. The Codex leg
   (`expect_codex` busy-confirm) must be examined for the analogous
   startup-queueing race and covered or explicitly ruled out.
2. **Any-tick stranded-resume self-heal.** Independent of the confirm:
   on any tick, a pane whose composer holds EXACTLY the track's
   expected resume text, unsubmitted, gets Enter re-sent — never a
   respawn (a fresh session-written `ready` remains the sole respawn
   trigger). Instance #2 proved one Enter heals; instance #3 proved the
   window can be 32 hours, so the self-heal is the layer that bounds
   the damage whatever the confirm misses.
3. **Restarted-but-never-worked attention condition.** A session with
   no context consumption whose composer holds the expected resume text
   is detectable on any tick; it should surface in `NEEDS YOU` (and the
   window badge) if it persists past a short floor — report-only,
   edge-triggered, following the attention-condition conventions the
   ratified spec already carries. This is the backstop that makes the
   NEXT unknown stranding mode visible, not just this known one.

## Constraints (unchanged invariants)

- THE CARDINAL RULE: no respawn without a fresh session-written
  `ready`; the self-heal re-sends Enter ONLY.
- The atomic bracketed paste, the bounded Enter loop, and the
  paste-failure hard-False stay.
- The Codex confirm's existing guard (payloads must not contain
  busy-marker substrings) stays.
- Attention stays edge-triggered and clears when the condition clears.

## Spec-bearing or implementation-only? (decide first)

Front 1 and front 2 look implementation-shaped, BUT the ratified spec
speaks about the restart's submission and the round's closure —
`SPECIFICATION/spec.md` §"The restart" and §"The supervision round"
(round closes on restart / on actual resume submission), and the
scenario "A dropped resume submission is retried without a second
kill" in `SPECIFICATION/scenarios.md` — so the executor must sweep
those (plus `SPECIFICATION/contracts.md` and the shipped prose
`.claude-plugin/prose/overseer.md`, `overseer/marker-protocol.md`)
before concluding the confirm/self-heal need no contract change. Front
3 (a NEW attention condition) is presumptively contract-bearing: the
`NEEDS YOU` membership set is ratified surface (the v003/v004
precedents), so it routes through `/livespec:propose-change` →
independent Fable review → `/livespec:revise` regardless.

## Relations

- **`overseer-mgg`** — the defect record; this thread's epic anchors
  the fix work; mgg becomes ledger work routed under the epic when the
  slices are cut.
- **`plan/ready-certification-deadlock/`** (epic `overseer-er6ikw`) —
  the sibling restart-leg thread: it fixes what may AUTHORIZE a
  restart; this thread fixes whether the authorized restart actually
  DELIVERS its kick. Independent; neither blocks the other; both raise
  each other's importance.
- **`overseer-daj`** — supervisor charters restarting Codex workers
  unadoptably: a third restart-leg defect (adoptability), out of scope
  here.
- Code anchors: `overseer/_supervisor_launch.py` (`submit_prompt`),
  `signals.input_box_ready` / `signals._input_box_present`
  (`overseer/signals.py`), `overseer/_supervisor_restart.py` (the
  restart caller + `resume_pending`), `overseer/_supervisor_recovery.py`
  (`do_launch` — the `start`/recover path instance #2 exercised).
