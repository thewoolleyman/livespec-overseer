#!/usr/bin/env python3
"""Refuse dispatch of live-exercise items lacking a parking acceptance label.

overseer-57f2 half (ii), maintainer-ratified 2026-08-17: the repo-wide
``dispatcher.acceptance_mode`` stays ``ai-only``, so a merged item auto-closes
on CI-green. An item whose acceptance genuinely requires LIVE-EXERCISE
evidence must therefore carry a per-item ``acceptance:ai-then-human`` (or
``acceptance:human-only``) label — the orchestrator's own per-item precedence
lever — so it parks post-merge in ``acceptance`` until a human accepts it
against recorded evidence. This guard makes that mechanical: the dispatch
entry point (``scripts/detached-dispatch.sh``) runs it for every ``impl:<id>``
argument and refuses the dispatch when the label is missing.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

__all__: list[str] = []

_LIVE_EXERCISE = re.compile(r"live[\s-]exercis|live[\s-]verif", re.IGNORECASE)
_PARKING_LABELS = frozenset({"acceptance:ai-then-human", "acceptance:human-only"})
_TEXT_KEYS = ("title", "description", "notes", "design", "acceptance_criteria")
_BD_ENV_OVERRIDE = "DISPATCH_ACCEPTANCE_GUARD_BD"

_EX_USAGE = 64
_EX_UNAVAILABLE = 69


def main(argv: list[str] | None = None) -> int:
    item_ids = sys.argv[1:] if argv is None else argv
    if not item_ids:
        _ = sys.stderr.write("usage: dispatch_acceptance_guard.py <work-item-id>...\n")
        return _EX_USAGE
    refused = False
    for item_id in item_ids:
        item = _show_item(item_id=item_id)
        if item is None:
            return _EX_UNAVAILABLE
        if _needs_parking_label(item=item):
            _ = sys.stderr.write(_refusal(item_id=item_id))
            refused = True
        else:
            _ = sys.stdout.write(f"dispatch acceptance guard: {item_id} ok\n")
    return 1 if refused else 0


def _needs_parking_label(*, item: dict[str, object]) -> bool:
    text = "\n".join(value for key in _TEXT_KEYS if isinstance(value := item.get(key), str))
    if _LIVE_EXERCISE.search(text) is None:
        return False
    labels = item.get("labels")
    if not isinstance(labels, list):
        return True
    label_set = {label for label in labels if isinstance(label, str)}
    return not (label_set & _PARKING_LABELS)


def _refusal(*, item_id: str) -> str:
    return (
        f"dispatch refused (overseer-57f2): {item_id} carries a live-exercise\n"
        "criterion but no parking acceptance label; under the repo-wide\n"
        "acceptance_mode=ai-only it would auto-close on CI-green with no recorded\n"
        "evidence. Label it first:\n"
        f"    bd label add {item_id} acceptance:ai-then-human\n"
        "(or acceptance:human-only), then re-dispatch; the item will park\n"
        "post-merge in `acceptance` until evidence-backed human acceptance.\n"
    )


def _show_item(*, item_id: str) -> dict[str, object] | None:
    command = [*_bd_command(), "show", item_id, "--json"]
    completed = subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        _ = sys.stderr.write(
            f"dispatch acceptance guard: `{' '.join(command)}` failed "
            f"(exit {completed.returncode}); refusing to dispatch blind.\n"
            f"{completed.stderr}"
        )
        return None
    return _parse_item(stdout=completed.stdout, item_id=item_id)


def _parse_item(*, stdout: str, item_id: str) -> dict[str, object] | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        _ = sys.stderr.write(
            f"dispatch acceptance guard: unparseable bd show output for {item_id}; "
            "refusing to dispatch blind.\n"
        )
        return None
    if isinstance(payload, list):
        payload = payload[0] if payload else None
    if not isinstance(payload, dict):
        _ = sys.stderr.write(
            f"dispatch acceptance guard: no record for {item_id}; " "refusing to dispatch blind.\n"
        )
        return None
    return payload


def _bd_command() -> list[str]:
    override = os.environ.get(_BD_ENV_OVERRIDE)
    if override:
        return [override]
    return [*_credential_wrapper(path=Path(".livespec.jsonc")), "bd"]


def _credential_wrapper(*, path: Path) -> list[str]:
    if not path.is_file():
        return []
    stripped = "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("//")
    )
    try:
        config = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    wrapper = config.get("credential_wrapper") if isinstance(config, dict) else None
    if isinstance(wrapper, list):
        return [part for part in wrapper if isinstance(part, str)]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
