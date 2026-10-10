"""Metadata reads and report writes performed inside installed store roles."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from _lpm_op_entrypoints import metadata_read_result, metadata_write_result
from _lpm_role_context import RoleContext, role_context, role_entry
from _lpm_store import ConditionalSet

__all__: list[str] = [
    "store_role_result",
]


def store_role_result(
    *, role_name: str, members: dict[str, object], environ: Mapping[str, str]
) -> dict[str, object]:
    """Validate and execute one metadata-reader or report-writer request."""
    return (
        role_context()
        .map(
            lambda context: _store_result(
                context=context,
                role_name=role_name,
                members=members,
                environ=environ,
            )
        )
        .value_or(_failure())
    )


def _store_result(
    *,
    context: RoleContext,
    role_name: str,
    members: dict[str, object],
    environ: Mapping[str, str],
) -> dict[str, object]:
    version = members.get("version")
    executable = members.get("op_executable")
    record_id = members.get("record_id")
    effect_id = members.get("effect_id")
    expected_record = members.get("expected_record")
    desired_record = members.get("desired_record")
    list_request = (role_name, members, type(version), type(executable), bool(executable)) == (
        "metadata-reader",
        {"version": 1, "mode": "list", "op_executable": executable},
        int,
        str,
        True,
    )
    get_request = (
        role_name,
        members,
        type(version),
        type(record_id),
        type(executable),
        bool(record_id),
        bool(executable),
    ) == (
        "metadata-reader",
        {
            "version": 1,
            "mode": "get",
            "record_id": record_id,
            "op_executable": executable,
        },
        int,
        str,
        str,
        True,
        True,
    )
    write_request = (
        role_name,
        members,
        type(version),
        type(record_id),
        type(effect_id),
        type(expected_record) in (str, type(None)),
        type(desired_record),
        type(executable),
        bool(record_id),
        bool(effect_id),
        bool(desired_record),
        bool(executable),
    ) == (
        "report-writer",
        {
            "version": 1,
            "mode": "credential-conditional-set",
            "record_id": record_id,
            "effect_id": effect_id,
            "expected_record": expected_record,
            "desired_record": desired_record,
            "op_executable": executable,
        },
        int,
        str,
        str,
        True,
        str,
        str,
        True,
        True,
        True,
        True,
    )
    if list_request:
        return metadata_read_result(
            entry=role_entry(
                role_name=role_name,
                members=members,
                environ=environ,
                context=context,
            ),
            mode="list",
            record_id=None,
        )
    if get_request:
        return metadata_read_result(
            entry=role_entry(
                role_name=role_name,
                members=members,
                environ=environ,
                context=context,
            ),
            mode="get",
            record_id=cast("str", record_id),
        )
    if write_request:
        return metadata_write_result(
            entry=role_entry(
                role_name=role_name,
                members=members,
                environ=environ,
                context=context,
            ),
            request=ConditionalSet(
                record_id=cast("str", record_id),
                effect_id=cast("str", effect_id),
                expected_record=cast("str | None", expected_record),
                desired_record=cast("str", desired_record),
            ),
        )
    return _failure()


def _failure() -> dict[str, object]:
    return {"version": 1, "status": "unavailable"}
