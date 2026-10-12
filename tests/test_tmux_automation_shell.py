"""The shared tmux session builder marks automation-owned shells."""

from test_tmuxio_fakes import io as _io

__all__: list[str] = []


def test_overseer_new_session_argv_marks_the_automation_shell() -> None:
    io, fake = _io()

    assert io.new_session(name="livespec:t", cwd="/data/projects/livespec") is True
    assert fake.calls[0]["argv"] == [
        "tmux",
        "new-session",
        "-e",
        "LIVESPEC_AUTOMATION_SHELL=1",
        "-d",
        "-s",
        "livespec:t",
        "-c",
        "/data/projects/livespec",
    ]
