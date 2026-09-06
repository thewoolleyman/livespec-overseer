"""Repository-config readers retained from the retired foreman gatherer.

WHY THE NAME OUTLIVED ITS SUBJECT. The foreman seat was retired whole by
SPECIFICATION v047, and every gatherer that drove this module went with it. Two
functions did NOT, because bucket-1 code reaches them: `_registry_epic` and
`ledger_comments` read `parse_repo_config` and `string_list`, the grooming
conformance readers and `scripts/check-full-autonomy-config-conformance.py`
read `parse_repo_config`. The module keeps its name so those imports stay
byte-stable across the cut rather than churning call sites for cosmetics.

WHAT LEFT WITH THE SEAT, so nobody reconstructs it from the name: the GitHub
release-lane fetch, the repo-slug derivation, the JSON-emitting source runner,
the dispatch-journal reader, the skip-payload constructor, and the
`default_needs_attention_command` probe. All six were the FOREMAN GATHERER's
primitives, all six lost their only callers, and the `OverseerSourceError`
failure track they returned on left with them (`overseer/errors.py` had no
other raiser).
"""

from __future__ import annotations

from pathlib import Path

import jsonio
from _foreman_vendor_path import VENDOR_PATHS_INSTALLED

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "parse_repo_config",
    "string_list",
    "strip_jsonc_line_comment",
]


def string_list(*, value: object) -> list[str] | None:
    items = jsonio.as_list(value=value)
    if items is None or not all(isinstance(item, str) for item in items):
        return None
    return [str(item) for item in items]


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
    path = repo / ".livespec.jsonc"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    stripped = "\n".join(strip_jsonc_line_comment(line=line) for line in text.splitlines())
    parsed = jsonio.parse_object(text=stripped)
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
