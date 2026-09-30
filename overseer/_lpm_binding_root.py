"""Plugin-root and manifest validation: what a thin manager binding must prove first.

SPECIFICATION/contracts.md requires every harness binding to resolve this
plugin's root through its own harness-defined discovery, canonicalize it to an ABSOLUTE
directory, and validate it BEFORE invoking the manager. Validation requires a regular
UTF-8 JSON `plugin.json` whose `name` is exactly `livespec-overseer` and whose `version`
and `description` are non-empty strings; a regular UTF-8 JSON `.codex-plugin/plugin.json`
whose `name`, `version` and `description` EQUAL those outer values and whose `skills` is
exactly `./.codex-plugin/skills/`; and the three manager bindings plus the shared prose as
regular files. A missing required file, malformed manifest, wrong name or unequal lockstep
field is a mismatched plugin manifest, reported as `internal-bug` with exit `70`.

WHY A BINDING VALIDATES A ROOT IT DID NOT AUTHOR. The root arrives from harness plugin
discovery — a cache directory, a `codex plugin list` answer, a dogfooding checkout. The
binding cannot assume any of those resolved to THIS plugin at the version whose contract
it is about to execute, and the failure mode of assuming so is not a clean error: it is
reading one plugin's prose and running another plugin's executable. Refusing up front,
before any launch, is the only point where that is cheap to catch.

THE MANAGER EXECUTABLE IS DELIBERATELY NOT CHECKED HERE. The contract separates a
mismatched MANIFEST from a missing, non-regular or non-executable plugin PATH; both land
on `internal-bug`/70, but they are different findings and the launch boundary owns the
second. Folding it in would also make this validator refuse a correctly-shipped operator
surface whose engine is installed by a separate deliverable, which is exactly the state
this repository ships in today.

LOCKSTEP IS COMPARED, NOT RE-DERIVED. The nested Codex manifest's three fields are checked
for EQUALITY against the outer manifest rather than against any literal of their own, so
the validator keeps working across a release bump without being part of the release.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_results import ManagerError, internal_bug

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "CODEX_MANIFEST_RELATIVE_PATH",
    "CODEX_SKILLS_VALUE",
    "LOCKSTEP_FIELDS",
    "MANIFEST_RELATIVE_PATH",
    "PLUGIN_NAME",
    "REQUIRED_SURFACE_FILES",
    "validated_plugin_root",
]

PLUGIN_NAME: Final = "livespec-overseer"
MANIFEST_RELATIVE_PATH: Final = "plugin.json"
CODEX_MANIFEST_RELATIVE_PATH: Final = ".codex-plugin/plugin.json"
CODEX_SKILLS_VALUE: Final = "./.codex-plugin/skills/"

LOCKSTEP_FIELDS: Final[tuple[str, ...]] = ("name", "version", "description")

# The operation's own four shipped artifacts. The three bindings are listed separately
# rather than derived from a harness table because the contract names these exact paths,
# and the pi entry's `livespec-overseer-` prefix is a real difference in shape -- pi's
# skill namespace is flat -- not a formatting variation.
REQUIRED_SURFACE_FILES: Final[tuple[str, ...]] = (
    "skills/llm-provider-manager/SKILL.md",
    ".codex-plugin/skills/llm-provider-manager/SKILL.md",
    ".pi-plugin/skills/livespec-overseer-llm-provider-manager/SKILL.md",
    "prose/llm-provider-manager.md",
)


@dataclass(frozen=True, kw_only=True)
class _Manifest:
    """A parsed manifest object, carried with the root-relative path that produced it."""

    relative_path: str
    members: dict[str, object]


def _mismatch(*, detail: str) -> ManagerError:
    """Every finding in this module is the contract's one mismatched-manifest result."""
    return internal_bug(message=f"mismatched plugin manifest: {detail}")


def _loaded_manifest(*, root: Path, relative_path: str) -> Result[_Manifest, ManagerError]:
    path = root / relative_path
    if not path.is_file():
        return Failure(_mismatch(detail=f"{relative_path} is not a regular file"))
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return Failure(_mismatch(detail=f"{relative_path} is not readable UTF-8 JSON"))
    if not isinstance(parsed, dict):
        return Failure(_mismatch(detail=f"{relative_path} is not a JSON object"))
    members: dict[str, object] = parsed
    return Success(_Manifest(relative_path=relative_path, members=members))


def _non_empty_string(*, manifest: _Manifest, field: str) -> Result[str, ManagerError]:
    value = manifest.members.get(field)
    if not isinstance(value, str) or not value:
        return Failure(
            _mismatch(detail=f"{manifest.relative_path} {field} is not a non-empty string")
        )
    return Success(value)


def _outer_manifest_values(*, manifest: _Manifest) -> Result[dict[str, str], ManagerError]:
    values: dict[str, str] = {}
    for field in LOCKSTEP_FIELDS:
        resolved = _non_empty_string(manifest=manifest, field=field)
        if isinstance(resolved, Failure):
            return resolved
        values[field] = resolved.unwrap()
    if values["name"] != PLUGIN_NAME:
        return Failure(_mismatch(detail=f"{manifest.relative_path} name is not {PLUGIN_NAME!r}"))
    return Success(values)


def _codex_manifest_agrees(
    *, manifest: _Manifest, outer: dict[str, str]
) -> Result[None, ManagerError]:
    for field in LOCKSTEP_FIELDS:
        if manifest.members.get(field) != outer[field]:
            return Failure(
                _mismatch(
                    detail=f"{manifest.relative_path} {field} differs from the outer manifest"
                )
            )
    if manifest.members.get("skills") != CODEX_SKILLS_VALUE:
        return Failure(
            _mismatch(detail=f"{manifest.relative_path} skills is not {CODEX_SKILLS_VALUE!r}")
        )
    return Success(None)


def _surface_files_present(*, root: Path) -> Result[None, ManagerError]:
    for relative_path in REQUIRED_SURFACE_FILES:
        if not (root / relative_path).is_file():
            return Failure(_mismatch(detail=f"{relative_path} is not a regular file"))
    return Success(None)


def validated_plugin_root(*, plugin_root: Path) -> Result[Path, ManagerError]:
    """Canonicalize `plugin_root` and prove it is this plugin, or report the mismatch."""
    # No separate directory check: a root that is absent, or that is a file, simply has
    # no regular `plugin.json` under it, and `_loaded_manifest` already reports exactly
    # that. A second check here would add a branch that says the same thing twice.
    root = plugin_root.resolve()
    manifest = _loaded_manifest(root=root, relative_path=MANIFEST_RELATIVE_PATH)
    if isinstance(manifest, Failure):
        return manifest
    outer = _outer_manifest_values(manifest=manifest.unwrap())
    if isinstance(outer, Failure):
        return outer

    codex = _loaded_manifest(root=root, relative_path=CODEX_MANIFEST_RELATIVE_PATH)
    if isinstance(codex, Failure):
        return codex
    agreement = _codex_manifest_agrees(manifest=codex.unwrap(), outer=outer.unwrap())
    if isinstance(agreement, Failure):
        return agreement

    surface = _surface_files_present(root=root)
    if isinstance(surface, Failure):
        return surface
    return Success(root)
