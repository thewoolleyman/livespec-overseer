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

import importlib
import importlib.util
import re
import shlex
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

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

# A generated charter must record WHICH generator produced it, and must be able
# to CHECK that record itself (overseer-yho.2).
#
# WHY THIS EXISTS. Adopters emit charters from a PINNED plugin cache, so a
# generator fix is inert until that cache refreshes, and nothing about an emitted
# charter says which generation it came from. That is not a coverage gap, it is
# structural: `tests/prompts/test_stale_cache_generation_is_detectable.py`
# measures three real cached generations and finds that TODAY's contract floor
# reports the stale 0.14.0 one as fully conformant — a verdict identical to the
# current generation's — while everything that does catch it was written seven
# hours AFTER it shipped. A content gate recognises only the staleness it already
# has a detector for, so it is permanently one release behind, and the next stale
# generation will carry defects nobody has named yet.
#
# WHY A DIGEST AND NOT THE PLUGIN VERSION, which was the original suggestion.
# Measured across eleven cache refs on 2026-07-30: six releases (0.12.2 through
# 0.13.3) shipped BYTE-IDENTICAL generator prose, so a version stamp reports six
# generators where there is one; and a prose fix that lands without a release
# bump — the exact hole `check-prose-release-hygiene` exists to catch — reports
# an UNCHANGED version for CHANGED prose. The digest has neither failure. The ref
# directory name is no help either: it is sometimes a sha and sometimes a version
# (`0.12.2` and `0.12.3` are real ref directories), so it is not an identity key
# in either direction. Version and ref ride along as human-readable companions.
#
# WHY THE COMPARISON LIVES IN THE CHARTER RATHER THAN IN CI. The cache exists
# only on the adopter's host, at generation and boot time; CI has none and never
# will. Equality-in-CI would also be wrong on its own terms — a charter emitted
# three weeks ago legitimately names an older generator, so requiring
# recorded == current would redden every charter on every release. CI's rung is
# to gate that the prose MANDATES the record; the comparison is a HALT-first
# precondition the supervisor runs where the cache actually is.
_PROVENANCE_DIGEST = re.compile(r"generator_prose_md5\s*=\s*['\"]?([0-9a-f]{32})\b")
_PROVENANCE_DIGEST_COMMAND = re.compile(r"\b(?:md5sum|sha256sum|shasum)\b")
_PROVENANCE_COMPARISON = re.compile(r"\$\{?generator_prose_md5\}?")


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
            "handed_to",
            "receipt_ack",
            "peer_recorded",
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
_OBLIGATION_START = re.compile(r"^\s*-\s+id:\s*(?P<value>.*?)\s*$")
_OBLIGATION_FIELD = re.compile(r"^\s+(?P<key>[a-z_]+):\s*(?P<value>.*?)\s*$")
_PEER_HOLDER = re.compile(r"\bpeer\b", re.IGNORECASE)


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


def _obligation_records(*, charter: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_obligations = False
    for line in charter.splitlines():
        if "open_obligations:" in line:
            in_obligations = True
            continue
        if not in_obligations:
            continue
        start = _OBLIGATION_START.match(line)
        if start is not None:
            current = {"id": start.group("value").strip()}
            records.append(current)
            continue
        if current is None:
            continue
        field = _OBLIGATION_FIELD.match(line)
        if field is None:
            if line.strip().startswith("## "):
                in_obligations = False
            continue
        current[field.group("key")] = field.group("value").strip()
    return records


def invalid_handoff_confirmations(*, charter: str) -> list[str]:
    invalid: list[str] = []
    for record in _obligation_records(charter=charter):
        if _PEER_HOLDER.search(record.get("holder", "")) is None:
            continue
        if record.get("receipt_ack", "").lower() in {"", "none"}:
            invalid.append("handoff-receipt-ack-confirmation")
        if record.get("peer_recorded", "").lower() in {"", "none"}:
            invalid.append("handoff-peer-recorded-confirmation")
    return invalid


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


def _has_generator_provenance(*, charter: str) -> bool:
    """A recorded generator digest AND an executable self-check against it.

    THE PROPERTY, in three legs, rather than one spelling:

    1. a REAL 32-hex digest is bound to `generator_prose_md5` — a `<placeholder>`
       is not a record, and a version number is not one either;
    2. a digest COMMAND appears in a fenced block, so the check is runnable
       rather than a sentence about being runnable — `.4`'s bar;
    3. the recorded binding is DEREFERENCED, so the value is compared against the
       installed generator rather than merely stated.

    Leg 3 is the one that carries the requirement. A charter satisfying only legs
    1 and 2 announces its provenance and can never notice when that stops being
    true, which is a stamp rather than a check — the same distinction as a HALT
    precondition that reports a session NAME instead of proving a live agent.
    """
    blocks = "\n".join(_command_blocks(charter=charter))
    return (
        _PROVENANCE_DIGEST.search(blocks) is not None
        and _PROVENANCE_DIGEST_COMMAND.search(blocks) is not None
        and _PROVENANCE_COMPARISON.search(blocks) is not None
    )


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
    if not _has_generator_provenance(charter=charter):
        missing.append("generator-provenance-self-check")
    if not _has_conflicting_lane_procedure(charter=charter):
        missing.append("stall-mode-1-conflicting-lane")
    if not _has_ripe_valve_same_turn_rule(charter=charter):
        missing.append("picker-ripe-valves-same-turn")
    guard_at = charter.find('[ -z "$pane" ]')
    diff_at = charter.find('if [ "$pane" = "$prev" ]')
    if guard_at == -1 or diff_at == -1 or diff_at < guard_at:
        missing.append("watcher-empty-capture-guard")
    missing.extend(invalid_handoff_confirmations(charter=charter))
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

    ONE REQUIREMENT IS EXEMPT, AND ONLY ONE. This test works because every other
    requirement is a fixed string the emitted charter SHARES with the template,
    so the template satisfies the charter-level rule by carrying the same words.
    `generator-provenance-self-check` is categorically different: its value is
    RESOLVED PER GENERATION — the digest of the very file being read — so it
    cannot exist in a template, and it must not, because an example digest is
    something a generator can copy verbatim.

    The exemption is asserted as an EXACT list rather than a filter, so it is not
    a hole: if the prose ever stopped instructing any other requirement the list
    would grow and this would fail. What the prose must say about provenance is
    checked by `test_the_generator_prose_mandates_the_provenance_record` instead,
    with needles — the same shape as the two-layer and Corrections prose tests.
    """
    assert missing_requirements(charter=_GENERATOR_PROSE.read_text(encoding="utf-8")) == [
        "generator-provenance-self-check"
    ]


def test_the_generator_prose_mandates_the_provenance_record():
    """The prose-level half of the provenance rule, since the template is exempt.

    Needles rather than the validator, for the reason above: a template cannot
    carry a resolved digest. What it CAN carry, and must, is the instruction to
    emit one, the identity choice, and the comparison.
    """
    prose = _GENERATOR_PROSE.read_text(encoding="utf-8")
    # WHITESPACE-NORMALISED, not a raw substring: every phrase below spans a
    # markdown line break in the shipped prose, and markdown gets rewrapped. A
    # raw `in` check would fail for reflow rather than for meaning, which is a
    # gate that reddens on formatting and teaches people to loosen it.
    flattened = " ".join(prose.split()).lower()
    # The record itself, and the fact that it is emitted concretely.
    assert "generator_prose_md5" in prose
    assert "generator_ref" in prose
    assert "a placeholder here is not a record" in flattened
    # The identity choice, which supersedes overseer-d4t's version proposal.
    assert "do not use the version as the identity" in flattened
    # The comparison — a stamp that is never checked is the defect, not the fix.
    assert "md5sum" in prose
    assert "recording without comparing is not enough" in flattened


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


class _RealizationModule(Protocol):
    def missing_requirements(self, *, charter: str) -> list[str]: ...

    def banned_requirements(self, *, charter: str) -> list[str]: ...

    def non_parameterizable_requirements(self) -> frozenset[str]: ...


def _homelab_parameterized_charter() -> str:
    original_re_entry = """## Never end a turn without an armed re-entry
    The trigger is ANY open obligation. Arm a background pane watcher before ending any turn.
    For a non-pane wait, arm a condition watcher that tests terminal state first
    from the authoritative field. On unrecognized value, wake and never silently wait."""
    adopter_re_entry = """## Never end a turn while work remains unwatched
    Never end a turn while any open obligation remains. Start a background pane
    watcher before ending the turn. For a non-pane wait, start a condition watcher
    that tests terminal state first from the authoritative field. On unrecognized value,
    wake and never silently wait."""
    original_safety = "Never pass --no-verify. Never kill the acting overseer daemon."
    adopter_safety = "Never pass --no-verify. Never run kill-server on the maintainer's socket."
    return (
        _fully_conformant_charter()
        .replace(original_re_entry, adopter_re_entry)
        .replace(original_safety, adopter_safety)
        .replace(
            'tmux capture-pane -p -t "$W" # visible only',
            'tmux capture-pane -p -t "$W" # visible only\n'
            "    tmux send-keys -t \"$W\" -- 'drive the next safe action' Enter",
        )
    )


def _realization_module() -> _RealizationModule | None:
    name = "overseer._prompt_realizations"
    spec = importlib.util.find_spec(name)
    module: ModuleType | None = None if spec is None else importlib.import_module(name)
    return None if module is None else cast(_RealizationModule, module)


def _realization_missing_requirements(*, charter: str) -> list[str]:
    module = _realization_module()
    return (
        missing_requirements(charter=charter)
        if module is None
        else module.missing_requirements(charter=charter)
    )


def _realization_banned_requirements(*, charter: str) -> list[str]:
    module = _realization_module()
    return (
        banned_requirements(charter=charter)
        if module is None
        else module.banned_requirements(charter=charter)
    )


def _realization_non_parameterizable_requirements() -> frozenset[str]:
    module = _realization_module()
    return frozenset() if module is None else module.non_parameterizable_requirements()


def test_adopter_realization_clears_only_the_wording_failure():
    """homelab satisfies the behavior while failing the literal needle.

    Needle equality reports two missing required clauses plus one banned command.
    The realization gate clears only `stall-mode-2-armed-re-entry`; the real
    missing absolute rule and the banned one-shot command survive.
    """
    assert missing_required_needles_for_layers(layers=("Never pass --no-verify.",))
    charter = _homelab_parameterized_charter()
    assert "armed re-entry" not in charter.lower()
    assert missing_required_needles(charter=charter) == [
        "stall-mode-2-armed-re-entry",
        "acting-daemon-prohibition",
    ]
    assert _realization_banned_requirements(charter=charter) == ["one-shot-send-keys-enter"]
    assert _realization_missing_requirements(charter=charter) == [
        "acting-daemon-prohibition",
        "one-shot-send-keys-enter",
    ]


def test_redacting_adopter_realizations_makes_the_gate_red():
    charter = _homelab_parameterized_charter().replace(
        """## Never end a turn while work remains unwatched
    Never end a turn while any open obligation remains. Start a background pane
    watcher before ending the turn. For a non-pane wait, start a condition watcher
    that tests terminal state first from the authoritative field. On unrecognized value,
    wake and never silently wait.""",
        """## Status report
    I will check back later.""",
    )
    assert "stall-mode-2-armed-re-entry" in _realization_missing_requirements(charter=charter)


def test_non_parameterizable_rules_are_enumerated_and_cannot_be_overridden():
    charter = _fully_conformant_charter().replace(
        "Never pass --no-verify. Never kill the acting overseer daemon.",
        "Never pass --no-verify. Never kill the acting overseer daemon. "
        "An adopter may restart the acting overseer daemon after confirming it is idle.",
    )
    assert "acting-daemon-prohibition" not in missing_required_needles(charter=charter)
    assert "acting-daemon-override" in _realization_missing_requirements(charter=charter)
    assert _realization_non_parameterizable_requirements() == frozenset(
        ("acting-daemon-prohibition", "one-shot-send-keys-enter")
    )


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


def test_sender_held_handoff_with_missing_confirmations_remains_open():
    charter = """
    # Supervisor Handoff - demo
    ## Obligation record
    Maintain tmp/overseer/<topic>/.supervisor-state:
      open_obligations:
        - id: cross-track-receipt
          holder: supervisor
          handed_to: demo-peer
          receipt_ack: none
          peer_recorded: none
          waiting_on: demo-peer to confirm the handoff
          wake_mechanism: condition watcher polls the peer reply
          if_nothing_happens: escalate to maintainer
          timeout: 2026-07-30T13:00:00Z
    """
    assert invalid_handoff_confirmations(charter=charter) == []


def test_a_peer_held_handoff_without_receipt_ack_confirmation_is_rejected():
    charter = """
    # Supervisor Handoff - demo
    ## Obligation record
    Maintain tmp/overseer/<topic>/.supervisor-state:
      open_obligations:
        - id: cross-track-receipt
          holder: peer
          handed_to: demo-peer
          receipt_ack: none
          peer_recorded: 2026-07-30T12:05:00Z
          waiting_on: demo-peer acknowledgement
          wake_mechanism: condition watcher polls the peer reply
          if_nothing_happens: escalate to maintainer
          timeout: 2026-07-30T13:00:00Z
    """
    missing = missing_requirements(charter=charter)
    assert "handoff-receipt-ack-confirmation" in missing


def test_a_peer_held_handoff_without_peer_recorded_confirmation_is_rejected():
    charter = """
    # Supervisor Handoff - demo
    ## Obligation record
    Maintain tmp/overseer/<topic>/.supervisor-state:
      open_obligations:
        - id: cross-track-receipt
          holder: peer
          handed_to: demo-peer
          receipt_ack: 2026-07-30T12:00:00Z
          peer_recorded: none
          waiting_on: demo-peer to record the obligation locally
          wake_mechanism: condition watcher polls the peer reply
          if_nothing_happens: escalate to maintainer
          timeout: 2026-07-30T13:00:00Z
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    The trigger is ANY open obligation. Arm a condition watcher; test terminal state first
    from the authoritative field. On unrecognized value, wake and never silently wait.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify. Never kill the acting overseer daemon.
    """
    missing = missing_requirements(charter=charter)
    assert "handoff-peer-recorded-confirmation" in missing


def test_a_peer_held_handoff_with_both_confirmations_is_accepted():
    charter = """
    # Supervisor Handoff - demo
    ## Obligation record
    Maintain tmp/overseer/<topic>/.supervisor-state:
      open_obligations:
        - id: cross-track-receipt
          holder: peer
          handed_to: demo-peer
          receipt_ack: 2026-07-30T12:00:00Z
          peer_recorded: 2026-07-30T12:05:00Z
          waiting_on: demo-peer to close the transferred obligation
          wake_mechanism: condition watcher polls the peer reply
          if_nothing_happens: escalate to maintainer
          timeout: 2026-07-30T13:00:00Z
    ## No idle, no silent block
    A conflicting lane is not a blocked state; stand down on that action only.
    ## Never end a turn without an armed re-entry
    The trigger is ANY open obligation. Arm a condition watcher; test terminal state first
    from the authoritative field. On unrecognized value, wake and never silently wait.
    ## AskUserQuestion
    Recommended first. Never pass --no-verify. Never kill the acting overseer daemon.
    """
    assert invalid_handoff_confirmations(charter=charter) == []


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
    ## Generator provenance
    ```sh
    generator_plugin='livespec-overseer'
    generator_ref='013d35d48cde'
    generator_version='0.15.0'
    generator_prose_md5='9ca18d56772dcf8fcdc2cf78ed8108a8'
    cache_root="$HOME/.claude/plugins/cache/$generator_plugin/$generator_plugin"
    generator_prose="$cache_root/$generator_ref/prose/supervise-plan.md"
    [ -f "$generator_prose" ] \
      || { echo "HALT: generator absent"; echo "REMEDY: regenerate or re-stamp"; exit 1; }
    installed=$(md5sum "$generator_prose")
    digest_rc=$?
    [ "$digest_rc" -eq 0 ] \
      || { echo "HALT: cannot digest"; echo "REMEDY: fix read access"; exit 1; }
    installed_md5=${installed%% *}
    [ "$installed_md5" = "$generator_prose_md5" ] \
      || { echo "HALT: stale generator"; echo "REMEDY: regenerate before driving"; exit 1; }
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
          handed_to: none
          receipt_ack: none
          peer_recorded: none
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


_PROVENANCE_CHECK = """
    ```sh
    generator_prose_md5='9ca18d56772dcf8fcdc2cf78ed8108a8'
    generator_prose="$HOME/.claude/plugins/cache/p/p/013d35d48cde/prose/supervise-plan.md"
    installed=$(md5sum "$generator_prose")
    installed_md5=${installed%% *}
    [ "$installed_md5" = "$generator_prose_md5" ] \
      || { echo "HALT: stale"; echo "REMEDY: regenerate"; exit 1; }
    ```
"""


def test_a_charter_recording_its_generator_and_checking_it_is_accepted():
    """The acceptance leg: a real digest, a digest command, and a comparison."""
    assert _has_generator_provenance(charter=_PROVENANCE_CHECK)


def test_a_charter_that_states_its_generator_but_cannot_check_it_is_rejected():
    """A STAMP IS NOT A CHECK, and this is the distinction that carries the rule.

    The digest is recorded and never compared, so the charter announces its
    provenance and can never notice when that stops being true. It is the same
    shape as a precondition that reports a session NAME instead of proving a live
    agent — observed 2026-07-28, when a supervisor session created as a bare
    `zsh` returned PASS.
    """
    charter = """
    ```sh
    generator_prose_md5='9ca18d56772dcf8fcdc2cf78ed8108a8'
    generator_ref='013d35d48cde'
    ```
    """
    assert not _has_generator_provenance(charter=charter)
    assert "generator-provenance-self-check" in missing_requirements(charter=charter)


def test_a_placeholder_digest_is_not_a_provenance_record():
    """An unsubstituted placeholder must not satisfy the rule.

    This charter carries the whole comparison machinery and would EXECUTE — and
    always mismatch. Accepting it would let the generator emit the shape of a
    provenance record without ever resolving one, which is precisely the
    unsubstitutable-placeholder defect the cold-open dry-runs caught.
    """
    charter = _PROVENANCE_CHECK.replace("9ca18d56772dcf8fcdc2cf78ed8108a8", "<generator-md5>")
    assert not _has_generator_provenance(charter=charter)


def test_a_version_stamp_is_not_a_provenance_record():
    """THE FIX-SHAPE CORRECTION, pinned so it cannot quietly regress.

    `overseer-d4t` originally proposed recording the plugin VERSION. Measured
    across eleven cache refs: six releases (0.12.2 through 0.13.3) shipped
    byte-identical prose, so a version reports six generators where there is one;
    and a prose fix landing without a release bump reports an unchanged version
    for changed prose. A version alone must therefore not satisfy this rule.
    """
    charter = """
    ```sh
    generator_version='0.15.0'
    generator_ref='013d35d48cde'
    installed=$(md5sum "$generator_prose")
    [ "$installed" = "$generator_version" ] || { echo "HALT"; echo "REMEDY: regenerate"; exit 1; }
    ```
    """
    assert not _has_generator_provenance(charter=charter)


def test_provenance_stated_only_in_prose_does_not_satisfy_the_rule():
    """Prose about provenance is not a provenance check — `.4`'s bar, again.

    The three legs are all read from FENCED COMMANDS, so a charter that merely
    describes recording its generator is rejected exactly like one that describes
    its preconditions instead of emitting them.
    """
    charter = """
    This charter was generated from plugin cache ref 013d35d48cde, whose prose
    digest is 9ca18d56772dcf8fcdc2cf78ed8108a8, and a reader should md5sum the
    installed generator and compare it against $generator_prose_md5 before
    driving anything.
    """
    assert not _has_generator_provenance(charter=charter)


def test_the_control_a_fully_conformant_charter_passes():
    """The control for every rejection above. Without it, the negative fixtures
    prove only that the validator can say no — not that it can ever say yes."""
    assert missing_requirements(charter=_fully_conformant_charter()) == []
