"""Importable entry point for supervised sessions declaring overseer state."""

from __future__ import annotations

import argparse
import os
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pane_router
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
ACCEPTED_FORMS = "winding-down, ready, blocked <reason>, done [summary], or clear"
MAX_DETAIL_LENGTH = 200


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
    if tmux is None:
        coordinate = pane_router.current_process_coordinate()
        if coordinate is not None:
            return _topic_from_mapping(repo=repo, session=coordinate)
    pane = os.environ.get("TMUX_PANE")
    if not pane:
        return None
    driver = tmux if tmux is not None else tmuxio.TmuxIO()
    session = driver.pane_session_name(pane=pane)
    if session is None:
        return None
    return _topic_from_mapping(repo=repo, session=session)


def _write_state(*, repo: Path, topic: str, token: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    registry.atomic_write(
        path=signals.state_path(repo=str(repo), topic=topic), body=f"{token}{suffix}\n"
    )


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
    worker_topic = signals.topic_supervised_worker(topic=topic)
    for track in registry.read_valid_mapping(store_path=registry.DEFAULT_STORE_PATH):
        if registry.norm(repo=track.repo) == repo_key and track.topic == topic:
            return track
        if worker_topic is not None and track.topic == worker_topic:
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
    winding_down = sub.add_parser("winding-down", help="acknowledge and begin wrapping up")
    _add_target_options(parser=winding_down)
    ready = sub.add_parser("ready", help="declare that this session is safe to restart")
    _add_target_options(parser=ready)
    blocked = sub.add_parser("blocked", help="declare a human decision is needed")
    _ = blocked.add_argument("reason", nargs="*", help="one-line blocking reason")
    _add_target_options(parser=blocked)
    done = sub.add_parser(
        "done",
        aliases=["done:"],
        help="declare that this session's work is complete",
    )
    _ = done.add_argument("summary", nargs="*", help="optional one-line completion summary")
    _add_target_options(parser=done)
    clear = sub.add_parser("clear", help="clear a session-owned declaration")
    _add_target_options(parser=clear)
    return parser


def _add_target_options(*, parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    _ = parser.add_argument(
        "--topic",
        default=None,
        help="plan topic (default: current tmux session)",
    )


def _valid_detail(*, detail: str, required: bool) -> bool:
    if required and not detail:
        return False
    if len(detail) > MAX_DETAIL_LENGTH:
        return False
    return "\n" not in detail and not any(unicodedata.category(char) == "Cc" for char in detail)


def _refuse_value() -> int:
    streams.write_stderr(text=f"overseer-declare: accepted forms: {ACCEPTED_FORMS}\n")
    return 2


def _first_nonempty_line(*, text: str) -> str:
    return next((line for line in text.splitlines() if line.strip()), "")


def _clear_state(*, repo: Path, topic: str) -> None:
    path = signals.state_path(repo=str(repo), topic=topic)
    try:
        if not path.is_file() or path.is_symlink():
            streams.write_stdout(text="no state declaration to clear.\n")
            return
        initial_text = path.read_text(encoding="utf-8")
        initial_line = _first_nonempty_line(text=initial_text)
        initial_mtime = path.stat().st_mtime_ns
    except (OSError, ValueError):
        streams.write_stdout(text="no state declaration to clear.\n")
        return
    token = initial_line.partition(":")[0].strip().lower()
    allowed = (*signals.STATE_TOKENS, signals.STATE_IDLE_WITH_CONTEXT_LEFT)
    if token not in allowed:
        streams.write_stdout(text=f"state file left in place: daemon-written value {token!r}.\n")
        return
    try:
        final_text = path.read_text(encoding="utf-8")
        final_line = _first_nonempty_line(text=final_text)
        final_mtime = path.stat().st_mtime_ns
        if final_line != initial_line or final_mtime != initial_mtime:
            streams.write_stdout(text="state file changed; left in place.\n")
            return
        path.unlink()
    except (OSError, ValueError):
        streams.write_stdout(text="state file changed; left in place.\n")
        return
    streams.write_stdout(text="state declaration cleared.\n")


def main(
    *,
    argv: list[str] | None = None,
    tmux: tmuxio.SessionNameDriver | None = None,
) -> int:
    args = _parser().parse_args(argv)
    detail = " ".join(getattr(args, "reason", getattr(args, "summary", [])))
    if args.state == "blocked" and not _valid_detail(detail=detail, required=True):
        return _refuse_value()
    if args.state in {"done", "done:"} and not _valid_detail(detail=detail, required=False):
        return _refuse_value()
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
    if args.state == "clear":
        _clear_state(repo=repo, topic=topic)
    elif args.state == "winding-down":
        _write_state(repo=repo, topic=topic, token=signals.STATE_WINDING_DOWN)
        streams.write_stdout(text="winding-down declaration written.\n")
    elif args.state == "blocked":
        _write_state(repo=repo, topic=topic, token=signals.STATE_BLOCKED, detail=detail)
        streams.write_stdout(text="blocked declaration written.\n")
    elif args.state in {"done", "done:"}:
        _write_state(repo=repo, topic=topic, token=signals.STATE_DONE, detail=detail)
        streams.write_stdout(text="done declaration written; no restart requested.\n")
    else:
        _write_state(repo=repo, topic=topic, token=signals.STATE_READY)
        reason = _uncertifiable_reason(repo=repo, topic=topic)
        if reason is None:
            streams.write_stdout(text=f"{READY_CONTRACT}\n")
        else:
            streams.write_stdout(text=f"{NOT_ARMED_PREFIX}: {reason}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
