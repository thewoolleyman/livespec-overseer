"""The production terminal releases command output only through its sanitizer."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from types import ModuleType

from overseer._lpm_observations import ObservationSanitizer

__all__: list[str] = []

_TOKEN = "sk-ant-oat01-partial"


def _write_terminal_standin(*, path: Path, invalid_utf8: bool = False) -> None:
    body = (
        "import os\nos.write(1, b'\\xff')\n"
        if invalid_utf8
        else """import os
os.write(1, b"prefix sk-ant-oat01-par")
os.read(0, 4096)
os.write(1, b"tial suffix\\n")
os.write(2, b"stderr-safe\\n")
"""
    )
    path.write_text(f"#!/usr/bin/env python3\n{body}", encoding="utf-8")
    path.chmod(0o755)


def _write_split_utf8_standin(*, path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "os.write(1, b'before \\xe2')\n"
        "os.read(0, 4096)\n"
        "os.write(1, b'\\x82\\xac after\\n')\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _command(*, module: ModuleType, path: Path) -> object:
    status = path.stat()
    return module.ExecutionCommand(
        path=str(path.resolve()),
        device=status.st_dev,
        inode=status.st_ino,
        arguments=(),
    )


def _sanitizer() -> ObservationSanitizer:
    def token_handle(*, value: str) -> str:
        assert value == _TOKEN
        return "terminal:opaque"

    return ObservationSanitizer(
        token_handles={},
        sensitive_values=frozenset(),
        new_token_handle=token_handle,
    )


def _assert_incremental_sanitized_output(*, module: ModuleType, tmp_path: Path) -> None:
    executable = tmp_path / "execution-command"
    _write_terminal_standin(path=executable)
    performer = module.TerminalPerformer(
        command=_command(module=module, path=executable),
        sanitizer=_sanitizer(),
        environ={
            "PATH": os.environ["PATH"],
            "CLAUDE_CODE_OAUTH_TOKEN": "must-not-cross",
        },
        read_timeout_seconds=0.5,
    )
    assert performer.observe().response == {"version": 1, "status": "unavailable"}
    assert performer.send_line(text="not-started") == {"version": 1, "status": "unavailable"}
    assert performer.start() == {"version": 1, "status": "ok"}
    assert performer.start() == {"version": 1, "status": "unavailable"}

    first = performer.observe()
    assert first.response["stdout"] == "prefix "
    assert _TOKEN not in repr(first)
    assert performer.send_line(text="continue") == {"version": 1, "status": "ok"}
    observations = [first]
    for _ in range(5):
        observed = performer.observe()
        observations.append(observed)
        if observed.response.get("running") is False:
            break
    assert observations[-1].response["running"] is False
    stdout = "".join(str(item.response.get("stdout", "")) for item in observations)
    stderr = "".join(str(item.response.get("stderr", "")) for item in observations)
    assert stdout == "prefix [[redacted-token:terminal:opaque]] suffix\n"
    assert stderr == "stderr-safe\n"
    assert _TOKEN not in repr(observations)
    performer.close()


def _assert_bad_reference_and_spawn_refuse(*, module: ModuleType, tmp_path: Path) -> None:
    executable = tmp_path / "bad-reference"
    _write_terminal_standin(path=executable)
    command = _command(module=module, path=executable)
    stale = module.TerminalPerformer(
        command=replace(command, inode=0),
        sanitizer=_sanitizer(),
        environ={"PATH": os.environ["PATH"]},
        read_timeout_seconds=0.0,
    )
    assert stale.start() == {"version": 1, "status": "unavailable"}

    unspawnable = tmp_path / "unspawnable"
    unspawnable.write_text("not an executable format", encoding="utf-8")
    unspawnable.chmod(0o755)
    refused = module.TerminalPerformer(
        command=_command(module=module, path=unspawnable),
        sanitizer=_sanitizer(),
        environ={"PATH": os.environ["PATH"]},
        read_timeout_seconds=0.0,
    )
    assert refused.start() == {"version": 1, "status": "unavailable"}


def _assert_lifecycle_races_refuse(*, module: ModuleType, tmp_path: Path) -> None:
    disappeared = tmp_path / "disappeared"
    _write_terminal_standin(path=disappeared)
    command = _command(module=module, path=disappeared)
    disappeared.unlink()
    performer = module.TerminalPerformer(
        command=command,
        sanitizer=_sanitizer(),
        environ={"PATH": os.environ["PATH"]},
        read_timeout_seconds=0.0,
    )
    assert performer.start() == {"version": 1, "status": "unavailable"}

    exited = tmp_path / "exited-before-write"
    exited.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    exited.chmod(0o755)
    performer = replace(
        performer,
        command=_command(module=module, path=exited),
        read_timeout_seconds=0.5,
    )
    assert performer.start() == {"version": 1, "status": "ok"}
    for _ in range(5):
        if performer.observe().response.get("running") is False:
            break
    assert performer.send_line(text="too-late") == {"version": 1, "status": "unavailable"}
    performer.close()


def _assert_split_utf8_is_incremental(*, module: ModuleType, tmp_path: Path) -> None:
    executable = tmp_path / "split-utf8"
    _write_split_utf8_standin(path=executable)
    performer = module.TerminalPerformer(
        command=_command(module=module, path=executable),
        sanitizer=_sanitizer(),
        environ={"PATH": os.environ["PATH"]},
        read_timeout_seconds=0.5,
    )
    assert performer.start() == {"version": 1, "status": "ok"}
    first = performer.observe()
    assert first.response["stdout"] == "before "
    assert performer.send_line(text="continue") == {"version": 1, "status": "ok"}
    observations = [first]
    for _ in range(5):
        observed = performer.observe()
        observations.append(observed)
        if observed.response.get("running") is False:
            break
    assert "".join(str(item.response.get("stdout", "")) for item in observations) == (
        "before € after\n"
    )
    performer.close()


def _assert_invalid_output_is_unavailable(*, module: ModuleType, tmp_path: Path) -> None:
    executable = tmp_path / "invalid-output"
    _write_terminal_standin(path=executable, invalid_utf8=True)
    performer = module.TerminalPerformer(
        command=_command(module=module, path=executable),
        sanitizer=_sanitizer(),
        environ={"PATH": os.environ["PATH"]},
        read_timeout_seconds=0.5,
    )
    assert performer.start() == {"version": 1, "status": "ok"}
    assert performer.observe().response == {"version": 1, "status": "unavailable"}
    performer.close()


def test_terminal_performer_releases_execution_output_only_through_incremental_sanitizer(
    *, tmp_path: Path
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_terminal_performer.py"
    assert module_path.is_file(), "the production terminal performer must exist"

    import overseer._lpm_terminal_performer as module

    _assert_incremental_sanitized_output(module=module, tmp_path=tmp_path)
    _assert_bad_reference_and_spawn_refuse(module=module, tmp_path=tmp_path)
    _assert_lifecycle_races_refuse(module=module, tmp_path=tmp_path)
    _assert_split_utf8_is_incremental(module=module, tmp_path=tmp_path)
    _assert_invalid_output_is_unavailable(module=module, tmp_path=tmp_path)
