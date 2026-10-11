"""Unresolved-native-mutation admission for deliberate public start."""

from __future__ import annotations

from typing import cast

import streams
from _supervisor_cli_start_types import NativePending, StartContext

__all__: list[str] = ["admitted_start_context"]


def _pending_native_start(*, context: StartContext, repo: str, topic: str) -> str:
    if context.native_source is None or not hasattr(context.io, "pending_initial_start"):
        return ""
    return cast(NativePending, context.io).pending_initial_start(
        repo=repo,
        topic=topic,
        session=context.session,
    )


def admitted_start_context(
    *, context: StartContext | None, repo: str, topic: str
) -> StartContext | None:
    """Refuse before liveness shortcuts when a native effect is unresolved."""
    if context is None:
        return None
    pending = _pending_native_start(context=context, repo=repo, topic=topic)
    if pending:
        streams.write_stderr(text=f"start REFUSED: {pending}\n")
        return None
    return context
