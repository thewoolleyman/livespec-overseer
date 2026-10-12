#!/usr/bin/env python3
"""CLI binding for the shipped isolated-exercise evidence verifier."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from overseer.live_exercise_evidence import main  # noqa: E402

__all__: list[str] = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
