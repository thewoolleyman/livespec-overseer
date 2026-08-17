"""Read the plan ledger epic anchor for assignment-time mapping rows."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import cast

from _registry_core import warn
from foreman_gather_sources import parse_repo_config, string_list

__all__: list[str] = ["epic_from_plan_anchor"]


_LEDGER_ANCHOR = re.compile(
    r"(?:[Ll]edger(?: epic)?|[Ee]pic) anchor:?\*{0,2}[^\n`]*\n?[^\n`]*`([a-z0-9-]+(?:\.[0-9]+)?)`"
)
# The current plan-migration/correction tooling writes epic.md as a markdown
# heading followed by the BARE id on its own line, with no backticks and a blank line
# in between (`# Ledger epic anchor\n\noverseer-4w2m\n...`). _LEDGER_ANCHOR predates
# that shape and requires backtick-quoting plus at most one newline, so it never
# matches it — every migrated plan's epic.md silently fails to resolve.
_LEDGER_ANCHOR_BARE = re.compile(
    r"^#\s*(?:[Ll]edger(?: epic)?|[Ee]pic) anchor\s*$\n+^([a-z0-9-]+(?:\.[0-9]+)?)\s*$",
    re.MULTILINE,
)
_LEDGER_TIMEOUT_SECONDS = 30
_LEDGER_COMMAND = ["bd", "list", "--type", "epic", "--status", "all", "--json"]


def _resolve_ledger_epic_matches(
    *, repo: Path, topic: str, matches: list[tuple[str, object]]
) -> str | None:
    if len(matches) == 1:
        return matches[0][0]
    open_matches = [record_id for record_id, status in matches if status != "closed"]
    if len(open_matches) == 1:
        return open_matches[0]
    if len(open_matches) > 1:
        warn(message=f"could not resolve plan ledger epic for {repo}/{topic}: ambiguous anchors")
    return None


def _anchor_from_path(*, path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        if path.exists():
            warn(message=f"could not read plan ledger anchor {path}: {exc}")
        return None
    match = _LEDGER_ANCHOR.search(text)
    if match is not None:
        return match.group(1)
    bare_match = _LEDGER_ANCHOR_BARE.search(text)
    if bare_match is not None:
        return bare_match.group(1)
    return None


def _credential_wrapper(*, repo: Path) -> list[str]:
    config = parse_repo_config(repo=repo)
    if config is None:
        return []
    wrapper = string_list(value=config.get("credential_wrapper"))
    return wrapper if wrapper is not None else []


def _ledger_epic_from_plan_tag(*, repo: Path, topic: str) -> str | None:
    """Return the uniquely tagged plan epic from the repository ledger.

    Ledger-backed plan binders deliberately carry their anchor only in Beads.  This
    lookup is assignment-only, like the legacy handoff read above it; discovery stays
    directory-only and never reaches either path.
    """
    command = [*_credential_wrapper(repo=repo), *_LEDGER_COMMAND]
    try:
        completed = subprocess.run(  # noqa: S603 — fixed bd argv, no shell
            command,
            capture_output=True,
            check=False,
            cwd=repo,
            text=True,
            timeout=_LEDGER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        warn(message=f"could not read plan ledger epic for {repo}/{topic}: {exc}")
        return None
    if completed.returncode != 0:
        warn(
            message=f"could not read plan ledger epic for {repo}/{topic}: "
            f"bd exited {completed.returncode}"
        )
        return None
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        warn(message=f"could not parse plan ledger epic for {repo}/{topic}: {exc}")
        return None
    if not isinstance(raw, list):
        warn(message=f"could not parse plan ledger epic for {repo}/{topic}: expected list")
        return None
    matches: list[tuple[str, object]] = []
    for raw_item in cast("list[object]", raw):
        if not isinstance(raw_item, dict):
            continue
        item = cast("dict[str, object]", raw_item)
        record_id = item.get("id")
        metadata = item.get("metadata")
        is_plan_anchor = item.get("spec_id") == f"plan:{topic}" or (
            isinstance(metadata, dict)
            and cast("dict[str, object]", metadata).get("plan_slug") == topic
        )
        if item.get("issue_type") == "epic" and isinstance(record_id, str) and is_plan_anchor:
            matches.append((record_id, item.get("status")))
    return _resolve_ledger_epic_matches(repo=repo, topic=topic, matches=matches)


def epic_from_plan_anchor(*, repo: str | os.PathLike[str], topic: str) -> str | None:
    """Return the plan's handoff or ledger-declared anchor, or None when absent.

    This helper is for ASSIGNMENT surfaces. The daemon discovery pass must keep using
    directory-only discovery and must not call it.
    """
    root = Path(repo)
    path = root / "plan" / topic / "epic.md"
    anchor = _anchor_from_path(path=path)
    if anchor is not None:
        return anchor
    legacy_handoff = root / "plan" / topic / "handoff.md"
    if not path.exists():
        anchor = _anchor_from_path(path=legacy_handoff)
        if anchor is not None:
            return anchor
    return _ledger_epic_from_plan_tag(repo=root, topic=topic)
