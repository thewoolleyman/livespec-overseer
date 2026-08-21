"""Importable entry point for supervised sessions declaring overseer state."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import registry
import signals
import streams
import tmuxio

__all__: list[str] = ["READY_CONTRACT", "main"]

READY_CONTRACT = (
    "restart armed - any further output cancels/downgrades this; you will know it "
    "worked because this conversation ends."
)
NOT_ARMED_PREFIX = "ready declaration written, but restart is not armed"


def _topic_from_mapping(*, repo: Path, session: str) -> str:
    repo_key = registry.norm(repo=repo)
    for track in registry.read_valid_mapping(store_path=registry.DEFAULT_STORE_PATH):
        if registry.norm(repo=track.repo) == repo_key and track.tmux == session:
            return track.topic
    return session


def _resolve_topic(
    *,
    explicit_topic: str | None,
    repo: Path,
    tmux: tmuxio.SessionNameDriver | None,
) -> str | None:
    if explicit_topic is not None:
        return explicit_topic
    env_topic = os.environ.get("OVERSEER_TOPIC")
    if env_topic:
        return env_topic
    pane = os.environ.get("TMUX_PANE")
    if not pane:
        return None
    driver = tmux if tmux is not None else tmuxio.TmuxIO()
    session = driver.pane_session_name(pane=pane)
    if session is None:
        return None
    return _topic_from_mapping(repo=repo, session=session)


def _write_ready(*, repo: Path, topic: str) -> None:
    registry.atomic_write(path=signals.state_path(repo=str(repo), topic=topic), body="ready\n")


def _has_iso_added_at(*, track: registry.Track) -> bool:
    added_at = track.added_at
    return (
        added_at is not None
        and len(added_at) == len("2026-08-16T23:45:00Z")
        and added_at[4] == "-"
        and added_at[7] == "-"
        and added_at[10] == "T"
        and added_at[13] == ":"
        and added_at[16] == ":"
        and added_at.endswith("Z")
    )


def _matching_track(*, repo: Path, topic: str) -> registry.Track | None:
    repo_key = registry.norm(repo=repo)
    for track in registry.read_valid_mapping(store_path=registry.DEFAULT_STORE_PATH):
        if registry.norm(repo=track.repo) == repo_key and track.topic == topic:
            return track
    return None


def _uncertifiable_reason(*, repo: Path, topic: str) -> str | None:
    reason: str | None = None
    record = registry.read_round_record(
        repo=str(repo), topic=topic, stamp_path=registry.DEFAULT_STAMP_PATH
    )
    if record.malformed_reason is not None:
        reason = record.malformed_reason
    elif record.at is None:
        track = _matching_track(repo=repo, topic=topic)
        if track is None:
            reason = "no matching overseer mapping row; daemon cannot certify this declaration"
        elif not _has_iso_added_at(track=track):
            reason = "mapping row missing added_at; daemon cannot certify this declaration"
    return reason


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="overseer-declare",
        description="declare this supervised session's out-of-band overseer state",
    )
    sub = parser.add_subparsers(dest="state", required=True)
    ready = sub.add_parser("ready", help="declare that this session is safe to restart")
    _ = ready.add_argument("--repo", default=".", help="repository root (default: cwd)")
    _ = ready.add_argument(
        "--topic",
        default=None,
        help="plan topic (default: current tmux session)",
    )
    return parser


def main(
    *,
    argv: list[str] | None = None,
    tmux: tmuxio.SessionNameDriver | None = None,
) -> int:
    args = _parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    topic = _resolve_topic(explicit_topic=args.topic, repo=repo, tmux=tmux)
    if topic is None:
        streams.write_stderr(
            text=(
                "overseer-declare: cannot infer plan topic; pass --topic or run inside "
                "a tmux pane whose session is the tracked topic\n"
            )
        )
        return 2
    _write_ready(repo=repo, topic=topic)
    reason = _uncertifiable_reason(repo=repo, topic=topic)
    if reason is None:
        streams.write_stdout(text=f"{READY_CONTRACT}\n")
    else:
        streams.write_stdout(text=f"{NOT_ARMED_PREFIX}: {reason}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
