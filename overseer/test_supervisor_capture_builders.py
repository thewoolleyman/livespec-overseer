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


def idle_capture(*, ctx=None, body="", topic=None):
    """The idle box. ``topic`` renders the `-n <topic>` TITLED top border (B2)."""
    status = "  Opus 4.8 (1M context) | /x/repo"
    if ctx is not None:
        status += f" | Ctx: {ctx}% left"
    head = f"● {body}\n" if body else "● prior response\n"
    top = RULE if topic is None else ("─" * 30) + f" {topic} ──"
    return f"{head}{top}\n❯ \n{RULE}\n{status}\n{HINT}\n"


def busy_capture(*, ctx=None):
    """An actively-generating pane: the real spinner above the (idle-shaped) box."""
    return f"● response\n{SPINNER}\n" + idle_capture(ctx=ctx)


# The REAL live idle Codex TUI shape (verified 2026-07-17, codex-cli 0.144.5): a `›`
# input line above the Codex statusline `model · cwd · Context N% left · <name>` — NOT
# Claude's empty-`❯`-between-rules box. An UNNAMED session shows its UUID where a named
# one shows the thread_name; here we render the topic (a named session).
def codex_idle_capture(*, ctx=None, topic="topic"):
    status = "  gpt-5.5 high · /x/repo"
    if ctx is not None:
        status += f" · Context {ctx}% left"
    status += f" · {topic}"
    return f"● prior response\n› Write tests for @filename\n{status}\n"


def codex_busy_capture(*, ctx=None):
    """An actively-generating Codex pane: `esc to interrupt` (what `is_busy` matches) —
    the signal `_submit_prompt(expect_codex=True)` confirms a Codex submit by."""
    status = "  gpt-5.5 high · /x/repo"
    if ctx is not None:
        status += f" · Context {ctx}% left"
    return f"● response\n◦ Working (1s • esc to interrupt)\n› Write tests for @filename\n{status}\n"


# Legacy alias kept for readability in tests that predate the real-shape fixtures.
IDLE_BOX = idle_capture()


# The plan's WRITE-ONCE METADATA ANCHOR, in the shape assignment surfaces parse it from.
# A plan that carries one is the ordinary case: it is what lets an assignment surface
# record the track's `epic`, and therefore what lets the daemon build a resume prompt at
# all. A test that needs the anchor-less case passes `handoff=` without this line.
_ANCHORED_HANDOFF = f"HANDOFF v1\n\n**Ledger anchor:** `{TEST_EPIC}`\n".encode()
