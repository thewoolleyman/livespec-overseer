"""Rung 3, first gate: a supervisor that SIGNPOSTS a decision must open a picker.

The supervision ladder is *static prose -> generated output -> observed conduct*.
Rungs 1 and 2 have executable gates for eleven defect classes. Rung 3 -- whether a
supervisor READ a clause and did otherwise -- had nothing, and this module is the
first gate for it (`overseer-oydugu`).

THE RULE BEING POLICED, and it is the most heavily text-enforced rule in the whole
contract: `.ai/supervisor-protocol.md` says *"Every maintainer-facing action is an
AskUserQuestion call carrying a recommendation."* SIX of the charter contract's
thirty-one requirements police it -- `picker-rule`, `picker-recommended-first`,
`picker-option-costs`, `picker-full-repository-names`, `picker-final-line-fence`,
`picker-batch-ripe-valves` -- the gate asserting all six is GREEN, and on
2026-08-02 a supervisor raised four ripe valves as prose anyway, after applying
the rule correctly three times earlier in the same session. That is charter
correction C20. **A rule's text-enforcement strength says nothing about whether it
binds conduct**, and this module is the first thing in the repo that observes the
conduct rather than the text.

WHAT IS OBSERVED. Not prose -- the TOOL-CALL STREAM. Whether a turn contained an
`AskUserQuestion` call is a fact about the transcript, which is what makes this
corner of rung 3 tractable where most conduct claims are not.

THE UNIT IS THE **STOP MESSAGE**, AND GETTING THAT WRONG INVERTS THE GATE.
The charter names the turn (*"A ripe valve is raised in the same turn it becomes
ripe"*), but in an autonomous supervisor loop a turn bounded by maintainer inputs
runs for HOURS: `d0bdaa90` is seven turns across 5.5 hours, and the turn holding
the violation ALSO holds two correct `AskUserQuestion` calls raised 45 minutes
earlier. So "did this turn contain a picker?" answers *yes* for the violation --
a turn-scoped gate does not merely blur, it PASSES the one violation we have.
`test_turn_granularity_cannot_discriminate` pins that, so nobody re-derives the
obvious rule and ships it.

The unit that works is the stop message: the last assistant message of a turn, the
one that hands control back. Exactly one per turn, and it is where a supervisor
either opens a valve or fails to. A picker is never a stop message -- the call is
answered and the turn continues -- so the rule needs no exception for it.

THE DISCRIMINATOR, and why it survives the objection that killed four gates on the
originating thread. `overseer-oydugu` warns that *"intent is not reliably in the
text"*: a detector keying on "prose + question mark + no picker" flags the
legitimate ANSWERING turn, and the false positive was always prose that legitimately
RESEMBLES the defect. This gate never infers intent. It fires only when the
supervisor SIGNPOSTS a section as soliciting direction -- writes a heading meaning
*these are yours to decide* -- and then stops without a picker. That is the actor's
own declaration of intent, authored by the actor being gated, so it is in the text
by construction rather than by inference.

WHAT THIS DELIBERATELY DOES NOT FIRE ON, measured rather than assumed. Six of the
ten clean stop messages mention maintainer-owned decisions in passing -- *"Still
yours: `overseer-yho.3`"*, *"that's your call, not mine"*, *"someone should decide
whether that work is wanted"*. All six are CORRECT: the charter escalates only
genuinely BLOCKING decisions, and one of them says so outright (*"Already surfaced
at close -- restating, not re-asking"*). A lexical sweep for second-person decision
language flags 7 of 11 and is useless. The signal is not that a decision is
mentioned; it is that a section is SIGNPOSTED as soliciting direction.

**RECALL IS UNMEASURED AND CANNOT BE MEASURED FROM THIS CORPUS.** Exactly one true
positive exists. Precision is 1/1 against ten true negatives; a violation phrased
without a signposting heading is invisible here by construction. That ceiling is
stated rather than hidden, and it is the correct first cut: a precision-first gate
that never cries wolf can be widened as new positives are recorded, whereas a
recall-first gate flagging the six benign mentions above would be discounted within
a day -- the exact fate this epic's own record predicts for advisory rules.

The full measurement is
`plan/archive/daemon-liveness-truth/research/rung-3-corpus-measurement.md` (the thread
archived 2026-08-03; nothing resolves this path mechanically, so it rots silently).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

__all__: list[str] = []

_FIXTURES = Path(__file__).resolve().parent / "fixtures"

# The 2026-08-02 supervisor session that produced charter correction C20, and its
# successor. Both are REAL transcripts, slimmed by emptying tool-call INPUTS and
# tool_result CONTENT -- bulk with no bearing on any verdict here. Every record's
# role, message id, text and tool NAMES survive, which is the whole structure this
# module reads. Nothing was selected for or against: the slimming is mechanical.
#
# The `tool_result` RECORDS are kept, and an earlier cut of these fixtures dropped
# them entirely. That was a fidelity gap worth naming: a `tool_result` wears the
# `user` role, so `is_maintainer_input` must reject it or every tool call would
# slice a turn -- and a fixture without any could not exercise the guard that a
# LIVE transcript depends on most. The eleven-stop-message count is identical
# either way, which is the evidence that the guard works rather than a coincidence.
_C20_SESSION = _FIXTURES / "supervisor-session-2026-08-02-c20.jsonl"
_SUCCESSOR_SESSION = _FIXTURES / "supervisor-session-2026-08-02-successor.jsonl"

# The violation's own words, quoted so the fixture cannot silently stop containing
# the thing every assertion below is about.
_FOUR_VALVES_HEADING = "## What needs your direction"
_ANSWERING_TURN_MARK = "Not a new class — it's the one this track has always named as uncovered"

# A signpost is a HEADING or a bolded lead-in whose text declares that what follows
# is the maintainer's to decide. Anchored to that position deliberately: the same
# words inside a sentence are the benign restating case measured above, and matching
# them flags 7 of 11 stop messages instead of 1.
#
# Curated rather than generative. Each alternative below is a phrasing a supervisor
# would use to hand a decision over; the list is the gate's reach, and widening it is
# a decision to be made in writing when a new positive is recorded -- not a regex to
# be loosened until something passes.
_SIGNPOST_WORDS = (
    r"needs? your (?:direction|call|ruling|decision|input|sign-?off)",
    r"what needs you\b",
    r"for your (?:direction|call|ruling|decision|sign-?off)",
    r"your (?:call|cut|ruling|decision)s?\b",
    r"decisions? for you\b",
    r"awaiting your\b",
    r"(?:open|ripe) valves?\b",
)
#
# TWO POSITIONS, and the second one's bound is load-bearing. A heading IS its own
# line, so the words may sit anywhere in it. A bolded lead-in is not: the very
# first cut allowed the words anywhere on the line after `**`, and it matched
# `**Phase 2 is one slice from done.** … Your cut; I did not self-assign it.` --
# a bolded STATUS sentence whose paragraph happens to mention a decision further
# along. That is the benign inline case this gate must tolerate, so the words must
# fall INSIDE the bolded span, which is the part the supervisor wrote as a label.
_SIGNPOST = re.compile(
    r"^\s{0,3}(?:"
    r"#{1,6}\s+[^\n]*?(?:" + "|".join(_SIGNPOST_WORDS) + r")"
    r"|"
    r"\*\*[^*\n]*?(?:" + "|".join(_SIGNPOST_WORDS) + r")[^*\n]*?\*\*"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

_WAIT_PREMISE_KINDS = ("fabro-run", "ci-run", "work-item-close", "pr")
_WAIT_OPTION = re.compile(
    r"^\s*(?:[-*]|\d+[.)])\s+.*\bwait(?:ing)?\b.*\b("
    r"fabro[- ]run|pr|ci[- ]run|work[- ]item[- ]close"
    r")\b[^\n]*",
    re.IGNORECASE | re.MULTILINE,
)
_TYPED_WAIT_PREMISE = re.compile(
    r"\bwait-premise\s*:\s*"
    r"(?=[^\n]*(?:kind|target))"
    r"(?=[^\n]*\bkind\s*=\s*(?:" + "|".join(_WAIT_PREMISE_KINDS) + r")\b)"
    r"(?=[^\n]*\btarget\s*=\s*\S+)",
    re.IGNORECASE,
)


# Marks a maintainer turn boundary in the message-id order. Not a message id, and
# no real one can collide with it.
_TURN_BOUNDARY = ""


@dataclass(frozen=True)
class StopMessage:
    """The last assistant message of a turn -- the one that hands control back."""

    index: int
    timestamp: str
    text: str
    tools: tuple[str, ...]


@dataclass
class _Accumulator:
    """One assistant message under construction, folded across its records."""

    index: int
    timestamp: str
    texts: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


def _content_blocks(*, record: dict[str, object]) -> tuple[list[str], list[str]]:
    message = record.get("message")
    if not isinstance(message, dict):
        return [], []
    content = message.get("content")
    texts: list[str] = []
    tools: list[str] = []
    if isinstance(content, str):
        texts.append(content)
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text":
                value = block.get("text")
                texts.append(value if isinstance(value, str) else "")
            elif kind == "tool_use":
                name = block.get("name")
                tools.append(name if isinstance(name, str) else "")
            elif kind == "tool_result":
                tools.append("<tool_result>")
    return texts, tools


def _role(*, record: dict[str, object]) -> str:
    message = record.get("message")
    if isinstance(message, dict):
        role = message.get("role")
        if isinstance(role, str):
            return role
    kind = record.get("type")
    return kind if isinstance(kind, str) else ""


def _message_id(*, record: dict[str, object], fallback: int) -> str:
    message = record.get("message")
    if isinstance(message, dict):
        identifier = message.get("id")
        if isinstance(identifier, str) and identifier:
            return identifier
    return f"line{fallback}"


def is_maintainer_input(*, record: dict[str, object]) -> bool:
    """Is this record a real maintainer turn boundary?

    A `tool_result` record wears the `user` role but is the harness replying to the
    assistant, and so does a `<task-notification>`. Treating either as a boundary
    would slice a turn wherever a tool ran, which is everywhere.
    """
    if _role(record=record) != "user":
        return False
    texts, tools = _content_blocks(record=record)
    if "<tool_result>" in tools:
        return False
    joined = "\n".join(texts).strip()
    if not joined or joined.startswith("<task-notification>"):
        return False
    return bool(
        re.sub(r"<system-reminder>.*?</system-reminder>", "", joined, flags=re.DOTALL).strip()
    )


def read_records(*, path: Path) -> tuple[dict[str, object], ...]:
    """Parse a transcript, skipping blank and malformed lines."""
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            records.append(parsed)
    return tuple(records)


def _group_by_message(
    *, records: tuple[dict[str, object], ...]
) -> tuple[dict[str, _Accumulator], list[str]]:
    """Fold records into one entry per assistant message, in arrival order.

    One assistant message arrives as SEVERAL records when it carries both text and
    a tool call. Treating those as separate messages is exactly what makes the
    answering turn look picker-less, which is the wrong premise this gate exists to
    correct -- so the fold by `message.id` is load-bearing, not tidying.

    `order` interleaves maintainer boundaries as the empty string, so the caller can
    find each turn's last message without a second pass over the records.
    """
    grouped: dict[str, _Accumulator] = {}
    order: list[str] = []
    for index, record in enumerate(records):
        if is_maintainer_input(record=record):
            order.append(_TURN_BOUNDARY)
            continue
        if _role(record=record) != "assistant":
            continue
        identifier = _message_id(record=record, fallback=index)
        if identifier not in grouped:
            timestamp = record.get("timestamp")
            grouped[identifier] = _Accumulator(
                index=index,
                timestamp=timestamp if isinstance(timestamp, str) else "",
            )
            order.append(identifier)
        texts, tools = _content_blocks(record=record)
        grouped[identifier].texts.extend(text for text in texts if text.strip())
        grouped[identifier].tools.extend(tool for tool in tools if tool != "<tool_result>")
    return grouped, order


def _last_message_per_turn(*, order: list[str]) -> list[str]:
    """The message id that ended each turn."""
    stops: list[str] = []
    pending: str | None = None
    for identifier in order:
        if identifier == _TURN_BOUNDARY:
            if pending is not None:
                stops.append(pending)
                pending = None
            continue
        pending = identifier
    if pending is not None:
        stops.append(pending)
    return stops


def stop_messages(*, records: tuple[dict[str, object], ...]) -> tuple[StopMessage, ...]:
    """The last assistant message of every turn, in order."""
    grouped, order = _group_by_message(records=records)
    return tuple(
        StopMessage(
            index=grouped[identifier].index,
            timestamp=grouped[identifier].timestamp,
            text="\n".join(grouped[identifier].texts),
            tools=tuple(grouped[identifier].tools),
        )
        for identifier in _last_message_per_turn(order=order)
    )


def signposts(*, text: str) -> tuple[str, ...]:
    """Every solicitation signpost in `text`, as matched."""
    return tuple(match.group(0).strip() for match in _SIGNPOST.finditer(text))


def solicitations_without_a_picker(
    *, records: tuple[dict[str, object], ...]
) -> tuple[StopMessage, ...]:
    """Stop messages that signpost a decision and hand control back anyway."""
    return tuple(
        stop
        for stop in stop_messages(records=records)
        if signposts(text=stop.text) and "AskUserQuestion" not in stop.tools
    )


def picker_wait_premise_violations(*, text: str) -> tuple[str, ...]:
    """Picker options that wait on a typed target without naming its premise."""
    violations: list[str] = []
    for match in _WAIT_OPTION.finditer(text):
        option = match.group(0).strip()
        if not _TYPED_WAIT_PREMISE.search(option):
            violations.append(option)
    return tuple(violations)


def _c20_records() -> tuple[dict[str, object], ...]:
    return read_records(path=_C20_SESSION)


def _successor_records() -> tuple[dict[str, object], ...]:
    return read_records(path=_SUCCESSOR_SESSION)


def test_the_fixture_still_contains_the_recorded_violation() -> None:
    """Positive control for the fixture itself.

    An empty result is not a finding. Every assertion below is about one recorded
    turn, so the corpus must be proven to still hold it -- otherwise a fixture that
    quietly lost the violation would turn this whole module green.
    """
    text = _C20_SESSION.read_text(encoding="utf-8")
    assert _FOUR_VALVES_HEADING in text
    assert _ANSWERING_TURN_MARK in text


def test_the_four_valves_as_prose_turn_is_flagged() -> None:
    """RED: the recorded 2026-08-02 violation, the reason this gate exists."""
    flagged = solicitations_without_a_picker(records=_c20_records())
    assert len(flagged) == 1
    assert flagged[0].timestamp.startswith("2026-08-02T03:16")
    assert _FOUR_VALVES_HEADING in flagged[0].text
    assert signposts(text=flagged[0].text) == (_FOUR_VALVES_HEADING,)


def test_the_answering_turn_is_not_flagged() -> None:
    """The load-bearing control -- a gate without it must not land.

    This is the turn `overseer-oydugu` and C20 both name as the one a naive
    detector would wrongly flag: prose, question marks, no picker, and CORRECT.

    Asserted in BOTH directions, because a control that passes vacuously proves
    nothing: the corpus must CONTAIN that message, and it must not be flagged.
    """
    records = _c20_records()
    answering = [
        stop for stop in stop_messages(records=records) if _ANSWERING_TURN_MARK in stop.text
    ]
    flagged_text = [stop.text for stop in solicitations_without_a_picker(records=records)]
    assert all(_ANSWERING_TURN_MARK not in text for text in flagged_text)
    # It is not a stop message at all -- it ends with a picker, so its turn
    # continued. Both halves of that are the finding, so both are pinned.
    assert answering == []


def test_the_answering_prose_and_its_picker_are_one_message() -> None:
    """`overseer-oydugu`'s central premise is FALSE, and this pins the measurement.

    The item and C20 both describe the answering turn as *"prose, question marks,
    no picker"*. Measured: the prose and the `AskUserQuestion` call share one
    `message.id` -- one assistant message. The supervisor answered in prose and
    opened the valve in the same breath, which is exactly what C20 prescribes.

    So the feared false positive was inferred from the rendered text and never
    measured against the record. Without this test the next reader re-derives the
    same wrong premise and concludes the gate cannot be built.
    """
    identifiers: dict[str, list[str]] = {}
    for index, record in enumerate(_c20_records()):
        if _role(record=record) != "assistant":
            continue
        identifier = _message_id(record=record, fallback=index)
        texts, tools = _content_blocks(record=record)
        bucket = identifiers.setdefault(identifier, [])
        bucket.extend(tools)
        if any(_ANSWERING_TURN_MARK in text for text in texts):
            bucket.append("<answering-prose>")
    carriers = [tools for tools in identifiers.values() if "<answering-prose>" in tools]
    assert len(carriers) == 1
    assert "AskUserQuestion" in carriers[0]


def test_turn_granularity_cannot_discriminate() -> None:
    """Why the unit is the stop message and not the turn.

    A turn bounded by maintainer inputs is hours long here, and the turn holding
    the violation also holds two correct pickers raised 45 minutes earlier. A
    turn-scoped gate therefore PASSES the one violation we have -- it is inverted,
    not merely imprecise. Pinned so the obvious rule is not re-derived and shipped.
    """
    records = _c20_records()
    turns: list[list[str]] = []
    for record in records:
        if is_maintainer_input(record=record):
            turns.append([])
            continue
        if _role(record=record) != "assistant" or not turns:
            continue
        _, tools = _content_blocks(record=record)
        turns[-1].extend(tools)

    violation = solicitations_without_a_picker(records=records)[0]
    owning = [
        turn
        for turn_index, turn in enumerate(turns)
        if turn_index == _turn_index_of(records=records, target=violation.index)
    ]
    assert owning, "the violation must land in a turn"
    assert "AskUserQuestion" in owning[0]


def _turn_index_of(*, records: tuple[dict[str, object], ...], target: int) -> int:
    boundaries_at_or_before = sum(
        1
        for index, record in enumerate(records)
        if index <= target and is_maintainer_input(record=record)
    )
    return boundaries_at_or_before - 1


def test_the_three_correct_picker_turns_are_not_flagged() -> None:
    """GREEN: the three the supervisor itself cited as correct applications.

    The batched three-valve call, the repo-ownership question and the epic-filing
    consent, all raised BEFORE the violation in the same session.
    """
    records = _c20_records()
    pickers = [
        index
        for index, record in enumerate(records)
        if _role(record=record) == "assistant"
        and "AskUserQuestion" in _content_blocks(record=record)[1]
    ]
    early = [
        index
        for index in pickers
        if index < solicitations_without_a_picker(records=records)[0].index
    ]
    assert len(early) >= 3
    flagged = {stop.index for stop in solicitations_without_a_picker(records=records)}
    assert flagged.isdisjoint(set(pickers))


def test_no_other_stop_message_in_either_session_is_flagged() -> None:
    """Precision, stated as a number rather than an impression.

    Eleven stop messages across the two recorded sessions; exactly one is flagged.
    The other ten include six that MENTION maintainer-owned decisions in passing
    and are correct to do so -- the measurement that rules out a lexical sweep.
    """
    c20 = _c20_records()
    successor = _successor_records()
    total = len(stop_messages(records=c20)) + len(stop_messages(records=successor))
    flagged = len(solicitations_without_a_picker(records=c20)) + len(
        solicitations_without_a_picker(records=successor)
    )
    assert total == 11
    assert flagged == 1


def test_a_benign_restating_stop_message_is_not_flagged() -> None:
    """The shape the gate must tolerate, isolated from the corpus.

    Real text from a clean stop message: it names maintainer-owned work inline and
    says outright that it is restating rather than asking. A detector that flags
    this is the recall-first one that gets discounted within a day.
    """
    benign = (
        "Two things worth a moment of your attention, neither a request for a "
        "decision:\n\n1. **`overseer-c45` is still unhomed.** Already surfaced at "
        "close — restating, not re-asking. That's your call, not mine.\n"
    )
    assert signposts(text=benign) == ()


def test_the_detector_can_fire_on_a_constructed_signpost() -> None:
    """Positive control for the DETECTOR.

    A sabotage that produces no RED is UNVERIFIED, not passed. If the signpost
    pattern ever stops matching, every "not flagged" assertion above would go
    green for the wrong reason; this proves the pattern can still fire.
    """
    for heading in (
        "## What needs your direction",
        "### Needs your ruling",
        "**Your call:** two threads now cover the same subject",
        "## Ripe valves",
    ):
        assert signposts(text=f"{heading}\n\n1. something\n")


def test_wait_premise_picker_option_without_typed_record_is_flagged() -> None:
    """A wait option is unsafe when it rests on prose alone."""
    picker = (
        "Choose the next action:\n\n"
        "1. Wait for Fabro run 01JABC to finish, then archive the plan.\n"
        "2. Stop waiting and escalate the branch."
    )
    assert picker_wait_premise_violations(text=picker) == (
        "1. Wait for Fabro run 01JABC to finish, then archive the plan.",
    )


def test_wait_premise_picker_option_with_typed_record_is_accepted() -> None:
    """The same option becomes checkable when it names the typed premise."""
    picker = (
        "Choose the next action:\n\n"
        "1. Wait for Fabro run 01JABC to finish, then archive the plan. "
        "wait-premise: kind=fabro-run target=01JABC\n"
        "2. Stop waiting and escalate the branch."
    )
    assert picker_wait_premise_violations(text=picker) == ()


def test_picker_without_wait_premise_is_accepted() -> None:
    """The detector must not reject ordinary maintainer choices."""
    picker = (
        "Choose the next action:\n\n"
        "1. Ask the worker to narrow the implementation scope.\n"
        "2. File a follow-up work item for the unrelated defect."
    )
    assert picker_wait_premise_violations(text=picker) == ()


def test_foreman_prose_carries_wait_premise_picker_rule() -> None:
    """The ratified rule must reach the shipped operator prose."""
    prose = (Path(__file__).resolve().parents[2] / ".claude-plugin/prose/foreman.md").read_text(
        encoding="utf-8"
    )
    assert "wait-premise: kind=<kind> target=<target-identifier>" in prose
    assert "write the wait-premise record" in prose
    assert "before raising the picker" in prose
    assert "This recording obligation is fail-soft" in prose
    assert "target kind is inexpressible" in prose
    assert "record cannot be written" in prose
    assert "you may still raise the question" in prose
    assert "surface the gap" in prose
    assert "supervised session's own harness is\nobserved, never forbidden" in prose
    assert "Nothing here authorizes you to alter, withdraw,\nanswer, or select" in prose


def test_a_tool_result_record_is_not_a_turn_boundary() -> None:
    """The guard a live transcript leans on hardest.

    A `tool_result` carries the `user` role, so without this rejection every tool
    call would slice a turn and the stop message would be whatever text preceded
    the next Bash call -- which is most of them.
    """
    result_record: dict[str, object] = {
        "message": {"role": "user", "content": [{"type": "tool_result", "content": "…"}]}
    }
    assert not is_maintainer_input(record=result_record)


def test_harness_chatter_is_not_a_turn_boundary() -> None:
    """A notification and a bare system-reminder are the harness, not the maintainer."""
    notification: dict[str, object] = {
        "message": {"role": "user", "content": [{"type": "text", "text": "<task-notification>x"}]}
    }
    reminder: dict[str, object] = {
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": "<system-reminder>only this</system-reminder>"}],
        }
    }
    empty: dict[str, object] = {
        "message": {"role": "user", "content": [{"type": "text", "text": ""}]}
    }
    assert not is_maintainer_input(record=notification)
    assert not is_maintainer_input(record=reminder)
    assert not is_maintainer_input(record=empty)


def test_malformed_records_degrade_instead_of_deciding() -> None:
    """Fail-soft on shapes a hand-edited or truncated transcript can produce.

    A conduct gate reads a file written by another process; a record it cannot
    parse must contribute NOTHING rather than default into a verdict either way.
    """
    no_message: dict[str, object] = {"type": "assistant"}
    assert _content_blocks(record=no_message) == ([], [])
    assert _role(record=no_message) == "assistant"
    assert _role(record={}) == ""

    string_content: dict[str, object] = {"message": {"role": "user", "content": "plain string"}}
    assert _content_blocks(record=string_content) == (["plain string"], [])

    junk_blocks: dict[str, object] = {
        "message": {
            "role": "assistant",
            "content": [
                "not-a-dict",
                {"type": "text", "text": 7},
                {"type": "tool_use", "name": None},
                {"type": "tool_result", "content": "…"},
            ],
        }
    }
    assert _content_blocks(record=junk_blocks) == ([""], ["", "<tool_result>"])

    assert _message_id(record={"message": {"id": ""}}, fallback=4) == "line4"
    assert _message_id(record={}, fallback=9) == "line9"

    # `content` that is neither a string nor a list, a block whose `type` this
    # module does not model, and a `role` that is not a string. Each is a shape a
    # future harness version could introduce; none may be allowed to decide.
    odd_content: dict[str, object] = {"message": {"role": "assistant", "content": None}}
    assert _content_blocks(record=odd_content) == ([], [])

    unknown_block: dict[str, object] = {
        "message": {"role": "assistant", "content": [{"type": "thinking", "text": "x"}]}
    }
    assert _content_blocks(record=unknown_block) == ([], [])

    assert _role(record={"message": {"role": 3}, "type": "assistant"}) == "assistant"


def test_blank_transcript_lines_are_skipped(*, tmp_path: Path) -> None:
    """A trailing newline is not a record, and must not become one."""
    transcript = tmp_path / "t.jsonl"
    transcript.write_text('\n{"type": "assistant"}\n[1, 2]\n\n', encoding="utf-8")
    assert read_records(path=transcript) == ({"type": "assistant"},)


def test_a_transcript_ending_on_a_maintainer_input_has_no_stop_message() -> None:
    """The maintainer got the last word, so no message handed control back.

    A live transcript is read WHILE the session runs, so this is the ordinary
    mid-turn shape rather than an exotic one -- and reporting a stop that never
    happened would be a verdict about a turn still in progress.
    """
    only_a_prompt: dict[str, object] = {
        "message": {"role": "user", "content": [{"type": "text", "text": "do the thing"}]}
    }
    assert stop_messages(records=(only_a_prompt,)) == ()
