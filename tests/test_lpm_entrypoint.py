"""The shared entrypoint every manager binding delegates to, and what it may not do.

SPECIFICATION/non-functional-requirements.md requires each manager binding to
resolve and validate the plugin root, DELEGATE TO SHARED IMPORTABLE CODE, and carry no
operation behavior of its own. The layer it delegates to is confined to exact argument
validation, `invalid-request` and pre-exec `internal-bug` construction, prevalidated
absolute-path executable launch, verbatim result presentation, and secret-free
explanation -- not manager behavior.

THE LAUNCH IS INJECTED, so these tests are hermetic: no subprocess, no plugin cache, no
credential. That is not merely convenient. The properties worth pinning here are all
about WHAT IS HANDED TO the launch and WHAT IS DONE WITH its answer, and a real
subprocess would hide both behind a process boundary. The recording double below captures
the argv, the stdin bytes and the executable path, which is exactly the evidence the
contract's rules are stated about.

The three rules this module exists to enforce, each of which has an easy wrong
implementation that a coarser test would accept:

* A REFUSED request must not reach the executable AT ALL. The easy wrong version launches
  first and maps a non-zero exit to `invalid-request`, which looks identical from the
  outside unless you ask whether the launch happened.
* The executable's JSON is presented VERBATIM and its exit status propagated UNCHANGED.
  The easy wrong version re-serializes the object -- which silently normalizes whitespace
  and member order -- or collapses an unfamiliar exit status onto a familiar one.
* The launch target is the ROOT'S OWN absolute `bin/llm-provider-manager`. The easy wrong
  version resolves the name on `PATH`, which the contract forbids because it would run
  whichever manager the consumer's environment happened to expose.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

__all__: list[str] = []

MODULE_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "llm_provider_manager.py"

MANIFEST = {
    "name": "livespec-overseer",
    "version": "9.9.9",
    "description": "Control-plane operator plugin for livespec.",
}
CODEX_MANIFEST = {**MANIFEST, "skills": "./.codex-plugin/skills/"}

SURFACE_FILES = (
    "skills/llm-provider-manager/SKILL.md",
    ".codex-plugin/skills/llm-provider-manager/SKILL.md",
    ".pi-plugin/skills/livespec-overseer-llm-provider-manager/SKILL.md",
    "prose/llm-provider-manager.md",
)

FOUR_PAIRS = [
    "--provider",
    "anthropic",
    "--account-id",
    "acct-1",
    "--kind",
    "oauth",
    "--purpose",
    "factory",
]


def _entrypoint() -> Any:
    assert MODULE_PATH.is_file(), "overseer/llm_provider_manager.py must exist"
    return importlib.import_module("llm_provider_manager")


@dataclass(kw_only=True)
class _RecordingLaunch:
    """A launch double that records its exact inputs and replays a fixed answer."""

    stdout: str = '{"version":1,"status":"ok","operation":"attention","items":[]}'
    exit_status: int = 0
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, *, executable: pathlib.Path, argv: tuple[str, ...], stdin_bytes: Any) -> Any:
        self.calls.append({"executable": executable, "argv": argv, "stdin_bytes": stdin_bytes})
        return _entrypoint().LaunchResult(stdout=self.stdout, exit_status=self.exit_status)


def _write(*, path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _complete_root(*, tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "plugin-root"
    _write(path=root / "plugin.json", text=json.dumps(MANIFEST))
    _write(path=root / ".codex-plugin" / "plugin.json", text=json.dumps(CODEX_MANIFEST))
    for relative in SURFACE_FILES:
        _write(path=root / relative, text="# binding\n")
    return root


def _run(*, root: pathlib.Path, arguments: list[str], launch: Any) -> Any:
    return _entrypoint().run_operator_invocation(
        arguments=arguments, plugin_root=root, launch=launch
    )


def test_a_valid_acquire_request_reaches_the_roots_own_absolute_executable(
    tmp_path: pathlib.Path,
) -> None:
    root = _complete_root(tmp_path=tmp_path)
    launch = _RecordingLaunch()

    _run(root=root, arguments=FOUR_PAIRS, launch=launch)

    assert len(launch.calls) == 1
    call = launch.calls[0]
    assert call["executable"] == root.resolve() / "bin" / "llm-provider-manager"
    assert call["executable"].is_absolute()
    assert call["argv"] == ("acquire", "--acquisition-json", "-")
    assert json.loads(call["stdin_bytes"].decode("utf-8"))["account_id"] == "acct-1"


def test_zero_arguments_launch_the_attention_list_with_no_standard_input(
    tmp_path: pathlib.Path,
) -> None:
    root = _complete_root(tmp_path=tmp_path)
    launch = _RecordingLaunch()

    _run(root=root, arguments=[], launch=launch)

    assert launch.calls[0]["argv"] == ("attention",)
    assert launch.calls[0]["stdin_bytes"] is None


def test_the_executable_json_is_presented_verbatim_and_its_exit_status_unchanged(
    tmp_path: pathlib.Path,
) -> None:
    """Byte-for-byte: a re-serializing presenter would reorder members and add spaces."""
    root = _complete_root(tmp_path=tmp_path)
    quirky = '{"version":1,  "status":"ok","operation":"acquire","record_id":"abc"}'
    launch = _RecordingLaunch(stdout=quirky, exit_status=3)

    presentation = _run(root=root, arguments=FOUR_PAIRS, launch=launch)

    assert presentation.stdout == quirky
    assert presentation.exit_status == 3


def test_a_refused_request_never_reaches_the_executable(tmp_path: pathlib.Path) -> None:
    """The discriminating property: refusal is PRE-EXEC, not a mapped launch failure."""
    root = _complete_root(tmp_path=tmp_path)
    launch = _RecordingLaunch()

    presentation = _run(root=root, arguments=["--provider", "anthropic"], launch=launch)

    assert launch.calls == [], "a rejected operator request must not launch the manager"
    assert json.loads(presentation.stdout)["error_type"] == "invalid-request"
    assert presentation.exit_status == 2


def test_a_mismatched_plugin_root_is_internal_bug_seventy_and_never_launches(
    tmp_path: pathlib.Path,
) -> None:
    root = _complete_root(tmp_path=tmp_path)
    (root / "prose" / "llm-provider-manager.md").unlink()
    launch = _RecordingLaunch()

    presentation = _run(root=root, arguments=FOUR_PAIRS, launch=launch)

    assert launch.calls == []
    assert json.loads(presentation.stdout)["error_type"] == "internal-bug"
    assert presentation.exit_status == 70


def test_the_root_is_validated_before_the_arguments_are(tmp_path: pathlib.Path) -> None:
    """Both are broken; the contract validates the root first, so 70 wins over 2."""
    root = _complete_root(tmp_path=tmp_path)
    (root / "prose" / "llm-provider-manager.md").unlink()

    presentation = _run(root=root, arguments=["garbage"], launch=_RecordingLaunch())

    assert presentation.exit_status == 70


def test_a_launch_that_fails_before_a_valid_result_is_internal_bug_seventy(
    tmp_path: pathlib.Path,
) -> None:
    """A missing or non-executable plugin path is the contract's other 70."""
    root = _complete_root(tmp_path=tmp_path)

    def _raising(*, executable: pathlib.Path, argv: Any, stdin_bytes: Any) -> Any:
        del argv, stdin_bytes
        raise OSError(f"no such executable: {executable}")

    presentation = _run(root=root, arguments=FOUR_PAIRS, launch=_raising)

    assert json.loads(presentation.stdout)["error_type"] == "internal-bug"
    assert presentation.exit_status == 70


def test_every_error_object_is_a_single_line_with_the_exact_four_members(
    tmp_path: pathlib.Path,
) -> None:
    """The contract permits no additional field, and `items` must stay one line."""
    root = _complete_root(tmp_path=tmp_path)

    presentation = _run(root=root, arguments=["garbage"], launch=_RecordingLaunch())

    assert "\n" not in presentation.stdout
    assert set(json.loads(presentation.stdout)) == {
        "version",
        "status",
        "error_type",
        "message",
    }


def test_subprocess_launch_runs_the_given_path_and_relays_its_stdout_and_status(
    tmp_path: pathlib.Path,
) -> None:
    """The real launch seam, driven against a stub executable rather than a double.

    Covers what the injected double structurally cannot: that the request bytes actually
    reach the child's standard input, and that an unfamiliar exit status survives the
    subprocess boundary instead of being normalized to 0 or 1.
    """
    module = _entrypoint()
    executable = tmp_path / "llm-provider-manager"
    executable.write_text('#!/bin/sh\nprintf \'{"echoed":"%s"}\' "$(cat)"\nexit 5\n')
    executable.chmod(0o755)

    result = module.subprocess_launch(
        executable=executable, argv=("acquire",), stdin_bytes=b"streamed"
    )

    assert result.stdout == '{"echoed":"streamed"}'
    assert result.exit_status == 5


def test_main_presents_exactly_one_line_and_returns_the_presentation_status(
    monkeypatch: Any, capsys: Any
) -> None:
    """`main` is the console seam: it must not invent a status or a second line.

    It is driven here against the SOURCE package, whose `default_plugin_root()` is the
    repository root -- which is deliberately not a plugin root, the manifests living
    under `.claude-plugin/`. So this also pins the seam's root-first ordering end to end:
    a bad argument list behind an unvalidated root reports `internal-bug`/70, not
    `invalid-request`/2.
    """
    module = _entrypoint()
    assert not (module.default_plugin_root() / "plugin.json").exists()
    monkeypatch.setattr(sys, "argv", ["llm-provider-manager", "garbage"])

    status = module.main()

    written = capsys.readouterr().out
    assert status == 70
    assert written.endswith("\n")
    assert written.count("\n") == 1
    assert json.loads(written)["error_type"] == "internal-bug"


def test_main_defaults_its_plugin_root_to_the_package_carriers_own_root() -> None:
    """The shipped mirror is the root a plugin-launched entrypoint must resolve to.

    SPECIFICATION/contracts.md requires the plugin executable to resolve its product
    package only from `<plugin-root>/overseer/`. Deriving the default root from the
    module's own location is what makes that true without an environment variable a
    consumer could repoint.
    """
    module = _entrypoint()

    default_root = module.default_plugin_root()

    assert default_root == pathlib.Path(module.__file__).resolve().parent.parent
