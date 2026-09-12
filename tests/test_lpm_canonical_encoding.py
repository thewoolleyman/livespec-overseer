"""One byte representation, and one unforgeable identity digest.

SPECIFICATION/contracts.md decides this whole
operation by COMPARING BYTES: a conditional-set's `predecessor_sha256`, an audit append's
`effect_id` idempotency scan and a pending fence's byte-identical retry all fail closed
when two encoders disagree. These tests pin the encoder's exact output rather than
round-tripping it, because a round-trip passes for any self-consistent encoder — including
one that emits a space, sorts by code point instead of UTF-8 bytes, or keeps the last of
two duplicate members.

The digest half is pinned by COLLISION rather than by a golden value: length prefixing
exists so that a delimiter embedded inside an account id cannot forge the boundary between
`LP(provider)` and `LP(account_id)`, and a collision there means two different accounts
sharing one lease file.
"""

from __future__ import annotations

import hashlib
import importlib
import pathlib

__all__: list[str] = []


def _canonical():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_canonical.py"
    assert module_path.is_file(), "overseer/_lpm_canonical.py must exist"
    # The FLAT name: this package imports its siblings flat, so `_lpm_paths` binds the
    # flat module object. Importing the packaged alias here would exercise a second copy.
    return importlib.import_module("_lpm_canonical")


def _text(*, value: object) -> str:
    return _canonical().canonical_json_text(value=value).unwrap()


def _defect(*, value: object) -> str:
    return _canonical().canonical_json_text(value=value).failure().reason


def test_length_prefix_is_eight_big_endian_bytes_then_the_utf8_bytes():
    canonical = _canonical()

    assert canonical.length_prefixed(value="ab") == b"\x00\x00\x00\x00\x00\x00\x00\x02ab"
    # Length counts UTF-8 BYTES, not characters: "é" is two bytes.
    assert canonical.length_prefixed(value="é") == b"\x00\x00\x00\x00\x00\x00\x00\x02\xc3\xa9"
    assert canonical.length_prefixed(value="") == b"\x00" * 8


def test_an_embedded_separator_cannot_forge_a_length_prefixed_identity_boundary():
    canonical = _canonical()

    left = canonical.length_prefixed_digest(values=("a|b", "c"))
    right = canonical.length_prefixed_digest(values=("a", "b|c"))

    assert left != right, "delimiter-joined text would collide these two identities"
    assert (
        left
        == hashlib.sha256(b"\x00" * 7 + b"\x03" + b"a|b" + b"\x00" * 7 + b"\x01" + b"c").hexdigest()
    )


def test_raw_sha256_is_the_unprefixed_digest_the_contract_states_for_single_values():
    assert _canonical().sha256_hex(data=b"run-7") == hashlib.sha256(b"run-7").hexdigest()


def test_object_members_are_sorted_by_utf8_bytes_recursively_with_no_whitespace():
    encoded = _text(value={"b": {"z": 1, "a": 2}, "a": [3, 1, 2], "É": 0, "Z": 0})

    # "Z" (0x5A) before "b" (0x62) before "É" (0xC3 0x89): UTF-8 byte order, and the
    # nested object is sorted too while the ARRAY keeps its authored order.
    assert encoded == '{"Z":0,"a":[3,1,2],"b":{"a":2,"z":1},"É":0}'


def test_literals_integers_and_strings_use_the_one_canonical_spelling():
    assert _text(value=[True, False, None]) == "[true,false,null]"
    assert _text(value={"n": -7, "z": 0, "p": 10}) == '{"n":-7,"p":10,"z":0}'
    # Quotation mark and reverse solidus escape; every other character stays literal,
    # including the non-ASCII scalar that a JSON encoder would otherwise \u-escape.
    assert _text(value='a"b\\c—d') == '"a\\"b\\\\c—d"'
    assert _text(value="\x00\x1f ") == '"\\u0000\\u001f "'
    assert _text(value={}) == "{}"
    assert _text(value=[]) == "[]"
    assert not _text(value={"a": 1}).endswith("\n")


def test_a_value_no_second_encoder_reproduces_is_refused_rather_than_coerced():
    reason = "value is not canonical-JSON encodable"

    assert _defect(value=1.5) == reason, "a float's shortest repr is platform-sensitive"
    assert _defect(value={1: "x"}) == reason, "a non-string key has no decoded name to order"
    assert _defect(value=[1.5]) == reason
    assert _defect(value={"a": 1.5}) == reason
    assert _defect(value={"\ud800": 1}) == reason, "a lone surrogate is not a scalar value"
    assert _defect(value="\ud800") == reason
    assert _defect(value={"a", "b"}) == reason, "a set is not a JSON value at all"


def test_canonical_bytes_are_utf8_without_a_byte_order_mark_and_carry_the_defect_through():
    canonical = _canonical()

    assert canonical.canonical_json_bytes(value={"k": "é"}).unwrap() == b'{"k":"\xc3\xa9"}'
    assert (
        canonical.canonical_json_bytes(value=1.5).failure().reason
        == "value is not canonical-JSON encodable"
    )


def test_parsing_accepts_canonical_text_and_refuses_malformed_text():
    canonical = _canonical()

    assert canonical.parse_canonical_json(text='{"a":[1,null]}').unwrap() == {"a": [1, None]}
    assert canonical.parse_canonical_json(text="{").failure().reason == "malformed JSON"


def test_a_duplicate_member_name_is_reported_rather_than_silently_collapsed():
    canonical = _canonical()

    top = canonical.parse_canonical_json(text='{"status":"valid","status":"dead"}')
    nested = canonical.parse_canonical_json(text='{"r":{"kind":"a","kind":"b"}}')

    assert top.failure().reason == "duplicate member name: status"
    assert nested.failure().reason == "duplicate member name: kind"
