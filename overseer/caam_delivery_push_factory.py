"""Send a host the factory selection record alone, with no credential delivery."""

from __future__ import annotations

import json
from collections.abc import Callable

from caam_delivery_apply_script import apply_program
from caam_delivery_push_state import Host, scrubbed, seconds

__all__: list[str] = ["send_factory_only"]

Runner = Callable[..., tuple[int, str]]


def send_factory_only(
    *,
    host: Host,
    factory: tuple[bytes, str] | None,
    lines: dict[str, str],
    run: Runner,
    send: tuple[dict[str, object], str, str],
) -> None:
    """Send a macOS host the factory record alone; its credential delivery stays unsupported."""
    if factory is None:
        return
    settings, known_hosts, token = send
    payload = {"factory_only": True, "factory_record": factory[0].decode("utf-8")}
    reply = run(
        target=host.target,
        program=apply_program(payload=json.dumps(payload)),
        key=str(settings["ssh_key"]),
        known_hosts=known_hosts,
        timeout=seconds(settings=settings, key="push_timeout_s"),
    )[1]
    lines[host.label] = scrubbed(text=reply, token=token)
