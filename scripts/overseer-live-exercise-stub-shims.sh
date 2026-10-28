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

mkdir -p -- "$bin_dir"
{
  printf '%s\n' '#!/usr/bin/env bash' 'set -euo pipefail'
  printf 'exec python3 %q "$@"\n' "$codex_script"
} >"$bin_dir/codex"
{
  printf '%s\n' '#!/usr/bin/env bash' 'set -euo pipefail'
  printf 'printf '\''%%s\\n'\'' "$*" >> %q\n' "$herdr_log"
  # The real herdr is looked up when the shim runs, past the shim's own directory,
  # so preparing shims needs no herdr on PATH (CI containers carry none).
  printf '%s\n' \
    'self_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"' \
    'search_path=":${PATH}:"' \
    'search_path="${search_path//:$self_dir:/:}"' \
    'real_herdr="$(PATH="${search_path#:}" command -v herdr)" || {' \
    '  echo "herdr shim: no real herdr on PATH" >&2' \
    '  exit 127' \
    '}' \
    'exec "$real_herdr" "$@"'
} >"$bin_dir/herdr"
chmod 755 "$bin_dir/codex" "$bin_dir/herdr"

printf 'prepared stub shims: codex=%s herdr=%s\n' "$bin_dir/codex" "$bin_dir/herdr"
