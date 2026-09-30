"""ANSI stripping and statusline context parsing for pane captures."""

from __future__ import annotations

import re

__all__: list[str] = ["is_available_prompt", "parse_ctx_remaining", "strip_ansi"]

# --------------------------------------------------------------------------- #
# ANSI stripping (terminal escape sequences corrupt naive substring matching).
# --------------------------------------------------------------------------- #

_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"  # CSI: colors, cursor moves, erases
    r"|\x1b\][^\x07]*\x07"  # OSC: e.g. terminal-title, BEL-terminated
    r"|\x1b[@-Z\\-_]"  # two-char escapes (e.g. ESC c)
)

_ANSI_SGR = r"(?:\x1b\[[0-9;]*m)*"
_DIM_TRY_PLACEHOLDER_RE = re.compile(
    rf'^{_ANSI_SGR}❯[ \xa0]+{_ANSI_SGR}\x1b\[2mTry "[^"\r\n]+"\x1b\[0m{_ANSI_SGR}$'
)


def strip_ansi(*, text: str) -> str:
    """Remove ANSI/VT escape sequences from captured pane text."""
    return _ANSI_RE.sub("", text)


def is_available_prompt(*, raw_line: str, plain_line: str) -> bool:
    """True for an empty prompt or Claude's ANSI-proven generated placeholder."""
    return (plain_line.startswith("❯") and not plain_line[1:].strip()) or (
        _DIM_TRY_PLACEHOLDER_RE.fullmatch(raw_line.strip()) is not None
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
