"""The contract a GENERATED supervisor handoff must satisfy (overseer-hbr.16).

This is the floor for what `supervise-plan` emits. It is asserted over CHARTER
TEXT — the artifact the generator produces — not over the generator's own prose,
so a charter that merely *mentions* a rule cannot pass while omitting it.

Why a validator instead of substring assertions on the prose: `gap-lqxagafn`'s
evidence is six `assert "<string>" in prose` checks, which prove the instruction
EXISTS and cannot prove a generated charter OBEYS it. The negative fixtures below
are the difference — each one is a charter that looks complete and is not, and
each must be REJECTED for a named reason.

The two stall-mode requirements are checked INDEPENDENTLY on purpose. A charter
that ends its supervisor guidance at the conflicting-lane rule is exactly the
shape that shipped the second stall mode fleet-wide, so a fixture that cannot
tell the two apart is a verifier that cannot fail.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXEMPLAR = _REPO_ROOT / "plan" / "ship-overseer-to-fleet" / "supervisor-handoff.md"
_GENERATOR_PROSE = _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md"

# A cwd-relative `test -d "plan/<topic>"` passes while pointed at the WRONG repo,
# because nothing in the skill establishes a working directory. The containment
# check has to resolve an absolute path instead.
_CWD_RELATIVE_TEST_D = re.compile(r'test\s+-d\s+"?plan/')

# `tmux send-keys -t <s> -- '<text>' Enter` lands the text in the prompt but does
# NOT submit it — measured 2026-07-26 against a live worker pane. Enter must be a
# separate call, after a capture confirms the text landed.
_ONE_SHOT_SEND_KEYS = re.compile(r"send-keys[^\n]*--\s*'[^']*'\s+Enter")


# The contract, as data. Each entry is (requirement-name, needles-that-must-all-
# appear). Table-driven rather than a chain of ifs so adding a requirement is a
# one-line change and the function stays under the complexity ceiling.
_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    # STALL MODE 1 — a conflicting lane is not a blocked state.
    ("stall-mode-1-conflicting-lane", ("conflicting lane", "stand down")),
    # STALL MODE 2 — never end a turn with the worker mid-flight and nothing
    # armed. Checked separately from mode 1; see the module docstring.
    ("stall-mode-2-armed-re-entry", ("armed re-entry",)),
    # Mode 2 is only actionable if the charter names a MECHANISM. "I'll check
    # back" is an intention, and intentions are what the rule exists to reject.
    ("stall-mode-2-watcher-mechanism", ("watcher",)),
    # Maintainer-facing actions are AskUserQuestion calls with a recommendation.
    ("picker-rule", ("askuserquestion", "recommend")),
    # The one prohibition that must survive every regeneration.
    ("no-verify-prohibition", ("--no-verify",)),
    # The prohibition that is specific to THIS product. A supervisor charter
    # hands its reader broad tmux authority; the acting daemon is just another
    # tmux session to that reader, and killing it stops supervision for the
    # WHOLE fleet, not for the one track the charter governs.
    ("acting-daemon-prohibition", ("never kill the acting overseer daemon",)),
    # `.4`'s bar: RUNNABLE inspection commands, not prose describing them.
    ("executable-capture-pane", ("capture-pane", "-S -40")),
    # Proving the pane holds a live agent needs a real process-tree command.
    ("executable-live-agent-precondition", ("pane_pid",)),
    # Repo containment must resolve a real path.
    ("executable-repo-containment", ("readlink -f",)),
)

# Patterns whose PRESENCE is the defect, rather than whose absence is.
#
# These match LITERALLY, so a charter that quotes one of these forms as a
# counter-example is flagged too. That is a deliberate trade: the check stays
# simple and cannot be talked out of a real hit by surrounding prose. Documents
# that need to warn against a form describe it instead of reproducing it — the
# generator prose does exactly that for the cwd-relative containment check.
_BANNED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("cwd-relative-plan-test", _CWD_RELATIVE_TEST_D),
    ("one-shot-send-keys-enter", _ONE_SHOT_SEND_KEYS),
)


def missing_requirements(*, charter: str) -> list[str]:
    """Return the contract requirements a generated charter FAILS to satisfy.

    An empty list means the charter satisfies the floor. Each returned string
    names one requirement, so a caller can assert on the specific failure rather
    than on a bare boolean.
    """
    lowered = charter.lower()
    missing = [
        name
        for name, needles in _REQUIRED
        if not all(needle.lower() in lowered for needle in needles)
    ]
    missing.extend(name for name, pattern in _BANNED if pattern.search(charter))
    return missing


def test_the_corrected_exemplar_satisfies_the_whole_contract():
    """The hand-written exemplar is what the generator must be able to produce.

    Sabotage that reddens this: delete the "Never end a turn without an armed
    re-entry" section from the exemplar.
    """
    assert missing_requirements(charter=_EXEMPLAR.read_text(encoding="utf-8")) == []


def test_the_generator_prose_instructs_every_contract_requirement():
    """The SHIPPED generator must tell the model to emit each requirement.

    This is the test that fails before the generator is fixed. It is deliberately
    asserted over the generator prose as well as the exemplar: a charter can only
    carry the floor if the thing producing it says to.

    Sabotage that reddens this: remove the armed-re-entry section from
    `.claude-plugin/prose/supervise-plan.md`.
    """
    assert missing_requirements(charter=_GENERATOR_PROSE.read_text(encoding="utf-8")) == []


def test_a_charter_ending_at_the_conflicting_lane_rule_is_rejected():
    """THE fixture that had to be able to fail.

    This charter carries stall mode 1 in full and stops there — the exact shape
    that shipped the second stall mode fleet-wide. If this passed, the two modes
    would be indistinguishable and the verifier would be worthless.
    """
    charter = """
    # Supervisor Handoff - demo
    ## How to inspect and drive
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    ## No idle, no silent block
    A conflicting lane owned by another track is NOT a blocked state. Stand down
    on that action only, enumerate the rest, and drive the next safe action.
    ## AskUserQuestion presentation rules
    One question per turn, recommended option first.
    ## Standing safety clauses
    Never pass --no-verify.
    """
    missing = missing_requirements(charter=charter)
    assert "stall-mode-2-armed-re-entry" in missing
    assert "stall-mode-2-watcher-mechanism" in missing
    # ...and mode 1 is NOT reported, which is what makes the two independent.
    assert "stall-mode-1-conflicting-lane" not in missing


def test_a_charter_carrying_only_the_armed_re_entry_rule_is_also_rejected():
    """The converse. Independence has to hold in both directions, or the pair is
    really one check wearing two names."""
    charter = """
    # Supervisor Handoff - demo
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    ## Never end a turn without an armed re-entry
    Launch a background pane watcher before ending any turn.
    ## AskUserQuestion presentation rules
    Recommended option first.
    Never pass --no-verify.
    """
    missing = missing_requirements(charter=charter)
    assert "stall-mode-1-conflicting-lane" in missing
    assert "stall-mode-2-armed-re-entry" not in missing


def test_an_armed_re_entry_rule_with_no_mechanism_is_rejected():
    """ "I'll check back" is an intention. The rule exists because intentions do
    not wake anyone up, so naming the rule without naming a mechanism fails."""
    charter = """
    # Supervisor Handoff - demo
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Before ending a turn, make sure you will come back to it. I'll check back.
    ## AskUserQuestion rules
    Recommended option first. Never pass --no-verify.
    """
    assert "stall-mode-2-watcher-mechanism" in missing_requirements(charter=charter)


def test_a_charter_with_prose_instead_of_runnable_commands_is_rejected():
    """`.4`'s bar. HALT preconditions that state a requirement and supply no
    command are what forced a cold-open supervisor to invent them."""
    charter = """
    # Supervisor Handoff - demo
    ## HALT-first preconditions
    Inspect the target session's pane process tree and confirm it contains a
    claude or codex CLI process. Confirm the pane cwd is inside the repo.
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify.
    """
    missing = missing_requirements(charter=charter)
    assert "executable-capture-pane" in missing
    assert "executable-live-agent-precondition" in missing
    assert "executable-repo-containment" in missing


def test_a_cwd_relative_plan_containment_check_is_rejected():
    """`test -d "plan/<topic>"` passes while pointed at the wrong repo. The skill
    never establishes a working directory, so this is not a hypothetical."""
    charter = """
    # Supervisor Handoff - demo
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    test -d "plan/<topic>"
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify.
    """
    assert "cwd-relative-plan-test" in missing_requirements(charter=charter)


def test_the_one_shot_send_keys_enter_form_is_rejected():
    """Measured 2026-07-26 against a live worker pane: the trailing `Enter`
    argument lands the text but does NOT submit it, leaving the instruction
    queued at the prompt — which is the idle-plus-queued-input stall."""
    charter = """
    # Supervisor Handoff - demo
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    tmux send-keys -t demo -- 'do the thing' Enter
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify.
    """
    assert "one-shot-send-keys-enter" in missing_requirements(charter=charter)


def test_a_charter_with_no_picker_rule_is_rejected():
    """A charter that never says maintainer-facing actions are AskUserQuestion
    calls with a recommendation produces a supervisor that asks in prose — which
    is how a finished decision sits unnoticed in a pane."""
    charter = """
    # Supervisor Handoff - demo
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher.
    Never pass --no-verify.
    """
    assert "picker-rule" in missing_requirements(charter=charter)


def test_a_charter_omitting_the_no_verify_prohibition_is_rejected():
    """The one prohibition that must survive every regeneration. A charter that
    drops it has shipped a supervisor willing to work around a failing gate."""
    charter = """
    # Supervisor Handoff - demo
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher.
    ## AskUserQuestion presentation rules
    Recommended option first.
    """
    assert "no-verify-prohibition" in missing_requirements(charter=charter)


def test_a_charter_omitting_the_acting_daemon_prohibition_is_rejected():
    """The blast radius here is wider than any other requirement in this file.

    Every other rule protects the one track the charter governs. This one
    protects the daemon supervising the whole fleet — and a charter that grants
    tmux authority without naming it reads as though `livespec-overseer:1.1`
    were an ordinary session to clean up. The charter below is otherwise
    conformant, including the generic `kill-server` warning, which is exactly
    why the generic warning is not a substitute.
    """
    charter = """
    # Supervisor Handoff - demo
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher.
    ## AskUserQuestion presentation rules
    Recommended option first.
    ## Standing safety clauses
    Never pass --no-verify. Never run kill-server on the maintainer's socket.
    """
    assert "acting-daemon-prohibition" in missing_requirements(charter=charter)


def test_the_control_a_fully_conformant_charter_passes():
    """The control for every rejection above. Without it, the negative fixtures
    prove only that the validator can say no — not that it can ever say yes."""
    charter = """
    # Supervisor Handoff - demo
    ## HALT-first preconditions
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    case "$(readlink -f "$pane_cwd")" in /data/projects/demo|/data/projects/demo/*) ;; esac
    ## How to inspect and drive
    tmux capture-pane -p -t demo -S -40
    ## No idle, no silent block
    A conflicting lane owned by another track is NOT a blocked state. Stand down
    on that action only; enumerate the rest; drive the next safe action.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher before ending any turn.
    ## AskUserQuestion presentation rules
    One question per turn, recommended option first.
    ## Standing safety clauses
    Never pass --no-verify. Never kill the acting overseer daemon.
    """
    assert missing_requirements(charter=charter) == []
