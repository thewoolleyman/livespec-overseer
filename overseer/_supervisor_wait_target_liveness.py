"""Factory process-view source reader for remote wait-target verification."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess

import jsonio

__all__: list[str] = [
    "remote_factory_run_present_with",
]

_FABRO_REMOTE_TIMEOUT_SECONDS = 12.0
# The fleet gitops inventory's factory registry, as each dispatching host renders
# it. A registry-backed committed entry names no machine, so this file is the only
# binding from a factory name to the server that answers for it.
_FACTORY_REGISTRY_PATH = Path("/etc/livespec/fabro-factories.json")
_TERMINAL_STATUSES = frozenset(
    {
        "blocked",
        "canceled",
        "cancelled",
        "closed",
        "done",
        "error",
        "failed",
        "merged",
        "success",
        "succeeded",
    }
)


def string_field(*, record: dict[str, object], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value else None


def strip_jsonc_line_comment(*, line: str) -> str:
    in_string = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = in_string
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string and char == "/" and index + 1 < len(line) and line[index + 1] == "/":
            return line[:index]
    return line


def parse_repo_config(*, repo: Path) -> dict[str, object] | None:
    try:
        text = (repo / ".livespec.jsonc").read_text(encoding="utf-8")
    except OSError:
        return None
    stripped = "\n".join(strip_jsonc_line_comment(line=line) for line in text.splitlines())
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return jsonio.as_object(value=value)


def dispatcher_config(*, repo: Path) -> dict[str, object] | None:
    config = parse_repo_config(repo=repo)
    if config is None:
        return None
    dispatcher_owner_config = jsonio.as_object(
        value=config.get("livespec-orchestrator-beads-fabro")
    )
    if dispatcher_owner_config is None:
        return None
    return jsonio.as_object(value=dispatcher_owner_config.get("dispatcher"))


def committed_factory_config(*, repo: Path, factory: str) -> dict[str, object] | None:
    """The repository's committed ``dispatcher.factories`` entry for one factory."""
    dispatcher = dispatcher_config(repo=repo)
    if dispatcher is None:
        return None
    factories = jsonio.as_object(value=dispatcher.get("factories"))
    if factories is None:
        return None
    return jsonio.as_object(value=factories.get(factory))


def registry_factory_server(*, registry_path: Path, factory: str) -> str | None:
    """Resolve a registry-backed factory's server address by factory name.

    The registry is a JSON object mapping factory name to ``{server, optional
    docker_host}``. A registry that is absent, unreadable, malformed, or that
    declares no such factory, yields ``None`` — which the caller must report as
    "the factory cannot answer", never as "no run exists". Fail-soft rather than
    raising, because no sandbox carries the host file at all.
    """
    try:
        text = registry_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    payload = jsonio.as_object(value=value) or {}
    entry = jsonio.as_object(value=payload.get(factory)) or {}
    return string_field(record=entry, key="server")


def factory_server(
    *, repo: Path, factory: str | None, registry_path: Path = _FACTORY_REGISTRY_PATH
) -> str | None:
    """Resolve a factory's server from its committed entry, else from the registry.

    A committed entry that declares ``"registry": true`` and carries no ``server``
    names no machine, so the address it routes to is bound only in the factory
    registry the dispatching host renders at ``registry_path``.
    """
    if factory is None:
        return None
    factory_config = committed_factory_config(repo=repo, factory=factory)
    if factory_config is None:
        return None
    committed = string_field(record=factory_config, key="server")
    if committed is not None:
        return committed
    if factory_config.get("registry") is not True:
        return None
    return registry_factory_server(registry_path=registry_path, factory=factory)


def factory_client(*, repo: Path, factory: str | None) -> str:
    """Return the committed client binary for a factory, or the PATH default."""
    if factory is None:
        return "fabro"
    factory_config = committed_factory_config(repo=repo, factory=factory)
    if factory_config is None:
        return "fabro"
    return string_field(record=factory_config, key="bin") or "fabro"


def process_records_from_payload(*, stdout: str) -> list[dict[str, object]] | None:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    runs = jsonio.as_list(value=value)
    if runs is None:
        payload = jsonio.as_object(value=value) or {}
        runs = jsonio.as_list(value=payload.get("runs"))
        if runs is None:
            runs = jsonio.as_list(value=payload.get("items"))
        if runs is None:
            return None
    elif not runs:
        return None
    return [item for raw in runs if (item := jsonio.as_object(value=raw)) is not None]


def run_matches_target(
    *, process_record: dict[str, object], target_id: str, work_item_id: str | None
) -> bool:
    ids = (
        string_field(record=process_record, key="id"),
        string_field(record=process_record, key="run_id"),
        string_field(record=process_record, key="dispatch_id"),
    )
    if target_id in ids:
        return True
    return (
        work_item_id is not None
        and string_field(record=process_record, key="work_item_id") == work_item_id
    )


def active_process(*, process_record: dict[str, object]) -> bool:
    for key in ("status", "state", "conclusion"):
        status = string_field(record=process_record, key=key)
        if status is not None:
            return status.lower() not in _TERMINAL_STATUSES
    return True


def dispatch_factory_target(*, record: dict[str, object]) -> tuple[str | None, str | None]:
    """A record's dispatch factory name, and the server its dispatch recorded.

    `dispatch_factory` is recorded either as a bare factory name or as an object
    carrying ``name`` and the ``server`` the dispatch resolved for it. Reading only
    the string form yielded ``None`` for the object shape, which the caller read as
    "this record names no factory" and answered NO RUN for a live run.
    """
    recorded = jsonio.as_object(value=record.get("dispatch_factory"))
    if recorded is None:
        return string_field(record=record, key="dispatch_factory"), None
    return string_field(record=recorded, key="name"), string_field(record=recorded, key="server")


def remote_factory_run_present_with(
    *,
    repo: Path,
    record: dict[str, object],
    target_id: str,
    run: Callable[..., CompletedProcess[str]],
    registry_path: Path = _FACTORY_REGISTRY_PATH,
) -> bool | None:
    """Return remote liveness, or ``None`` when the factory cannot answer."""
    dispatch_factory, recorded_server = dispatch_factory_target(record=record)
    if dispatch_factory is None and recorded_server is None:
        return False
    server = recorded_server or factory_server(
        repo=repo, factory=dispatch_factory, registry_path=registry_path
    )
    if server is None:
        return None
    client = factory_client(repo=repo, factory=dispatch_factory)
    try:
        completed = run(
            [client, "ps", "-a", "--json", "--server", server],
            capture_output=True,
            check=False,
            cwd=repo,
            text=True,
            timeout=_FABRO_REMOTE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    records = process_records_from_payload(stdout=completed.stdout)
    if records is None:
        return None
    work_item_id = string_field(record=record, key="work_item_id")
    return any(
        active_process(process_record=process_record)
        for process_record in records
        if run_matches_target(
            process_record=process_record,
            target_id=target_id,
            work_item_id=work_item_id,
        )
    )
