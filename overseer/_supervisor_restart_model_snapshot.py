"""Restart-model verdict payloads for the status snapshot."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

import codex_sessions
import jsonio
import registry
from _supervisor_statusline_model import rendered_statusline_model
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["current_default_statusline_model_from_store", "restart_model_payload"]

# The reason an unreadable default carries, keyed by the ROW'S OWN harness. A Codex
# row's default does not live in `~/.claude/settings.json`, so the Claude spelling named
# the wrong file at exactly the moment an operator needs to know which one to go read.
# The Claude spelling is unchanged: the established Claude result is retained whole.
_DEFAULT_UNREADABLE_REASON = {
    "claude": "default-unreadable",
    "codex": "codex-default-unreadable",
}

# Codex's permitted CONFIGURATION source for the model a profile-less relaunch selects:
# the ROOT-table `model` key of `<codex home>/config.toml`. Read by a deliberately narrow
# scan rather than a TOML parser — this package is stdlib-only and supports Python 3.10,
# where `tomllib` does not exist — so it admits the root key and nothing else: the first
# table header ENDS the root table, and a `model` under one is that table's model, not the
# default. Reading the config is also what keeps this off the prohibited path: a Codex
# rollout BODY must never be read to derive a runtime model.
_CODEX_MODEL_RE = re.compile(r"^model\s*=\s*(?P<quote>[\"'])(?P<model>[^\"']*)(?P=quote)")


def _track_for_row(*, sup: Supervisor, row: RowView) -> registry.Track | None:
    if not hasattr(sup, "store_path"):
        return None
    store_path = getattr(sup, "store_path", None)
    repo = registry.norm(repo=row.repo)
    for track in registry.read_valid_mapping(store_path=store_path):
        if registry.norm(repo=track.repo) == repo and track.topic == row.topic:
            return track
    return None


def _harness_for_row(*, row: RowView) -> str:
    """The harness whose configuration governs ROW's restart-model evidence.

    ``RowView.runtime`` is set exactly for a row with a LIVE MANAGED pane; the
    no-managed-pane rows (``unassigned`` / ``session-gone`` / ``live-outside-tmux``)
    carry ``None`` and keep the established Claude source.
    """
    return "codex" if row.runtime == "codex" else "claude"


def _claude_default_model() -> str | None:
    try:
        settings_path = Path.home() / ".claude" / "settings.json"
        parsed = jsonio.parse_object(text=settings_path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if jsonio.is_parse_failure(result=parsed):
        return None
    payload = parsed.unwrap()
    if payload is None:
        return None
    model = payload.get("model")
    return model if isinstance(model, str) and model else None


def _codex_home(*, sup: Supervisor) -> Path:
    home = getattr(sup, "codex_home", None)
    if home is None:
        return codex_sessions.default_codex_home()
    return Path(home)


def _codex_default_model(*, codex_home: Path) -> str | None:
    try:
        text = (codex_home / "config.toml").read_text(encoding="utf-8")
    except OSError:
        return None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("["):
            return None
        match = _CODEX_MODEL_RE.match(line)
        if match is not None:
            return match.group("model") or None
    return None


def _current_default_model(*, sup: Supervisor, harness: str) -> str | None:
    """The default model the ROW'S OWN runtime would launch with.

    Every row used to read `~/.claude/settings.json`, so a Codex row reported Claude's
    default as its own and compared its rendered Codex model against it: live 5.4.3 rows
    rendering `gpt-5.6-sol xhigh` reported `opus[1m]`, resolved it to `Opus 5 (1M
    context)` and emitted `would-change` — which is not evidence about what a
    profile-less Codex relaunch would select.
    """
    if harness == "codex":
        return _codex_default_model(codex_home=_codex_home(sup=sup))
    return _claude_default_model()


def current_default_statusline_model_from_store(
    *, sup: Supervisor, current_default: str | None, harness: str
) -> str | None:
    """CURRENT_DEFAULT's rendered statusline form, from HARNESS profiles only.

    The search is harness-scoped because a model TOKEN only means anything inside the
    runtime that launched it. A Claude track running through the local-llm wrapper
    legitimately records a non-Anthropic token, so an unscoped search can answer a Codex
    row's default with a Claude row's rendering — a comparison between two runtimes'
    display strings, reported as though it were about this row.
    """
    if current_default is None or not hasattr(sup, "store_path"):
        return None
    store_path = getattr(sup, "store_path", None)
    for track in registry.read_valid_mapping(store_path=store_path):
        profile = track.model_profile
        if profile is None or profile.get("harness") != harness:
            continue
        if profile.get("model") != current_default:
            continue
        rendered = profile.get("statusline_model")
        if isinstance(rendered, str) and rendered:
            return rendered
    return None


def _current_default_statusline_model(
    *, sup: Supervisor, current_default: str | None, harness: str
) -> str | None:
    if current_default is None:
        return None
    reader = getattr(sup, "current_default_statusline_model", None)
    if not callable(reader):
        return None
    rendered = reader(current_default=current_default, harness=harness)
    return rendered if isinstance(rendered, str) and rendered else None


def _capture_for_row(*, sup: Supervisor, row: RowView) -> str | None:
    if row.tmux is None:
        return None
    tmux = getattr(sup, "tmux", None)
    if tmux is None:
        return None
    # Mirror `latest_input_provenance`: a supervisor stand-in may carry a tmux that
    # implements only the readers its own case needs, so probe for the method rather
    # than assuming the full protocol.
    reader = getattr(tmux, "capture_pane", None)
    if not callable(reader):
        return None
    return cast("str | None", reader(session=row.tmux))


def _restart_model_payload(
    *,
    current_default: str | None,
    current_default_statusline_model: str | None,
    harness: str,
    model_profile: Mapping[str, str | None] | None,
    rendered: str | None,
    row: RowView,
) -> dict[str, object]:
    recorded = None if model_profile is None else model_profile.get("statusline_model")
    base: dict[str, object] = {
        "current_default": current_default,
        "current_default_statusline_model": current_default_statusline_model,
        "rendered_statusline_model": rendered,
        "recorded_statusline_model": recorded,
    }
    if model_profile is not None:
        return {"verdict": "profile-preserved", "reason": "recorded-profile", **base}
    if row.tmux is None:
        return {"verdict": "unknown", "reason": "pane-absent", **base}
    if rendered is None:
        return {"verdict": "unknown", "reason": "statusline-unreadable", **base}
    if current_default is None:
        verdict, reason = "unknown", _DEFAULT_UNREADABLE_REASON[harness]
    elif current_default_statusline_model is None:
        verdict, reason = "unknown", "default-statusline-unresolved"
    elif rendered == current_default_statusline_model:
        verdict, reason = "no-op", "matches-current-default"
    else:
        verdict, reason = "would-change", "differs-from-current-default"
    return {"verdict": verdict, "reason": reason, **base}


def restart_model_payload(*, sup: Supervisor, row: RowView) -> dict[str, object]:
    track = _track_for_row(sup=sup, row=row)
    model_profile = None if track is None else track.model_profile
    capture = _capture_for_row(sup=sup, row=row)
    rendered = None if capture is None else rendered_statusline_model(capture=capture)
    harness = _harness_for_row(row=row)
    current_default = _current_default_model(sup=sup, harness=harness)
    return _restart_model_payload(
        current_default=current_default,
        current_default_statusline_model=_current_default_statusline_model(
            sup=sup, current_default=current_default, harness=harness
        ),
        harness=harness,
        model_profile=model_profile,
        rendered=rendered,
        row=row,
    )
