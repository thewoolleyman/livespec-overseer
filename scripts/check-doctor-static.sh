#!/usr/bin/env bash
set -euo pipefail

core_root="${LIVESPEC_CORE_PLUGIN_ROOT:-}"
if [[ -z "$core_root" ]]; then
  core_root="$(
    python3 -c 'import subprocess, pathlib; mk = pathlib.Path.home() / ".claude" / "plugins" / "marketplaces" / "livespec"; head = subprocess.run(["git", "-C", str(mk), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True).stdout.strip().lower(); cache = pathlib.Path.home() / ".claude" / "plugins" / "cache" / "livespec" / "livespec" / head; print(cache if head and (cache / "scripts" / "bin" / "doctor_static.py").is_file() else "")' 2>/dev/null || true
  )"
fi

if [[ -z "$core_root" || ! -f "$core_root/scripts/bin/doctor_static.py" ]]; then
  echo "livespec core not found. Set LIVESPEC_CORE_PLUGIN_ROOT to a livespec checkout's .claude-plugin, or install the livespec@livespec plugin (claude plugin install livespec@livespec)." >&2
  exit 1
fi

python3 "$core_root/scripts/bin/doctor_static.py" --project-root .
