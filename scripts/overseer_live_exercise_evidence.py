#!/usr/bin/env python3
"""CLI binding for the shipped isolated-exercise evidence verifier."""

from __future__ import annotations

from overseer.live_exercise_evidence import main

__all__: list[str] = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
