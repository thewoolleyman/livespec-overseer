---
topic: foreman-own-unresolved-decision-surfacing-wording
author: claude-opus-5
created_at: 2026-08-23T14:24:21Z
---

## Proposal: The own-unresolved-decision scenario states the tick's terminal state, not merely that ticking continues

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Adds one Then-clause to the scenario "A foreman's own unresolved decision escalates without blocking" so that it states the tick returns idle with its required recurring schedule still armed. The scenario currently asserts only that the foreman continues ticking, which is a weaker and materially different claim than the one spec.md already requires of the same situation.

### Motivation

spec.md already requires, of a foreman surfacing its own unresolved decision, that it "MUST surface that decision through the non-blocking mechanical attention path and return idle with any required recurring schedule still armed". The scenario that exercises that requirement asserts only "And the foreman continues ticking and supervising every other tracked session". Those are not the same property: continuing to tick is about the operator loop surviving, whereas returning idle with the recurring schedule still armed is about this tick's terminal state and about the bounded re-check actually being scheduled. An implementation could continue ticking while dropping the recurring schedule, satisfying the scenario as written and violating the clause it exists to exercise. This is a scenario under-specified against its own tree's clause, not a new obligation. It was carried out of work-item overseer-afaj criterion 6 and is held by carrier work-item overseer-764a.2.

### Proposed Changes

In `SPECIFICATION/scenarios.md`, in the scenario `## Scenario: A foreman's own unresolved decision escalates without blocking`, add one Then-clause after `And the foreman continues ticking and supervising every other tracked session`:

```diff
 And the foreman continues ticking and supervising every other tracked session
 
+And the tick returns idle with its required recurring schedule still armed
+
 And no restart authorization is altered by this escalation
```

The added clause restates, in the scenario that exercises it, an obligation `spec.md` already imposes: the foreman MUST return idle with any required recurring schedule still armed when it surfaces its own unresolved decision. No new obligation is introduced and no existing clause changes. This edit adds no new heading, so `tests/heading-coverage.json` requires no corresponding entry.

## Proposal: The own-decision escalation clause states its requirement without implying a permitted alternative

### Target specification files

- SPECIFICATION/spec.md

### Summary

Replaces "it MUST default to a non-blocking escalation" with wording that states the requirement directly, because the same paragraph goes on to forbid absolutely the only alternative that "default" implies is available.

### Motivation

The paragraph beginning "When the foreman itself needs a human decision it cannot make" currently says the foreman "MUST default to a non-blocking escalation", and then two sentences later says "The foreman MUST NOT use a blocking question to surface its own unresolved human decision. It MUST surface that decision through the non-blocking mechanical attention path". The phrase "default to" is only meaningful if some non-default alternative is permitted, and the only alternative here is a blocking escalation, which the same paragraph prohibits without exception. The wording therefore implies, by construction, an exception that does not exist. A careful reader reconciles the two; a reader looking for the permitted exception will search for a condition that is never stated. This is an internal-consistency repair against text in the same paragraph, carried out of work-item overseer-afaj criterion 6 and held by carrier work-item overseer-764a.2.

### Proposed Changes

In `SPECIFICATION/spec.md`, in the paragraph beginning `When the foreman itself needs a human decision it cannot make`, replace the clause `it MUST default to a non-blocking escalation:` with `it MUST use a non-blocking escalation:`.

```diff
-never block" — it MUST default to a non-blocking escalation: the affected
+never block" — it MUST use a non-blocking escalation: the affected
```

The remainder of the paragraph MUST be left unchanged. In particular the operative obligations that follow it — that the foreman MUST NOT use a blocking question to surface its own unresolved human decision, and MUST surface that decision through the non-blocking mechanical attention path and return idle with any required recurring schedule still armed — already carry the enforcement, so this edit MUST NOT be taken as strengthening, duplicating, or relocating them. The change removes an implied permission that no other sentence grants; it does not alter what is required.
