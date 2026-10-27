#!/usr/bin/env bash
# Prepare the tracked stand-ins used to prove the Codex-on-Herdr controller.
#
# This intentionally performs only fixture setup: the controller, Herdr server,
# panes, and overseer daemon remain their shipped implementations.  Keeping the
# setup here lets a factory proof record run one checked-in command before it
# puts either temporary shim on PATH.

set -euo pipefail

usage() {
  echo "usage: overseer-live-exercise-stub-shims.sh --bin-dir DIR --codex-script FILE --herdr-log FILE" >&2
  exit 2
}

bin_dir=""
codex_script=""
herdr_log=""
while (($#)); do
  case "$1" in
    --bin-dir | --codex-script | --herdr-log)
      (($# >= 2)) || usage
      case "$1" in
        --bin-dir) bin_dir="$2" ;;
        --codex-script) codex_script="$2" ;;
        --herdr-log) herdr_log="$2" ;;
      esac
      shift 2
      ;;
    *) usage ;;
  esac
done

[[ -n "$bin_dir" && -n "$codex_script" && -n "$herdr_log" ]] || usage
codex_script="$(realpath -e -- "$codex_script")"
real_herdr="$(command -v herdr)"
real_herdr="$(realpath -e -- "$real_herdr")"

mkdir -p -- "$bin_dir"
{
  printf '%s\n' '#!/usr/bin/env bash' 'set -euo pipefail'
  printf 'exec python3 %q "$@"\n' "$codex_script"
} >"$bin_dir/codex"
{
  printf '%s\n' '#!/usr/bin/env bash' 'set -euo pipefail'
  printf 'printf '\''%%s\\n'\'' "$*" >> %q\n' "$herdr_log"
  printf 'exec %q "$@"\n' "$real_herdr"
} >"$bin_dir/herdr"
chmod 755 "$bin_dir/codex" "$bin_dir/herdr"

printf 'prepared stub shims: codex=%s herdr=%s\n' "$bin_dir/codex" "$bin_dir/herdr"
