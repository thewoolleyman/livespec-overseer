"""Chrooted installed-distribution fixture for LPM subprocess scenarios."""

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from overseer.test_lpm_installed_runtime import copy_installed_python, copy_shell_runtime

__all__: list[str] = [
    "InstalledManagerSandbox",
    "ManagerResult",
]

_UID = 1000
_GID = 1000
_CONSOLE = "/opt/lpm/bin/llm-provider-manager"
_PLUGIN = "/plugin/bin/llm-provider-manager"
_PATH = "/opt/lpm/bin:/usr/bin:/bin"


@dataclass(frozen=True, kw_only=True)
class ManagerResult:
    """One installed launcher completion and its decoded wire object."""

    executable: str
    exit_status: int
    stdout: str
    stderr: str
    body: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class InstalledManagerSandbox:
    """A private account database and filesystem around one clean package install."""

    root: Path
    repository: Path

    @classmethod
    def create(cls, *, root: Path, repository: Path) -> "InstalledManagerSandbox":
        """Install the package and flatten the plugin into an isolated root."""
        sandbox = cls(root=root / "installed-root", repository=repository)
        sandbox.root.mkdir(mode=0o755)
        sandbox._install_distribution()
        copy_installed_python(root=sandbox.root)
        copy_shell_runtime(root=sandbox.root)
        sandbox._copy_plugin()
        sandbox._write_account_database()
        return sandbox

    def console_on_path(self) -> str | None:
        """Resolve the clean installation's console command through its PATH entry."""
        resolved = shutil.which("llm-provider-manager", path=str(self.root / "opt" / "lpm" / "bin"))
        if resolved is None:
            return None
        return f"/{Path(resolved).relative_to(self.root)}"

    def run(
        self,
        *,
        surface: str,
        arguments: tuple[str, ...],
        input_text: str = "",
    ) -> ManagerResult:
        """Run one real installed launcher after entering the isolated root."""
        executable = "llm-provider-manager" if surface == "console" else _PLUGIN
        completed = subprocess.run(  # noqa: S603 - fixed chroot and fixture-owned argv
            [
                "/usr/sbin/chroot",
                f"--userspec={_UID}:{_GID}",
                str(self.root),
                executable,
                *arguments,
            ],
            input=input_text,
            capture_output=True,
            check=False,
            text=True,
            timeout=60.0,
            env={
                "HOME": "/consumer-controlled-home-is-ignored",
                "PATH": _PATH,
                "LANG": "C.UTF-8",
            },
        )
        lines = completed.stdout.splitlines()
        body: dict[str, object] = {}
        if len(lines) == 1:
            decoded = json.loads(lines[0])
            if isinstance(decoded, dict):
                body = cast("dict[str, object]", decoded)
        return ManagerResult(
            executable=_CONSOLE if surface == "console" else _PLUGIN,
            exit_status=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            body=body,
        )

    def _install_distribution(self) -> None:
        destination = self.root / "opt" / "lpm"
        uv = shutil.which("uv")
        assert uv is not None
        for argv in (
            (
                uv,
                "venv",
                "--relocatable",
                "--python",
                "/usr/bin/python3.12",
                "--no-python-downloads",
                str(destination),
            ),
            (
                uv,
                "pip",
                "install",
                "--no-deps",
                "--python",
                str(destination / "bin" / "python"),
                str(self.repository),
            ),
        ):
            _ = subprocess.run(  # noqa: S603 - resolved uv and fixture-owned paths
                argv,
                check=True,
                capture_output=True,
                text=True,
                timeout=120.0,
            )

    def _copy_plugin(self) -> None:
        shutil.copytree(self.repository / ".claude-plugin", self.root / "plugin")

    def _write_account_database(self) -> None:
        etc = self.root / "etc"
        etc.mkdir(mode=0o755)
        _ = (etc / "passwd").write_text(
            f"fixture:x:{_UID}:{_GID}:fixture:/home/fixture:/bin/sh\n",
            encoding="utf-8",
        )
        _ = (etc / "group").write_text(f"fixture:x:{_GID}:\n", encoding="utf-8")
        home = self.root / "home" / "fixture"
        home.mkdir(mode=0o700, parents=True)
        os.chown(home, _UID, _GID)
        device = self.root / "dev"
        device.mkdir(mode=0o755)
        null = device / "null"
        null.touch(mode=0o666)
        null.chmod(0o666)
