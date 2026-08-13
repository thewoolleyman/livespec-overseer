"""Integration-tier regression: the read-first chain resolves with NO handoff file.

The read-first target a track hands to its sessions is the plan's LEDGER-HELD PLAN
STATE — the entries on the governed plan's ledger epic — not `plan/<topic>/handoff.md`
(SPECIFICATION/spec.md section "Track discovery and the mapping store", and
SPECIFICATION/contracts.md section "The restart interlock" / section "Durable stores").

This test pins the COLD-OPEN case the file-shaped pointer could not survive: a governed
plan whose directory carries NO `handoff.md` at all, and a mapping row that records no
handoff path. Both of the daemon's pastes into such a track — the wrap-up that opens the
round, and the single resume prompt handed to the respawned session — must resolve from
the repository path and the recorded epic id alone.

Each `handoff.md` absence assertion is paired with a SABOTAGE control on the same
string: the same predicate is re-run against a deliberately corrupted copy of the very
payload under test, and must report the hit. A bare absence would otherwise pass
vacuously on an empty or unexpectedly-short paste.

Tier: `tests.integration` is one of the documented default `scenario_tiers` prefixes.
"""

from __future__ import annotations

import io as _io

from overseer import registry, signals
from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    make_supervisor,
)
from overseer.test_supervisor_fakes import FakeTmux

EPIC = "overseer-pfpfty"


def _plan_directory_without_a_handoff(*, tmp_path, topic="coldopen"):
    """A discovered plan whose directory holds NO `handoff.md` — the cold-open shape."""
    repo = tmp_path / "repo"
    plan = repo / "plan" / topic
    plan.mkdir(parents=True)
    assert not (plan / "handoff.md").exists()
    return repo, topic


def _sabotaged(*, payload, repo, topic):
    """`payload` with a handoff pointer spliced back in — the positive control."""
    return f"{payload}\nread {repo}/plan/{topic}/handoff.md and follow it"


def test_cold_open_respawn_without_a_handoff_file_resolves_and_injects(*, tmp_path):
    """A track with no handoff file still warns, respawns, and resumes from its epic.

    The mapping row carries `epic` and nothing path-shaped: no `handoff`, no `resume`
    override. That is the row shape the store contract now describes, so the daemon has
    only the repository path and the epic id to build both pastes from.
    """
    repo, topic = _plan_directory_without_a_handoff(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = registry.Track(topic=topic, repo=str(repo), tmux=session, epic=EPIC)

    opened = sup.evaluate(track=track, act=True)

    assert opened.status == "warned"
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )

    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    restarted = sup.evaluate(track=track, act=True)

    assert restarted.status == "restarting"
    assert len([call for call in fake.calls if call[0] == "respawn"]) == 1

    wrapup, resume = fake.paste_texts()

    # The wrap-up names the ledger-held plan state by repository and epic id, and names
    # no handoff file. The epic id is the positive control on the SAME string; the
    # sabotage control proves the absence predicate can report a hit on this payload.
    assert EPIC in wrapup
    assert str(repo) in wrapup
    assert "handoff.md" not in wrapup
    assert "handoff.md" in _sabotaged(payload=wrapup, repo=repo, topic=topic)

    # The single resume prompt the fresh session is handed resolves the same way.
    assert EPIC in resume
    assert str(repo) in resume
    assert "handoff.md" not in resume
    assert "handoff.md" in _sabotaged(payload=resume, repo=repo, topic=topic)

    # Nothing in the act created the file the old pointer named, and the round closed.
    assert not (repo / "plan" / topic / "handoff.md").exists()
    assert not signals.state_path(repo=str(repo), topic=topic).exists()
