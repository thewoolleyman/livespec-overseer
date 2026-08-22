"""Extracted supervisor beside-test builders."""

__all__: list[str] = []

NUDGE_SENTINEL = "do NOT offer to stop"
TEST_EPIC = "overseer-test-epic"
RULE = "─" * 40
HINT = "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents"
SPINNER = "✻ Galloping… (running stop hooks… 1/3 · 24s · ↓ 1.4k tokens)"
WRAPUP_SENTINEL = "Declare your state by writing ONE line"
GREEN = "\x1b[32m"
RESET = "\x1b[0m"
_ANCHORED_HANDOFF = f"HANDOFF v1\n\n**Ledger anchor:** `{TEST_EPIC}`\n".encode()


def nudge_count(*, fake):
    return len([t for t in fake.paste_texts() if NUDGE_SENTINEL in t])


# --------------------------------------------------------------------------- #
# Panes that vanish or never come up. Every step of an act is a hard gate: an
# unresolvable pane, a respawn whose pane never becomes the expected runtime, and
# a fresh TUI sitting on a gate all STOP the act with the declaration preserved.
# --------------------------------------------------------------------------- #


def render_of(*, sup, views):
    """Render VIEWS and return what the daemon printed (the table + attention block)."""
    sup.render(rows=views)
    return sup.out.getvalue()


def row_line(*, out, topic):
    """The single rendered line for TOPIC (the data row, not the header)."""
    return next(ln for ln in out.splitlines() if topic in ln and "Topic" not in ln)


# --------------------------------------------------------------------------- #
# R1 — self-healing resume-submit (2026-07-18). A freshly-respawned Claude can
# DROP the resume line's Enter while still drawing its welcome screen (proven live
# 2026-07-17: fabro / autonomous-mode / overseer-rewrite all stranded this way in
# one day). The old code cleared the `ready` marker and logged "restarted" anyway,
# so the daemon never retried and the session sat idle with an un-run handoff. Now
# the daemon KEEPS the round open, marks `resume_pending`, and retries the SUBMIT
# ONLY (re-send Enter, never a re-respawn) until the box clears.
# --------------------------------------------------------------------------- #


def wrapup_count(*, fake):
    return len([t for t in fake.paste_texts() if WRAPUP_SENTINEL in t])


# --------------------------------------------------------------------------- #
# adopt: pick up live Claude sessions by their registry name (~/.claude/sessions).
# --------------------------------------------------------------------------- #


def cell_row(*, out, topic):
    """The single rendered DATA line for TOPIC (skipping the header row)."""
    return next(ln for ln in out.splitlines() if topic in ln and "Topic" not in ln)


# --------------------------------------------------------------------------- #
# Fail-soft marker I/O. The state file is written by the SESSION and read by the
# daemon, so every marker read/write/delete can fail on a tick (a directory in
# the file's place, an unwritable marker dir). Each failure must be LOGGED and
# the surrounding decision left in its safe default — never raised out of the
# tick, which would strand every other track the daemon is supervising.
# --------------------------------------------------------------------------- #
