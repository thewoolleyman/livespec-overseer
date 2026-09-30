"""Plugin-root validation is what makes a harness binding thin instead of trusting.

SPECIFICATION/contracts.md requires every manager binding to resolve
this plugin's root through its harness-defined discovery, canonicalize it to an ABSOLUTE
directory and VALIDATE it before invoking anything. Validation requires a regular UTF-8
JSON `plugin.json` named exactly `livespec-overseer` with non-empty `version` and
`description`; a regular UTF-8 JSON `.codex-plugin/plugin.json` whose `name`, `version`
and `description` EQUAL the outer manifest's and whose `skills` is exactly
`./.codex-plugin/skills/`; and the three manager bindings plus the shared prose as regular
files. Any missing required file, malformed manifest, wrong name or unequal lockstep field
is a mismatched plugin manifest, which the binding reports as `internal-bug` with exit
`70`.

EACH REJECTION LEG IS DRIVEN SEPARATELY, from a root that is otherwise COMPLETE. A gate
built by validating one broken fixture proves only that something was noticed; it cannot
tell a validator that checks the codex `skills` value from one that stops at the outer
manifest and gets lucky. So every test below starts from a known-good root, breaks
exactly one thing, and asserts that one thing is refused -- and the first test asserts the
known-good root is ACCEPTED, without which every rejection leg would pass for a validator
that refuses everything.

Note that this module does NOT assert the manager executable's presence. The contract
splits those concerns: the root's manifests and surface files are validated here, while a
missing, non-regular or non-executable plugin path is a LAUNCH failure reported by the
entrypoint. Both land on `internal-bug`/70, so collapsing them would be invisible -- and
would also make this validator refuse a correctly-shipped surface whose engine is
installed separately.
"""

from __future__ import annotations

import importlib
import json
import pathlib
from typing import Any

__all__: list[str] = []

MODULE_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_binding_root.py"

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


def _binding_root_module() -> Any:
    assert MODULE_PATH.is_file(), "overseer/_lpm_binding_root.py must exist"
    return importlib.import_module("_lpm_binding_root")


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


def _refusal(*, root: pathlib.Path) -> Any:
    return _binding_root_module().validated_plugin_root(plugin_root=root).failure()


def test_a_complete_root_is_accepted_and_returned_canonical_and_absolute(
    tmp_path: pathlib.Path,
) -> None:
    """Without this leg every rejection test below would pass for a blanket refusal."""
    root = _complete_root(tmp_path=tmp_path)
    indirect = root / ".codex-plugin" / ".."

    accepted = _binding_root_module().validated_plugin_root(plugin_root=indirect).unwrap()

    assert accepted == root.resolve()
    assert accepted.is_absolute()


def test_a_root_that_is_not_a_directory_is_a_mismatched_manifest(
    tmp_path: pathlib.Path,
) -> None:
    refusal = _refusal(root=tmp_path / "absent")

    assert refusal.error_type == "internal-bug"


def test_a_malformed_outer_manifest_is_refused(tmp_path: pathlib.Path) -> None:
    root = _complete_root(tmp_path=tmp_path)
    _write(path=root / "plugin.json", text="{not json")

    assert _refusal(root=root).error_type == "internal-bug"


def test_a_manifest_that_is_valid_json_but_not_an_object_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    """`[]` parses; it just cannot carry a name. Parsing is not the same as conforming."""
    root = _complete_root(tmp_path=tmp_path)
    _write(path=root / "plugin.json", text="[]")

    assert _refusal(root=root).error_type == "internal-bug"


def test_an_absent_or_malformed_nested_codex_manifest_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    """The nested manifest is loaded on its own legs, not inferred from its sibling."""
    absent = _complete_root(tmp_path=tmp_path / "absent")
    (absent / ".codex-plugin" / "plugin.json").unlink()
    malformed = _complete_root(tmp_path=tmp_path / "malformed")
    _write(path=malformed / ".codex-plugin" / "plugin.json", text="{not json")

    assert _refusal(root=absent).error_type == "internal-bug"
    assert ".codex-plugin/plugin.json" in _refusal(root=absent).message
    assert _refusal(root=malformed).error_type == "internal-bug"


def test_an_outer_manifest_with_the_wrong_name_is_refused(tmp_path: pathlib.Path) -> None:
    root = _complete_root(tmp_path=tmp_path)
    _write(path=root / "plugin.json", text=json.dumps({**MANIFEST, "name": "some-other-plugin"}))

    assert _refusal(root=root).error_type == "internal-bug"


def test_an_outer_manifest_with_an_empty_lockstep_field_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    root = _complete_root(tmp_path=tmp_path)
    _write(path=root / "plugin.json", text=json.dumps({**MANIFEST, "version": ""}))

    assert _refusal(root=root).error_type == "internal-bug"


def test_a_nested_codex_manifest_that_drifted_on_a_lockstep_field_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    """The lockstep fields are the whole point: availability must agree across harnesses."""
    root = _complete_root(tmp_path=tmp_path)
    _write(
        path=root / ".codex-plugin" / "plugin.json",
        text=json.dumps({**CODEX_MANIFEST, "version": "0.0.1"}),
    )

    assert _refusal(root=root).error_type == "internal-bug"


def test_a_nested_codex_manifest_with_the_wrong_skills_value_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    """`skills` is the Codex surface's registration data, not decoration."""
    root = _complete_root(tmp_path=tmp_path)
    _write(
        path=root / ".codex-plugin" / "plugin.json",
        text=json.dumps({**CODEX_MANIFEST, "skills": "./skills/"}),
    )

    assert _refusal(root=root).error_type == "internal-bug"


def test_each_required_surface_file_is_independently_required(
    tmp_path: pathlib.Path,
) -> None:
    """Driven once per file, so no single one can be the only one actually checked."""
    unrefused: list[str] = []
    for relative in SURFACE_FILES:
        root = _complete_root(tmp_path=tmp_path / relative.replace("/", "_"))
        (root / relative).unlink()
        if _refusal(root=root).error_type != "internal-bug":
            unrefused.append(relative)

    assert unrefused == [], f"these required surface files were not required: {unrefused}"


def test_a_required_surface_path_that_is_a_directory_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    """The contract says REGULAR file; a directory at the path satisfies `exists` only."""
    root = _complete_root(tmp_path=tmp_path)
    prose = root / "prose" / "llm-provider-manager.md"
    prose.unlink()
    prose.mkdir()

    assert _refusal(root=root).error_type == "internal-bug"


def test_every_refusal_message_names_the_root_relative_cause_and_stays_secret_free(
    tmp_path: pathlib.Path,
) -> None:
    root = _complete_root(tmp_path=tmp_path)
    (root / "prose" / "llm-provider-manager.md").unlink()

    message = _refusal(root=root).message

    assert "prose/llm-provider-manager.md" in message
    assert "internal-bug" not in message
