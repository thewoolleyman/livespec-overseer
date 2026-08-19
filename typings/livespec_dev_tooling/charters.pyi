from collections.abc import Callable
from pathlib import Path

Detector = Callable[..., list[str]]

CHARTER_GLOBS: tuple[str, ...]
DETECTORS: tuple[tuple[str, Detector], ...]

def charters_in(*, root: Path) -> list[Path]: ...
def defects_in(*, text: str) -> list[str]: ...
