"""What `op` printed, read back as a closed shape — never as whatever JSON happened to parse.

SPECIFICATION/contracts.md gives this backend three argument vectors and then constrains
what each answer may be: an enumeration of titles, one item's application fields, and the
create whose template is streamed rather than argued. This module is the READING half of
that — the narrow door every byte `op` writes has to come through before any decision is
made on it.

THE PARSE IS CLOSED BECAUSE THE DECISIONS DOWNSTREAM ARE ABSOLUTE. An enumeration is what
makes absence AUTHORITATIVE, and absence is what licenses a genesis create; an item's
fields carry the predecessor digest a conditional write is judged against. A forgiving
parse that shrugged at a missing title or a non-string value would hand those decisions a
value nobody checked, and the failure would surface as a chain that cannot be explained
rather than as output that was not conforming.

A DEFECT REASON NAMES THE SHAPE, NEVER THE VALUE. `op` is not manager-owned and its output
can carry credential bytes — a values-vault item's `credential` field arrives through
:func:`parse_item_fields` — so no reason here interpolates a parsed value, a member name or
a label. The shape is the whole of what a reader needs, and it is the only part this module
can vouch for being secret-free.

A DUPLICATE LABEL IS REFUSED RATHER THAN COLLAPSED. `parse_canonical_json` already rejects a
repeated OBJECT MEMBER, but an item's fields arrive as an ARRAY, where repetition is legal
JSON and silently keeping the last one would let a second `record` field decide a record no
reader ever saw written.

BOTH PUBLIC PARSERS GO THROUGH ONE DECODE, rather than each re-testing it. The decode is
the step they genuinely share — same bytes, same two failures — and spelling its refusal
twice would mean two places where a future reason could drift, in the one module whose
reasons have to stay secret-free. :func:`_read_answer` is that single step, and the SHAPE it
hands the decoded value to is what differs between an enumeration and one item's fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import parse_canonical_json

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "OpItem",
    "item_create_template",
    "parse_item_fields",
    "parse_item_summaries",
]

# A metadata revision item carries only text fields, so the template needs only the text
# type. The concealed type belongs to a values-vault generation item, which this backend
# creates from the acquisition writer alone; adding it here before that role has a creator
# would widen the template beyond what any shipped caller can ask for.
_ITEM_TEXT_TYPE = "STRING"
_ITEM_CATEGORY = "SECURE_NOTE"

_Shaped_co = TypeVar("_Shaped_co", covariant=True)


class _AnswerShape(Protocol[_Shaped_co]):
    """One closed shape a decoded `op` answer may be read as, or its shape-only reason."""

    def __call__(self, *, answer: object) -> Result[_Shaped_co, str]:
        """Read `answer` as this shape, or say why its shape is not that one."""
        ...


@dataclass(frozen=True, kw_only=True)
class OpItem:
    """One enumerated backend item: the id a get is addressed by, and its title.

    Both, always. A get is addressed by ITEM ID because no backend in this operation may
    rely on 1Password item-title uniqueness, while every decision about WHICH item this is
    — the reserved namespace title, a revision title, a generation title — is made on the
    TITLE. An enumeration that yielded only one of the two would force a caller to guess
    the other.
    """

    item_id: str
    title: str


def parse_item_summaries(*, stdout: bytes) -> Result[tuple[OpItem, ...], str]:
    """`op item list`'s answer as id/title pairs, or why that output is not one.

    Order is PRESERVED rather than sorted. The contract's ordering requirements are on the
    manager's own result arrays, which are ordered where they are produced; sorting here
    would discard the backend's own answer before anything had compared the two.
    """
    return _read_answer(stdout=stdout, shape=_summaries_of)


def parse_item_fields(*, stdout: bytes) -> Result[dict[str, str], str]:
    """`op item get`'s answer as its application fields, keyed by unique label."""
    return _read_answer(stdout=stdout, shape=_fields_of)


def item_create_template(*, title: str, fields: Mapping[str, str]) -> dict[str, object]:
    """The one item object `op item create -` reads from its child's standard input.

    STREAMED, NEVER ARGUED. "It MUST use no assignment argument, template file or
    environment field for the credential": all three are readable from outside the process,
    so the template exists only in this process's memory and in the pipe.

    THE FIELD ORDER IS DETERMINISTIC because a retry may append "only the byte-identical
    revision title and fields". Sorting by label is what makes two independently-built
    templates for one logical revision the same bytes; relying on a caller's mapping order
    would make a late duplicate a DIFFERENT physical item, which is a conflict rather than
    the harmless copy the fence depends on.
    """
    return {
        "title": title,
        "category": _ITEM_CATEGORY,
        "fields": [
            {"id": label, "type": _ITEM_TEXT_TYPE, "label": label, "value": fields[label]}
            for label in sorted(fields)
        ],
    }


def _summaries_of(*, answer: object) -> Result[tuple[OpItem, ...], str]:
    """One decoded enumeration as id/title pairs, or why its shape is not one."""
    if not isinstance(answer, list):
        return Failure("an enumeration that is not a JSON array")
    summaries: list[OpItem] = []
    for element in cast("list[object]", answer):
        summary = _summary(element=element)
        if isinstance(summary, Failure):
            return summary
        summaries.append(summary.unwrap())
    return Success(tuple(summaries))


def _fields_of(*, answer: object) -> Result[dict[str, str], str]:
    """One decoded item's application fields, keyed by label, or why its shape is not one."""
    if not isinstance(answer, dict):
        return Failure("an item that is not an object")
    members: dict[str, object] = answer
    declared = members.get("fields")
    if not isinstance(declared, list):
        return Failure("an item whose application fields are not an array")
    fields: dict[str, str] = {}
    for element in cast("list[object]", declared):
        field = _field(element=element)
        if isinstance(field, Failure):
            return field
        label, value = field.unwrap()
        if label in fields:
            return Failure("an item carrying one application-field label twice")
        fields[label] = value
    return Success(fields)


def _summary(*, element: object) -> Result[OpItem, str]:
    """One enumerated entry, requiring both halves of the pair to be usable text."""
    if not isinstance(element, dict):
        return Failure("an enumerated entry that is not an object")
    members: dict[str, object] = element
    item_id = members.get("id")
    title = members.get("title")
    if not _is_text(value=item_id) or not _is_text(value=title):
        return Failure("an enumerated entry whose id and title are not both non-empty strings")
    return Success(OpItem(item_id=str(item_id), title=str(title)))


def _field(*, element: object) -> Result[tuple[str, str], str]:
    """One application field as a label/value pair; an empty VALUE is legal, a label is not.

    The asymmetry is the contract's. A concealed `credential` or a text `record` must be
    non-empty, but that is a rule about a PARTICULAR field, enforced where that field is
    read; a label is what identifies the field at all, so an unlabelled one cannot be
    carried far enough to be judged.
    """
    if not isinstance(element, dict):
        return Failure("an application field that is not an object")
    members: dict[str, object] = element
    label = members.get("label")
    value = members.get("value")
    if not _is_text(value=label) or not isinstance(value, str):
        return Failure("an application field whose label and value are not both text")
    return Success((str(label), value))


def _read_answer(*, stdout: bytes, shape: _AnswerShape[_Shaped_co]) -> Result[_Shaped_co, str]:
    """Decode one `op` answer and hand it to `shape`, or report why it cannot be read."""
    parsed = _decoded_answer(stdout=stdout)
    if isinstance(parsed, Failure):
        return parsed
    return shape(answer=parsed.unwrap())


def _is_text(*, value: object) -> bool:
    """Whether `value` is a non-empty string, the only usable spelling of an identifier."""
    return isinstance(value, str) and value != ""


def _decoded_answer(*, stdout: bytes) -> Result[object, str]:
    """One `op` answer decoded and parsed, or the shape-only reason it could not be.

    `parse_canonical_json` is used rather than a bare `json.loads` because it REJECTS a
    duplicate member name instead of keeping the last one. The parser's own reason is
    DISCARDED rather than forwarded: it names the offending member, and that name comes
    from the backend's output, which may carry credential bytes.
    """
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError:
        return Failure("output that is not UTF-8")
    parsed = parse_canonical_json(text=text.strip())
    if isinstance(parsed, Failure):
        return Failure("output that is not one JSON value")
    return Success(parsed.unwrap())
