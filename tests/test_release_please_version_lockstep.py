"""Release-please gates for mirrored package and plugin version data."""

from __future__ import annotations

import json
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_VERSION_PATH = ROOT / "overseer" / "version.json"
PLUGIN_VERSION_PATH = ROOT / ".claude-plugin" / "overseer" / "version.json"


def _release_please_json_version_targets(*, config: dict[str, object]) -> dict[str, str]:
    """Every release-please JSON file target that updates a top-level version."""
    packages = config.get("packages", {})
    if not isinstance(packages, dict):
        return {}

    targets: dict[str, str] = {}
    for package in packages.values():
        if not isinstance(package, dict):
            continue
        extra_files = package.get("extra-files", [])
        if not isinstance(extra_files, list):
            continue
        for entry in extra_files:
            if (
                isinstance(entry, dict)
                and entry.get("type") == "json"
                and isinstance(entry.get("path"), str)
            ):
                targets[entry["path"]] = str(entry.get("jsonpath", ""))
    return targets


def _with_synthetic_release_version(*, path: Path, version: str) -> str:
    """Apply the only release-please JSON update shape this repo declares."""
    document = json.loads(path.read_text(encoding="utf-8"))
    document["version"] = version
    return json.dumps(document, indent=2) + "\n"


def test_plugin_version_json_matches_package_version_json():
    package_version = json.loads(PACKAGE_VERSION_PATH.read_text(encoding="utf-8"))["version"]
    plugin_version = json.loads(PLUGIN_VERSION_PATH.read_text(encoding="utf-8"))["version"]

    assert plugin_version == package_version, (
        f".claude-plugin/overseer/version.json says {plugin_version!r} but "
        f"overseer/version.json says {package_version!r}; the shipped plugin mirror drifted"
    )


def test_release_please_json_version_target_parser_ignores_malformed_entries():
    assert _release_please_json_version_targets(config={"packages": []}) == {}
    assert _release_please_json_version_targets(
        config={
            "packages": {
                "bad-package": [],
                "bad-extra-files": {"extra-files": {}},
                "mixed": {
                    "extra-files": [
                        "not-a-dict",
                        {"type": "toml", "path": "pyproject.toml"},
                        {"type": "json"},
                        {
                            "type": "json",
                            "path": "overseer/version.json",
                            "jsonpath": "$.version",
                        },
                    ]
                },
            }
        }
    ) == {"overseer/version.json": "$.version"}


def test_release_please_bumps_both_mirrored_version_json_files():
    config = json.loads((ROOT / "release-please-config.json").read_text(encoding="utf-8"))

    mirrored_version_paths = {
        "overseer/version.json",
        ".claude-plugin/overseer/version.json",
    }
    json_version_targets = _release_please_json_version_targets(config=config)
    assert {path: json_version_targets.get(path) for path in mirrored_version_paths} == {
        "overseer/version.json": "$.version",
        ".claude-plugin/overseer/version.json": "$.version",
    }, "release-please must bump both mirrored version.json files via the same JSON path"

    bumped = {
        path: _with_synthetic_release_version(path=ROOT / path, version="9.99.0")
        for path in mirrored_version_paths
    }
    assert len(set(bumped.values())) == 1, (
        "a future release-please JSON version bump would not leave the mirrored "
        f"version.json files byte-identical: {sorted(bumped)}"
    )
