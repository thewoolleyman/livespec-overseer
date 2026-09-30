"""Discovering every PENDING attention artifact, and the six-member items it reports.

SPECIFICATION/contracts.md fixes this surface precisely: `llm-provider-manager attention`
with no other argument "MUST then discover every pending artifact under the manager state
directory and emit exactly one secret-free single-line JSON object
`{"version":1,"status":"ok","operation":"attention","items":[...]}`, whose items contain
exactly `path`, `record_id`, `provider`, `account_id`, `reason` and `deadline`". Each `path`
"MUST be the absolute `<manager-state>/attention/<sha256>.json` path, and items MUST sort by
the UTF-8 bytes of that absolute path." And: "If attention state cannot be read, it MUST emit
the common single-line `store-unavailable` error object and exit `4`."

THE THREE PROPERTIES WORTH PINNING, each with an easy wrong implementation:

* ABSENCE IS NOT UNAVAILABILITY. A manager that has never held an artifact has no
  `attention/` directory at all, and the honest answer to "what is waiting on a human?" is
  an EMPTY list, not `store-unavailable`. The easy wrong version fails closed on a missing
  directory and reports a store outage to every operator on a healthy host.
* UNREADABILITY IS NOT ABSENCE. The mirror-image error: an artifact this manager does not
  own, or one whose bytes are not a conforming record, must be `store-unavailable` rather
  than quietly skipped. A skipped artifact is a credential identity waiting on a human that
  no operator is ever told about, which is the exact failure this operation exists to
  prevent.
* THE SORT IS ON THE PATH'S BYTES, NOT ON DIRECTORY ORDER. `Path.glob` yields entries in
  filesystem order, which is neither stable nor meaningful, so an implementation that just
  iterates produces a different list on a different host from identical state.

NOTHING READ OUT OF AN ARTIFACT REACHES A REFUSAL MESSAGE. An artifact is written by the
acquisition worker, and this operation's output is required to be secret-free, so a
malformed one is refused by NAMING THE DEFECT rather than by quoting the bytes that carry it.
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib
from typing import Any

import pytest

__all__: list[str] = []

MODULE_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_attention.py"

_RECORD_ID = "d1f0c2a4-8b6e-4c1a-9f3d-0e7a5b2c4d69"
_OTHER_RECORD_ID = "9b3e7c51-0a2d-4f68-b1c4-7e5a2d9f06b8"
_DEADLINE = "2026-09-30T23:00:00Z"
_SECRET = "sk-ant-oat0-never-in-a-message"


def _attention() -> Any:
    assert MODULE_PATH.is_file(), "overseer/_lpm_attention.py must exist"
    return importlib.import_module("_lpm_attention")


def _artifact(**overrides: object) -> dict[str, object]:
    stored: dict[str, object] = {
        "version": 1,
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": "acct-1",
        "reason": "a human must complete the browser challenge",
        "deadline": _DEADLINE,
        "status": "pending",
    }
    stored.update(overrides)
    return stored


def _write(
    *, directory: pathlib.Path, name: str, stored: object, mode: int = 0o600
) -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    _ = path.write_text(json.dumps(stored, sort_keys=True), encoding="utf-8")
    path.chmod(mode)
    return path


def _directory(*, state_dir: pathlib.Path) -> pathlib.Path:
    return _attention().attention_directory(state_dir=state_dir)


def _items(*, state_dir: pathlib.Path) -> Any:
    return _attention().attention_items(state_dir=state_dir, owner_uid=os.getuid())


def _listed(*, state_dir: pathlib.Path) -> Any:
    outcome = _items(state_dir=state_dir)
    assert not isinstance(outcome, _failure_type()), "attention listing must succeed"
    return outcome.unwrap()


def _refused(*, state_dir: pathlib.Path) -> Any:
    outcome = _items(state_dir=state_dir)
    assert isinstance(outcome, _failure_type()), "attention listing must be refused"
    return outcome.failure()


def _failure_type() -> Any:
    from overseer._vendor.returns.result import Failure

    return Failure


def test_the_artifact_and_item_member_tables_are_the_ratified_ones() -> None:
    module = _attention()

    assert module.ATTENTION_ITEM_MEMBERS == (
        "path",
        "record_id",
        "provider",
        "account_id",
        "reason",
        "deadline",
    )
    assert module.ATTENTION_ARTIFACT_MEMBERS == (
        "version",
        "record_id",
        "provider",
        "account_id",
        "reason",
        "deadline",
        "status",
    )
    assert module.ATTENTION_STATUSES == ("pending", "resolved", "give-up")
    assert module.PENDING_ATTENTION == "pending"
    assert module.ATTENTION_DIRECTORY == "attention"


def test_a_manager_that_has_never_held_an_artifact_lists_nothing(tmp_path: pathlib.Path) -> None:
    assert _listed(state_dir=tmp_path / "state") == ()


def test_an_existing_but_empty_attention_directory_lists_nothing(
    tmp_path: pathlib.Path,
) -> None:
    _directory(state_dir=tmp_path).mkdir(parents=True)

    assert _listed(state_dir=tmp_path) == ()


def test_a_pending_artifact_becomes_one_item_carrying_its_absolute_path(
    tmp_path: pathlib.Path,
) -> None:
    path = _write(directory=_directory(state_dir=tmp_path), name="aa.json", stored=_artifact())

    listed = _listed(state_dir=tmp_path)

    assert len(listed) == 1
    item = listed[0]
    assert item.path == str(path)
    assert pathlib.Path(item.path).is_absolute()
    assert item.record_id == _RECORD_ID
    assert item.provider == "anthropic"
    assert item.account_id == "acct-1"
    assert item.reason == "a human must complete the browser challenge"
    assert item.deadline == _DEADLINE


def test_the_item_object_carries_exactly_the_six_ratified_members(
    tmp_path: pathlib.Path,
) -> None:
    _write(directory=_directory(state_dir=tmp_path), name="aa.json", stored=_artifact())
    item = _listed(state_dir=tmp_path)[0]

    encoded = _attention().attention_item_object(item=item)

    assert sorted(encoded) == sorted(_attention().ATTENTION_ITEM_MEMBERS)
    assert encoded["record_id"] == _RECORD_ID


@pytest.mark.parametrize("status", ["resolved", "give-up"])
def test_an_artifact_that_is_no_longer_pending_is_not_reported(
    *, tmp_path: pathlib.Path, status: str
) -> None:
    _write(
        directory=_directory(state_dir=tmp_path),
        name="aa.json",
        stored=_artifact(status=status),
    )

    assert _listed(state_dir=tmp_path) == ()


def test_items_sort_by_the_utf8_bytes_of_their_absolute_path(tmp_path: pathlib.Path) -> None:
    directory = _directory(state_dir=tmp_path)
    for name in ("cc.json", "aa.json", "bb.json"):
        _write(directory=directory, name=name, stored=_artifact())

    listed = _listed(state_dir=tmp_path)

    assert [pathlib.Path(item.path).name for item in listed] == ["aa.json", "bb.json", "cc.json"]


def test_a_non_json_sibling_in_the_directory_is_not_an_artifact(
    tmp_path: pathlib.Path,
) -> None:
    directory = _directory(state_dir=tmp_path)
    _write(directory=directory, name="aa.json", stored=_artifact())
    _ = (directory / "notes.txt").write_text("not an artifact\n", encoding="utf-8")

    assert len(_listed(state_dir=tmp_path)) == 1


def test_an_attention_directory_that_is_a_symlink_is_store_unavailable(
    tmp_path: pathlib.Path,
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _directory(state_dir=tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _directory(state_dir=tmp_path).symlink_to(elsewhere, target_is_directory=True)

    assert _refused(state_dir=tmp_path).error_type == "store-unavailable"


def test_an_artifact_this_manager_does_not_own_is_store_unavailable(
    tmp_path: pathlib.Path,
) -> None:
    _write(
        directory=_directory(state_dir=tmp_path),
        name="aa.json",
        stored=_artifact(),
        mode=0o644,
    )

    assert _refused(state_dir=tmp_path).error_type == "store-unavailable"


@pytest.mark.parametrize(
    "stored",
    [
        ["not", "an", "object"],
        _artifact(version=2),
        _artifact(version=True),
        _artifact(status="unknown"),
        _artifact(record_id="D1F0C2A4-8B6E-4C1A-9F3D-0E7A5B2C4D69"),
        _artifact(deadline="2026-09-30 23:00:00"),
        _artifact(provider=""),
        _artifact(account_id=""),
        _artifact(reason=""),
        _artifact(reason=7),
        {"version": 1, "record_id": _RECORD_ID},
    ],
)
def test_a_nonconforming_artifact_is_store_unavailable(
    *, tmp_path: pathlib.Path, stored: object
) -> None:
    _write(directory=_directory(state_dir=tmp_path), name="aa.json", stored=stored)

    assert _refused(state_dir=tmp_path).error_type == "store-unavailable"


def test_unparsable_artifact_bytes_are_store_unavailable(tmp_path: pathlib.Path) -> None:
    directory = _directory(state_dir=tmp_path)
    directory.mkdir(parents=True)
    path = directory / "aa.json"
    _ = path.write_text("{not json", encoding="utf-8")
    path.chmod(0o600)

    assert _refused(state_dir=tmp_path).error_type == "store-unavailable"


def test_no_refusal_message_ever_quotes_the_artifact_bytes(tmp_path: pathlib.Path) -> None:
    _write(
        directory=_directory(state_dir=tmp_path),
        name="aa.json",
        stored=_artifact(reason=_SECRET, status="nonsense"),
    )

    assert _SECRET not in _refused(state_dir=tmp_path).message


def test_an_artifact_that_vanished_before_it_could_be_read_is_simply_absent(
    tmp_path: pathlib.Path,
) -> None:
    outcome = _attention().attention_item(
        path=_directory(state_dir=tmp_path) / "gone.json", owner_uid=os.getuid()
    )

    assert not isinstance(outcome, _failure_type())
    assert outcome.unwrap() is None


def test_two_pending_artifacts_for_different_records_are_both_reported(
    tmp_path: pathlib.Path,
) -> None:
    directory = _directory(state_dir=tmp_path)
    _write(directory=directory, name="aa.json", stored=_artifact())
    _write(directory=directory, name="bb.json", stored=_artifact(record_id=_OTHER_RECORD_ID))

    assert [item.record_id for item in _listed(state_dir=tmp_path)] == [
        _RECORD_ID,
        _OTHER_RECORD_ID,
    ]
