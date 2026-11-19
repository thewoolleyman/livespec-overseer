"""`caam-strip-refresh-tokens`: step 3 of contracts.md "Moving the role".

The old role holder must hold no managed account's refresh token once the role
has moved, so the command strips `refreshToken` from the live credential and
from every caam snapshot, backups included, and proves none is left. It refuses
while anything that could still refresh is running, and never prints a value.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

REFRESH = "rt-" + "do-not-print"
ACCESS = "at-" + "do-not-print"


def _strip() -> ModuleType:
    return importlib.import_module("caam_refresh_strip")


def _cred(*, path: Path, refresh: bool = True, extra: dict[str, object] | None = None) -> None:
    oauth: dict[str, object] = {"accessToken": ACCESS, "expiresAt": 1, "scopes": ["a"]}
    if refresh:
        oauth["refreshToken"] = REFRESH
    body: dict[str, object] = {"claudeAiOauth": oauth, "mcpOAuth": {"k": "v"}}
    if extra is not None:
        body.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(body), encoding="utf-8")
    path.chmod(0o600)


def _home(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _snapshots(*, home: Path) -> list[Path]:
    caam = home / ".local/share/caam"
    return [
        caam / "vault/claude/anthropic-1/.credentials.json",
        caam / "vault/claude/_backup_20261114/.credentials.json",
        caam / "vault/claude/_caam-vault-backup~1/previous/.credentials.json",
        caam / "vault.pre-0.1.25-20261112T193123Z/claude/anthropic-2/.credentials.json",
    ]


def _proc(*, tmp_path: Path) -> Path:
    root = tmp_path / "proc"
    root.mkdir()
    return root


def _process(*, proc: Path, pid: int, argv: list[str]) -> None:
    (proc / str(pid)).mkdir()
    _ = (proc / str(pid) / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")


def _run(
    *, proc: Path, capsys: pytest.CaptureFixture[str], argv: list[str] | None = None
) -> tuple[int, str]:
    code = _strip().main(argv=[] if argv is None else argv, proc_root=proc)
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_strips_live_and_every_snapshot_preserving_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = _home(tmp_path=tmp_path, monkeypatch=monkeypatch)
    live = home / ".claude/.credentials.json"
    _cred(path=live, extra={"other": 1})
    for snap in _snapshots(home=home):
        _cred(path=snap)
    code, out = _run(proc=_proc(tmp_path=tmp_path), capsys=capsys)
    assert code == 0, out
    for path in [live, *_snapshots(home=home)]:
        body = json.loads(path.read_text(encoding="utf-8"))
        assert "refreshToken" not in body["claudeAiOauth"]
        assert body["claudeAiOauth"]["accessToken"] == ACCESS
        assert body["claudeAiOauth"]["scopes"] == ["a"]
        assert body["mcpOAuth"] == {"k": "v"}
        assert path.stat().st_mode & 0o777 == 0o600
        assert f"stripped {path} " in out
    assert json.loads(live.read_text(encoding="utf-8"))["other"] == 1
    assert "OK refresh tokens removed: stripped=5 clean=0" in out
    assert REFRESH not in out
    assert ACCESS not in out
    assert not list(home.rglob("*.strip-tmp"))


def test_second_run_is_a_clean_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = _home(tmp_path=tmp_path, monkeypatch=monkeypatch)
    live = home / ".claude/.credentials.json"
    _cred(path=live)
    proc = _proc(tmp_path=tmp_path)
    assert _run(proc=proc, capsys=capsys)[0] == 0
    before = live.read_bytes()
    code, out = _run(proc=proc, capsys=capsys)
    assert code == 0, out
    assert live.read_bytes() == before
    assert f"clean {live} " in out
    assert "OK refresh tokens removed: stripped=0 clean=1" in out


def test_dry_run_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = _home(tmp_path=tmp_path, monkeypatch=monkeypatch)
    snap = _snapshots(home=home)[0]
    _cred(path=snap)
    before = snap.read_bytes()
    code, out = _run(proc=_proc(tmp_path=tmp_path), capsys=capsys, argv=["--dry-run"])
    assert code == 0, out
    assert snap.read_bytes() == before
    assert f"would-strip {snap} " in out
    assert f"absent {home / '.claude/.credentials.json'}" in out
    assert "OK dry run: would strip 1" in out
    assert REFRESH not in out


def test_without_confirmation_only_reports_refresh_token_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = _home(tmp_path=tmp_path, monkeypatch=monkeypatch)
    live = home / ".claude/.credentials.json"
    snapshot = _snapshots(home=home)[0]
    _cred(path=live)
    _cred(path=snapshot)
    before = {path: path.read_bytes() for path in (live, snapshot)}

    code, out = _run(proc=_proc(tmp_path=tmp_path), capsys=capsys)

    assert code == 0, out
    assert {path: path.read_bytes() for path in (live, snapshot)} == before
    for path in (live, snapshot):
        assert f"would-strip {path} " in out
    assert REFRESH not in out


@pytest.mark.parametrize(
    "argv",
    [
        ["/home/u/.venv/bin/python3", "/home/u/.venv/bin/caam-delivery-push", "run"],
        ["/usr/bin/python3", "-m", "overseer.caam_anthropic_loop"],
        ["/home/u/.local/bin/caam", "refresh"],
    ],
)
def test_refuses_while_a_refreshing_process_runs(
    argv: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = _home(tmp_path=tmp_path, monkeypatch=monkeypatch)
    live = home / ".claude/.credentials.json"
    _cred(path=live)
    before = live.read_bytes()
    proc = _proc(tmp_path=tmp_path)
    _process(proc=proc, pid=4242, argv=argv)
    code, out = _run(proc=proc, capsys=capsys)
    assert code != 0
    assert live.read_bytes() == before
    assert "REFUSED process 4242" in out
    assert "nothing changed" in out


def test_refuses_while_a_claude_session_is_live_but_not_for_a_stale_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = _home(tmp_path=tmp_path, monkeypatch=monkeypatch)
    live = home / ".claude/.credentials.json"
    _cred(path=live)
    sessions = home / ".claude/sessions"
    sessions.mkdir(parents=True)
    _ = (sessions / "77.json").write_text(json.dumps({"pid": 77}), encoding="utf-8")
    _ = (sessions / "88.json").write_text(json.dumps({"pid": 88}), encoding="utf-8")
    _ = (sessions / "junk.json").write_text("{", encoding="utf-8")
    proc = _proc(tmp_path=tmp_path)
    _process(proc=proc, pid=77, argv=["claude", "--resume", "x"])
    _process(proc=proc, pid=5, argv=[])
    (proc / "6").mkdir()
    (proc / "self").mkdir()
    (sessions / "dir.json").mkdir()
    before = live.read_bytes()
    code, out = _run(proc=proc, capsys=capsys)
    assert code != 0
    assert live.read_bytes() == before
    assert "REFUSED Claude Code session 77" in out
    assert "session 88" not in out
    (proc / "77" / "cmdline").unlink()
    (proc / "77").rmdir()
    code, out = _run(proc=proc, capsys=capsys)
    assert code == 0, out


def test_unreadable_snapshot_and_residue_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = _home(tmp_path=tmp_path, monkeypatch=monkeypatch)
    bad = _snapshots(home=home)[0]
    bad.parent.mkdir(parents=True)
    _ = bad.write_text('{"claudeAiOauth": {"refreshToken": "' + REFRESH, encoding="utf-8")
    plain = _snapshots(home=home)[1]
    _cred(path=plain, refresh=False)
    no_oauth = _snapshots(home=home)[2]
    no_oauth.parent.mkdir(parents=True)
    _ = no_oauth.write_text(json.dumps({"mcpOAuth": {}}), encoding="utf-8")
    code, out = _run(proc=_proc(tmp_path=tmp_path), capsys=capsys)
    assert code != 0
    assert f"unreadable {bad}" in out
    assert f"residue {bad}" in out
    assert f"clean {plain} " in out
    assert f"clean {no_oauth} " in out
    assert "FAIL refresh tokens may remain: unreadable=1 failed=0 residue=1" in out
    assert REFRESH not in out


def test_a_failed_write_leaves_the_file_intact_and_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = _home(tmp_path=tmp_path, monkeypatch=monkeypatch)
    live = home / ".claude/.credentials.json"
    _cred(path=live)
    before = live.read_bytes()
    stale_tmp = live.with_name(".credentials.json.strip-tmp")
    _ = stale_tmp.write_text("old", encoding="utf-8")

    def _refuse(*, src: Path, dst: Path) -> None:
        del src, dst
        raise OSError("disk full")

    monkeypatch.setattr(_strip().os, "replace", _refuse)
    code, out = _run(proc=_proc(tmp_path=tmp_path), capsys=capsys)
    assert code != 0
    assert live.read_bytes() == before
    assert f"failed {live} OSError" in out
    assert f"residue {live}" in out
    assert not stale_tmp.exists()
