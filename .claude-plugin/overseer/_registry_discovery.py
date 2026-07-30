"""Plan discovery, the discovery ⋈ mapping join, the watch set, and archive-GC.

Extracted from `registry.py` at its own section banner when that module crossed the
250-LLOC hard ceiling. Also carries the small JSONC scanner the watch-set
declaration is parsed with. `registry.py` re-exports this surface, so consumers keep
importing `registry`.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

import jsonio
import signals
from _registry_core import (
    Track,
    norm,
    warn,
)

__all__: list[str] = [
    "archived_or_gone",
    "discover_plans",
    "join",
    "repo_root_present",
    "watch_set_from_config",
]


# --------------------------------------------------------------------------- #
# Discovery, join, watch-set, archive-GC.
# --------------------------------------------------------------------------- #


def discover_plans(
    *,
    watch_repos: Iterable[str | os.PathLike[str]],
) -> list[tuple[str, str, str]]:
    """Enumerate each watched repo's ``plan/*/`` DIRECTORIES (a track per dir).

    Returns ``(repo, topic, abs-handoff-path)`` triples, sorted for
    determinism. Discovery keys on the ``plan/<topic>/`` DIRECTORY existing — it
    does NOT read or stat any FILE inside it, because the overseer never touches
    a session's ``plan/`` files (the handoff and its contents are the session's
    own workflow). The returned handoff path (``plan/<topic>/handoff.md``) is a
    CONVENTIONAL pointer the resume line hands to the session; the overseer never
    opens it. Excludes ``plan/archive/**`` (only direct children of ``plan/`` are
    considered, and the literal ``archive`` dir is skipped).
    Fail-soft: a repo with no ``plan/`` dir contributes nothing, and an OSError
    on ONE repo (a ``plan/`` that becomes unreadable between the ``is_dir`` check
    and ``iterdir`` — chmod, NFS hiccup, mid-clone) is warned and skipped rather
    than propagated out to crash the daemon that supervises ALL tracks
    (adversarial code review 2026-07-13, blocker B7).
    """
    triples: list[tuple[str, str, str]] = []
    for repo in watch_repos:
        repo_norm = norm(repo=repo)
        plan_dir = Path(repo_norm) / "plan"
        try:
            if not plan_dir.is_dir():
                continue
            children = list(plan_dir.iterdir())
        except OSError as exc:
            warn(message=f"unreadable plan dir {plan_dir}: {exc}")
            continue
        for child in children:
            try:
                if not child.is_dir() or child.name == "archive":
                    continue
                if signals.topic_reserved_for_supervisor(topic=child.name):
                    warn(message=f"refusing reserved supervisor plan directory {child}")
                    continue
                # Directory existence IS the track; the handoff path is only a
                # conventional pointer for the resume line (never opened here).
                handoff = child / "handoff.md"
                triples.append((repo_norm, child.name, str(handoff)))
            except OSError as exc:
                warn(message=f"unreadable plan child {child}: {exc}")
                continue
    triples.sort(key=lambda t: (t[0], t[1]))
    return triples


def join(
    *,
    discovered: Iterable[tuple[str, str, str]],
    mapping: Iterable[Track],
) -> list[Track]:
    """LEFT JOIN discovered plans with mapping rows on ``(repo, topic)``.

    Discovery is the left side: one Track per discovered triple. A discovered
    plan with a mapping row yields the mapped Track (its ``handoff`` filled from
    discovery if the row lacked one); a discovered-but-unmapped plan yields an
    ``unassigned`` Track. Mapping rows with no discovered plan do NOT appear
    here — those are dropped by the daemon's archive-GC, not the join.
    """
    index: dict[tuple[str, str], Track] = {}
    for track in mapping:
        index[(norm(repo=track.repo), track.topic)] = track

    result: list[Track] = []
    for repo, topic, handoff in discovered:
        mapped = index.get((norm(repo=repo), topic))
        if mapped is None:
            result.append(Track.make_unassigned(repo=repo, topic=topic, handoff=handoff))
        elif mapped.handoff:
            result.append(mapped)
        else:
            result.append(replace(mapped, handoff=handoff))
    result.sort(key=lambda t: (norm(repo=t.repo), t.topic))
    return result


def _scan_string_literal(*, text: str, start: int) -> int:
    """Index just past the JSON string literal opening at ``start``.

    ``text[start]`` is the opening quote. Backslash escapes are honored, so an
    escaped quote does not end the literal. An UNTERMINATED literal consumes to
    the end of the input rather than raising: this is a comment stripper, not a
    validator, and reporting malformed JSON is :func:`json.loads`'s job.
    """
    n = len(text)
    i = start + 1
    escape = False
    while i < n:
        ch = text[i]
        if escape:
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == '"':
            return i + 1
        i += 1
    return n


def _scan_line_comment(*, text: str, start: int) -> int:
    """Index of the newline ending the ``//`` comment at ``start``.

    The newline itself is NOT consumed, so stripping preserves line structure
    (and therefore the line numbers in any downstream parse error).
    """
    end = text.find("\n", start)
    return len(text) if end == -1 else end


def _scan_block_comment(*, text: str, start: int) -> int:
    """Index just past the ``/* */`` comment opening at ``start``.

    An unterminated block comment consumes to the end of the input, matching
    :func:`_scan_string_literal`'s fail-soft posture.
    """
    end = text.find("*/", start + 2)
    return len(text) if end == -1 else end + 2


def _strip_jsonc_comments(*, text: str) -> str:
    """Strip ``//`` line and ``/* */`` block comments, string-literal-aware.

    A hand-rolled scanner (not a regex) so a ``//`` or ``/*`` inside a JSON
    string value is preserved. Avoids adding a JSONC/TOML/YAML dependency.

    Each ``_scan_*`` helper takes the index where its construct begins and
    returns the index just past it, so this loop stays a flat dispatch over
    "what starts here?" rather than an interleaved multi-flag state machine.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '"':
            end = _scan_string_literal(text=text, start=i)
            out.append(text[i:end])
            i = end
        elif text.startswith("//", i):
            i = _scan_line_comment(text=text, start=i)
        elif text.startswith("/*", i):
            i = _scan_block_comment(text=text, start=i)
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _parse_jsonc(*, text: str) -> object:
    stripped = _strip_jsonc_comments(text=text)
    # Tolerate trailing commas before a closing brace/bracket (common in JSONC).
    stripped = re.sub(r",(\s*[}\]])", r"\1", stripped)
    return json.loads(stripped)


def watch_set_from_config(
    *,
    config_path: str | os.PathLike[str],
    extra_repos: Iterable[str | os.PathLike[str]] = (),
) -> list[str]:
    """Compute the watch-set from the ``$HOME`` declaration rather than a manifest.

    This is the SOLE watch-set source, and it is what makes the overseer
    relocatable. It REPLACED a manifest-seeded ``watch_set`` that resolved
    ``.livespec-fleet-manifest.jsonc`` by walking UP from this file — which broke
    the moment the package moved out of ``<core>/.claude/skills/``. That function
    was REMOVED with the relocation and is defined nowhere in this package; no
    non-test code reads the fleet manifest at all. Reading an absolute ``$HOME``
    path instead is position-independent, and it drops the manifest dependency
    D5 forbids a shipped overseer from carrying.

    The document is ``{"repos": ["<checkout>", ...]}``, parsed as JSONC rather
    than strict JSON: this is a HAND-EDITED operator file, so ``//`` comments
    beside an entry ("paused while the migration lands") are worth more than
    format purity, and the repo already carries the lenient parser.

    Each entry is included only if the checkout exists AND has a ``plan/`` dir —
    the SAME admission rule the superseded manifest seeding applied, so
    relocating does not quietly widen or narrow what gets supervised.

    Listing a repo that has no assigned track yet is the POINT, not an edge
    case: discovery has to scan repos with zero mapping rows in order to surface
    their unassigned plans at all. That is why the watch-set cannot be derived
    from the mapping store's own rows — doing so would make a brand-new plan
    invisible until someone had already assigned it.

    Fail-soft in the same shape as the rest of this module: an absent,
    unreadable, or malformed declaration warns and yields just the ``extra_repos``,
    rather than taking the daemon down. An absent file is the ordinary
    first-run state, so it warns without ceremony.
    """
    path = Path(config_path).expanduser()

    selected: list[str] = []
    seen: set[str] = set()

    def _add(*, candidate: Path) -> None:
        candidate_norm = norm(repo=candidate)
        if candidate_norm not in seen:
            seen.add(candidate_norm)
            selected.append(candidate_norm)

    declared: list[str] = []
    try:
        document = jsonio.as_object(value=_parse_jsonc(text=path.read_text(encoding="utf-8")))
    # ValueError subsumes BOTH json.JSONDecodeError and the UnicodeDecodeError a
    # non-UTF-8 watch-set raises, so the tuple gets shorter, not longer.
    except (OSError, ValueError) as exc:
        warn(message=f"unreadable/unparsable watch-set {path}: {exc}")
        document = None
    if document is not None:
        entries = jsonio.as_list(value=document.get("repos"))
        if entries is None:
            warn(message=f"watch-set {path}: 'repos' is missing or not a list")
        else:
            declared = [entry for entry in entries if isinstance(entry, str)]

    for name in declared:
        candidate = Path(name).expanduser()
        if candidate.is_dir() and (candidate / "plan").is_dir():
            _add(candidate=candidate)

    for extra in extra_repos:
        candidate = Path(extra).expanduser()
        if candidate.is_dir():
            _add(candidate=candidate)

    return selected


def repo_root_present(*, repo: str) -> bool:
    """True if the repo checkout root itself exists as a directory.

    The daemon's GC preconditions on this so a TRANSIENTLY-unreachable repo (an
    unmounted volume, a repo mid-move) is not mistaken for "plan deleted" and its
    mapping row permanently dropped + later re-created with DEFAULT overrides
    (adversarial code review 2026-07-13, blocker B6). A missing root ⇒ keep the
    row and surface; only a plan gone UNDER an existing root is a real deletion.
    """
    try:
        return Path(repo).is_dir()
    except OSError:
        return False


def archived_or_gone(*, repo: str, topic: str) -> bool:
    """True if ``<repo>/plan/<topic>/`` is archived or deleted (ACTIVE wins).

    Used by the daemon's GC to drop a mapping row whose plan has been archived or
    deleted. The ACTIVE ``plan/<topic>`` is checked FIRST and wins: a live plan
    whose topic name ALSO happens to exist under ``plan/archive/`` (a new plan
    reusing a retired topic slug) must NOT be treated as archived — the old code
    checked the archive path first and would GC-drop the active plan's row every
    tick (adversarial code review 2026-07-13, blocker B6). Callers should
    precondition on :func:`repo_root_present` so a missing repo ROOT (transient
    unmount) is not read here as a gone plan.
    """
    base = Path(repo) / "plan"
    if (base / topic).is_dir():
        return False  # active plan present — wins over any same-named archive copy
    if (base / "archive" / topic).is_dir():
        return True  # archived
    return True  # plan dir gone under an existing repo root ⇒ deleted
