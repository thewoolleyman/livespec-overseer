"""Tests for tmuxio.py — the WRITE half of the tmux subprocess boundary.

Split from `test_tmuxio.py`, which carried reads and writes together and crossed
the 250-LLOC hard ceiling. The seam is the one the file already documented with
section banners, so no test changed meaning in the move: this module owns
send-keys, bracketed paste, respawn, session/window/pane construction, and
layout; `test_tmuxio.py` keeps reads and the fail-soft/liveness guarantees.

No REAL tmux runs: a fake ``run`` callable (same shape as ``subprocess.run``) is
injected from `test_tmuxio_fakes`, so assertions are on the exact argv tmux
would be invoked with.
"""

from test_tmuxio_fakes import io as _io

__all__: list[str] = []

# --------------------------------------------------------------------------- #
# Writes.
# --------------------------------------------------------------------------- #


def test_send_keys_argv():
    io, fake = _io()
    assert io.send_keys(session="s", keys="Enter") is True
    assert fake.calls[0]["argv"] == ["tmux", "send-keys", "-t", "s", "Enter"]


def test_bracketed_paste_loads_then_pastes_with_stdin():
    io, fake = _io()
    assert io.bracketed_paste(session="livespec--t", text="line1\nline2") is True
    # First call loads the buffer from stdin; second pastes bracketed + deletes.
    load_argv = fake.calls[0]["argv"]
    assert load_argv[:3] == ["tmux", "load-buffer", "-b"]
    buffer_name = load_argv[3]
    # B6: the buffer name is UNIQUE per paste (pid + counter), not the fixed global.
    assert buffer_name.startswith("overseer-inject-")
    assert load_argv[4] == "-"
    assert fake.calls[0]["input"] == "line1\nline2"
    # the SAME unique buffer is pasted then deleted.
    assert fake.calls[1]["argv"] == [
        "tmux",
        "paste-buffer",
        "-b",
        buffer_name,
        "-p",
        "-d",
        "-t",
        "livespec--t",
    ]


def test_bracketed_paste_false_when_load_fails():
    io, _ = _io(returncode=1)
    assert io.bracketed_paste(session="s", text="x") is False


def test_respawn_pane_argv_is_kill_and_cwd():
    io, fake = _io()
    assert (
        io.respawn_pane(session="livespec:t", cwd="/data/projects/livespec", command="claude -n t")
        is True
    )
    assert fake.calls[0]["argv"] == [
        "tmux",
        "respawn-pane",
        "-k",
        "-c",
        "/data/projects/livespec",
        "-t",
        "livespec:t",
        "claude -n t",
    ]


def test_new_session_argv():
    io, fake = _io()
    assert io.new_session(name="livespec:t", cwd="/data/projects/livespec") is True
    assert fake.calls[0]["argv"] == [
        "tmux",
        "new-session",
        "-d",
        "-s",
        "livespec:t",
        "-c",
        "/data/projects/livespec",
    ]


def test_split_window_top_argv_and_pane_id():
    # The two-pane bootstrap: split THIS pane's window, new pane ABOVE (-b -v),
    # keep focus (-d), print the new pane id (-P -F). Target is the skill's own
    # $TMUX_PANE — never a session grabbed by name.
    io, fake = _io(stdout="%47\n")
    assert (
        io.split_window_top(pane="%20", cwd="/data/projects/livespec", command="overseerd") == "%47"
    )
    assert fake.calls[0]["argv"] == [
        "tmux",
        "split-window",
        "-v",
        "-b",
        "-d",
        "-P",
        "-F",
        "#{pane_id}",
        "-t",
        "%20",
        "-c",
        "/data/projects/livespec",
        "overseerd",
    ]
    io2, _ = _io(returncode=1)  # split failed → None (fail-soft)
    assert io2.split_window_top(pane="%20", cwd="/tmp", command="overseerd") is None
    io3, _ = _io(stdout="   \n")  # empty pane id → None
    assert io3.split_window_top(pane="%20", cwd="/tmp", command="overseerd") is None


def test_set_pane_title_argv():
    io, fake = _io()
    assert io.set_pane_title(pane="%47", title="overseer-daemon") is True
    assert fake.calls[0]["argv"] == [
        "tmux",
        "select-pane",
        "-t",
        "%47",
        "-T",
        "overseer-daemon",
    ]


def test_select_layout_even_argv():
    io, fake = _io()
    assert io.select_layout_even(pane="%20") is True
    assert fake.calls[0]["argv"] == ["tmux", "select-layout", "-t", "%20", "even-vertical"]
    io2, _ = _io(returncode=1)  # fail-soft
    assert io2.select_layout_even(pane="%20") is False


def test_pane_by_title_finds_matching_pane_id():
    # The idempotent-path read: which pane in THIS window carries the title.
    io, fake = _io(stdout="%20\tzsh\n%47\toverseer-daemon\n")
    assert io.pane_by_title(pane="%20", title="overseer-daemon") == "%47"
    assert fake.calls[0]["argv"] == [
        "tmux",
        "list-panes",
        "-t",
        "%20",
        "-F",
        "#{pane_id}\t#{pane_title}",
    ]
    io2, _ = _io(stdout="%20\tzsh\n")  # title absent in this window → None
    assert io2.pane_by_title(pane="%20", title="overseer-daemon") is None
    io3, _ = _io(returncode=1)  # list failed → None (fail-soft)
    assert io3.pane_by_title(pane="%20", title="overseer-daemon") is None


def test_set_pane_height_percent_argv():
    # Percentage sizing (tmux 3.5a) — the `%` suffix is what makes it a share of
    # the window rather than an absolute row count.
    io, fake = _io()
    assert io.set_pane_height_percent(pane="%47", percent=25) is True
    assert fake.calls[0]["argv"] == ["tmux", "resize-pane", "-t", "%47", "-y", "25%"]
    io2, _ = _io(returncode=1)  # fail-soft
    assert io2.set_pane_height_percent(pane="%47", percent=25) is False


def test_rename_window_renames_then_pins_automatic_rename_off():
    # Pinning is PART of renaming: without `automatic-rename off` tmux re-derives
    # the window name from its foreground command and overwrites NAME.
    io, fake = _io()
    assert io.rename_window(pane="%20", name="overseer") is True
    assert fake.calls[0]["argv"] == ["tmux", "rename-window", "-t", "%20", "overseer"]
    assert fake.calls[1]["argv"] == [
        "tmux",
        "set-window-option",
        "-t",
        "%20",
        "automatic-rename",
        "off",
    ]


def test_rename_window_false_when_rename_fails_and_skips_the_pin():
    io, fake = _io(returncode=1)
    assert io.rename_window(pane="%20", name="overseer") is False
    # the pin is never attempted once the rename itself failed
    assert len(fake.calls) == 1


def test_window_pane_titles_parses_and_fail_soft():
    io, fake = _io(stdout="overseer-daemon\nzsh\n\n")
    assert io.window_pane_titles(pane="%20") == ["overseer-daemon", "zsh"]
    assert fake.calls[0]["argv"] == ["tmux", "list-panes", "-t", "%20", "-F", "#{pane_title}"]
    io2, _ = _io(returncode=1)
    assert io2.window_pane_titles(pane="%20") == []
