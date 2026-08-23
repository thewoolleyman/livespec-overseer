"""Direct coverage for malformed resume-pending identity sidecar entries."""

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERSEER = ROOT / "overseer"
if str(OVERSEER) not in sys.path:
    sys.path.insert(0, str(OVERSEER))

__all__: list[str] = []


def test_resume_pending_identity_absent_when_flag_is_not_true(*, tmp_path):
    reader = importlib.import_module("_registry_stamp_resume")
    stamp = tmp_path / "stamps.json"
    stamp.write_text(
        json.dumps({"/r\tt": {"resume_pending_session_identity": "claude:s:t"}}),
        encoding="utf-8",
    )

    assert reader.read_resume_pending_identity(repo="/r", topic="t", stamp_path=stamp) is None
