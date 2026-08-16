---
topic: out-of-band-edit-2026-08-16t15-47-34z
author: livespec-doctor
created_at: 2026-08-16T15:47:34Z
---

## Proposal: out-of-band-edit-2026-08-16t15-47-34z

doctor detected drift between HEAD-active spec content and the
HEAD-history-vN snapshot; this auto-backfill records the active
state as the new canonical version.

### Proposed Changes

```diff
--- history/vN/contracts.md
+++ active/contracts.md
@@ -493,11 +493,16 @@
 
 Membership also includes a successfully restarted fresh session with no
 observed context consumption and an exact expected resume payload still in
-its composer continuously past the 60-second floor, including the case where
-`resume_pending` was not recorded. This is a distinct report-only member with
-normal coordinates; it participates in the NEEDS YOU count and window badge,
-is edge-triggered, and authorizes no act. Discovered-but-unassigned tracks
-remain outside this membership.
+its composer continuously past the 60-second floor. This is a distinct
+report-only member with normal coordinates; it participates in the NEEDS YOU
+count and window badge, is edge-triggered, and authorizes no act on its own.
+The same exact expected composer evidence independently authorizes the
+submission-only self-heal: on any acting tick, including when
+`resume_pending` was not recorded, the daemon records the round-scoped
+`resume_pending` retry and re-sends Enter only. It MUST NOT re-paste,
+respawn, terminate the session, write a declaration, or keystroke any
+non-exact composer text. Discovered-but-unassigned tracks remain outside this
+membership.
 
 ## The foreman valve disposition
 
--- history/vN/scenarios.md
+++ active/scenarios.md
@@ -505,7 +505,7 @@
 
 And the track remains visible as needing attention until the resume submits
 
-## Scenario: A restarted session that never begins work is surfaced without a second kill
+## Scenario: A restarted session that never begins work retries submission without a second kill
 
 Given a successful respawn
 
@@ -515,13 +515,21 @@
 
 And no `resume_pending` flag was recorded
 
+When the daemon observes the track on a later acting tick
+
+Then it records `resume_pending`
+
+And it re-sends Enter only
+
+And it does not re-paste, respawn, terminate the session, or write a declaration
+
 When the evidence remains continuous beyond the 60-second floor
 
 Then the track is in NEEDS YOU
 
 And the attention count badges the overseer window
 
-And the daemon reports coordinates without respawning, submitting, writing state, or terminating the session
+And the daemon reports coordinates without re-pasting, respawning, terminating the session, or writing a declaration
 
 When the session begins work or the composer changes
 
--- history/vN/spec.md
+++ active/spec.md
@@ -313,10 +313,13 @@
 
 After a respawn succeeds, the daemon retains enough live observation to
 recognize a fresh session that has consumed no context and whose composer
-holds exactly the track's expected resume text. If those facts remain
-continuously observed for a bounded 60-second post-respawn floor, the daemon
-MUST surface the track as report-only NEEDS YOU attention, even when the
-ordinary `resume_pending` retry state is absent. The daemon MUST re-evaluate
+holds exactly the track's expected resume text. On any acting tick observing
+that exact expected composer evidence, the daemon MUST re-arm the
+round-scoped `resume_pending` retry and re-send Enter only; it MUST NOT
+re-paste the resume, respawn, terminate the session, or treat any non-exact
+composer text as retry authority. If those facts remain continuously
+observed for a bounded 60-second post-respawn floor, the daemon MUST surface
+the track as report-only NEEDS YOU attention. The daemon MUST re-evaluate
 this condition on every supervision tick, MUST emit the attention edge only
 on entry, and MUST clear and re-arm it when the session begins work or the
 composer no longer exactly matches the expected resume text. An unknown or
```
