"""Copy the host runtime required by an isolated installed-manager fixture."""

import os
import shutil
import subprocess
from pathlib import Path

__all__: list[str] = [
    "copy_installed_python",
    "copy_shell_runtime",
]


def copy_installed_python(*, root: Path) -> None:
    """Copy the installed interpreter, standard library, and shared libraries."""
    installed = root / "opt" / "lpm" / "bin" / "python"
    interpreter = installed.resolve()
    completed = subprocess.run(  # noqa: S603 - the clean install's fixed interpreter
        [
            str(installed),
            "-c",
            "import sysconfig; print(sysconfig.get_path('stdlib'))",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30.0,
    )
    standard_library = Path(completed.stdout.strip())
    shutil.copytree(
        standard_library,
        root / standard_library.relative_to("/"),
        symlinks=True,
        copy_function=_linked_copy,
    )
    _copy_executable(root=root, source=interpreter)
    for extension in (standard_library / "lib-dynload").glob("*.so"):
        _copy_dependencies(root=root, executable=extension)


def copy_shell_runtime(*, root: Path) -> None:
    """Copy the shell programs used by the flattened plugin executable."""
    for source in (
        Path("/bin/dash"),
        Path("/usr/bin/dirname"),
        Path("/usr/bin/env"),
        Path("/usr/bin/realpath"),
    ):
        _copy_executable(root=root, source=source)
    (root / "bin" / "sh").symlink_to("dash")
    (root / "usr" / "bin" / "sh").symlink_to("dash")


def _linked_copy(source: str, destination: str, /) -> str:
    """Hard-link the immutable interpreter tree, falling back across filesystems."""
    try:
        os.link(source, destination)
    except OSError:
        _ = shutil.copy2(source, destination)
    return destination


def _copy_executable(*, root: Path, source: Path) -> None:
    destination = root / source.relative_to("/")
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    _ = shutil.copy2(source, destination)
    _copy_dependencies(root=root, executable=source)


def _copy_dependencies(*, root: Path, executable: Path) -> None:
    completed = subprocess.run(  # noqa: S603 - fixed ldd over a fixture-selected executable
        ["/usr/bin/ldd", str(executable)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30.0,
    )
    for line in completed.stdout.splitlines():
        candidate = _dependency_path(line=line)
        if candidate is None or candidate.is_relative_to(executable.parent.parent):
            continue
        destination = root / candidate.relative_to("/")
        if destination.exists():
            continue
        destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        _ = shutil.copy2(candidate, destination)


def _dependency_path(*, line: str) -> Path | None:
    fields = line.strip().split()
    if "=>" in fields:
        candidate = fields[fields.index("=>") + 1]
    elif fields and fields[0].startswith("/"):
        candidate = fields[0]
    else:
        return None
    return Path(candidate) if candidate.startswith("/") else None
