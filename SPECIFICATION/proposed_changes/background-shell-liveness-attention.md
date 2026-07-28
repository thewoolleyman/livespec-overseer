---
topic: background-shell-liveness-attention
author: claude-opus-5[1m]
created_at: 2026-07-28T03:11:07Z
widened_at: 2026-07-28T15:40:00Z
---

## Proposal: Bound the suppression of attention, supervise the supervisor pair, and ratify the control-plane liveness contract

### Target specification files

- spec.md
- contracts.md

### Summary

The narrow form of this proposal bounded busy-suppression of ATTENTION for one signal — a prolonged background command on a low-context track. Two measured incidents and an eight-review adversarial gate showed that signal is an instance of a class: the daemon's decision cascade has absorbing regions in which no supervision round can open while a track's context runs down; exactly one signal in the daemon carries a duration and none carries progress; and the control plane's own supervisor sessions sit entirely outside supervision. This widened proposal ratifies the general contract in ONE cycle. It (1) bounds the suppression of attention generally — a track that has been observably unable to open a round past a bounded floor MUST be surfaced, with the background-command case as its named instance; (2) gives standing human-waits a duration and a bounded escalation; (3) makes the supervisor PAIR member a fully supervised entity under the identical marker protocol and restart interlock (maintainer ruling, 2026-07-28); and (4) adds the guarded both-stalled supervisor nudge, including the one explicitly bounded exception to busy-classification suppressing acts.

Action against WORKER sessions remains exactly as suppressed as it is today: every new worker-side obligation in this proposal is report-only. The cardinal rule is unchanged and is restated per supervised entity — only an entity's own fresh `ready` restarts that entity.

### Motivation

**Incident 1 — the immortal shell.** The supervised tmux session `04-convergence-loop` in `/data/projects/homelab` sat at an empty Claude input prompt with 29% remaining context while a `Bash(run_in_background)` poller had been alive for roughly 39 hours. The poller invoked `gh pr checks 61 --json …`; the installed `gh` does not support `--json`, its stderr was discarded, and the `until` loop could therefore never observe `0`. Its pull request had already merged and its worktree cwd had been deleted. Claude correctly published registry status `shell`, so the daemon took the top-precedence busy branch: it wrote no injection stamp, opened no round, sent no wrap-up, and rendered the row green as `working (background shell)`, outside the attention surface, through every remaining escalation band.

**Incident 2 — the blocked/generating oscillation.** The track `console-happy-path-mvp` cycled between two states for roughly 54 hours. While a `blocked:` declaration stood and its pane was idle, the blocked branch preempted the threshold branch, so no round opened. While the session generated, the busy branch preempted it, so no round opened — and the now-stale declaration was voided, 32 times, at declaration ages from 121 s to about 22.4 hours, after which the session re-declared and the cycle repeated. Across those 32 observed cycles the track was never in a third state; it burned to 22% with no wrap-up ever sent. The trap is therefore branch PRECEDENCE, not the permanence of any one declaration, and a remedy aimed only at voiding behavior would miss it entirely.

**The control plane is unsupervised.** A read-only render shows 33 tracks and zero supervisors, while the host holds nine to eleven `<topic>-supervisor` tmux sessions and roughly ten live supervisor sessions between 57% and 80% remaining context. The only supervisor-facing surface reduces a supervisor to two booleans — a handoff artifact exists, a session is running — and is reachable only from one leaf of the worker's cascade. No context monitoring, no duration, no wind-down, no restart, and no attention exists for any supervisor in the fleet; a supervisor that exhausts its context dies mid-thought, silently, taking its live brief with it. Measured against the daemon's own unmodified detectors, five of nine live supervisor panes were sitting on structured human gates at one instant, and none of them appeared in the attention surface.

**A mutual wait is invisible from inside either session.** A worker waiting on its supervisor and a supervisor waiting on its worker each look healthy from their own vantage.

The restart interlock behaved exactly as specified throughout and is NOT weakened here. Restarting without a fresh session-written `ready` would violate the cardinal rule, and the missing restart is not the defect. The defect is indefinite SILENT shielding, and the absence of any supervision of the supervising layer.

The full analysis — every candidate, its rejected alternatives and their failure modes, the clearing/re-arm/daemon-restart table for every time-based mechanism, and the primary-goal test applied to each operator line in both directions — is in `plan/background-shell-supervision-liveness/research/control-plane-liveness.md`. Its adversarial review ran two waves and eight reviews across two model families, all verified and folded, with the per-finding verdicts (including findings refuted by verification) logged beside it.

The wording below is deliberately implementation-neutral. spec.md's scope statement places the pane's track table, its columns, and its COMMAND vocabulary outside the governed contract, so no status token, constant, or identifier is named in governed prose; the ratified values — the floors, the band set, the staleness window, the continuity-gap derivation, the escalation count, and every status token — belong to the implementing slices and are recorded with their rulings in the research note.

No `## ` heading is added, removed, or renamed in either file, so this proposal owes no `tests/heading-coverage.json` co-edit. Every new Gherkin scenario, its integration test, and its coverage row are the implementing slices' atomic obligation. (A precision worth stating rather than assuming: the heading-coverage check enforces that a heading CARRIES a registry row, and its scenario-tier direction accepts a node id on a string prefix without resolving it — so "no new heading ahead of its test" is a discipline this proposal honors deliberately, not something the gate would catch.)

### Proposed changes

**Nine edits: six to spec.md, three to contracts.md.**

**EDIT 1 — spec.md §"Fail-soft posture", the busy-detection bullet.** Replace:

"- Busy detection deliberately over-fires: a false \"busy\" merely suppresses\n  action, while a missed \"busy\" could inject into a working session — so\n  ambiguity always resolves toward doing nothing."

with:

"- Busy detection deliberately over-fires: a false \"busy\" merely suppresses\n  action, while a missed \"busy\" could inject into a working session — so\n  ambiguity always resolves toward doing nothing. That suppression is\n  unbounded for ACTION and bounded for ATTENTION (see below)."

**EDIT 2 — spec.md §"Fail-soft posture", a new paragraph appended after that bullet list, at the end of the section.** Add:

"Suppressing action without limit is correct; suppressing ATTENTION without limit is not. A track can sit in a state in which no supervision round can open — a busy classification that never ends, a standing `blocked:` declaration, an alternation between the two — while its remaining context runs down, and while it does, the track is never warned and never reported. A low-context track shielded silently is therefore its own failure, distinct from the restart the cardinal rule correctly withholds. When a track's remaining context is KNOWN and has been continuously at or below its wind-down threshold past a bounded floor, no round has opened in that time, and the session is not observed actively generating, the daemon MUST surface the track to the operator, naming EVERY piece of evidence currently preventing the round — a background command and its age, a standing declaration and its age, a visible gate — never a single presumed cause. Where the preventing evidence is a background command observed continuously past its own bounded floor, the report names that instance specifically. Separately, a track whose busy classification rests SOLELY on a background command and that has shown no observable progress past a LONGER bounded floor MUST be surfaced regardless of its remaining context. Surfacing is the ENTIRE response in every case above: on this evidence the daemon MUST NOT inject a wrap-up, send a keystroke, terminate the command, write a declaration, or restart the session, and a fresh session-written `ready` remains the SOLE restart authorization. Each floor MUST be long enough that ordinary long-running background work completes inside it, so a genuine build is not ordinarily reported; a genuine command that outlives its floor produces exactly one report-only line whose text is literally true, and that residual is accepted rather than designed away. Every condition here MUST be re-derived from live state each cycle, MUST clear on its own when its evidence clears, MUST re-arm for a later episode, and MUST key its continuity on continuously OBSERVED evidence — an observation gap restarts the floor rather than shortening it. An unknown remaining-context reading is NEVER a crossing and NEVER starts any of these floors; the requirement that the reading be KNOWN is explicit in every restatement, so a track whose context has never been read cannot fire them. A duration the daemon asserts is carried either by a declaration file's own modification time or by an in-memory clock over continuously observed evidence; a daemon restart resets every in-memory clock, which DELAYS every report and fabricates none. Remaining-context knowledge itself ages: a last-known value unseen past a bounded staleness window no longer satisfies any context gate, and a track whose last-known value was at or below its threshold when knowledge went stale MUST be surfaced with full coordinates — losing sight of a low track is itself attention."

**EDIT 3 — spec.md §"Notify, never block", the edge-trigger sentence.** Replace:

"Alerts are edge-triggered — one line when a track enters a condition, not one\nper cycle —"

with:

"Alerts are edge-triggered — one line when a track enters a condition, not one\nper cycle, plus at most one further line per crossed age band for a standing\nhuman-wait, a declared block that persists re-reporting on a small set of\nrising age boundaries, with a re-declaration starting those bands afresh —"

and append to the same paragraph:

"An alert's dedup identity is its CONDITION, and any live value embedded in an alert line is quantized to the value at entry or to the boundary just crossed, so a standing condition never re-emits merely because a number drifted. Each condition re-arms when THAT condition clears, independently of any other condition the same track carries."

**EDIT 4 — spec.md §"Session-name derivation", appended paragraph.** Add:

"The `-supervisor` suffix is RESERVED for pair members (per §\"Supervised runtimes\"). No worker entity may be derived, registered, or accepted under a session name ending in `-supervisor` — compared case-insensitively — by discovery, by the cross-repository collision qualifier, or by any operator command; a plan directory or request that would produce one is refused and surfaced by name. A pair member's session name is derived from its worker's PLAN TOPIC, using the same derivation and the same collision qualification with the suffix appended, never from whatever tmux session currently happens to host the worker."

**EDIT 5 — spec.md §"Supervised runtimes", appended paragraphs.** Add:

"A tracked session MAY have an attended SUPERVISOR session beside it (the artifact permission is in §\"Non-interference with tracked work\"). That pair member is itself a SUPERVISED ENTITY under this whole specification: the same marker protocol, the same wind-down threshold and escalation bands, the same restart interlock, and the cardinal rule verbatim per entity — only the supervisor's OWN fresh `ready`, declared in its OWN state file, may restart the supervisor, and no worker declaration may ever restart its supervisor or the reverse.\n\nIts distinct identities are exactly these, and every topic-parameterized surface MUST draw from them: its state file and its round records key on the suffixed entity name; its wrap-up and keep-going messages are entity VARIANTS whose paths, session name, and commit ritual refer to the supervisor's own artifacts — `plan/<topic>/supervisor-handoff.md`, committed through the repository's own discipline — and never to the worker's handoff; and its restart preserves the suffixed session name and hands the fresh session exactly one prompt: read the supervisor handoff and follow it. The respawn is additionally gated on that artifact EXISTING, re-checked immediately before the act, so a `ready` with no artifact preserves the declaration and surfaces the existing capture offer instead of resuming onto a dead pointer; the daemon takes no content or modification-time dependence on the artifact, so brief freshness remains the supervisor's own protocol obligation, discharged by committing the brief before declaring `ready`.\n\nA supervisor has no supervisor of its own, by design: the supervision-offer surface is NOT applied to a pair member. Whether a track's supervision needs attention is evaluated independently of the worker's own classification on every cycle, rather than only when the worker happens to be idle. A pair member that disappears while its wind-down round is open MUST be surfaced as attention — supervision died mid-handoff and the brief is at risk; one that disappears with no round open is surfaced only through the ordinary supervision offer."

**EDIT 6 — spec.md §"The keep-going nudge", appended paragraphs.** Add:

"One further nudge exists, and it is aimed at the PAIR. When a worker and its supervisor have BOTH shown no observable progress continuously past a bounded floor, and NEITHER presents a human wait — no structured gate, no runtime report of waiting on a human, no standing `blocked:` — and the supervisor has no open round and no fresh wind-down acknowledgement, the daemon pastes ONE nudge into the SUPERVISOR, because the supervisor owns direction for the pair. The message names the stall and its duration, names the worker's coordinates, and offers exactly two honest outs: resume driving, or surface and declare the human question actually being waited on. Progress, for this purpose, is the runtime's own authoritative report that it is working, or the remaining-context reading moving between two KNOWN readings. A pane's displayed TEXT is never progress evidence for a session whose runtime reports authoritatively: displayed content routinely contains busy-looking text, and evidence that deliberately over-fires is safe only where it SUPPRESSES an act, never where it AFFIRMS progress and thereby suppresses detection.\n\nThis nudge is the ONE bounded exception to busy classification suppressing acts: the paste MAY land while the supervisor's only busy evidence is a background command at its prompt, and only then — at a verified empty and settled input prompt, never while the session is generating, never over a gate or a declared block, never while a round is open or a fresh acknowledgement stands, and only for a runtime whose empty input state is positively verifiable. A runtime whose input box cannot be verified empty is never pair-nudged; that divergence is justified by the evidence gap rather than assumed, exactly as other runtime divergences in this specification are. The nudge fires at most once per stall episode. An episode that ends only in the nudge's own answering turn does NOT reset the escalation: on the second consecutive episode ending in a nudge, the daemon skips the paste and surfaces the pair to the operator, naming both panes, the supervisor first, and the fact that the autonomous remedy has already failed.\n\nTwo residuals are accepted and stated rather than hidden. A human question posed only in scrolled-off prose is invisible to this guard set, which is why the nudge's own text instructs the supervisor to convert such a wait into a declared block. And a structured gate whose rendering escapes the gate detector is not suppressed by it."

**EDIT 7 — contracts.md §"The state file", an added table row and added rules.** The value table gains:

"| (per entity) | — | A supervisor pair member keeps its OWN state file at `<repo>/tmp/overseer/<topic>-supervisor/.overseer-state`, with the same grammar, the same writers, and the same rules as a worker's. |"

and the contract rules gain:

"- A declaration is honored for an ACT only when its file's canonicalized path equals that entity's canonical state path — no symlinked parent directories, no symlinked file — compared against an identically canonicalized repository root, so a legitimately symlinked checkout still passes. An aliased path is surfaced by name and treated as NO declaration, so one entity's write can never satisfy another entity's authorization."

**EDIT 8 — contracts.md §"The restart interlock", three amendments.**

(a) In the restart guarantees, the fresh-session guarantee generalizes from the worker to the entity: the fresh session is named after the ENTITY's derived session name, and is handed exactly one prompt — read that entity's resume artifact, `<repo>/plan/<topic>/handoff.md` for a worker and `<repo>/plan/<topic>/supervisor-handoff.md` for a supervisor pair member, and follow it.

(b) The preservation guarantee is CORRECTED. Replace:

"- Every step is a hard gate. A failed respawn or a pane that never becomes a\n  live supervised session surfaces the failure and PRESERVES the `ready`\n  declaration so the next cycle retries."

with:

"- Every step is a hard gate, and the two failures are NOT the same. A respawn that FAILED — the pane's process was never replaced — surfaces the failure and PRESERVES the `ready` declaration so the next cycle retries. A respawn that SUCCEEDED but whose fresh session is not recognized in time has already destroyed the predecessor, so it CONSUMES the kill authorization: the round is held open for submission retry only, and any further kill requires a genuinely fresh `ready`. One declaration MUST NEVER authorize two kills.\n- A restart is additionally held, and the track surfaced instead, when the session identity observed at the pane has changed since the `ready` was first seen — a declaration authorizes the restart of the session that wrote it, never of whatever session later occupies that pane."

(c) Append to the section:

"The interlock and every guarantee above apply per supervised entity, under that entity's own key."

**EDIT 9 — contracts.md §"Attention surface", the membership sentence.** Replace:

"The daemon owns \"what needs attention now\". Membership: a blocked track, a\nnon-responding track at the danger line, a track whose mapped session is\ngone, a malformed state value, and a restart whose resume has not yet\nsubmitted."

with:

"The daemon owns \"what needs attention now\". Membership: a blocked track, a non-responding track at the danger line, a track whose mapped session is gone, a malformed or path-aliased state value, a restart whose resume has not yet submitted, a supervisor pair member that disappeared while its round was open, and the REPORT-ONLY bounded members of spec.md §\"Fail-soft posture\" — a known-low track that has been unable to open a round past its floor (naming its background-command instance where that is the evidence), a track busy-shielded past the longer no-progress floor, a low track whose context knowledge has gone stale, and a pair whose autonomous nudge has already failed. Every member carries the same coordinates and the same edge-triggering; the report-only members MUST NOT authorize any act. A supervisor pair member needs no membership entry of its own — as a supervised entity it enters attention through the same statuses as any other."

### Explicitly unchanged

The cardinal rule (restated per entity, weakened nowhere); the supervision round; the escalating wrap-up's trigger, bands, and message obligations for workers; §"Notify, never block"'s ownership rule, under which the daemon still owns no decision and still never prompts on a track's behalf; surface-only startup; the watch-set declaration; discovery's plan-directory basis, since the reservation in EDIT 4 refuses a name pattern and discovers nothing new; the state-file grammar, since no new token ships and the pair-nudge bookkeeping is in-memory; and every constraint on worker-directed action.
