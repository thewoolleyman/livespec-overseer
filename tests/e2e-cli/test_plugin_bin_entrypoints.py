"""Executable E2E gate for every shipped plugin ``bin/`` launcher.

The inventory is ENUMERATED FROM THE TREE rather than tabulated here, so the gate
follows the shipped surface as it changes: when the foreman seat was retired
(SPECIFICATION v047) its eight launchers left `bin/` and this test simply stopped
probing them. The three foreman-specific E2E cases that used to sit beside it --
the `foreman-act` plugin-cache filing, its occupied-tmux refusal, and the seeded
seed-session/attention/cadence walk -- went with the launchers they drove.

NOT EVERY LAUNCHER IS AN ARGPARSE CLI, and this gate used to assume one was the only
kind there is: it probed ``--help`` and required exit 0 plus a ``usage:`` line from
every file in ``bin/``. ``llm-provider-manager`` is a CONSUMER WIRE PROTOCOL rather
than a human CLI -- SPECIFICATION/contracts.md requires "a missing or unknown
subcommand [to] emit the common single-line `invalid-request` object with exit `2`
before configuration, recovery or external access", and ``--help`` is an unknown
subcommand -- so answering ``usage:`` with exit 0 is precisely what it must NOT do.

The blanket probe is therefore split rather than relaxed, and the split is strictly
MORE discriminating than what it replaced: each launcher is now asserted against the
contract it actually has. A wire-protocol launcher that started printing usage text,
or an argparse launcher that started refusing ``--help``, both fail here now, and
neither would have before.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_BIN = ROOT / ".claude-plugin" / "bin"


def _scrubbed_env() -> dict[str, str]:
    removed = {"PYTHONPATH", "COVERAGE_PROCESS_START"}
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in removed and not key.startswith("COV_CORE_")
    }
    assert "PYTHONPATH" not in env
    return env


# Launchers whose argument surface is a consumer WIRE PROTOCOL, not a human CLI. Each
# maps to the exact single-line refusal the contract requires for an unknown subcommand.
WIRE_PROTOCOL_LAUNCHERS = {"llm-provider-manager": "invalid-request"}


def _probe(*, entrypoint):
    return subprocess.run(  # noqa: S603
        [str(entrypoint), "--help"],
        cwd=ROOT,
        env=_scrubbed_env(),
        check=False,
        capture_output=True,
        text=True,
        timeout=60.0,
    )


def test_every_plugin_bin_entrypoint_executes_help_from_clean_environment():
    entrypoints = sorted(path for path in PLUGIN_BIN.iterdir() if path.is_file())
    assert entrypoints, "plugin bin directory must ship executable entrypoints"
    assert set(WIRE_PROTOCOL_LAUNCHERS) <= {
        path.name for path in entrypoints
    }, "a wire-protocol launcher named here has left bin/; drop the entry with it"

    failures: list[str] = []
    for entrypoint in entrypoints:
        completed = _probe(entrypoint=entrypoint)
        combined = completed.stdout + completed.stderr
        if "Traceback" in combined:
            failures.append(f"{entrypoint.name} raised\nstderr:\n{completed.stderr}")
            continue
        expected_error = WIRE_PROTOCOL_LAUNCHERS.get(entrypoint.name)
        if expected_error is not None:
            _assert_wire_refusal(
                entrypoint=entrypoint, completed=completed, expected_error=expected_error
            )
            continue
        if completed.returncode != 0:
            failures.append(
                f"{entrypoint.name} exited {completed.returncode}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
            continue
        assert f"usage: {entrypoint.name}" in combined

    assert failures == []


def _assert_wire_refusal(*, entrypoint, completed, expected_error):
    """`--help` is an unknown subcommand: one JSON line, the typed refusal, exit 2."""
    lines = completed.stdout.splitlines()
    assert len(lines) == 1, f"{entrypoint.name} must write exactly one line, wrote {lines!r}"
    body = json.loads(lines[0])
    assert body["status"] == "error"
    assert body["error_type"] == expected_error
    assert completed.returncode == 2
    assert "usage:" not in completed.stdout + completed.stderr
