"""Extracted supervisor beside-test builders."""

import signals
import supervisor
from test_supervisor_store_builders import declare

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


def arm_ready_marker(*, repo, topic, mtime=1001.0):
    """The session declares `ready` — the ONLY thing that authorizes a restart."""
    return declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=mtime)


def assert_no_tmux_scoping(*, command):
    """The L1 env inversion is REMOVED (plan/tmux-fleet-visibility): a spawn
    command must carry NO tmux socket scoping, so a bare `tmux ls` in the
    spawned agent lists the real fleet. This pins the ABSENCE so the prefix
    cannot silently regress."""
    assert "TMUX_TMPDIR" not in command
    assert "unset TMUX" not in command


# --------------------------------------------------------------------------- #
# Reboot recovery is runtime-dispatched (defect #5): a dead track whose TOPIC names a
# session in the persistent codex index is a CODEX track — resumed via `codex resume <id>`
# (option c) when its rollout survives, else skip+surface (option b), NEVER recreated as
# Claude. A topic absent from the index is a Claude track and recovers as before.
# --------------------------------------------------------------------------- #


def on_respawn(*, fake, after):
    """Run ``after(session)`` right after a SUCCESSFUL FakeTmux respawn.

    Models what the pane actually BECOMES once the respawn lands — a bare shell (the
    launch never came up), or a fresh TUI that opened on a trust/update gate.
    """
    inner = fake.respawn_pane

    def respawn(*, session, cwd, command, env=None):
        landed = inner(session=session, cwd=cwd, command=command, env=env)
        if landed:
            after(session)
        return landed

    fake.respawn_pane = respawn


# --------------------------------------------------------------------------- #
# The `NEEDS YOU` attention block (the daemon owns "what needs attention?").
#
# The bottom pane is an LLM: it prints text ONCE and that text then ages silently,
# so it reported tracks that had been resolved for minutes. Current state therefore
# belongs to the daemon's re-rendered table, which is free and cannot go stale.
# --------------------------------------------------------------------------- #


def unsubmitted_resume_capture(*, ctx=30, repo="/x/repo", epic=TEST_EPIC):
    """A freshly-respawned Claude with the resume line sitting UN-submitted in the box.

    The box holds the pasted ledger-epic resume prompt (a `❯ resume plan epic …` line
    between rules), so it is NOT the empty idle box (`input_box_ready` False) and NOT busy
    — exactly the stranded state a dropped Enter leaves. ``repo``/``epic`` default to the
    coordinates most callers use; a caller whose track has different ones passes its own,
    so the rendered box matches what the daemon would actually have pasted."""
    status = "  Opus 4.8 (1M context) | /x/repo"
    if ctx is not None:
        status += f" | Ctx: {ctx}% left"
    resume = supervisor.plan_epic_resume(repo=repo, epic=epic)
    return f"● welcome\n{RULE}\n❯ {resume}\n{RULE}\n{status}\n{HINT}\n"


def undeletable_state_file(*, repo, topic):
    """Put a DIRECTORY where the ``.overseer-state`` file belongs.

    ``unlink`` on a directory always fails (``EISDIR``) for every user including
    root, so this models an undeletable marker without a chmod the CI container
    (which runs as root) would ignore.
    """
    path = signals.state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()
    return path
