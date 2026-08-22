"""Extracted supervisor beside-test builders."""

import json
import os

import _registry_core
import _supervisor_config
import registry
import signals
import supervisor

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


def make_plan(
    *,
    tmp_path,
    repo_name="repo",
    topic="topic",
    handoff=_ANCHORED_HANDOFF,
):
    repo = tmp_path / repo_name
    plan = repo / "plan" / topic
    plan.mkdir(parents=True)
    (plan / "handoff.md").write_bytes(handoff)
    return repo, topic


def mapped_track(*, repo, topic, session):
    """An ASSIGNED row in the shape assignment surfaces now write.

    No `handoff` (the store no longer carries one) and no `resume` (that field is the
    operator's optional override, not a derived line), so the daemon has only `repo` and
    `epic` to build both of its prompts from — exactly the production shape.
    """
    return registry.Track(
        topic=topic,
        repo=str(repo),
        tmux=session,
        epic=TEST_EPIC,
    )


def key_for(*, repo, topic):
    """The normalized in-memory inject-state key the supervisor uses."""
    return _supervisor_config.track_key(repo=str(repo), topic=topic)


def declare(*, repo, topic, value, mtime=1001.0):
    """Write the session's ONE state file with ``value`` (e.g. "ready", "blocked: x").

    The single indicator lives at ``<repo>/tmp/overseer/<topic>/.overseer-state`` — its
    parent dir does not exist yet, so create it. One file with a VALUE: there is no way
    to be simultaneously `ready` and `blocked`, which is the whole point.
    """
    path = signals.state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{value}\n")
    os.utime(path, (mtime, mtime))
    return path


def write_fresh_supervisor_state(*, repo, topic):
    """Write the supervisor-half freshness marker required by the daemon."""
    marker_topic = signals.supervisor_topic(entity_topic=topic)
    path = signals.marker_dir(repo=str(repo), topic=marker_topic) / ".supervisor-state"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"topic: {topic}\nupdated_at: 2999-01-01T00:00:00Z\nopen_obligations: []\n",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------- #
# CLI mapping edits.
# --------------------------------------------------------------------------- #


def isolate_store(*, tmp_path, monkeypatch):
    """Redirect the hard-coded mapping store at a tmp file.

    The de-gold-plated CLI (2026-07-13) no longer exposes ``--store``; the path is
    fixed to ``registry.DEFAULT_STORE_PATH``. Tests point that module default at a
    tmp file so a CLI ``main(argv=[...])`` never writes into the developer's real
    ``~/.livespec-overseer.jsonl``.
    """
    store = tmp_path / "map.jsonl"
    # Patch the module that DEFINES the default and RESOLVES it. `_store()` reads
    # `DEFAULT_STORE_PATH` as a bare module global, so patching the `registry` facade
    # would set an attribute nothing reads and let this CLI test append to the
    # developer's real ~/.livespec-overseer.jsonl.
    monkeypatch.setattr(_registry_core, "DEFAULT_STORE_PATH", store)
    # The STAMP sidecar needs the identical treatment, for the identical reason.
    # `resolve_stamp_store()` reads `DEFAULT_STAMP_PATH` as a bare module global too.
    # This was latent until a launch-time statusline baseline began being recorded on
    # the START path (2026-08-21): before that, no CLI `start` wrote a stamp, so an
    # unredirected stamp path never showed. Afterwards every CLI start test wrote into
    # the developer's real ~/.livespec-overseer-stamps.json -- 120 junk entries were
    # found in a live operator file, keyed by pytest tmp dirs that no longer exist.
    monkeypatch.setattr(_registry_core, "DEFAULT_STAMP_PATH", tmp_path / "stamps.json")
    # `add`/`start` now consult the real fleet manifest to detect cross-repo topic
    # collisions (for the single-dash prefix). Neutralize that read by default so a
    # CLI test is hermetic and never flakes on the host's actual fleet; a collision
    # test overrides this with its own set.
    monkeypatch.setattr(supervisor, "_cli_colliding", lambda: frozenset())
    return store


def write_session(*, sessions_dir, pid, name, cwd, proc_start="pt", status="idle"):
    payload = {"pid": pid, "name": name, "cwd": str(cwd), "procStart": proc_start, "status": status}
    (sessions_dir / f"{pid}.json").write_text(json.dumps(payload), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Row color: the operator scans the live table by hue. Green = working, yellow =
# idle/waiting-on-human, red = broken, default (uncolored) = unassigned. Color is
# TTY-only, so it never corrupts piped `list` output or the beside-tests' plain
# StringIO — the render gates on `out.isatty()`.
# --------------------------------------------------------------------------- #

GREEN = "\x1b[32m"

RESET = "\x1b[0m"
