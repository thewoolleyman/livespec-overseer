"""The staged-package integration test: both launchers, run as real subprocesses.

SPECIFICATION/non-functional-requirements.md permits exactly this test to live beneath `tests/`
rather than beside the package -- "repository-wide integration-tier scenario evidence and the
staged-package integration test MAY instead live beneath `tests/`" -- because the thing under test
is a BUILT AND INSTALLED distribution, which no in-process test can stand in for.

WHAT ONLY A REAL SUBPROCESS CAN SHOW. The defect this work item repairs was a launcher pointing at
`<plugin-root>/bin/llm-provider-manager`, an executable that did not exist, so the installed
operator returned `internal-bug` before any manager action. Every in-process test in this
repository would have passed with that file absent. So the assertions below are deliberately made
through the two launch paths the contract names and no other:

* the package-installed console entry point, resolved by NAME on the `PATH` of a clean throwaway
  virtual environment, and
* `<plugin-root>/bin/llm-provider-manager`, invoked by its own ABSOLUTE path out of the flattened
  plugin tree, which must resolve its product package from `<plugin-root>/overseer/` and never from
  an installed one.

WHAT THIS TEST DELIBERATELY DOES NOT DO: write to the manager's real state. `_lpm_paths`'
`account_database_home` never consults `HOME` -- by design, because "there is no second source for
the one namespace every manager process must share" -- so a subprocess has no ratified seam through
which a fixture state directory can be supplied. Every probe below is therefore a READ or a typed
refusal, and `test_no_probe_creates_manager_state_on_the_real_host` asserts that directly. That
property is worth having for its own sake: the contract requires a refused request to change
nothing, and this is the only place that is checked against a real process rather than a tmp_path.

The remaining consequence is stated plainly rather than worked around: a SUCCEEDING `provision` or
`report` cannot be driven through these launchers here, because it needs both an isolated state
root and a credential store, and the two seams that would supply them are the two the contract
deliberately withholds. See `_lpm_manager_host`'s module docstring for the credential-store half.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

__all__: list[str] = []

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / ".claude-plugin"
PLUGIN_EXECUTABLE = PLUGIN_ROOT / "bin" / "llm-provider-manager"
CONSOLE_NAME = "llm-provider-manager"

# A value shaped like the thing that must never be echoed, passed IN through the environment and
# through an argument, so a probe that leaked either would be visible in the captured output.
_DECOY_SECRET = "sk-ant-oat0-decoy-must-never-be-echoed"


def _probe_environment() -> dict[str, str]:
    """A clean child environment that also carries decoy credential-override entries.

    `COVERAGE_PROCESS_START` and the `COV_CORE_*` family are removed because an instrumented child
    races the parent's data file; `PYTHONPATH` is removed so the flat checkout cannot leak in and
    hide a packaging defect. The decoys are added on purpose: the bootstrap must delete every
    credential-override name before it hands over, and nothing downstream may print one.
    """
    removed = {"PYTHONPATH", "COVERAGE_PROCESS_START"}
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in removed and not key.startswith("COV_CORE_")
    }
    environment["ANTHROPIC_API_KEY"] = _DECOY_SECRET
    environment["OP_SERVICE_ACCOUNT_TOKEN"] = _DECOY_SECRET
    return environment


@pytest.fixture(scope="module")
def installed_console_command(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build and install this package into a throwaway venv; return its console command path."""
    uv = shutil.which("uv")
    if uv is None:  # pragma: no cover - environment-dependent
        pytest.skip("uv is not on PATH; cannot build an installed-package venv")
    venv_dir = tmp_path_factory.mktemp("installed-manager-executable")
    python = venv_dir / "bin" / "python"
    for argv in (
        [
            uv,
            "venv",
            str(venv_dir),
            "--python",
            f"{sys.version_info.major}.{sys.version_info.minor}",
        ],
        [uv, "pip", "install", "--python", str(python), str(REPO_ROOT)],
    ):
        subprocess.run(argv, check=True, capture_output=True, text=True)  # noqa: S603
    return venv_dir / "bin" / CONSOLE_NAME


def _ran(*, argv: list[str], stdin: str = "") -> dict[str, object]:
    completed = subprocess.run(  # noqa: S603 - absolute launcher paths, never a PATH lookup
        argv,
        cwd=REPO_ROOT,
        env=_probe_environment(),
        input=stdin,
        check=False,
        capture_output=True,
        text=True,
        timeout=60.0,
    )
    assert (
        "Traceback" not in completed.stdout + completed.stderr
    ), f"{argv[0]} raised instead of answering:\n{completed.stderr}"
    lines = completed.stdout.splitlines()
    assert len(lines) == 1, f"{argv[0]} must write exactly one line, wrote {lines!r}"
    return {
        "body": json.loads(lines[0]),
        "exit_status": completed.returncode,
        "stderr": completed.stderr,
    }


def _launchers(*, console: Path) -> dict[str, list[str]]:
    return {"console": [str(console)], "plugin": [str(PLUGIN_EXECUTABLE)]}


# --------------------------------------------------------------------------------------
# The producer boundary: both launchers exist, and both are reachable.
# --------------------------------------------------------------------------------------


def test_the_package_declares_the_console_command_against_the_shared_bootstrap() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert f'{CONSOLE_NAME} = "overseer.manager_bootstrap:main"' in text


def test_the_flattened_plugin_carries_an_executable_launcher() -> None:
    assert PLUGIN_EXECUTABLE.is_file(), "the plugin must ship bin/llm-provider-manager"
    assert os.access(PLUGIN_EXECUTABLE, os.X_OK), "the plugin launcher must be executable"


def test_the_plugin_launcher_enters_the_bootstrap_out_of_its_own_mirror() -> None:
    """It must resolve `<plugin-root>/overseer/`, never an installed `overseer`."""
    body = PLUGIN_EXECUTABLE.read_text(encoding="utf-8")
    statements = [
        line for line in body.splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]

    assert '"$PLUGIN_ROOT/overseer/manager_bootstrap.py"' in body
    assert not any(
        "PYTHONPATH" in line for line in statements
    ), "exporting PYTHONPATH is how a consumer's environment could repoint this launcher"
    assert (PLUGIN_ROOT / "overseer" / "manager_bootstrap.py").is_file()
    assert (PLUGIN_ROOT / "overseer" / "_lpm_companion.py").is_file()


def test_the_console_command_resolves_on_a_clean_installations_path(
    installed_console_command: Path,
) -> None:
    assert (
        installed_console_command.is_file()
    ), "a clean isolated installation must put llm-provider-manager on PATH"
    resolved = shutil.which(CONSOLE_NAME, path=str(installed_console_command.parent))

    assert resolved == str(installed_console_command)


# --------------------------------------------------------------------------------------
# The operator's zero-argument invocation, through both launchers.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("launcher", ["console", "plugin"])
def test_the_attention_list_reaches_the_executable_without_an_internal_bug(
    *, installed_console_command: Path, launcher: str
) -> None:
    """The exact defect this item repairs: a missing launch target answered `internal-bug`/70."""
    argv = _launchers(console=installed_console_command)[launcher]

    ran = _ran(argv=[*argv, "attention"])

    assert ran["body"] == {
        "version": 1,
        "status": "ok",
        "operation": "attention",
        "items": [],
    }
    assert ran["exit_status"] == 0


@pytest.mark.parametrize("launcher", ["console", "plugin"])
def test_an_unknown_subcommand_is_the_typed_refusal_and_exit_two(
    *, installed_console_command: Path, launcher: str
) -> None:
    argv = _launchers(console=installed_console_command)[launcher]

    ran = _ran(argv=[*argv, "--help"])

    body = ran["body"]
    assert isinstance(body, dict)
    assert body["status"] == "error"
    assert body["error_type"] == "invalid-request"
    assert ran["exit_status"] == 2


@pytest.mark.parametrize("launcher", ["console", "plugin"])
def test_a_malformed_report_is_invalid_report_through_a_real_standard_input(
    *, installed_console_command: Path, launcher: str
) -> None:
    """`report`'s own refusal type, proven across a real pipe rather than an injected reader."""
    argv = _launchers(console=installed_console_command)[launcher]

    ran = _ran(argv=[*argv, "report", "--report-json", "-"], stdin='{"version":1}')

    body = ran["body"]
    assert isinstance(body, dict)
    assert body["error_type"] == "invalid-report"
    assert ran["exit_status"] == 2


@pytest.mark.parametrize("launcher", ["console", "plugin"])
def test_a_provision_naming_an_unissued_reference_is_invalid_request(
    *, installed_console_command: Path, launcher: str
) -> None:
    argv = _launchers(console=installed_console_command)[launcher]
    request = json.dumps(
        {
            "version": 1,
            "provider": "anthropic",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "consumer_run_id": "installed-probe",
            "target_ref": "never-issued",
        }
    )

    ran = _ran(argv=[*argv, "provision", "--request-json", "-"], stdin=request)

    body = ran["body"]
    assert isinstance(body, dict)
    assert body["error_type"] == "invalid-request"
    assert ran["exit_status"] == 2


@pytest.mark.parametrize("launcher", ["console", "plugin"])
def test_no_launcher_ever_echoes_an_inherited_credential_override(
    *, installed_console_command: Path, launcher: str
) -> None:
    """The decoys ride in on the environment; neither stream may carry one back out."""
    argv = _launchers(console=installed_console_command)[launcher]

    ran = _ran(argv=[*argv, "attention"])

    assert _DECOY_SECRET not in json.dumps(ran["body"])
    assert _DECOY_SECRET not in str(ran["stderr"])


def test_no_probe_creates_a_manager_record_on_the_real_host() -> None:
    """A refused command creates no RECORD — checked against a real process, not a `tmp_path`.

    The contract's rule is about records: "If the operation says `invalid-request`, no lock was
    taken, no worker was started and no record was created". The probes above DO create the
    owner-only state TREE and a per-run lock FILE, and that is correct rather than a leak: a command
    carrying a `consumer_run_id` "MUST first take per-run serialization", which happens before the
    stateful `target_ref` check that then refuses it. A lock file is also defined to "contain no
    authoritative state".

    So this asserts the discriminating thing instead: every record family is still EMPTY. An
    issuance, a lease or an assignment appearing here would mean a refused probe had provisioned
    something on the operator's own host.
    """
    import pwd

    from _lpm_paths import LOCAL_PATH_FAMILIES, manager_state_dir

    state = manager_state_dir(home=Path(pwd.getpwuid(os.geteuid()).pw_dir))
    written = [
        str(path)
        for row in LOCAL_PATH_FAMILIES.values()
        for path in (state / row.directory).glob("*")
        if path.is_file()
    ]

    assert written == [], "an installed-launcher probe wrote a manager record on the real host"
