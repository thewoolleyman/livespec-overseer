"""Installed metadata and report roles execute the concrete OnePassword store."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Protocol, cast

import pytest

from overseer._lpm_canonical import canonical_json_text
from overseer._lpm_onepassword import (
    METADATA_VAULT,
    NAMESPACE_ITEM_TITLE,
    namespace_item_fields,
    value_ref,
)
from overseer._lpm_paths import manager_state_dir
from overseer._lpm_revisions import revision_title
from overseer._vendor.returns.result import Success

__all__: list[str] = []

_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
_MACHINE = "e" * 64
_NOW = "2026-10-10T20:00:00Z"
_READER_TOKEN = "reader-role-token-sentinel"
_WRITER_TOKEN = "writer-role-token-sentinel"


class _OpFixture(Protocol):
    executable: str

    def seed(
        self,
        *,
        items: list[dict[str, object]],
        refuse: tuple[str, ...] = (),
        garble: tuple[str, ...] = (),
    ) -> None: ...

    def calls(self) -> list[dict[str, object]]: ...


def _record(*, validated_at: str) -> str:
    return canonical_json_text(
        value={
            "version": 1,
            "record_id": _RECORD,
            "provider": "anthropic",
            "account_id": "account-a",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "status": "valid",
            "acquired_at": _NOW,
            "expires_at": None,
            "last_validated": validated_at,
            "value_generation": _GENERATION,
            "value_ref": value_ref(record_id=_RECORD, value_generation=_GENERATION),
            "previous_value_ref": None,
        }
    ).unwrap()


def _seed(*, op_fixture: _OpFixture, state_dir: Path, before: str) -> None:
    fields = namespace_item_fields(
        machine_id_sha256=_MACHINE,
        effective_uid=os.getuid(),
        manager_state=str(state_dir),
    )
    op_fixture.seed(
        items=[
            {
                "id": "metadata-namespace",
                "title": NAMESPACE_ITEM_TITLE,
                "vault": METADATA_VAULT,
                "fields": fields,
            },
            {
                "id": "metadata-revision-1",
                "title": revision_title(record_id=_RECORD, revision=1, effect_id="a" * 64),
                "vault": METADATA_VAULT,
                "fields": {"predecessor_sha256": "0" * 64, "record": before},
            },
        ]
    )


def _configure_context(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    context = importlib.import_module("_lpm_role_context")

    def account_home(*, uid: int) -> Path:
        _ = uid
        return tmp_path

    def machine_digest(*, path: Path) -> Success[str]:
        _ = path
        return Success(_MACHINE)

    monkeypatch.setattr(context, "account_database_home", account_home)
    monkeypatch.setattr(context, "machine_id_defect", machine_digest)
    return manager_state_dir(home=tmp_path)


def _record_of(*, answer: dict[str, object]) -> object:
    item = answer["item"]
    assert isinstance(item, dict)
    return cast("dict[str, object]", item)["record"]


def test_installed_store_roles_read_metadata_and_commit_reports(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op_fixture: _OpFixture
) -> None:
    service = importlib.import_module("_lpm_role_service")
    assert hasattr(
        service, "store_role_result"
    ), "installed metadata and report roles need a concrete service"
    state_dir = _configure_context(tmp_path=tmp_path, monkeypatch=monkeypatch)
    before = _record(validated_at=_NOW)
    after = _record(validated_at="2026-10-10T20:01:00Z")
    _seed(op_fixture=op_fixture, state_dir=state_dir, before=before)
    reader = {
        "PATH": "/usr/bin:/bin",
        "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN": _READER_TOKEN,
    }
    writer = {
        "PATH": "/usr/bin:/bin",
        "LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN": _WRITER_TOKEN,
    }

    def call(*, role_name: str, request: object, environ: dict[str, str]) -> dict[str, object]:
        return service.role_result(
            role_name=role_name,
            request=request,
            environ=environ,
            lock_descriptor=None,
        )

    listed = call(
        role_name="metadata-reader",
        request={"version": 1, "mode": "list", "op_executable": op_fixture.executable},
        environ=reader,
    )
    got = call(
        role_name="metadata-reader",
        request={
            "version": 1,
            "mode": "get",
            "record_id": _RECORD,
            "op_executable": op_fixture.executable,
        },
        environ=reader,
    )
    written = call(
        role_name="report-writer",
        request={
            "version": 1,
            "mode": "credential-conditional-set",
            "record_id": _RECORD,
            "effect_id": "b" * 64,
            "expected_record": before,
            "desired_record": after,
            "op_executable": op_fixture.executable,
        },
        environ=writer,
    )
    reread = call(
        role_name="metadata-reader",
        request={
            "version": 1,
            "mode": "get",
            "record_id": _RECORD,
            "op_executable": op_fixture.executable,
        },
        environ=reader,
    )

    assert listed["status"] == got["status"] == "ok"
    assert _record_of(answer=got) == json.loads(before)
    assert written == {"version": 1, "status": "committed"}
    assert _record_of(answer=reread) == json.loads(after)
    assert call(role_name="metadata-reader", request=[], environ=reader) == {
        "version": 1,
        "status": "unavailable",
    }
    assert service.store_role_result(role_name="report-writer", members={}, environ=writer) == {
        "version": 1,
        "status": "unavailable",
    }
    assert all(
        call["credential_names"] == ["OP_SERVICE_ACCOUNT_TOKEN"] for call in op_fixture.calls()
    )
    role_results = json.dumps((listed, got, written, reread))
    assert _READER_TOKEN not in role_results
    assert _WRITER_TOKEN not in role_results
