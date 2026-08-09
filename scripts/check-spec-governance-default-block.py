#!/usr/bin/env python3
"""Verify this repo's documented spec-governance default block."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from livespec_runtime.spec_governance import verify_livespec_jsonc_default_block
from returns.result import Failure

__all__: list[str] = []


def main() -> int:
    result = verify_livespec_jsonc_default_block(path=Path(".livespec.jsonc"))
    if isinstance(result, Failure):
        _ = sys.stderr.write(f"{result.failure()}\n")
        return 1
    payload = result.unwrap()
    _ = sys.stdout.write(f"{json.dumps(_json_payload(payload=payload), sort_keys=True)}\n")
    return 0


def _json_payload(*, payload: dict[str, Any]) -> dict[str, Any]:
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
