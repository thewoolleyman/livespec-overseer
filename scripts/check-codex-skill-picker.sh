#!/usr/bin/env bash
set -euo pipefail

if [[ "${CI:-}" == "true" && "${LIVESPEC_REQUIRE_CODEX_TUI_PICKER:-}" != "1" ]]; then
  echo ":: check-codex-skill-picker: skipped in CI; set LIVESPEC_REQUIRE_CODEX_TUI_PICKER=1 on an authenticated Codex runner to enforce it"
  exit 0
fi

if ! command -v codex >/dev/null 2>&1; then
  echo ":: check-codex-skill-picker: codex CLI not found; skipping live TUI picker acceptance"
  exit 0
fi

LIVESPEC_CODEX_SKILL_PICKER=1 uv run pytest tests/e2e-cli/test_codex_skill_picker.py -v
