"""The live exercise binds exactly what the agent client's launcher executes, read-only.

Measured on the release host 2026-10-22 (work-item `overseer-fr8f`): `~/.local/bin/codex`
is a bash shim whose exec line runs the bun global install -- `exec ~/.bun/bin/bun
~/.bun/bin/codex "$@"` -- and the runner bound the shim as ONE FILE. The scratch home hid
`~/.bun`, so Codex never started inside the namespace.

The fixture below is that shape, plus the other home paths such a shim legitimately
NAMES: a `BUN_INSTALL`, an `XDG_CONFIG_HOME`, a cache directory. None of them may be
bound. A first attempt at this fix (PR #2573) bound every home path the launcher named
minus a denylist of the roots the exercise writes, and could not converge -- each review
round found one more named path. Resolving what the launcher EXECUTES makes the bound set
ONE path by construction, so it cannot grow with the launcher's prose.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent.parent
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"
_MOUNT_OPTIONS = frozenset({"--bind", "--ro-bind"})

# The release-host shim shape: a bash launcher that exports three other home paths and
# then execs the bun runtime against the bun-installed Codex script.
_LAUNCHER_BODY = """#!/usr/bin/env bash
export BUN_INSTALL="$HOME/.bun"
export XDG_CONFIG_HOME="$HOME/.config"
export CODEX_CACHE_DIR="$HOME/.cache/codex"
exec "$HOME/.bun/bin/bun" "$HOME/.bun/bin/codex" "$@"
"""


class _Client:
    """The fixture's launcher, the tree it executes, and the home paths it only names."""

    def __init__(self, *, home: Path) -> None:
        self.home = home
        self.install_root = home / ".bun"
        self.runtime = self.install_root / "bin" / "bun"
        self.entry = self.install_root / "bin" / "codex"
        self.launcher = home / ".local" / "bin" / "codex"
        self.named_only = (home / ".config", home / ".cache" / "codex")


def _client(*, home: Path) -> _Client:
    client = _Client(home=home)
    client.runtime.parent.mkdir(parents=True)
    client.runtime.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    client.runtime.chmod(0o755)
    client.entry.write_text("// codex\n", encoding="utf-8")
    for path in client.named_only:
        path.mkdir(parents=True)
    client.launcher.parent.mkdir(parents=True)
    client.launcher.write_text(_LAUNCHER_BODY, encoding="utf-8")
    client.launcher.chmod(0o755)
    return client


def _plan(*, tmp_path: Path) -> tuple[_Client, list[str]]:
    home = tmp_path / "home"
    home.mkdir()
    client = _client(home=home)
    evidence = tmp_path / "evidence"
    environment = {
        **os.environ,
        "HOME": str(home),
        "TMPDIR": str(tmp_path),
        "PATH": f"{client.launcher.parent}{os.pathsep}{os.environ['PATH']}",
    }
    subprocess.run(  # noqa: S603 -- fixed repo-owned script.
        [
            str(LIVE_EXERCISE),
            "run",
            "--plan-only",
            "--backend",
            "herdr",
            "--agent",
            "codex",
            "--topic",
            "client-install-root",
            "--checkout",
            str(ROOT),
            "--evidence",
            str(evidence),
            "--",
            "/bin/true",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=environment,
    )
    return client, (evidence / "namespace.argv").read_text(encoding="utf-8").splitlines()


def _mounts(*, argv: list[str]) -> list[tuple[str, str, str]]:
    return [
        (token, argv[index + 1], argv[index + 2])
        for index, token in enumerate(argv)
        if token in _MOUNT_OPTIONS
    ]


def _under(*, source: str, home: Path) -> bool:
    return source == str(home) or source.startswith(f"{home}{os.sep}")


def test_no_operator_home_path_reaches_the_namespace_through_a_writable_bind(
    tmp_path: Path,
) -> None:
    client, argv = _plan(tmp_path=tmp_path)
    mounts = _mounts(argv=argv)

    writable = [source for option, source, _ in mounts if option == "--bind"]
    assert not [one for one in writable if _under(source=one, home=client.home)]
    # Vacuously true of a runner that binds no home content at all, so the same case
    # asserts the content the client DOES need arrived -- read-only, which is the only
    # way an operator-home path may reach this namespace.
    read_only = {(source, target) for option, source, target in mounts if option == "--ro-bind"}
    assert (str(client.install_root), str(client.install_root)) in read_only
    assert (str(client.launcher), str(client.launcher)) in read_only


def test_the_install_root_of_what_the_launcher_executes_is_bound_read_only(
    tmp_path: Path,
) -> None:
    client, argv = _plan(tmp_path=tmp_path)
    mounts = _mounts(argv=argv)

    assert ("--ro-bind", str(client.install_root), str(client.install_root)) in mounts
    sources = {source for _, source, _ in mounts}
    # The install root is the FIRST directory below the operator home on the real path of
    # the program the exec line runs: neither the directory holding that program, nor any
    # parent of the root, stands in for it.
    assert str(client.runtime.parent) not in sources
    assert str(client.home) not in sources
    # Every client bind must be layered over the scratch home that hides it.
    scratch_home = argv.index(str(client.home))
    assert argv.index(str(client.install_root)) > scratch_home
    assert argv.index(str(client.launcher)) > scratch_home


def test_no_other_operator_home_path_is_bound_for_the_agent_client(tmp_path: Path) -> None:
    client, argv = _plan(tmp_path=tmp_path)

    bound = sorted(
        {source for _, source, _ in _mounts(argv=argv) if _under(source=source, home=client.home)}
    )
    assert bound == sorted([str(client.install_root), str(client.launcher)])
    # Restating the consequence the denylist approach could never reach: the home paths
    # the launcher merely NAMES are hidden by the scratch home, named or not.
    for path in client.named_only:
        assert str(path) not in bound
