"""Root-tree pairing test for Codex restart launch interlocks."""

from __future__ import annotations

from _supervisor_launch import canonical_codex_session_id


def test_codex_resume_interlock_accepts_only_canonical_uuid() -> None:
    """A picker-inducing missing or noncanonical id must fail closed."""
    session_id = "019ffd1a-254b-7342-865a-40a4b8a1cf43"

    assert canonical_codex_session_id(value=session_id) == session_id
    assert canonical_codex_session_id(value="") is None
    assert canonical_codex_session_id(value=session_id.upper()) is None
    assert canonical_codex_session_id(value=object()) is None
