#!/usr/bin/env bash
set -euo pipefail

start=".claude-plugin/bin/overseer-start"
daemon=".claude-plugin/bin/overseerd"
plugin_pkg=".claude-plugin/overseer"

test -x "$start"
test -x "$daemon"
test -d "$plugin_pkg"

while IFS= read -r -d '' src; do
  rel="${src#overseer/}"
  dst="$plugin_pkg/$rel"
  test -f "$dst"
  cmp -s "$src" "$dst"
done < <(find overseer -maxdepth 1 \( -name '*.py' -o -name 'version.json' \) ! -name 'test_*.py' ! -name 'conftest.py' -print0 | sort -z)

while IFS= read -r -d '' dst; do
  rel="${dst#"$plugin_pkg"/}"
  test -f "overseer/$rel"
done < <(find "$plugin_pkg" -maxdepth 1 -type f -print0 | sort -z)

unexpected_dir="$(find "$plugin_pkg" -mindepth 1 -maxdepth 1 -type d ! -name __pycache__ -print -quit)"
test -z "$unexpected_dir"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
repo="$(pwd)"
(
  cd "$tmp"
  "$repo/$start" --help >"$tmp/overseer-start-help.out"
)
grep -F "the /overseer skill's two-pane bootstrap" "$tmp/overseer-start-help.out" >/dev/null
