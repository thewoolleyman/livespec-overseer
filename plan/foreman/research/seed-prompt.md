# Foreman — planning seed prompt (verbatim user capture)

- **Captured:** 2026-08-02, at the start of the foreman brainstorming session.
- **Source:** user prompt, reproduced verbatim below (formatting lightly wrapped; wording untouched).
- **Editor's note:** the phrase "the goals of the new 'overseer' skill" in the
  second sentence means the new **'foreman'** skill — confirmed by the rest of
  the prompt.
- **Disposition:** landed as `plan/foreman/research/seed-prompt.md`. The
  thread's ledger epic anchor is `overseer-z5fo4y`; the grounded architecture
  companion is `brainstorm.md` beside this file.

---

I want to brainstorm a new 'foreman' Skill, which will augment and work with
the existing Overseer skill, overseer daemon, and supervisor skills.

The goals of the new 'overseer' skill is:

1. to help ensure that existing plans, workitems, and tracks of work are moved
   along with minimal stalling-out and blocking with no progress until I
   intervene

2. minimal escalation to me for things that are not worthy of my attention,
   but could be resolved by consensus-decision of smart models' opinions

3. Ensuring that things that DO legitimately need my attention ARE blocked and
   presented to me when they arise, driven by same smart-model consensus
   decisions. E.g. NON-TWO-WAY-DOOR decisions, LEGITIMATE high-level
   architecture decisions, things that will incur SIGNIFICANT TECHNICAL DEBT
   BUT FOR POTENTIAL UNBLOCKING/EXPEDIENCE, TRADEOFFS, HIGH-IMPACT UX
   decisions, etc.

4. Continues to progress on all other work which is NOT blocked by my pending
   decisions.

There will be a 1-1 relationship between a foreman and a livespec repo (fleet
member or adopter). In other words, a foreman ONLY manages plans (and their
supervisor/worker sessions) and workitems in its OWN REPO.

HOWEVER, foremans ARE aware of foremans from OTHER repos in fleet/adopters,
and can coordinate with them to ensure that work is moving along smoothly, and
coordinate any blockers / dependencies / etc, by communicating and delegating
to each other.

Rough idea for architecture:

1. livespec-overseer:foreman skill entry point - singleton / idempotent, tied
   to repo in which it is invoked. Fails if not invoked in pwd of livespec
   fleet/adopter repo (known via livespec config file in root and membership
   in fleet config file, see other precednet for this)

2.1 Monitors status of all active non-archived plans as reported by overseerd
    daemon process. however is most reliable, if this means exposing overseer
    state via file, or API calls (e.g. grpc) or IPC calls, or whatever is best
    without overengineering but remaining strongly typed and reliable. It
    ensures all of these plans moves along without stalling, if the supervisor
    or worker is stalled despite overseerd's best efforts. should ONLY block
    when there is a SPECIFIC BLOCKING question for the human.

2.2 Should ALSO handle plans tracked by overseerd which DO NOT HAVE AN
    ASSOCIATED SUPERVISOR (e.g. no plan/supervisor-handoff.md).

3. Monitors status of work items in its repo, which are NOT owned by plan
   epics, and thus NOT exposed by current overseer daemon. These should be
   moved along automatically, in concordance with the various automation flags
   in the livespec config file - e.g. auto-ready, ai-only accept gates. EACH
   OF THESE MUST HAVE AN ASSOCIATED TMUX SESSION named exactly after the work
   item.

4. Any missing tmux sessions which should/could exist (i.e. existing
   plan/handoff.md, plan/supervisor-handoff.md, or unblocked automate-able
   non-plan work item which needs human-facing input, e.g. rejected out of
   factory for human intervention or ai-only acceptance failing for
   auto-accept) should be automatically created by the foreman, with the
   correct name and associated tmux session.

5. For any BLOCKED items - either blocking questions presented by a
   supervisor (or unsupervised) session, or items that were kicked out of the
   fabro factory as blocked and needing HUMAN intervention - it should:

   a. delegate the BLOCKED status to be reviewed by a FABLE sub agent, an
      OPUS subagent, and a GPT sol subagent

   b. and ask EITHER for a recommended action to unblock with no human
      intervention, OR to confirm that human attention is legitimately
      needed.

   c. If they ALL agree on the same recommended action, then it should be
      taken automatically.

   d. If ONLY ONE of them agrees human intervention is needed, and the OTHER
      TWO agree on the same unblocking action, then the "minority report"
      decision should be presented to the other two, for potential override
      if BOTH the others still agree on their original unblocking action.

   e. In ANY OTHER CASE (disagreement on unblocking action, or a
      non-overridden report that human blocking question is still needed)
      then the associated tmux session should be instructed to present a
      SUMMARY OF EACH REVIEWER'S DECISION, and an AskUserQuestion CHOICE
      PRESENTED TO RESOLVE THE DISAGREEMENT (it's unelcear if Codex supports
      AskUserQuestion or not, if not, fall back to its best representation).
      This may involve instructing a currently-blocked tmux session to
      dismiss its current prompt, and present the summary of each reviewer's
      decision and the AskUserQuestion choice again, with each reviewer's
      decision summarized, and an updated AskUserQuestion choice presented
      which incorporates the feedback from the reviewers.

6. Then, foreman should summarize a `NEEDS YOU:` section, auto-updated just
   like the overseer prints out, with the name of the tmux session holding
   the prompt.

7. The foreman is NOT a script/program, but an LLM session that runs a 'loop'
   command, to do all the above checks and actions on an interval. The
   default interval is every hour, to avoid burning too many tokens. If ALL
   MONITORED SESSIONS are blocked with the EXACT SAME QUESTION/STATE for 2
   consecutive hours, then the foreman should exit its loop and present an
   AskUserQuestion choice for the user to resume the loop (to avoid burning
   tokens indefinitely after long pauses)

Capture all that in a tmp/foreman-planning-seed-prompt.md for posterity and
future refernece (and copy into the eventual plan research dir), then lets
start brainstoring and working towards a plan for it.

---

## Addendum (user, later the same session, 2026-08-02)

8. foreman should always be required to run in a `<repo>-foreman` tmux named
   exactly that - to facilitate intra-foreman communication across repos (but
   there can be an API exposed to facilitate this as well)
