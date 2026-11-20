"""`caam-strip-refresh-tokens`: step 3 of contracts.md "Moving the role".

Once the role's stores are copied to the new holder, the OLD holder must hold no
managed account's refresh token, so no two machines can ever refresh. This strips
`refreshToken` from the live credential's `claudeAiOauth` and from every caam
snapshot under `~/.local/share/caam` -- the vault, its backups and any pre-upgrade
copy -- keeping every other key, writing each file atomically at mode 0600. It is
idempotent, and it then scans the same files for any residue.

It refuses, changing nothing, while anything that could still refresh is running:
the delivery service, the rotation loop, caam itself, or a live Claude Code
session (the rotation schedule is a session cron). Output names paths, outcomes
and sha256-12 fingerprints only; no credential value is ever printed.
"""

from __future__ import annotations

import hashlib
import io
import json
import os as _os
import sys
import tarfile
from pathlib import Path
from typing import Final

import jsonio
import streams
from caam_profile_state import live_creds_path

__all__: list[str] = ["blockers", "credential_files", "main", "strip_file"]

_PROC: Final = Path("/proc")
_CAAM_REL: Final = Path(".local/share/caam")
_SNAPSHOT: Final = ".credentials.json"
_KEY: Final = "refreshToken"
_ARCHIVE_SUFFIXES: Final = (".tar.gz", ".tgz")
# Exact program tokens, matched against the basenames of the first three argv
# entries (interpreter, script or `-m` module), so a journal reader or a shell
# that merely MENTIONS a unit name in a longer argument does not block.
_LIVE_PROGRAMS: Final = frozenset(
    {
        "caam",
        "caam-delivery-push",
        "caam-anthropic-loop",
        "caam_anthropic_loop",
        "overseer.caam_anthropic_loop",
        "overseer.caam_delivery_push_entry",
    }
)


class _OsSeam:
    """The one rename, behind a seam so a test can fail it without patching `os`."""

    @staticmethod
    def replace(*, src: Path, dst: Path) -> None:
        _ = src.replace(dst)


os = _OsSeam()


def _sha12(*, data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def credential_files(*, home: Path) -> tuple[Path, ...]:
    """The live credential, then every caam snapshot, backups included."""
    caam = home / _CAAM_REL
    archives = (path for path in caam.rglob("*") if path.name.endswith(_ARCHIVE_SUFFIXES))
    return (live_creds_path(home=home), *sorted(caam.rglob(_SNAPSHOT)), *sorted(archives))


def _argv(*, proc_dir: Path) -> list[str]:
    try:
        raw = (proc_dir / "cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode(errors="replace") for part in raw.split(b"\0") if part]


def _session_pid(*, record: Path) -> int | None:
    try:
        parsed = jsonio.parse_object(text=record.read_text(encoding="utf-8"))
    except OSError:
        return None
    body = None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
    pid = None if body is None else body.get("pid")
    return pid if isinstance(pid, int) else None


def blockers(*, home: Path, proc_root: Path) -> list[str]:
    """Every running thing that could still refresh, named without a value."""
    found: list[str] = []
    for proc_dir in sorted(proc_root.iterdir(), key=lambda path: path.name):
        argv = _argv(proc_dir=proc_dir) if proc_dir.name.isdigit() else []
        names = [Path(arg).name for arg in argv[:3]]
        if _LIVE_PROGRAMS.intersection(names):
            found.append(f"process {proc_dir.name}: {' '.join(names)}")
    for record in sorted((home / ".claude/sessions").glob("*.json")):
        pid = _session_pid(record=record)
        if pid is not None and (proc_root / str(pid)).is_dir():
            found.append(f"Claude Code session {pid}")
    return found


def _write_atomic(*, path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".strip-tmp")
    tmp.unlink(missing_ok=True)
    fd = _os.open(tmp, _os.O_WRONLY | _os.O_CREAT | _os.O_EXCL, 0o600)
    with _os.fdopen(fd, "wb") as handle:
        _ = handle.write(data)
    try:
        os.replace(src=tmp, dst=path)
    finally:
        tmp.unlink(missing_ok=True)


def _strip_text(*, text: str) -> str | None:
    """The credential JSON without its `claudeAiOauth.refreshToken`, or None if it has none."""
    parsed = jsonio.parse_object(text=text)
    body = None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
    oauth = None if body is None else jsonio.as_object(value=body.get("claudeAiOauth"))
    if body is None or oauth is None or _KEY not in oauth:
        return None
    kept = {key: value for key, value in oauth.items() if key != _KEY}
    return json.dumps({**body, "claudeAiOauth": kept})


def _archive_rewrite(*, before: bytes) -> bytes | None:
    """The archive with every member credential stripped, or None when none held a token."""
    out = io.BytesIO()
    changed = False
    with (
        tarfile.open(fileobj=io.BytesIO(before), mode="r:*") as source,
        tarfile.open(fileobj=out, mode="w:gz") as target,
    ):
        for member in source.getmembers():
            handle = source.extractfile(member) if member.isfile() else None
            data = None if handle is None else handle.read()
            if data is not None and member.name.endswith(_SNAPSHOT):
                stripped = _strip_text(text=data.decode(errors="replace"))
                if stripped is not None:
                    data, changed = stripped.encode(), True
                    member.size = len(data)
            target.addfile(member, None if data is None else io.BytesIO(data))
    return out.getvalue() if changed else None


def _archive_holds_refresh(*, path: Path) -> bool:
    try:
        return _archive_rewrite(before=path.read_bytes()) is not None
    except (OSError, tarfile.TarError):
        return True


def _strip_archive(*, path: Path, before: bytes, dry_run: bool) -> str:
    try:
        rewritten = _archive_rewrite(before=before)
    except (OSError, tarfile.TarError):
        return f"unreadable {path}"
    if rewritten is None:
        return f"clean {path} sha256-12 {_sha12(data=before)}"
    if dry_run:
        return f"would-strip {path} sha256-12 {_sha12(data=before)}"
    try:
        _write_atomic(path=path, data=rewritten)
    except OSError as error:
        return f"failed {path} {type(error).__name__}"
    return f"stripped {path} sha256-12 {_sha12(data=before)} -> {_sha12(data=rewritten)}"


def _strip_json(*, path: Path, before: bytes, dry_run: bool) -> str:
    text = before.decode(errors="replace")
    parsed = jsonio.parse_object(text=text)
    if jsonio.is_parse_failure(result=parsed):
        return f"unreadable {path}"
    stripped = _strip_text(text=text)
    if stripped is None:
        return f"clean {path} sha256-12 {_sha12(data=before)}"
    if dry_run:
        return f"would-strip {path} sha256-12 {_sha12(data=before)}"
    try:
        _write_atomic(path=path, data=stripped.encode())
    except OSError as error:
        return f"failed {path} {type(error).__name__}"
    return f"stripped {path} sha256-12 {_sha12(data=before)} -> {_sha12(data=stripped.encode())}"


def strip_file(*, path: Path, dry_run: bool) -> str:
    """One secret-free receipt line for one credential file or vault archive."""
    try:
        before = path.read_bytes()
    except OSError:
        return f"absent {path}"
    if path.name.endswith(_ARCHIVE_SUFFIXES):
        return _strip_archive(path=path, before=before, dry_run=dry_run)
    return _strip_json(path=path, before=before, dry_run=dry_run)


def _residue(*, files: tuple[Path, ...]) -> list[str]:
    return [f"residue {path}" for path in files if path.is_file() and _holds_refresh(path=path)]


def _holds_refresh(*, path: Path) -> bool:
    """True when the file still carries a managed account's refresh token.

    A parseable credential is judged by its `claudeAiOauth.refreshToken` alone, so a
    refresh token under another key (an MCP server's) is not residue. A file that
    does not parse is judged by a raw byte search, which fails closed.
    """
    if path.name.endswith(_ARCHIVE_SUFFIXES):
        return _archive_holds_refresh(path=path)
    data = path.read_bytes()
    parsed = jsonio.parse_object(text=data.decode(errors="replace"))
    if jsonio.is_parse_failure(result=parsed):
        return _KEY.encode() in data
    return _strip_text(text=data.decode(errors="replace")) is not None


def _count(*, lines: list[str], word: str) -> int:
    return sum(1 for line in lines if line.startswith(word + " "))


def main(*, argv: list[str] | None = None, proc_root: Path = _PROC) -> int:
    """Strip, or with `--dry-run` only report; exit non-zero unless none can remain."""
    dry_run = "--dry-run" in (sys.argv[1:] if argv is None else argv)
    home = Path.home()
    refusals = blockers(home=home, proc_root=proc_root)
    if refusals:
        for reason in refusals:
            streams.write_stderr(text=f"REFUSED {reason}\n")
        streams.write_stderr(
            text=f"FAIL refusing while the role is still live: {len(refusals)} "
            "blocker(s); nothing changed\n"
        )
        return 2
    files = credential_files(home=home)
    lines = [strip_file(path=path, dry_run=dry_run) for path in files]
    lines += [] if dry_run else _residue(files=files)
    for line in lines:
        streams.write_stdout(text=line + "\n")
    if dry_run:
        would = _count(lines=lines, word="would-strip")
        streams.write_stdout(text=f"OK dry run: would strip {would}\n")
        return 0
    bad = {word: _count(lines=lines, word=word) for word in ("unreadable", "failed", "residue")}
    if any(bad.values()):
        detail = " ".join(f"{word}={n}" for word, n in bad.items())
        streams.write_stderr(text=f"FAIL refresh tokens may remain: {detail}\n")
        return 1
    stripped, clean = _count(lines=lines, word="stripped"), _count(lines=lines, word="clean")
    streams.write_stdout(text=f"OK refresh tokens removed: stripped={stripped} clean={clean}\n")
    return 0
