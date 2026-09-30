"""The operator invocation layer accepts exactly two shapes and constructs nothing else.

SPECIFICATION/contracts.md closes the operator argument surface of
`llm-provider-manager` to ZERO arguments or the four order-independent pairs
`--provider`, `--account-id`, `--kind` and `--purpose`, each appearing once with a
non-empty value. Zero arguments run the `attention` LIST action; four valid pairs run
`acquire --acquisition-json -` with the canonical version-1 five-member object streamed
to standard input. Everything else is `invalid-request` with exit `2`, named by field,
and MUST NOT reach the executable at all.

These tests pin the ARGUMENT VECTOR, not just the accept/reject verdict. The vector is
the whole safety property here: the same executable also exposes
`attention --resolve <record_id>` and `attention --give-up <record_id>`, which the
contract forbids this layer from constructing, forwarding or executing. A gate that only
asked "was this rejected?" would pass for a layer that happily assembled a mutation
vector out of an accepted request.

The refusal message is pinned as SECRET-FREE by construction rather than by inspection:
an unknown `--flag=value` token and a bare positional argument can both carry a
credential, so the layer names the flag stem or the argument's POSITION and never echoes
a value back. A message that quoted the offending token would leak exactly the secret
this operation exists to keep out of operator-visible output.
"""

from __future__ import annotations

import importlib
import json
import pathlib
from typing import Any

__all__: list[str] = []

MODULE_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_operator_request.py"


def _operator_request_module() -> Any:
    assert MODULE_PATH.is_file(), "overseer/_lpm_operator_request.py must exist"
    # The FLAT name: this package imports its siblings flat, so the sibling `_lpm_*`
    # modules bind the flat module object. Importing the packaged alias would exercise
    # a second copy of the same source.
    return importlib.import_module("_lpm_operator_request")


def _accepted(*, arguments: list[str]) -> Any:
    return _operator_request_module().operator_request(arguments=arguments).unwrap()


def _refusal(*, arguments: list[str]) -> Any:
    return _operator_request_module().operator_request(arguments=arguments).failure()


def test_zero_arguments_construct_only_the_attention_list_vector() -> None:
    accepted = _accepted(arguments=[])

    assert accepted.argv == ("attention",)
    assert accepted.stdin_bytes is None


def test_four_order_independent_pairs_construct_the_acquire_vector_and_its_stdin() -> None:
    accepted = _accepted(
        arguments=[
            "--purpose",
            "factory",
            "--provider",
            "anthropic",
            "--kind",
            "oauth",
            "--account-id",
            "acct-1",
        ]
    )

    assert accepted.argv == ("acquire", "--acquisition-json", "-")
    assert accepted.stdin_bytes is not None
    assert json.loads(accepted.stdin_bytes.decode("utf-8")) == {
        "version": 1,
        "provider": "anthropic",
        "account_id": "acct-1",
        "kind": "oauth",
        "purpose": "factory",
    }


def test_the_acquire_stdin_object_is_canonical_bytes_with_no_trailing_newline() -> None:
    """Canonical means sorted members, no insignificant whitespace, no trailing newline."""
    accepted = _accepted(
        arguments=[
            "--provider",
            "anthropic",
            "--account-id",
            "acct-1",
            "--kind",
            "oauth",
            "--purpose",
            "factory",
        ]
    )

    assert accepted.stdin_bytes == (
        b'{"account_id":"acct-1","kind":"oauth","provider":"anthropic",'
        b'"purpose":"factory","version":1}'
    )


def test_a_missing_pair_is_refused_by_name_without_an_argument_vector() -> None:
    refusal = _refusal(arguments=["--provider", "anthropic", "--kind", "oauth"])

    assert refusal.error_type == "invalid-request"
    assert "--account-id" in refusal.message
    assert "--purpose" in refusal.message
    assert "--provider" not in refusal.message


def test_an_empty_value_and_a_repeated_flag_are_both_offending_fields() -> None:
    empty = _refusal(
        arguments=[
            "--provider",
            "",
            "--account-id",
            "acct-1",
            "--kind",
            "oauth",
            "--purpose",
            "factory",
        ]
    )
    repeated = _refusal(
        arguments=[
            "--provider",
            "anthropic",
            "--provider",
            "anthropic",
            "--account-id",
            "acct-1",
            "--kind",
            "oauth",
            "--purpose",
            "factory",
        ]
    )

    assert empty.error_type == "invalid-request"
    assert "--provider" in empty.message
    assert repeated.error_type == "invalid-request"
    assert "--provider" in repeated.message


def test_a_dangling_flag_with_no_value_is_refused_by_name() -> None:
    refusal = _refusal(
        arguments=[
            "--provider",
            "anthropic",
            "--account-id",
            "acct-1",
            "--kind",
            "oauth",
            "--purpose",
        ]
    )

    assert refusal.error_type == "invalid-request"
    assert "--purpose" in refusal.message


def test_an_unknown_flag_is_named_by_its_stem_and_never_echoes_its_value() -> None:
    """A `--flag=value` token can carry a credential; only the stem may be reported."""
    refusal = _refusal(arguments=["--token=sk-ant-oat0-super-secret"])

    assert refusal.error_type == "invalid-request"
    assert "--token" in refusal.message
    assert "sk-ant-oat0-super-secret" not in refusal.message


def test_a_positional_argument_is_reported_by_position_and_never_by_value() -> None:
    refusal = _refusal(arguments=["sk-ant-oat0-super-secret"])

    assert refusal.error_type == "invalid-request"
    assert "positional-argument-0" in refusal.message
    assert "sk-ant-oat0-super-secret" not in refusal.message


def test_no_accepted_or_refused_request_can_construct_an_attention_mutation_vector() -> None:
    """The contract forbids this layer from building `--resolve`/`--give-up` at all.

    Driven over a corpus that includes the mutation spellings THEMSELVES, because the
    only way this property could break is by a layer that forwarded operator tokens into
    the vector it constructs. A corpus of well-formed requests could not detect that.
    """
    module = _operator_request_module()
    corpus = [
        [],
        ["--provider", "anthropic", "--account-id", "a", "--kind", "oauth", "--purpose", "p"],
        ["attention", "--resolve", "8f14e45f-e0a1-4c5e-9d8b-2a3b4c5d6e7f"],
        ["--resolve", "8f14e45f-e0a1-4c5e-9d8b-2a3b4c5d6e7f"],
        ["--give-up", "8f14e45f-e0a1-4c5e-9d8b-2a3b4c5d6e7f"],
    ]

    constructed: list[tuple[str, ...]] = []
    for arguments in corpus:
        outcome = module.operator_request(arguments=arguments)
        alternative = outcome.value_or(None)
        if alternative is not None:
            constructed.append(alternative.argv)

    # Control: the corpus must actually produce vectors, or the assertion below is
    # vacuously true for a layer that accepted nothing at all.
    assert len(constructed) == 2, constructed
    assert set(constructed) == {("attention",), ("acquire", "--acquisition-json", "-")}
    assert all("--resolve" not in argv and "--give-up" not in argv for argv in constructed)
