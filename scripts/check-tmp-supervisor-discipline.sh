#!/usr/bin/env bash
set -euo pipefail

root="tmp/supervisor"
briefs_root="$root/briefs"

echo "LOCAL-ONLY: tmp/supervisor discipline cannot fire in CI/fresh clones because tmp/ is gitignored (.gitignore:2)."

if [[ ! -e "$root" ]]; then
  echo "tmp/supervisor does not exist; nothing local to inspect."
  exit 0
fi

violations=()

while IFS= read -r -d '' path; do
  rel="${path#./}"

  if [[ "$rel" == "$briefs_root" ]]; then
    continue
  fi

  if [[ "$rel" == "$briefs_root"/* ]]; then
    if [[ -d "$path" ]]; then
      violations+=("$rel: briefs/ may not contain subdirectories")
      continue
    fi

    name="${rel##*/}"
    if [[ ! "$name" =~ ^brief-[0-9]+\.md$ ]]; then
      violations+=("$rel: briefs/ may contain only brief-<number>.md files")
    fi
    continue
  fi

  if [[ -f "$path" && "$rel" != *.json ]]; then
    violations+=("$rel: only *.json files may live outside tmp/supervisor/briefs/")
  fi
done < <(find "$root" -mindepth 1 -print0 | sort -z)

if [[ "${#violations[@]}" -gt 0 ]]; then
  echo "tmp/supervisor discipline violations:" >&2
  printf '  - %s\n' "${violations[@]}" >&2
  exit 1
fi

echo "tmp/supervisor discipline passed: JSON-only outside briefs/, briefs-only inside briefs/."
