"""`winding-down` has two liveness-disambiguated meanings in the protocol doc."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MARKER_PROTOCOL = _REPO_ROOT / "overseer" / "marker-protocol.md"


def _marker_protocol_text() -> str:
    return _MARKER_PROTOCOL.read_text(encoding="utf-8")


def _flattened_marker_protocol_text() -> str:
    return " ".join(_marker_protocol_text().split())


def test_marker_protocol_documents_live_winding_down_ack():
    """The original live-pane ACK meaning must stay documented."""
    text = _marker_protocol_text()

    assert "**`winding-down`** — the ACK" in text
    assert "I got the wrap-up and am wrapping up now." in text
    assert "fresh** ACK suppresses further re-warns" in text


def test_marker_protocol_documents_gone_winding_down_as_wound_down():
    """A gone session with `winding-down` is finished, parked, and quiet."""
    text = _flattened_marker_protocol_text()

    assert "`winding-down` + **NO live session**" in text
    assert "`wound-down`" in text
    assert "finished, parked, do not restart" in text
    assert "Liveness is the disambiguator" in text
