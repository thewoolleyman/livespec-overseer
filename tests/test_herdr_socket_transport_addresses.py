"""The herdr socket transport tests bind AF_UNIX addresses no one else can hold.

`tests/test_herdr_socket_transport.py` binds real AF_UNIX listeners. A bind on a
path that already exists fails with EADDRINUSE, so two listeners the suite binds
at one path — inside one test, or across two concurrent runs — make a test
fail intermittently instead of deterministically.

The case loop in `test_every_unusable_reply_envelope_fails_closed_naming_its_defect`
used to derive each listener's file name from `hash(defect)`, a string hash that
is salted per process, truncated to four digits and concatenated to a variable
width length. Two cases could therefore land on one name on an unlucky process.
Forcing every `hash()` to one value turns that unlucky draw into a certainty, so
the assertion does not depend on the salt.
"""

from __future__ import annotations

import builtins
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import test_herdr_socket_transport as transport_tests

__all__: list[str] = []

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSPORT_TESTS = REPO_ROOT / "tests" / "test_herdr_socket_transport.py"


def test_the_case_loop_addresses_do_not_depend_on_a_string_hash(*, monkeypatch: pytest.MonkeyPatch):
    created = tempfile.mkdtemp(prefix="hrdr")
    try:
        with monkeypatch.context() as patched:
            patched.setattr(builtins, "hash", lambda _value: 0)
            transport_tests.test_every_unusable_reply_envelope_fails_closed_naming_its_defect(
                socket_dir=Path(created)
            )
    finally:
        shutil.rmtree(created, ignore_errors=True)


def test_two_runs_started_at_the_same_moment_both_pass():
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "--no-cov",
        str(TRANSPORT_TESTS),
    ]
    runs = [
        subprocess.Popen(  # noqa: S603
            command,
            cwd=REPO_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for _ in range(2)
    ]
    outputs = [run.communicate(timeout=120)[0] for run in runs]
    for run, output in zip(runs, outputs, strict=True):
        assert run.returncode == 0, f"a concurrent run failed:\n{output}"
        assert "Address already in use" not in output
