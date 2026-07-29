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
import shlex
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GENERATOR_PROSE = _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md"

# The exemplar is a LIVE plan thread's charter, and a plan thread moves into
# `plan/archive/` when it closes. An unguarded read of the live path alone made
# archiving `ship-overseer-to-fleet` a CI-reddening act: the read raised
# FileNotFoundError from inside the aggregate gate, for a reason that had
# nothing to do with the contract under test. Accepting either location keeps
# the thread's own lifecycle from breaking an unrelated verifier.
#
# Archiving does not weaken the pin. The exemplar is a known-good SAMPLE that
# must satisfy the requirement list below; that list lives in this module and
# is what actually holds the line.
_EXEMPLAR_CANDIDATES = (
    _REPO_ROOT / "plan" / "supervisor-prompt-quality" / "supervisor-handoff.md",
    _REPO_ROOT / "plan" / "ship-overseer-to-fleet" / "supervisor-handoff.md",
    _REPO_ROOT / "plan" / "archive" / "ship-overseer-to-fleet" / "supervisor-handoff.md",
)

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
    # `.4`'s bar: RUNNABLE inspection commands, not prose describing them. This
    # is deliberately the visible-only watcher capture, not the unrelated
    # scrollback-fed inspect command.
    ("executable-capture-pane", ("capture-pane -p -t", "visible only")),
    # Proving the pane holds a live agent needs a real process-tree command.
    ("executable-live-agent-precondition", ("pane_pid",)),
    # ...and the SUPERVISOR half needs the same proof (overseer-ejja5o). The
    # contract refused to trust a session NAME for the worker and then trusted
    # one for the supervisor — precondition 2's own warning, applied to the
    # other half of the pair. Observed 2026-07-28: a supervisor session created
    # as a bare `zsh` with no agent in it returned PASS, so a session that could
    # not supervise anything cleared the gate. The needle is deliberately the
    # DISTINCT variable name, because `pane_pid` is a substring of
    # `supervisor_pane_pid` and the worker's own binding would otherwise satisfy
    # this requirement without a single supervisor-side check existing.
    ("executable-live-supervisor-precondition", ("supervisor_pane_pid",)),
    # Repo containment must resolve a real path.
    ("executable-repo-containment", ("readlink -f",)),
    ("watcher-wait-channel-bootstrap", ("wait_channel", ": >")),
    ("watcher-wait-channel-fed", ("append", "milestone")),
    ("watcher-expiry-rearms-by-mechanism", ("WAKE:", "RE-ARM NOW")),
)

# Patterns whose PRESENCE is the defect, rather than whose absence is.
_FENCED_COMMANDS = re.compile(r"^[ \t]*```(?:bash|sh)\n(.*?)\n[ \t]*```", re.DOTALL | re.MULTILINE)
_ASSIGNMENT = re.compile(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)=(['\"])(.*?)\2")
_TARGETED_TMUX_COMMANDS = {
    "capture-pane",
    "display-message",
    "has-session",
    "list-panes",
    "paste-buffer",
    "send-keys",
}
_PICKER_FOOTER = re.compile(r"^[ \t]*Enter to (select|confirm)[ \t]*(·.*)?$", re.MULTILINE)


def _command_blocks(*, charter: str) -> list[str]:
    return [match.group(1) for match in _FENCED_COMMANDS.finditer(charter)]


def _logical_lines(*, block: str) -> list[str]:
    return block.replace("\\\n", " ").splitlines()


def _bindings_for(*, block: str) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for line in _logical_lines(block=block):
        match = _ASSIGNMENT.match(line)
        if match is not None:
            bindings[match.group(1)] = match.group(3)
    return bindings


def _target_token(*, parts: list[str]) -> str | None:
    for index, part in enumerate(parts):
        if part == "-t" and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith("-t") and len(part) > 2:
            return part[2:]
    return None


def _resolved_target(*, token: str, bindings: dict[str, str]) -> str:
    if token.startswith("${") and token.endswith("}"):
        return bindings.get(token[2:-1], "")
    if token.startswith("$"):
        return bindings.get(token.removeprefix("$"), "")
    return token


def _is_exact_tmux_target(*, target: str) -> bool:
    return target.startswith("=") and target.endswith(":") and len(target) > 2


def banned_requirements(*, charter: str) -> list[str]:
    """Return prohibited generated command forms found in fenced commands only."""
    banned: list[str] = []
    bindings: dict[str, str] = {}
    for block in _command_blocks(charter=charter):
        bindings.update(_bindings_for(block=block))
        if _CWD_RELATIVE_TEST_D.search(block):
            banned.append("cwd-relative-plan-test")
        if _ONE_SHOT_SEND_KEYS.search(block):
            banned.append("one-shot-send-keys-enter")
        for line in _logical_lines(block=block):
            try:
                parts = shlex.split(line, comments=True)
            except ValueError:
                continue
            if len(parts) < 2 or parts[0] != "tmux" or parts[1] not in _TARGETED_TMUX_COMMANDS:
                continue
            token = _target_token(parts=parts)
            if token is None:
                continue
            target = _resolved_target(token=token, bindings=bindings)
            if not _is_exact_tmux_target(target=target):
                banned.append(f"non-exact-tmux-target:{parts[1]}")
    return banned


def _halt_precondition_blocks(*, charter: str) -> list[str]:
    start = charter.find("## HALT-first preconditions")
    if start == -1:
        return []
    rest = charter[start:]
    end_match = re.search(r"\n## ", rest[len("## HALT-first preconditions") :])
    section = (
        rest
        if end_match is None
        else rest[: len("## HALT-first preconditions") + end_match.start()]
    )
    matches = list(re.finditer(r"(?m)^\s*\d+\. ", section))
    return [
        section[match.start() : matches[index + 1].start() if index + 1 < len(matches) else None]
        for index, match in enumerate(matches)
    ]


def _missing_remedy_labels(*, charter: str) -> list[str]:
    missing: list[str] = []
    for index, block in enumerate(_halt_precondition_blocks(charter=charter), start=1):
        if "REMEDY:" not in block:
            missing.append(f"precondition-{index}-remedy")
    return missing


def _has_readlink_empty_guard(*, charter: str) -> bool:
    for block in _command_blocks(charter=charter):
        readlink_at = block.find("readlink -f")
        if readlink_at == -1:
            continue
        guard_at = block.find('[ -n "$pane_cwd" ]')
        if guard_at == -1:
            guard_at = block.find('[ -n "$wcwd" ]')
        if guard_at != -1 and guard_at < readlink_at and "readlink -f --" in block:
            return True
    return False


def _has_pane_pid_empty_verdict(*, charter: str) -> bool:
    for block in _command_blocks(charter=charter):
        ps_at = block.find("ps -o pid=,comm=,args=")
        if ps_at == -1:
            continue
        guard_at = block.find('[ -n "$pane_pid" ]')
        if guard_at == -1:
            guard_at = block.find('[ -n "$wpid" ]')
        empty_at = block.find("empty pane_pid")
        if guard_at != -1 and empty_at != -1 and guard_at < ps_at:
            return True
    return False


def _has_supervisor_agent_proof(*, charter: str) -> bool:
    """The supervisor precondition must PROVE liveness, not merely mention a pid.

    A needle alone is satisfiable by a charter that binds `supervisor_pane_pid`
    and never uses it, which is the same shape of toothless check this whole
    thread exists to remove. So require, in ONE block: the pid resolved, guarded
    non-empty BEFORE it is used, proven DISTINCT from the worker's pane, and
    actually fed to the process-tree command.

    The distinct-pane guard is C1's lesson applied to this half. `<topic>` is a
    strict prefix of `<topic>-supervisor`, and a target that resolves onto the
    WORKER's pane would find the worker's live agent and report the supervisor
    as healthy — a check passing on the wrong pane's evidence.
    """
    for block in _command_blocks(charter=charter):
        ps_at = block.find('--ppid "$supervisor_pane_pid"')
        if ps_at == -1:
            continue
        guard_at = block.find('[ -n "$supervisor_pane_pid" ]')
        distinct_at = block.find('"$supervisor_pane_pid" != "$pane_pid"')
        if guard_at != -1 and distinct_at != -1 and max(guard_at, distinct_at) < ps_at:
            return True
    return False


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
    missing.extend(banned_requirements(charter=charter))
    missing.extend(_missing_remedy_labels(charter=charter))
    if not _has_readlink_empty_guard(charter=charter):
        missing.append("readlink-empty-guard")
    if not _has_pane_pid_empty_verdict(charter=charter):
        missing.append("pane-pid-empty-verdict")
    if not _has_supervisor_agent_proof(charter=charter):
        missing.append("supervisor-agent-proof")
    guard_at = charter.find('[ -z "$pane" ]')
    diff_at = charter.find('if [ "$pane" = "$prev" ]')
    if guard_at == -1 or diff_at == -1 or diff_at < guard_at:
        missing.append("watcher-empty-capture-guard")
    return missing


def has_picker_footer(*, capture: str) -> bool:
    """Return whether a visible pane capture contains a real picker footer."""
    return _PICKER_FOOTER.search(capture) is not None


def test_the_corrected_exemplar_satisfies_the_whole_contract():
    """The hand-written exemplar is what the generator must be able to produce.

    Sabotage that reddens this: delete the "Never end a turn without an armed
    re-entry" section from the exemplar. Sabotage that reddens the LOCATOR:
    rename both candidate paths, which must fail with the named-location message
    rather than a bare FileNotFoundError.
    """
    exemplar = next((path for path in _EXEMPLAR_CANDIDATES if path.is_file()), None)
    assert exemplar is not None, (
        "the exemplar charter is at neither its live nor its archived location — "
        + ", ".join(str(path) for path in _EXEMPLAR_CANDIDATES)
        + ". This contract pins the generated charter against a hand-written one, "
        "so if the plan thread moved again, add its new location to "
        "_EXEMPLAR_CANDIDATES rather than deleting this assertion."
    )
    assert missing_requirements(charter=exemplar.read_text(encoding="utf-8")) == []


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
    ```sh
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    test -d "plan/<topic>"
    ```
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
    ```sh
    tmux capture-pane -p -t demo -S -40
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    tmux send-keys -t demo -- 'do the thing' Enter
    ```
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify.
    """
    assert "one-shot-send-keys-enter" in missing_requirements(charter=charter)


def test_banned_form_lint_resolves_variable_bindings():
    good = """
    ```sh
    W='=demo:'
    tmux capture-pane -p -t "$W"
    tmux send-keys -t "$W" -- 'continue'
    ```
    """
    bad = """
    ```sh
    W='demo'
    tmux capture-pane -p -t "$W"
    tmux send-keys -t "$W" -- 'continue'
    ```
    """
    assert banned_requirements(charter=good) == []
    assert "non-exact-tmux-target:capture-pane" in banned_requirements(charter=bad)
    assert "non-exact-tmux-target:send-keys" in banned_requirements(charter=bad)


def test_banned_form_lint_covers_shell_edge_forms():
    charter = """
    ```sh
    W='=demo:'
    tmux capture-pane -p -t${W}
    tmux list-panes -tdemo
    tmux has-session
    tmux send-keys -t "unterminated
    ```
    """
    banned = banned_requirements(charter=charter)
    assert "non-exact-tmux-target:list-panes" in banned
    assert "non-exact-tmux-target:capture-pane" not in banned


def test_banned_form_lint_scans_fenced_command_blocks_only():
    charter = """
    The correction names a bad form in prose: tmux send-keys -t demo -- 'x'.

    ```sh
    W='=demo:'
    tmux send-keys -t "$W" -- 'x'
    ```
    """
    assert banned_requirements(charter=charter) == []


def test_each_halt_precondition_requires_a_literal_remedy_label():
    charter = """
    # Supervisor Handoff - demo
    ## HALT-first preconditions
    1. Worker session exists.

       ```sh
       W='=demo:'
       tmux has-session -t "$W" || { echo "HALT"; echo "REMEDY: start it"; exit 1; }
       ```

    2. Worker is a live agent.

       ```sh
       pane_pid=$(tmux display-message -p -t "$W" '#{pane_pid}')
       [ -n "$pane_pid" ] || { echo "HALT: empty pane_pid"; exit 1; }
       ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
       ```
    ## How to inspect and drive
    tmux capture-pane -p -t "$W" # visible only
    [ -z "$pane" ] && { echo "WAKE"; exit 0; }
    if [ "$pane" = "$prev" ]; then stable=$((stable+1)); else stable=0; prev="$pane"; fi
    readlink -f -- "$pane_cwd"
    """
    assert "precondition-2-remedy" in missing_requirements(charter=charter)


def test_readlink_empty_guard_is_required_before_coreutils_can_disagree():
    charter = """
    ```sh
    W='=demo:'
    pane_cwd=$(tmux display-message -p -t "$W" '#{pane_current_path}')
    case "$(readlink -f -- "$pane_cwd")" in /repo|/repo/*) echo PASS ;; esac
    ```
    """
    assert "readlink-empty-guard" in missing_requirements(charter=charter)


def test_empty_pane_pid_must_be_a_classified_verdict():
    charter = """
    ```sh
    W='=demo:'
    pane_pid=$(tmux display-message -p -t "$W" '#{pane_pid}')
    ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
    ```
    """
    assert "pane-pid-empty-verdict" in missing_requirements(charter=charter)


def test_picker_footer_detection_rejects_a_wrapped_quote():
    """A start-only anchor matches wrapped prose whose continuation begins with
    the footer words. A real footer owns the full line, including the end."""
    capture = """
    The charter quotes this deliberately: the terminal can wrap before
    Enter to select and then keep narrating why that quoted footer is unsafe.
    """
    assert not has_picker_footer(capture=capture)


def test_picker_footer_detection_accepts_both_footer_forms():
    assert has_picker_footer(capture="Enter to select")
    assert has_picker_footer(capture="Enter to confirm · Esc to cancel")


def test_a_watcher_without_wait_channel_bootstrap_is_rejected():
    charter = """
    # Supervisor Handoff - demo
    tmux capture-pane -p -t demo # visible only
    [ -z "$pane" ] && { echo "WAKE: pane unreadable"; exit 0; } # before the diff
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    wait_channel=/tmp/worker-status.log
    Tell the worker to append to it at every milestone.
    echo "WAKE: watcher ceiling reached — worker still busy, RE-ARM NOW"
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify. Never kill the acting overseer daemon.
    """
    assert "watcher-wait-channel-bootstrap" in missing_requirements(charter=charter)


def test_a_watcher_whose_expiry_only_echoes_intention_is_rejected():
    charter = """
    # Supervisor Handoff - demo
    tmux capture-pane -p -t demo # visible only
    [ -z "$pane" ] && { echo "WAKE: pane unreadable"; exit 0; } # before the diff
    pane_pid=$(tmux display-message -p -t demo '#{pane_pid}')
    readlink -f "$pane_cwd"
    wait_channel=/tmp/worker-status.log
    : > "$wait_channel"
    Tell the worker to append to it at every milestone.
    echo "watcher ceiling reached — worker still busy, re-arm"
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Arm a background pane watcher.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify. Never kill the acting overseer daemon.
    """
    assert "watcher-expiry-rearms-by-mechanism" in missing_requirements(charter=charter)


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


def test_a_supervisor_ps_command_without_its_guards_is_rejected():
    """The `ps` line alone must NOT satisfy the supervisor proof.

    This is the toothless-check shape one level down: a charter can emit a real
    process-tree command for the supervisor and still be unsound, because
    without the non-empty guard an absent session yields an empty pid, and
    without the distinct-pane guard a prefix match runs the check against the
    WORKER's pane and finds the worker's agent.

    The trailing second block is load-bearing, not padding: it forces the
    scanner to keep looking after this block fails, which is the arc that
    distinguishes "no conformant block yet" from "give up on the first miss".
    """
    charter = """
    ```sh
    S='=demo-supervisor:'
    supervisor_pane_pid=$(tmux display-message -p -t "$S" '#{pane_pid}')
    ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
    ```

    ```sh
    echo "a later block, so the scan continues past the unguarded one"
    ```
    """
    assert "supervisor-agent-proof" in missing_requirements(charter=charter)


def test_the_control_a_fully_conformant_charter_passes():
    """The control for every rejection above. Without it, the negative fixtures
    prove only that the validator can say no — not that it can ever say yes."""
    charter = """
    # Supervisor Handoff - demo
    ## HALT-first preconditions
    1. Worker session exists.

       ```sh
       W='=demo:'
       tmux has-session -t "$W" || { echo "HALT"; echo "REMEDY: start it"; exit 1; }
       ```

    2. Worker is a live agent.

       ```sh
       pane_pid=$(tmux display-message -p -t "$W" '#{pane_pid}')
       [ -n "$pane_pid" ] || { echo "HALT: empty pane_pid"; echo "REMEDY: retarget"; exit 1; }
       ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
       ```

    3. Supervisor session is a live agent too.

       ```sh
       S='=demo-supervisor:'
       tmux has-session -t "$S" || { echo "HALT"; echo "REMEDY: bootstrap it"; exit 1; }
       supervisor_pane_pid=$(tmux display-message -p -t "$S" '#{pane_pid}')
       [ -n "$supervisor_pane_pid" ] \
         || { echo "HALT: empty pane_pid"; echo "REMEDY: retarget"; exit 1; }
       [ "$supervisor_pane_pid" != "$pane_pid" ] \
         || { echo "HALT: same pane"; echo "REMEDY: re-check both exact targets"; exit 1; }
       ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
       ```

    4. Worker cwd is contained.

       ```sh
       pane_cwd=/data/projects/demo
       [ -n "$pane_cwd" ] \
         || { echo "HALT: empty pane_current_path"; echo "REMEDY: retarget"; exit 1; }
       case "$(readlink -f -- "$pane_cwd")" in /data/projects/demo|/data/projects/demo/*) ;; esac
       ```
    ## How to inspect and drive
    ```sh
    tmux capture-pane -p -t "$W" # visible only
    [ -z "$pane" ] && { echo "WAKE: pane unreadable"; exit 0; } # before the diff
    if [ "$pane" = "$prev" ]; then stable=$((stable+1)); else stable=0; prev="$pane"; fi
    wait_channel=/tmp/worker-status.log
    : > "$wait_channel"
    echo "WAKE: watcher ceiling reached — worker still busy, RE-ARM NOW"
    ```
    Tell the worker to append to it at every milestone.
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
