"""ANSI stripping and statusline context parsing for pane captures."""

from __future__ import annotations

import re

__all__: list[str] = [
    "codex_composer_placeholder_empty",
    "is_available_prompt",
    "parse_ctx_remaining",
    "strip_ansi",
]

# --------------------------------------------------------------------------- #
# ANSI stripping (terminal escape sequences corrupt naive substring matching).
# --------------------------------------------------------------------------- #

_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"  # CSI: colors, cursor moves, erases
    r"|\x1b\][^\x07]*\x07"  # OSC: e.g. terminal-title, BEL-terminated
    r"|\x1b[@-Z\\-_]"  # two-char escapes (e.g. ESC c)
)

_ANSI_SGR = r"(?:\x1b\[[0-9;]*m)*"
# Claude's generated composer text is rendered DIM: the ``Try "..."`` placeholder and,
# after a turn, a prompt suggestion such as ``continue`` (measured 2026-10-13 on Claude
# Code 2.1.296). Only an entirely dim remainder counts; any undimmed character is typed.
_DIM_TRY_PLACEHOLDER_RE = re.compile(
    rf"^{_ANSI_SGR}❯[ \xa0]+{_ANSI_SGR}\x1b\[2m[^\x1b\r\n]+\x1b\[0m{_ANSI_SGR}$"
)
_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")
_SGR_RESET = 0
_SGR_DIM = 2
_SGR_INDEXED_COLOR = 5
_SGR_NORMAL_INTENSITY = 22
_SGR_FOREGROUND = 38
_SGR_BACKGROUND = 48
_SGR_UNDERLINE = 58
_COLOR_OPERAND_COUNTS = {_SGR_DIM: 4, _SGR_INDEXED_COLOR: 2}


def strip_ansi(*, text: str) -> str:
    """Remove ANSI/VT escape sequences from captured pane text."""
    return _ANSI_RE.sub("", text)


def is_available_prompt(*, raw_line: str, plain_line: str) -> bool:
    """True for an empty prompt or Claude's ANSI-proven generated placeholder."""
    return (plain_line.startswith("❯") and not plain_line[1:].strip()) or (
        _DIM_TRY_PLACEHOLDER_RE.fullmatch(raw_line.strip()) is not None
    )


def _sgr_dim(*, parameters: str, dim: bool) -> bool:
    """Apply the intensity portions of one SGR sequence to ``dim``.

    Extended RGB background colors contain a literal ``2`` (for example,
    ``48;2;49;52;57``), which is a color-mode selector rather than SGR dim.  Skip
    those color operands before interpreting the remaining intensity codes.
    """
    codes = [int(value) for value in parameters.split(";") if value] or [0]
    index = 0
    while index < len(codes):
        code = codes[index]
        if code in {_SGR_FOREGROUND, _SGR_BACKGROUND, _SGR_UNDERLINE} and index + 1 < len(codes):
            mode = codes[index + 1]
            index += 1 + _COLOR_OPERAND_COUNTS.get(mode, 0)
            continue
        dim = {_SGR_RESET: False, _SGR_NORMAL_INTENSITY: False, _SGR_DIM: True}.get(code, dim)
        index += 1
    return dim


def _dim_codex_composer_row(*, raw_line: str) -> bool:
    """Whether one raw ``›`` row has a non-empty, entirely dim remainder."""
    dim = False
    cursor = raw_line.index("›") + 1
    saw_placeholder_glyph = False
    while cursor < len(raw_line):
        sgr = _SGR_RE.match(raw_line, cursor)
        if sgr is not None:
            dim = _sgr_dim(parameters=sgr.group(1), dim=dim)
            cursor = sgr.end()
            continue
        character = raw_line[cursor]
        cursor += 1
        if character == "\x1b":
            return False
        if character.isspace():
            continue
        if not dim:
            return False
        saw_placeholder_glyph = True
    return saw_placeholder_glyph


def _codex_composer_row(*, capture_text: str) -> str | None:
    """The current Codex composer: the non-empty row immediately above its statusline."""
    lines = capture_text.splitlines()
    for status_index in range(len(lines) - 1, -1, -1):
        if _CTX_RE.search(strip_ansi(text=lines[status_index])) is None:
            continue
        for composer_index in range(status_index - 1, -1, -1):
            if strip_ansi(text=lines[composer_index]).strip():
                return lines[composer_index]
        return None
    # The single-row shape keeps the pure style predicate directly testable.  A
    # multi-row capture with no statusline is not enough location evidence to act on.
    return lines[0] if len(lines) == 1 else None


def codex_composer_placeholder_empty(*, capture_text: str) -> bool:
    """True only when Codex's visible composer proves its placeholder is dim.

    Busy Codex panes retain the ``›`` row but lose the structural idle evidence.
    The placeholder's text rotates, so its ANSI SGR-2 styling, not its words,
    distinguishes an empty composer from typed input.  This requires a real dim
    glyph and fails closed for absent, malformed, or undimmed captures.
    """
    raw_line = _codex_composer_row(capture_text=capture_text)
    return (
        raw_line is not None
        and strip_ansi(text=raw_line).lstrip().startswith("›")
        and _dim_codex_composer_row(raw_line=raw_line)
    )


# --------------------------------------------------------------------------- #
# Context-% reading — anchored + fail-closed (see design.md, context-% reading,
# adversarial-review blocker #5).
# --------------------------------------------------------------------------- #

# Claude renders `Ctx: N% left`; Codex renders `Context N% left`. Both are the
# RUNTIME'S OWN computed number, which is the whole point of reading it here rather
# than recomputing occupancy ourselves — see the Codex note in `codex_sessions`.
_CTX_RE = re.compile(r"(?:Ctx:|Context)\s*(\d+)%\s*left")

# How many trailing non-empty rows to scan for the statusline. The live Claude
# TUI renders the statusline as the SECOND-to-last row — a footer hint line
# (`⏵⏵ bypass permissions…` / `? for shortcuts`) renders BELOW it (verified
# live 2026-07-13), so reading only the LAST row misses `Ctx:` entirely. A
# small bound (not the whole capture) preserves the anti-false-match intent
# (blocker #5): page content containing `Ctx: N% left` sits far above the
# bottom few rows.
_CTX_TAIL_ROWS = 4


def _tail_non_empty_lines(*, capture_text: str, n: int) -> list[str]:
    """The last ``n`` ANSI-stripped, non-empty lines, in top-to-bottom order."""
    out: list[str] = []
    for raw in reversed(capture_text.splitlines()):
        line = strip_ansi(text=raw).strip()
        if line:
            out.append(line)
            if len(out) >= n:
                break
    out.reverse()
    return out


def parse_ctx_remaining(*, capture_text: str) -> int | None:
    """Remaining-context percent from the statusline, anchored + fail-closed.

    Scans only the last few non-empty rows (`_CTX_TAIL_ROWS`) — the statusline
    is the SECOND-to-last row in the live TUI, with a footer hint line below it
    — and returns the LAST ``Ctx: N% left`` match found across them. Returns
    None ("unknown") if none of those rows carries a match; it NEVER scans the
    whole capture, because page content (including the overseer design doc
    itself) contains the literal string ``Ctx: N% left`` and would yield a false
    reading. "unknown" must NEVER count as a threshold crossing upstream.
    """
    matches: list[str] = []
    for line in _tail_non_empty_lines(capture_text=capture_text, n=_CTX_TAIL_ROWS):
        matches.extend(_CTX_RE.findall(line))
    if not matches:
        return None
    return int(matches[-1])
