"""Shared topic/session derivation for one-shot supervisor CLI commands."""

from __future__ import annotations

import registry
import streams
from _signals_topics import reserved_worker_suffix

__all__: list[str] = [
    "cli_colliding",
    "refuse_reserved_topic",
]


def cli_colliding() -> frozenset[str]:
    """Cross-repo topic-collision set for one-shot CLI naming (``add`` / ``start``)."""
    watch = registry.watch_set_from_config(
        config_path=registry.DEFAULT_WATCH_SET_PATH, extra_repos=[]
    )
    return registry.colliding_topics(discovered=registry.discover_plans(watch_repos=watch))


def refuse_reserved_topic(*, repo: str, topic: str) -> bool:
    if (suffix := reserved_worker_suffix(topic=topic)) is None:
        return False
    streams.write_stderr(
        text=(
            f"refusing reserved supervisor topic {repo}::{topic}; "
            f"worker topics may not end in {suffix}\n"
        )
    )
    return True
