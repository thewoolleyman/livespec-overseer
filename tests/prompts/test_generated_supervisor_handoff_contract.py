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
_SHARED_LAYER = _REPO_ROOT / ".ai" / "supervisor-protocol.md"

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
    # STALL MODE 2 — never end a turn with the worker mid-flight and nothing
    # armed. Checked separately from mode 1; see the module docstring.
    ("stall-mode-2-armed-re-entry", ("armed re-entry",)),
    # Mode 2 is only actionable if the charter names a MECHANISM. "I'll check
    # back" is an intention, and intentions are what the rule exists to reject.
    ("stall-mode-2-watcher-mechanism", ("watcher",)),
    # Maintainer-facing actions are AskUserQuestion calls, not prose.
    ("picker-rule", ("askuserquestion",)),
    ("picker-recommended-first", ("recommended option first",)),
    ("picker-option-costs", ("every option", "cost")),
    ("picker-full-repository-names", ("full", "repository names")),
    ("picker-final-line-fence", ("---", "final line")),
    ("picker-batch-ripe-valves", ("batch", "ripe", "single call")),
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
    # S4: generated charters must carry the supervisor's durable obligation
    # record, not just a memory/intention to check back.
    (
        "supervisor-state-location",
        ("tmp/overseer/<topic>/.supervisor-state",),
    ),
    (
        "supervisor-state-open-obligation-schema",
        (
            "open_obligations",
            "holder",
            "waiting_on",
            "wake_mechanism",
            "if_nothing_happens",
            "timeout",
        ),
    ),
    # Re-entry is triggered by ANY open obligation, including non-pane waits.
    ("re-entry-any-open-obligation", ("any open obligation",)),
    (
        "non-pane-condition-watcher",
        ("condition watcher", "terminal state first", "authoritative field"),
    ),
    (
        "condition-watcher-total-fallback",
        ("unrecognized value", "wake", "never silently"),
    ),
    ("ledger-remeasurement-command", ("bd show", "MEASURED_AT")),
    ("pipeline-status-preserved", ("tmux_rc=$?", '"$tmux_rc" -eq 0')),
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


def _has_conflicting_lane_procedure(*, charter: str) -> bool:
    """Accept the procedure, not one brittle spelling of its first verb."""
    lowered = charter.lower()
    has_conflict = "conflicting lane" in lowered
    has_scope = "not a thread-wide blocked state" in lowered or "not a blocked state" in lowered
    has_local_only = "that action only" in lowered
    has_remaining = "enumerate" in lowered and ("remaining" in lowered or "the rest" in lowered)
    has_next_action = "drive" in lowered and "next" in lowered and "safe action" in lowered
    has_hard_stop = "no legitimate non-conflicting action" in lowered
    return all(
        (
            has_conflict,
            has_scope,
            has_local_only,
            has_remaining,
            has_next_action,
            has_hard_stop,
        )
    )


def _has_ripe_valve_same_turn_rule(*, charter: str) -> bool:
    """Batching may group ripe valves, but cannot defer raising them."""
    lowered = charter.lower()
    has_ripe_valve = "ripe valve" in lowered or "ripe valves" in lowered
    has_same_turn = "same turn" in lowered
    has_grouping_not_deferral = (
        "grouping within a turn" in lowered
        or "never deferral across turns" in lowered
        or "not deferral across turns" in lowered
    )
    has_armed_wake_for_deferral = (
        "deferred to a future turn" in lowered or "valve deferred" in lowered
    ) and "armed wake" in lowered
    return (
        has_ripe_valve
        and has_same_turn
        and has_grouping_not_deferral
        and has_armed_wake_for_deferral
    )


def combined_charter(*, layers: tuple[str, ...]) -> str:
    """Return the validator input for a layered generated handoff."""
    return "\n\n".join(layers)


def missing_requirements_for_layers(*, layers: tuple[str, ...]) -> list[str]:
    """Return missing requirements across the union of emitted layers."""
    return missing_requirements(charter=combined_charter(layers=layers))


def missing_required_needles(*, charter: str) -> list[str]:
    lowered = charter.lower()
    return [
        name
        for name, needles in _REQUIRED
        if not all(needle.lower() in lowered for needle in needles)
    ]


def missing_required_needles_for_layers(*, layers: tuple[str, ...]) -> list[str]:
    return missing_required_needles(charter=combined_charter(layers=layers))


def _corrections_section(*, text: str) -> str:
    start = text.index("## Corrections")
    return text[start:]


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
    if not _has_conflicting_lane_procedure(charter=charter):
        missing.append("stall-mode-1-conflicting-lane")
    if not _has_ripe_valve_same_turn_rule(charter=charter):
        missing.append("picker-ripe-valves-same-turn")
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
    exemplar_text = exemplar.read_text(encoding="utf-8")
    assert (
        missing_requirements_for_layers(
            layers=(_SHARED_LAYER.read_text(encoding="utf-8"), exemplar_text)
        )
        == []
    )


def test_the_generator_prose_instructs_every_contract_requirement():
    """The SHIPPED generator must tell the model to emit each requirement.

    This is the test that fails before the generator is fixed. It is deliberately
    asserted over the generator prose as well as the exemplar: a charter can only
    carry the floor if the thing producing it says to.

    Sabotage that reddens this: remove the armed-re-entry section from
    `.claude-plugin/prose/supervise-plan.md`.
    """
    assert missing_requirements(charter=_GENERATOR_PROSE.read_text(encoding="utf-8")) == []


def test_the_generator_prose_requires_two_layer_output_and_no_live_status():
    prose = _GENERATOR_PROSE.read_text(encoding="utf-8")
    lowered = prose.lower()
    assert ".ai/supervisor-protocol.md" in prose
    assert "plan/<topic>/supervisor-handoff.md" in prose
    assert "startup bindings only" in lowered
    assert "no live status" in lowered
    assert "no next actions" in lowered
    assert "no date-gated behavior" in lowered
    assert "ledger anchor" in lowered


def test_the_generator_prose_requires_both_corrections_layers_preserved_byte_for_byte():
    prose = _GENERATOR_PROSE.read_text(encoding="utf-8")
    lowered = prose.lower()
    assert "role-level corrections" in lowered
    assert "thread-specific corrections" in lowered
    assert "byte-for-byte" in lowered
    assert "preserve spelling, punctuation, code formatting, blank lines, and ordering" in lowered


def test_layered_current_charter_is_the_iteration_stability_positive_control():
    binder = (
        _REPO_ROOT / "plan" / "supervisor-prompt-quality" / "supervisor-handoff.md"
    ).read_text(encoding="utf-8")
    shared = _SHARED_LAYER.read_text(encoding="utf-8")
    rows = (
        ("current binder alone", len(missing_requirements(charter=binder))),
        (
            "current shared plus binder",
            len(missing_requirements_for_layers(layers=(shared, binder))),
        ),
    )
    assert rows[0][1] > 0
    assert rows[1] == ("current shared plus binder", 0)


def test_union_validator_retarget_demonstrates_homelab_binder_shape():
    homelab_binder = """
    # Supervisor Handoff - homelab-demo
    ## Bindings
    WORKER_TARGET='=homelab-demo:'
    SUPERVISOR_TARGET='=homelab-demo-supervisor:'
    ## HALT-first preconditions
    ```sh
    pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
    supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
    pane_cwd=/data/projects/homelab
    case "$(readlink -f -- "$pane_cwd")" in /data/projects/homelab|/data/projects/homelab/*) ;; esac
    wait_channel=/tmp/homelab-status.log
    tmux capture-pane -p -t "$WORKER_TARGET" -S -40 # visible only
    ```
    ## Corrections
    Thread-specific corrections.
    """
    homelab_shared = """
    You are the supervisor, not the implementer. Hand work to verify.
    A conflicting lane owned by another track is not a blocked state; stand down.
    Never end a turn without an armed re-entry; arm a background watcher.
    AskUserQuestion calls carry a recommendation. Never pass --no-verify.
    Never kill the acting overseer daemon. RE-ARM NOW on expiry.
    """
    rows = (
        ("homelab binder alone", len(missing_required_needles(charter=homelab_binder))),
        (
            "homelab shared plus binder",
            len(missing_required_needles_for_layers(layers=(homelab_shared, homelab_binder))),
        ),
    )
    assert rows == (("homelab binder alone", 20), ("homelab shared plus binder", 15))


def test_both_corrections_sections_survive_regeneration_byte_for_byte():
    shared = _SHARED_LAYER.read_text(encoding="utf-8")
    binder = (
        _REPO_ROOT / "plan" / "supervisor-prompt-quality" / "supervisor-handoff.md"
    ).read_text(encoding="utf-8")
    regenerated_shared = shared.replace("# Supervisor Protocol", "# Supervisor Protocol")
    regenerated_binder = binder.replace("# Supervisor Handoff", "# Supervisor Handoff")
    assert _corrections_section(text=regenerated_shared) == _corrections_section(text=shared)
    assert _corrections_section(text=regenerated_binder) == _corrections_section(text=binder)
    reformatted_shared = shared.replace("`pane_pid`", "pane_pid", 1)
    assert _corrections_section(text=reformatted_shared) != _corrections_section(text=shared)


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
    on that action only, enumerate the rest, drive the next safe action, and ask
    only if no legitimate non-conflicting action exists.
    ## AskUserQuestion presentation rules
    Every maintainer-facing action is an AskUserQuestion call. Put the
    recommended option first. Every option states its own cost. Use full
    repository names. Put --- as the final line before the picker. Batch ripe
    valves into a single call. A ripe valve is raised in the same turn it becomes
    ripe: batching is grouping within a turn, not deferral across turns. A valve
    deferred to a future turn requires an armed wake.
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


def test_re_entry_restricted_to_pane_conditions_rejects_non_pane_obligations():
    """S4 RED shape: a CI/review/peer wait is open, but no pane is mid-flight.

    A pane-only trigger lets this charter end the turn after writing the record,
    so the non-pane obligation is never re-entered.
    """
    charter = """
    # Supervisor Handoff - demo
    ## Obligation record
    Write tmp/overseer/<topic>/.supervisor-state:
      open_obligations:
        - holder: supervisor
          waiting_on: CI check on PR 9
          wake_mechanism: condition watcher polls the check suite
          if_nothing_happens: escalate
          timeout: 2026-07-30T12:00:00Z
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    Before ending a turn while the worker is mid-flight, arm a pane watcher.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify. Never kill the acting overseer daemon.
    """
    missing = missing_requirements(charter=charter)
    assert "re-entry-any-open-obligation" in missing
    assert "non-pane-condition-watcher" in missing


def test_a_record_without_the_durable_obligation_schema_is_rejected():
    charter = """
    # Supervisor Handoff - demo
    ## Obligation record
    Keep notes somewhere under tmp; remember who owns each wait.
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    The trigger is ANY open obligation. Arm a condition watcher; test terminal state first
    from the authoritative field. On unrecognized value, wake and never silently wait.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify. Never kill the acting overseer daemon.
    """
    missing = missing_requirements(charter=charter)
    assert "supervisor-state-location" in missing
    assert "supervisor-state-open-obligation-schema" in missing


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


def _assert_only_injected_defect(*, defect: str, charter: str) -> None:
    assert missing_requirements(charter=charter) == [defect]


def test_conflicting_lane_rule_accepts_a_reworded_local_pause():
    charter = _fully_conformant_charter().replace("Stand down", "Pause", 1)
    assert "stand down" not in charter.lower()
    assert "stall-mode-1-conflicting-lane" not in missing_requirements(charter=charter)


def test_conflicting_lane_rule_requires_the_next_safe_action_procedure():
    charter = _fully_conformant_charter().replace(
        "enumerate the remaining non-conflicting work; drive the\n"
        "    next concrete safe action; only if no legitimate non-conflicting action\n"
        "    exists, ask exactly one maintainer-facing blocking question.",
        "record the conflict and wait for that owner.",
    )
    _assert_only_injected_defect(defect="stall-mode-1-conflicting-lane", charter=charter)


def test_picker_recommended_first_has_its_own_red_fixture():
    charter = _fully_conformant_charter().replace(
        "Put the\n    recommended option first.",
        "Choose an option order based on narrative flow.",
    )
    _assert_only_injected_defect(defect="picker-recommended-first", charter=charter)


def test_picker_option_costs_has_its_own_red_fixture():
    charter = _fully_conformant_charter().replace(
        "Every option states its own cost.",
        "Explain why the recommendation is useful.",
    )
    _assert_only_injected_defect(defect="picker-option-costs", charter=charter)


def test_picker_full_repository_names_has_its_own_red_fixture():
    charter = _fully_conformant_charter().replace(
        "Use full\n    repository names.",
        "Use short repo aliases.",
    )
    _assert_only_injected_defect(defect="picker-full-repository-names", charter=charter)


def test_picker_final_line_fence_has_its_own_red_fixture():
    charter = _fully_conformant_charter().replace(
        "Put --- as the final line before the picker.",
        "Put a short separator before the picker.",
    )
    _assert_only_injected_defect(defect="picker-final-line-fence", charter=charter)


def test_picker_batching_has_its_own_red_fixture():
    charter = _fully_conformant_charter().replace(
        "Batch ripe\n    valves into a single call.",
        "Raise ripe valves one at a time.",
    )
    _assert_only_injected_defect(defect="picker-batch-ripe-valves", charter=charter)


def test_ripe_valves_must_be_sent_same_turn_not_deferred_for_batching():
    charter = _fully_conformant_charter().replace(
        "A ripe valve is raised in the same turn it becomes\n"
        "    ripe: batching is grouping within a turn, not deferral across turns. A valve\n"
        "    deferred to a future turn requires an armed wake.",
        "A ripe valve may be held for a later turn so batching can collect more items.",
    )
    _assert_only_injected_defect(defect="picker-ripe-valves-same-turn", charter=charter)


def _fully_conformant_charter() -> str:
    return """
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
    ## Verification Discipline
    ```sh
    ledger_anchor='demo-item'
    bd show "$ledger_anchor" --json \
      || { echo "HALT: cannot re-measure ledger item '$ledger_anchor'"; \
           echo "REMEDY: fix ledger access before using any filed status claim"; \
           exit 1; }
    date -u '+MEASURED_AT: %Y-%m-%dT%H:%M:%SZ'
    pane_pid=$(tmux display-message -p -t "$W" '#{pane_pid}')
    tmux_rc=$?
    [ "$tmux_rc" -eq 0 ] \
      || { echo "HALT: tmux pane lookup failed for 'demo'"; \
           echo "REMEDY: re-check the exact target before filtering its output"; \
           exit 1; }
    printf '%s\n' "$pane_pid" | head -1
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
    on that action only; enumerate the remaining non-conflicting work; drive the
    next concrete safe action; only if no legitimate non-conflicting action
    exists, ask exactly one maintainer-facing blocking question.
    ## Obligation record
    Maintain tmp/overseer/<topic>/.supervisor-state:
      open_obligations:
        - holder: supervisor
          waiting_on: CI check on PR 9
          wake_mechanism: condition watcher polls the check suite
          if_nothing_happens: escalate to maintainer
          timeout: 2026-07-30T12:00:00Z
    ## Never end a turn without an armed re-entry
    The trigger is ANY open obligation. Arm a background pane watcher before ending any turn.
    For a non-pane wait, arm a condition watcher that tests terminal state first
    from the authoritative field. On unrecognized value, wake and never silently wait.
    ## AskUserQuestion presentation rules
    Every maintainer-facing action is an AskUserQuestion call. Put the
    recommended option first. Every option states its own cost. Use full
    repository names. Put --- as the final line before the picker. Batch ripe
    valves into a single call. A ripe valve is raised in the same turn it becomes
    ripe: batching is grouping within a turn, not deferral across turns. A valve
    deferred to a future turn requires an armed wake.
    ## Standing safety clauses
    Never pass --no-verify. Never kill the acting overseer daemon.
    """


def test_the_control_a_fully_conformant_charter_passes():
    """The control for every rejection above. Without it, the negative fixtures
    prove only that the validator can say no — not that it can ever say yes."""
    assert missing_requirements(charter=_fully_conformant_charter()) == []
