"""Explicit mode normalization for the installed LPM chroot fixture."""

import os
from pathlib import Path

__all__: list[str] = [
    "make_launcher_tree_runnable",
    "make_support_directories_traversable",
    "write_account_database",
]

_LAUNCHER_ROOTS: tuple[str, ...] = (
    "bin",
    "lib",
    "lib64",
    "opt",
    "plugin",
    "usr",
)


def make_launcher_tree_runnable(*, root: Path) -> None:
    """Restore launcher-tree modes after creation and copy under any umask."""
    root.chmod(0o755)
    for relative_root in _LAUNCHER_ROOTS:
        launcher_root = root / relative_root
        for path in (launcher_root, *launcher_root.rglob("*")):
            if path.is_symlink():
                continue
            if path.is_dir():
                path.chmod(0o755)
            elif path.is_file():
                mode = path.stat().st_mode
                path.chmod(0o755 if mode & 0o111 else 0o644)


def make_support_directories_traversable(*, root: Path) -> None:
    """Restore traversal modes for non-launcher paths the installed process reads."""
    for relative_path in (
        "dev",
        "etc",
        "home",
        "proc",
        "proc/self",
    ):
        (root / relative_path).chmod(0o755)
    (root / "proc" / "self" / "fd").chmod(0o555)


def write_account_database(*, root: Path, uid: int, gid: int) -> None:
    """Create chroot account and device files with explicit post-create modes."""
    etc = root / "etc"
    etc.mkdir(mode=0o755)
    etc.chmod(0o755)
    passwd = etc / "passwd"
    _ = passwd.write_text(
        f"fixture:x:{uid}:{gid}:fixture:/home/fixture:/bin/sh\n",
        encoding="utf-8",
    )
    passwd.chmod(0o644)
    group = etc / "group"
    _ = group.write_text(f"fixture:x:{gid}:\n", encoding="utf-8")
    group.chmod(0o644)
    home = root / "home" / "fixture"
    home.mkdir(mode=0o700, parents=True)
    home.parent.chmod(0o755)
    os.chown(home, uid, gid)
    device = root / "dev"
    device.mkdir(mode=0o755)
    device.chmod(0o755)
    null = device / "null"
    null.touch(mode=0o666)
    null.chmod(0o666)
