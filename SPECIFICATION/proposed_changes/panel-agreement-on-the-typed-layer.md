---
topic: panel-agreement-on-the-typed-layer
author: gpt-5-codex
created_at: 2026-08-22T14:00:10Z
---

## Proposal: Panel agreement is decided on the typed layer, not on prose

### Target specification files

- SPECIFICATION/spec.md

### Summary

When every reviewer on a constituted panel returns the same verdict and the
same typed action, and they differ only in a free-text payload that the action
carries, the panel MUST be treated as having agreed. The decision MUST be
recorded with a deterministically selected payload, and every reviewer's payload
MUST be retained verbatim in the verdict. Agreement MUST NOT be established by
semantic-similarity or fuzzy matching of free text.

### Motivation

Measured on 2026-08-22 on a live panel, cache key beginning 87ade105, convened
on the overseerd-observability blocked pane. All three pinned reviewers returned
verdict unblock and action id blocked_session_answer. They differed only in the
prose answer they would deliver, and all three said the same thing in different
words: the session's premise was stale, none of its four offered options should
be taken, the fix it had staged had already landed from another track, and it
should wait for an ordinary green master. The panel returned outcome escalate,
reason typed_action_disagreement, decision kind substantive non-decision, action
human_valve. Three reviewers agreed completely and the panel produced a
non-decision.

The mechanism is that agreement is currently keyed on the free text itself. The
consensus key for a blocked_session_answer action reduces to the action id plus
one surviving parameter, the answer string, and the unanimous path requires
exactly one canonical key. The one field that survives normalisation is the one
field that cannot match across independently sampled reviewers.

THE TRIGGER IS CONCENTRATED WHERE A PANEL IS MOST VALUABLE. When a blocked
session offers numbered options, reviewers answer with an option number, exact
match works, and panels decide normally; that is the common case on record.
Reviewers are forced into prose precisely when they conclude that NONE of the
offered options is right, which is the case a panel exists to resolve. In the
measured specimen all three reviewers rejected all four offered options.

THIS ALSO BINDS THE MAJORITY RULE, AND THAT IS THE URGENT PART. The majority
path consumes the same consensus key and requires two byte-identical keys to
declare a winner. Byte-identical prose from two independently sampled reviewers
does not occur. Measured on the same host, the only majority-resolved record,
cache key beginning 968721a9, won on single-character option numbers -- answers
"3", "2", "3". So a panel that rejects a session's offered options escalates
under the majority rule for the same reason it escalates under the unanimous
rule. Adopting a decision rule of majority therefore does NOT, on its own, make
the commonest hard case decidable: the rule would be satisfied on paper while
that case still lands on a human, which is worse than the current state because
it would be believed.

A FURTHER CONSEQUENCE, MEASURED: a verdict is cached under the request key
unless its reason is one of the structural refusals, currently malformed_input
and panel_size_mismatch. A prose-variance escalation is therefore CACHED, so the
non-decision is sticky for the whole cache lifetime and a re-convening that
might have produced agreement never happens.

WHY THIS IS A SPECIFICATION QUESTION AND NOT A CONFORMANCE FIX. The
specification distinguishes two member kinds: an ACTION the foreman itself
performs, and a TYPED RULING a supervised session executes, which MUST carry in
structured fields rather than in prose every value the executing session needs
in order to act without re-deciding anything, and which MUST escalate if the
session must interpret it before acting. blocked_session_answer is the first
kind. The specification does not say which side a prose answer RELAYED to a
session falls on -- whether it is a value the session can act on, or a member
the session must interpret. That gap is what this proposal closes. Resolving it
inside an implementation would be ratification by implementation.

The measurements above were taken by the plan/foreman-panel-and-consensus
thread on 2026-08-22 against live panel records under tmp/overseer/foreman/panel/
and tmp/overseer/foreman/panels/, and the mechanism was read from
foreman_consensus_matrix on origin/master. The population was 22 distinct panel
records, of which five escalated as typed_action_disagreement: two were an older
shape already cured by the existing consensus-key normalisation, two were
genuine disagreement over enumerated answers where escalation is correct and
must remain so, and one is the specimen above.

### Proposed Changes

In SPECIFICATION/spec.md, in the decision-rule section, state that agreement
between reviewers is evaluated on the TYPED LAYER: the action id together with
the enumerated parameters the governing orchestrator contract defines for that
action. A free-text payload carried by an action MUST NOT be part of the
agreement test.

Add that when the typed layer agrees and only a free-text payload differs, the
panel HAS agreed for the purposes of both the unanimous and the majority
decision rules, and:

- the verdict MUST record that agreement was reached on the typed layer with
  payloads differing;
- the payload that is delivered MUST be selected deterministically, from a
  designated primary reviewer seat, so that the same panel state always
  produces the same delivered payload and the selection is auditable;
- every reviewer's payload MUST be retained verbatim in the verdict record, so
  that a reader can see what each seat would have said and an operator can audit
  the selection;
- agreement MUST NOT be established by semantic-similarity, embedding distance,
  or any other fuzzy comparison of free text. An unauditable equality test is
  worse than an honest escalation, because it can silently authorise an act on
  the strength of a similarity score no reader can check.

State explicitly that this does not move the floor: it changes what counts as
AGREEMENT, not what a panel is permitted to authorise. Every existing floor
category, veto, security-dissent rule, and the cardinal restart rule are
unchanged, and a genuine difference in the typed action -- including two
reviewers choosing different enumerated answers -- MUST still escalate exactly
as it does today.

Where SPECIFICATION/scenarios.md carries panel scenarios, a scenario SHOULD
prove both sides: a panel whose reviewers agree on verdict and action id and
differ only in prose is DECIDED and records the differing payloads; a panel
whose reviewers choose genuinely different enumerated answers still escalates.
