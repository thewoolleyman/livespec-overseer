# Spec-bearing sweep verdict

Sweep completed 2026-08-12 for the `resume-submit-integrity` thread. The
authoritative sources read were:

- `SPECIFICATION/spec.md`, "The supervision round" and "The restart";
- `SPECIFICATION/scenarios.md`, "A dropped resume submission is retried
  without a second kill";
- `SPECIFICATION/contracts.md`, "The restart interlock" and "Attention
  surface";
- `.claude-plugin/prose/overseer.md`; and
- `overseer/marker-protocol.md`.

## Existing ratified behavior

The current letter already requires the relevant safety outcomes:

- a delivered round is closed by the restart, while a failed opening paste is
  un-opened;
- a successful respawn whose resume prompt does not submit keeps the round
  open for submission retry only;
- the retry re-sends submission only, never a second kill, and the track stays
  visible as needing attention until submission succeeds; and
- a fresh structured gate is surfaced and never keystroked.

The contracts also already list "a restart whose resume has not yet
submitted" as mechanical attention membership, with report-only,
edge-triggered rendering and a window badge that clears at zero.

## Per-front verdict

| Front | Verdict | Reason |
|---|---|---|
| 1. Two-phase submit confirmation | **Implementation-only** | Requiring the pasted text to be observed before an empty-box confirmation, or accepting a genuine busy transition, makes the existing submission guarantee truthful. It adds no new user-visible behavior and does not alter the cardinal rule. The Codex restart has no analogous paste/Enter window because `codex resume` receives and auto-submits its kick; its existing `expect_codex` busy-marker guard remains required and needs coverage or an explicit test ruling, not a contract change. |
| 2. Any-tick stranded-resume self-heal | **Implementation-only** | The ratified scenario already requires retry on later cycles, submission-only, no second kill, and attention until success. Detecting the exact expected composer text on any tick and arming the existing round-scoped retry is the missing implementation route to that behavior. The exact-text check must remain fail-closed for human drafts and must never respawn. |
| 3. Restarted-but-never-worked attention | **Ratified-letter required** | This is a new way to enter the daemon-owned `NEEDS YOU` set: a restarted session with no context consumption and the exact expected resume text, after a bounded floor, report-only and edge-triggered, with the badge. The existing "resume has not yet submitted" member does not cover the false-positive path because that path never arms `resume_pending`; the membership and clearing rules must be proposed explicitly. |

## Scope boundary

The proposal must preserve the single fresh-session-written `ready` as the
only respawn authorization. It should cover front 3 and its attention/badge
semantics. Fronts 1–2 should remain implementation children after the
ratification decision; no implementation children are filed by this sweep.

The next plan action is therefore the spec-side `/livespec:propose-change`
operation for front 3, followed by the independent review and maintainer
revision required by the handoff.
