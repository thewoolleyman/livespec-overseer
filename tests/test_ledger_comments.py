"""Tests for the ledger comment channel that carries worker objections."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "ledger_comments.py"

__all__: list[str] = []


def ledger_comments():
    assert MODULE_PATH.is_file(), (
        "objections must be read from a store that exists; overseer/ledger_comments.py "
        "is that reader"
    )
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("ledger_comments")


def test_reading_comments_uses_the_credential_wrapper_and_the_object_shape(
    *, tmp_path, monkeypatch
):
    module = ledger_comments()
    repo = tmp_path / "repo"
    repo.mkdir()
    repo.joinpath(".livespec.jsonc").write_text(
        json.dumps({"credential_wrapper": ["/wrapper", "--"]}),
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def run(*, args, **kwargs):
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout='{"comments":[{"text":"x"},7]}'
        )

    monkeypatch.setattr(subprocess, "run", run)

    assert module.read_comments(repo=repo, work_item_id="overseer-plan") == ({"text": "x"},)
    assert calls == [["/wrapper", "--", "bd", "comments", "overseer-plan", "--json"]]


def test_reading_comments_accepts_a_bare_list_from_a_wrapperless_repo(*, tmp_path, monkeypatch):
    module = ledger_comments()
    repo = tmp_path / "repo"
    repo.mkdir()
    repo.joinpath(".livespec.jsonc").write_text(json.dumps({}), encoding="utf-8")
    calls: list[list[str]] = []

    def run(*, args, **kwargs):
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='[{"body":"x"}]')

    monkeypatch.setattr(subprocess, "run", run)

    assert module.read_comments(repo=repo, work_item_id="overseer-plan") == ({"body": "x"},)
    assert calls == [["bd", "comments", "overseer-plan", "--json"]]


def test_an_unreadable_ledger_reads_as_none_not_as_an_empty_comment_list(*, tmp_path, monkeypatch):
    module = ledger_comments()
    repo = tmp_path / "repo"
    repo.mkdir()
    results: list[object] = [
        subprocess.CompletedProcess(args=[], returncode=1, stdout=""),
        subprocess.CompletedProcess(args=[], returncode=0, stdout="not json"),
        subprocess.CompletedProcess(args=[], returncode=0, stdout="7"),
        FileNotFoundError(),
    ]

    def run(*, args, **kwargs):
        del args, kwargs
        result = results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(subprocess, "run", run)

    assert module.read_comments(repo=repo, work_item_id="x") is None
    assert module.read_comments(repo=repo, work_item_id="x") is None
    assert module.read_comments(repo=repo, work_item_id="x") == ()
    assert module.read_comments(repo=repo, work_item_id="x") is None


def test_a_matching_objection_is_counted_and_a_neighbouring_one_is_not():
    module = ledger_comments()
    comments: list[object] = [
        {"text": "OBJECTION other-fp: a different ruling"},
        {"text": "OBJECTION fp: the ruling under relay"},
        {"text": "no marker at all, just prose"},
        7,
    ]

    tally = module.objection_tally(comments=comments, fingerprint="fp")

    assert tally.count == 1
    assert tally.source == module.SOURCE_LEDGER


def test_an_objection_argued_in_prose_ahead_of_its_marker_still_registers():
    module = ledger_comments()
    reasoned = (
        "I refuse this ruling on jurisdictional grounds: the deliverable is not mine.\n"
        "\n"
        "OBJECTION fp: routing this to my seat is outside my scope."
    )

    assert module.is_objection(comment={"body": reasoned}, fingerprint="fp") is True


def test_an_absent_ledger_is_its_own_condition_not_a_zero_objection_count():
    module = ledger_comments()

    absent = module.objection_tally(comments=None, fingerprint="fp")
    empty = module.objection_tally(comments=[], fingerprint="fp")

    assert absent.count == 0
    assert empty.count == 0
    assert absent.source == module.SOURCE_UNAVAILABLE
    assert empty.source == module.SOURCE_LEDGER
    assert absent.source != empty.source


def test_comment_text_and_latest_comment_at_read_the_shapes_bd_emits():
    module = ledger_comments()
    comments: list[object] = [
        {"created_at": "2026-08-30T01:00:00Z"},
        {"at": "2026-08-30T02:00:00Z"},
        {"id": 1},
        7,
    ]

    assert module.comment_text(comment={"content": "c"}) == "c"
    assert module.comment_text(comment={"id": 1}) is None
    assert module.comment_text(comment=7) is None
    assert module.latest_comment_at(comments=None) is None
    assert module.latest_comment_at(comments=[]) is None
    assert module.latest_comment_at(comments=comments) == "2026-08-30T02:00:00Z"
