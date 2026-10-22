"""The isolated live exercise runs the installed agent client, or refuses before starting.

Integration-tier coverage for the isolated live exercise's agent-client contract, stated
in `SPECIFICATION/spec.md` and scenarized in `SPECIFICATION/scenarios.md` at v065.

Measured on the release host 2026-10-22 (work-item `overseer-fr8f`): `~/.local/bin/codex`
is a 368-byte bash shim that execs the bun global install under `~/.bun`, and the runner
bound the shim FILE alone. The scratch home hides `~/.bun`, so Codex never reached its
input prompt and the mismatch surfaced as a FAILED `bootstrap` lifecycle stage of the
authenticated run (evidence run 2026-10-22T04:31Z) rather than as a refusal before the
backend started.

These tests drive the real checked-in runner the way the operator does, on a PATH built
from symlinks so the verdict cannot depend on which agent clients the host happens to
have installed. The namespace itself is never started: the factory sandbox is denied
namespace creation, so the authenticated idle-prompt leg of the scenario remains a
host-captured release obligation. What is capturable here is the bind plan the runner
builds and the refusal it owes before any terminal backend starts.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

__all__: list[str] = []

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"

# Everything the runner itself executes before it starts a namespace. `bwrap` is
# deliberately ABSENT: these tests must never attempt namespace creation, and a refusal
# that named the client only after the `bwrap` probe would be invisible on a host without
# it.
_RUNNER_TOOLS = (
    "basename",
    "bash",
    "cat",
    "chmod",
    "cp",
    "dirname",
    "env",
    "find",
    "git",
    "grep",
    "head",
    "id",
    "install",
    "mkdir",
    "mktemp",
    "python3",
    "realpath",
    "rm",
    "sed",
    "sort",
)


def _runner_path(*, tmp_path: Path) -> Path:
    """Return a bin directory holding ONLY the tools the runner needs.

    No agent client can leak in from the ambient PATH, so "absent from PATH" is a
    property of the fixture rather than of the host the suite runs on.
    """
    bin_dir = tmp_path / "runner-bin"
    bin_dir.mkdir()
    for tool in _RUNNER_TOOLS:
        resolved = shutil.which(tool)
        assert resolved is not None, f"the live-exercise runner needs {tool} on PATH"
        (bin_dir / tool).symlink_to(resolved)
    return bin_dir


def _run(
    *, home: Path, path: str, agent: str, topic: str, evidence: Path, plan_only: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- fixed repo-owned script.
        [
            str(LIVE_EXERCISE),
            "run",
            *(["--plan-only"] if plan_only else []),
            "--backend",
            "tmux",
            "--agent",
            agent,
            "--topic",
            topic,
            "--checkout",
            str(ROOT),
            "--evidence",
            str(evidence),
            "--",
            "/bin/true",
        ],
        check=False,
        text=True,
        capture_output=True,
        env={"HOME": str(home), "PATH": path, "TMPDIR": os.environ.get("TMPDIR", "/tmp")},
    )


def _bun_style_launcher(*, home: Path) -> Path:
    """Install the release host's own shape: a bash shim into a bun global install."""
    launcher = home / ".local" / "bin" / "codex"
    launcher.parent.mkdir(parents=True)
    launcher.write_text(
        '#!/usr/bin/env bash\nexec "$HOME/.bun/bin/bun" "$HOME/.bun/bin/codex" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    return launcher


def _bun_install_tree(*, home: Path) -> Path:
    """Install what that shim actually runs: the bun global install under `~/.bun`."""
    install = home / ".bun"
    binaries = install / "bin"
    binaries.mkdir(parents=True)
    bun = binaries / "bun"
    bun.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    bun.chmod(0o755)
    (binaries / "codex").write_text("// the entry point the shim hands to bun\n", encoding="utf-8")
    return install


def _local_install_launcher(*, home: Path, agent: str) -> Path:
    """Install a launcher whose install tree IS the state the scratch home provides.

    Claude Code's local install puts the client under `~/.claude` and Codex's own
    configuration lives at `~/.codex`, which are exactly the subtrees the scratch home
    replaces and the runner installs the supplied `--credential` into.
    """
    launcher = home / ".local" / "bin" / agent
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        f'#!/usr/bin/env bash\nexec "$HOME/.{agent}/local/{agent}" "$@"\n', encoding="utf-8"
    )
    launcher.chmod(0o755)
    client = home / f".{agent}" / "local" / agent
    client.parent.mkdir(parents=True)
    client.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    client.chmod(0o755)
    return launcher


def _plan_argv(*, home: Path, path: str, agent: str, topic: str, evidence: Path) -> list[str]:
    completed = _run(
        home=home, path=path, agent=agent, topic=topic, evidence=evidence, plan_only=True
    )
    assert completed.returncode == 0, completed.stderr
    return (evidence / "namespace.argv").read_text(encoding="utf-8").splitlines()


def _ro_binds(*, argv: list[str]) -> list[tuple[str, ...]]:
    return [tuple(argv[i : i + 3]) for i, token in enumerate(argv) if token == "--ro-bind"]


def test_the_agent_clients_install_tree_is_bound_read_only(*, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    install = _bun_install_tree(home=home)
    launcher = _bun_style_launcher(home=home)
    evidence = tmp_path / "evidence"

    argv = _plan_argv(
        home=home,
        path=f"{launcher.parent}:{_runner_path(tmp_path=tmp_path)}",
        agent="codex",
        topic="launcher-install",
        evidence=evidence,
    )

    mounts = _ro_binds(argv=argv)
    assert ("--ro-bind", str(launcher), str(launcher)) in mounts
    assert ("--ro-bind", str(install), str(install)) in mounts
    # Both sit BENEATH the scratch-home bind, or the scratch home would hide them again.
    home_bind = argv.index(str(home))
    assert argv.index(str(install)) > home_bind
    assert argv.index(str(launcher)) > home_bind


def _recorded_scratch_root(*, evidence: Path) -> str:
    isolation = (evidence / "isolation.env").read_text(encoding="utf-8").splitlines()
    recorded = [
        line.removeprefix("scratch_root=") for line in isolation if line.startswith("scratch_root=")
    ]
    assert len(recorded) == 1, isolation
    return recorded[0]


def test_the_namespace_binds_no_writable_operator_home_path(*, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    install = _bun_install_tree(home=home)
    launcher = _bun_style_launcher(home=home)
    evidence = tmp_path / "evidence"

    argv = _plan_argv(
        home=home,
        path=f"{launcher.parent}:{_runner_path(tmp_path=tmp_path)}",
        agent="codex",
        topic="writable-scope",
        evidence=evidence,
    )

    scratch_root = _recorded_scratch_root(evidence=evidence)
    writable = [tuple(argv[i : i + 3]) for i, token in enumerate(argv) if token == "--bind"]
    sources = [source for _, source, _ in writable]
    assert sources, argv
    for source in sources:
        permitted = source == str(evidence) or source.startswith(f"{scratch_root}/")
        assert permitted, f"{source} is writable inside the namespace but is not runner scratch"
    # The client's launcher and its install tree reach the namespace READ-ONLY. Making
    # either writable would hand an exercise run the operator's own install.
    assert str(install) not in sources
    assert str(launcher) not in sources
    assert ("--ro-bind", str(install), str(install)) in _ro_binds(argv=argv)


def test_an_agent_client_absent_from_path_refuses_before_any_backend_starts(
    *, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    evidence = tmp_path / "evidence"

    completed = _run(
        home=home,
        path=str(_runner_path(tmp_path=tmp_path)),
        agent="codex",
        topic="client-absent",
        evidence=evidence,
    )

    assert completed.returncode == 2, completed.stderr
    assert "codex" in completed.stderr
    assert not (evidence / "lifecycle.jsonl").exists(), completed.stderr
    assert not (evidence / "backend-runtime.env").exists(), completed.stderr


def test_no_install_root_rebinds_the_agent_state_the_scratch_home_replaces(
    *, tmp_path: Path
) -> None:
    """A launcher's install root may never re-expose the operator's own agent state.

    The scratch home exists to hide `~/.claude` and `~/.codex`: the operator's real
    credentials, the Claude session registry the daemon's adoption reads, and the
    `--credential` this runner installs into the scratch copy. Binding such a root back
    over the scratch home would hand the run the operator's own credential, shadow the
    supplied one, and leave the path read-only for a client that must write its session
    registry there.
    """
    home = tmp_path / "home"
    home.mkdir()
    launcher = _local_install_launcher(home=home, agent="claude")
    evidence = tmp_path / "evidence"

    argv = _plan_argv(
        home=home,
        path=f"{launcher.parent}:{_runner_path(tmp_path=tmp_path)}",
        agent="claude",
        topic="scratch-collision",
        evidence=evidence,
    )

    assert ("--ro-bind", str(launcher), str(launcher)) in _ro_binds(argv=argv)
    assert str(home / ".claude") not in argv, argv


def test_a_client_installed_where_the_scratch_home_replaces_it_refuses_by_name(
    *, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    launcher = _local_install_launcher(home=home, agent="codex")
    evidence = tmp_path / "evidence"

    completed = _run(
        home=home,
        path=f"{launcher.parent}:{_runner_path(tmp_path=tmp_path)}",
        agent="codex",
        topic="scratch-collision-refusal",
        evidence=evidence,
    )

    assert completed.returncode == 2, completed.stderr
    assert str(launcher) in completed.stderr
    assert str(home / ".codex") in completed.stderr
    assert not (evidence / "lifecycle.jsonl").exists(), completed.stderr
    assert not (evidence / "backend-runtime.env").exists(), completed.stderr


def test_an_unresolvable_script_launcher_refuses_and_names_the_client_path(
    *, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    launcher = _bun_style_launcher(home=home)
    evidence = tmp_path / "evidence"
    runner_bin = _runner_path(tmp_path=tmp_path)

    completed = _run(
        home=home,
        path=f"{launcher.parent}:{runner_bin}",
        agent="codex",
        topic="launcher-unresolvable",
        evidence=evidence,
    )

    assert completed.returncode == 2, completed.stderr
    assert str(launcher) in completed.stderr
    assert not (evidence / "lifecycle.jsonl").exists(), completed.stderr
    assert not (evidence / "backend-runtime.env").exists(), completed.stderr
