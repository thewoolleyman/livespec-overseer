"""A bare launch is a profile CANDIDATE, not a rejection (`overseer-phz7te`).

`read_launch_profile` used to refuse the moment argv and the environ carried no model
token, which made the harness's ONE additional permitted model source unreachable for
every process launched bare. These tests pin the repaired order: assemble the candidate
from the proven live process first, complete it from the runtime source, and reject only
once neither source has named a model.

`complete_launch_profile` is imported INSIDE each test body via ``importlib`` and guarded
by a genuine assertion, so this file's Red moment is an assertion failure rather than a
collection error.
"""

from __future__ import annotations

import importlib

from _supervisor_launch_profile import read_launch_profile

__all__: list[str] = []

_CARRIER_PID = 2914615
_SESSION_ID = "01a08bff-a75e-75a1-bb61-209e13ac8994"


def _nul(*, argv: list[str]) -> bytes:
    return b"\0".join(part.encode() for part in argv) + b"\0"


def _capture_module():
    module = importlib.import_module("_supervisor_launch_profile_capture")
    assert hasattr(
        module, "complete_launch_profile"
    ), "_supervisor_launch_profile_capture.complete_launch_profile does not exist yet"
    return module


def _bare_codex_candidate() -> dict[str, str | None]:
    return read_launch_profile(
        pid=_CARRIER_PID,
        harness="codex",
        pane_pid=100,
        cmdline_of=lambda *, pid: _nul(argv=["codex"]) if pid == _CARRIER_PID else None,
        environ_of=lambda *, pid: b"",
        ppid_of=lambda *, pid: None,
    )


def _codex_identity(*, model: str | None):
    sources = importlib.import_module("_supervisor_launch_profile_sources")
    return sources.CodexModelSource(
        session_id=_SESSION_ID,
        cwd="/data/projects/livespec",
        codex_home="/home/ubuntu/.codex",
        read=lambda *, codex_home, session_id, cwd: model,
    )


def test_a_bare_codex_launch_yields_a_candidate_with_no_model_rather_than_a_problem():
    assert _bare_codex_candidate() == {"harness": "codex", "model": None, "wrapper": None}


def test_a_bare_candidate_is_completed_from_the_exact_identity_state_database_model():
    capture = _capture_module()

    profile = capture.complete_launch_profile(
        profile=_bare_codex_candidate(),
        harness="codex",
        pid=_CARRIER_PID,
        runtime_model_of=lambda *, pid: None,
        codex_identity=_codex_identity(model="gpt-5.6-sol"),
    )

    assert profile == {"harness": "codex", "model": "gpt-5.6-sol", "wrapper": None}


def test_a_bare_candidate_no_source_can_complete_is_rejected_naming_the_pid_and_harness():
    capture = _capture_module()

    problem = capture.complete_launch_profile(
        profile=_bare_codex_candidate(),
        harness="codex",
        pid=_CARRIER_PID,
        runtime_model_of=lambda *, pid: None,
        codex_identity=_codex_identity(model=None),
    )

    assert isinstance(problem, capture.LaunchProfileProblem)
    assert f"pid {_CARRIER_PID}" in problem.message
    assert "no usable model token" in problem.message
    assert "codex" in problem.message
