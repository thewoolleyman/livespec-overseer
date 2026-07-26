"""Corrupt-input arms for claude_sessions.py's `/proc` readers, on a FAKE `/proc`.

Split from `test_claude_sessions.py`, which passed the 250-LLOC hard ceiling when the
keyword-only conversion (`overseer-bg2.9`) widened its seam substitutes. The seam is
the one that module already documented with a section banner: everything here drives
the readers against a REDIRECTED module-level `Path`, so no live process is read,
while the retained module checks them against THIS test process.

The module's documented guarantee is that a truncated `stat` line or a garbled
`children` token — exactly what a pid dying mid-read yields — degrades ONE reader to
None/[] rather than raising.
"""

import json
from pathlib import Path

import claude_sessions

__all__: list[str] = []


def _write(*, directory, pid, name, cwd, proc_start, status="idle"):
    """The registry-record writer, shared with the retained module by duplication.

    Two lines is cheaper than a third module or a cross-import between beside-tests,
    and it keeps each half independently readable.
    """
    payload = {"pid": pid, "name": name, "cwd": cwd, "procStart": proc_start, "status": status}
    (directory / f"{pid}.json").write_text(json.dumps(payload), encoding="utf-8")


# --------------------------------------------------------------------------- #
# The /proc readers' CORRUPT-INPUT arms, driven against a FAKE /proc tree.
#
# The readers above are checked against this live process, which can only ever
# produce well-formed input. A truncated `stat` line or a garbled `children`
# token is exactly what a pid dying mid-read yields, and the module's documented
# guarantee is that such a read degrades ONE reader to None/[] rather than
# raising. `/proc` is interpolated directly in these readers (it IS the host
# coupling the injected seams replace elsewhere), so the module-level `Path` is
# redirected at a tmp tree — no live process is read.
# --------------------------------------------------------------------------- #


def _fake_proc(*, tmp_path, monkeypatch):
    """Point the module's hardcoded ``/proc`` reads at a writable tmp tree."""
    root = tmp_path / "proc"
    root.mkdir(exist_ok=True)

    def _redirect(arg):
        text = str(arg)
        if text == "/proc":
            return root
        if text.startswith("/proc/"):
            return root / text[len("/proc/") :]
        return Path(text)

    monkeypatch.setattr(claude_sessions, "Path", _redirect)
    return root


def _write_stat(*, root, pid, text):
    (root / str(pid)).mkdir(parents=True, exist_ok=True)
    (root / str(pid) / "stat").write_text(text, encoding="utf-8")


def test_proc_readers_are_none_when_the_stat_line_has_no_comm_parens(*, tmp_path, monkeypatch):
    # `stat` is split AFTER the LAST `)` (comm may itself contain spaces and parens).
    # A line carrying no `)` at all — a truncated read of a vanishing pid — must yield
    # None from both readers rather than a mis-split field.
    root = _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    _write_stat(root=root, pid=100, text="100 truncated-with-no-parens 12345")
    assert claude_sessions.proc_ppid(pid=100) is None
    assert claude_sessions.proc_starttime(pid=100) is None


def test_proc_ppid_is_none_when_the_ppid_field_is_not_a_number(*, tmp_path, monkeypatch):
    # A garbled ppid degrades that ONE reader to None; the SAME line's start-time
    # (field 22) is still read, so one corrupt field never blinds the liveness check.
    root = _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fields = ["S", "not-a-pid"] + ["0"] * 17 + ["99887766"]
    _write_stat(root=root, pid=100, text="100 (cla ude) " + " ".join(fields))
    assert claude_sessions.proc_ppid(pid=100) is None
    assert claude_sessions.proc_starttime(pid=100) == "99887766"


def test_proc_children_skips_a_non_numeric_token(*, tmp_path, monkeypatch):
    # The children file is whitespace-separated pids; a garbled token is dropped and
    # the readable pids still come back — fail-soft per TOKEN, not per file.
    root = _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    children = root / "100" / "task" / "100"
    children.mkdir(parents=True)
    (children / "children").write_text("200 not-a-pid 300\n", encoding="utf-8")
    assert claude_sessions.proc_children(pid=100) == [200, 300]


def test_proc_children_is_empty_on_an_undecodable_children_file(*, tmp_path, monkeypatch):
    """Defence-in-depth, and labelled as such rather than overstated.

    The real kernel writes this file as ASCII pids and whitespace, so it CANNOT fail
    to decode — this state is unreachable in production and is only constructible
    against the fake ``/proc`` used here. The handler was widened anyway so every read
    boundary in the package carries ONE rule, and this test pins that choice so a
    later narrowing back to ``except OSError`` is a deliberate act rather than a
    silent regression.
    """
    root = _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    children = root / "100" / "task" / "100"
    children.mkdir(parents=True)
    (children / "children").write_bytes(b"\xff\xfe200 300\n")
    assert claude_sessions.proc_children(pid=100) == []


def test_read_live_sessions_is_fail_soft_when_the_registry_dir_cannot_be_listed(
    *, tmp_path, monkeypatch
):
    # An unlistable registry dir (an EIO/ESTALE directory scan) yields NO sessions
    # instead of propagating — one bad reader must never crash a daemon tick. Stubbed
    # rather than chmod'ed because `Path.glob` swallows the ordinary EACCES case itself.
    class _UnlistableDir:
        def glob(self, _pattern):
            raise OSError(5, "Input/output error")

    monkeypatch.setattr(claude_sessions, "Path", lambda _path: _UnlistableDir())
    assert (
        claude_sessions.read_live_sessions(sessions_dir=tmp_path, starttime_of=lambda *, pid: "111")
        == []
    )


def test_read_live_sessions_skips_records_with_wrongly_typed_fields(*, tmp_path):
    # pid/name/cwd of the wrong TYPE are skipped, never coerced: a corrupt registry
    # file degrades to "that one session is invisible", and the good ones still read.
    (tmp_path / "1.json").write_text(
        json.dumps({"pid": "100", "name": "alpha", "cwd": "/r/a", "procStart": "444"}),
        encoding="utf-8",
    )
    (tmp_path / "2.json").write_text(
        json.dumps({"pid": 200, "name": ["beta"], "cwd": "/r/b", "procStart": "444"}),
        encoding="utf-8",
    )
    (tmp_path / "3.json").write_text(
        json.dumps({"pid": 300, "name": "gamma", "cwd": 7, "procStart": "444"}),
        encoding="utf-8",
    )
    _write(directory=tmp_path, pid=400, name="delta", cwd="/r/d", proc_start="444")

    live = claude_sessions.read_live_sessions(
        sessions_dir=tmp_path, starttime_of=lambda *, pid: "444"
    )
    assert [(s.pid, s.name) for s in live] == [(400, "delta")]


def test_resolve_tmux_session_gives_up_after_the_bounded_parent_walk():
    # The walk is BOUNDED, not merely cycle-guarded: an unbroken ancestor chain (every
    # pid distinct, so the visited-set never fires) whose pane PID sits beyond the bound
    # returns None rather than climbing forever.
    got = claude_sessions.resolve_tmux_session(
        pid=100, pane_pid_to_session={1000: "far-away"}, ppid_of=lambda *, pid: pid + 1
    )
    assert got is None
