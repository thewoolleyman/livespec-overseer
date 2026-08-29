"""The watch-set declaration: its JSONC scanner, its entry shapes, and its two readers.

Split out of `_registry_discovery.py` when that module crossed the 200-LLOC soft band —
it had been carrying two concerns its own docstring already named separately, "the watch
set" and "the small JSONC scanner the watch-set declaration is parsed with", beside plan
discovery / the discovery ⋈ mapping join / archive-GC. Everything that reads
`~/.livespec-overseer-repos.json` lives here now, so the scanner sits with its only
consumers and stays private to them.

`_registry_discovery` imports both public readers back and re-exports them, and
`registry.py` re-exports that surface in turn, so no consumer's import changed.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import jsonio
from _registry_core import norm, warn

__all__: list[str] = [
    "repo_idle_nudge_from_config",
    "watch_set_from_config",
]


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


@dataclass(frozen=True, kw_only=True)
class _WatchEntry:
    """One parsed ``repos[]`` entry: where the checkout is, and what it overrides."""

    path: str
    idle_nudge: bool | None


def _watch_entries(*, declared: list[object]) -> list[_WatchEntry]:
    """Parse ``repos[]`` into entries, dropping anything unrecognizable.

    An entry is EITHER a bare path string — the original shape, and still the whole of
    every existing declaration on the fleet — OR an object ``{"path": …}`` that may also
    carry per-repo overrides beside it. Both are admitted side by side in ONE document,
    which is what makes the object form purely additive: nothing an operator already
    wrote has to change, and a repo grows an object only when it wants an override.

    An unrecognizable entry (a number, an object with no string ``path``) is dropped
    silently, exactly as a non-string entry always was — this is a hand-edited operator
    file, and the fail-soft posture is the rest of this module's too.
    """
    entries: list[_WatchEntry] = []
    for raw in declared:
        if isinstance(raw, str):
            entries.append(_WatchEntry(path=raw, idle_nudge=None))
            continue
        mapping = jsonio.as_object(value=raw)
        if mapping is None:
            continue
        path = mapping.get("path")
        if not isinstance(path, str):
            continue
        # The `idle_nudge_from_row` rule one tier down, and for the same reason: a
        # per-repo override is present ONLY if the entry carries a bool `idle_nudge`.
        # A missing (or non-bool) value means "no override" → None, so the per-track
        # field and then the daemon-wide default still decide — never "off".
        nudge = mapping.get("idle_nudge")
        entries.append(
            _WatchEntry(path=path, idle_nudge=nudge if isinstance(nudge, bool) else None)
        )
    return entries


def _read_watch_entries(*, path: Path) -> tuple[list[_WatchEntry], str | None]:
    """Read + parse the watch-set document into entries, plus a warning message or None.

    The message is RETURNED rather than warned here so the two public readers of this one
    document can differ on reporting. :func:`watch_set_from_config` runs every tick and
    owns the operator-facing diagnostic; :func:`repo_idle_nudge_from_config` reads the
    SAME file on the SAME tick and stays silent, because warning again would double-log
    every malformed declaration.

    A well-formed document that is not an object yields no entries and no warning, which
    is what it always did — reporting it is left alone rather than added here.
    """
    try:
        document = jsonio.as_object(value=_parse_jsonc(text=path.read_text(encoding="utf-8")))
    # ValueError subsumes BOTH json.JSONDecodeError and the UnicodeDecodeError a
    # non-UTF-8 watch-set raises, so the tuple gets shorter, not longer.
    except (OSError, ValueError) as exc:
        return [], f"unreadable/unparsable watch-set {path}: {exc}"
    if document is None:
        return [], None
    declared = jsonio.as_list(value=document.get("repos"))
    if declared is None:
        return [], f"watch-set {path}: 'repos' is missing or not a list"
    return _watch_entries(declared=declared), None


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

    The document is ``{"repos": [...]}``, parsed as JSONC rather than strict
    JSON: this is a HAND-EDITED operator file, so ``//`` comments beside an
    entry ("paused while the migration lands") are worth more than format
    purity, and the repo already carries the lenient parser.

    An entry is EITHER a bare ``"<checkout>"`` string or an object
    ``{"path": "<checkout>", ...}`` carrying per-repo overrides — see
    :func:`_watch_entries`. This function reads only the PATH out of either
    shape, so both are watched identically and an existing bare-string
    declaration keeps working untouched.

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

    declared, warning = _read_watch_entries(path=path)
    if warning is not None:
        warn(message=warning)

    for entry in declared:
        candidate = Path(entry.path).expanduser()
        if candidate.is_dir() and (candidate / "plan").is_dir():
            _add(candidate=candidate)

    for extra in extra_repos:
        candidate = Path(extra).expanduser()
        if candidate.is_dir():
            _add(candidate=candidate)

    return selected


def repo_idle_nudge_from_config(*, config_path: str | os.PathLike[str]) -> dict[str, bool]:
    """The per-repo ``idle_nudge`` overrides the watch-set declares, by normalized path.

    The MIDDLE tier of the idle-nudge precedence chain — per-track, then per-repo, then
    the daemon-wide default — resolved in
    ``_supervisor_idle_nudge_policy.resolve_idle_nudge`` like the other two, so the whole
    chain stays in one readable place. It lets an operator quiet (or un-quiet) a whole
    checkout without touching the daemon flag or every mapping row in it.

    A repo appears here ONLY when its entry is an object carrying a bool ``idle_nudge``.
    A bare-string entry and an object without the key are both ABSENT, which means "no
    override" rather than "off" — the same three-state reading the per-track field gets,
    and what keeps every existing bare-string declaration on exactly today's behaviour.

    Deliberately NOT filtered by the watch-set's exists-and-has-a-``plan/``-dir ADMISSION
    rule: admission decides what is SUPERVISED, while this map only records what an
    operator DECLARED about a repo. Keeping the two separate leaves this a pure read with
    no filesystem access, and means a temporarily-unmounted checkout does not silently
    lose its override the moment it goes missing.

    Deliberately silent, too. :func:`watch_set_from_config` reads the same document on
    the same tick and owns the diagnostic for it, so an absent, unreadable or malformed
    declaration yields an empty map here without a second warning.

    A repo declared twice resolves to its FIRST entry, matching the de-duplication
    :func:`watch_set_from_config` applies, so the two readings of one document can never
    disagree about which entry a duplicated repo actually is.
    """
    declared, _warning = _read_watch_entries(path=Path(config_path).expanduser())
    overrides: dict[str, bool] = {}
    for entry in declared:
        if entry.idle_nudge is None:
            continue
        key = norm(repo=Path(entry.path).expanduser())
        if key not in overrides:
            overrides[key] = entry.idle_nudge
    return overrides
