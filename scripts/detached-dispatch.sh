#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' "usage: scripts/detached-dispatch.sh <run-dir> -- <command> [args...]" >&2
}

write_verdict() {
  local verdict="$1"
  local status="$2"
  local exit_code="$3"
  local tmp

  tmp="${verdict}.tmp.$$"
  {
    printf 'status=%s\n' "$status"
    printf 'exit_code=%s\n' "$exit_code"
    printf 'finished_at=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } >"$tmp"
  mv "$tmp" "$verdict"
}

child_main() {
  local run_dir="$1"
  shift

  local output="$run_dir/output.log"
  local verdict="$run_dir/verdict.env"
  local tmp
  local rc

  tmp="${verdict}.tmp.$$"
  {
    printf 'status=running\n'
    printf 'exit_code=\n'
    printf 'started_at=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } >"$tmp"
  mv "$tmp" "$verdict"

  set +e
  "$@" >>"$output" 2>&1
  rc=$?
  set -e

  if [[ "$rc" -eq 0 ]]; then
    write_verdict "$verdict" "succeeded" "$rc"
  else
    write_verdict "$verdict" "failed" "$rc"
  fi
  exit "$rc"
}

if [[ "${1:-}" == "--child" ]]; then
  shift
  if [[ "$#" -lt 2 ]]; then
    usage
    exit 64
  fi
  child_main "$@"
fi

if [[ "$#" -lt 3 || "${2:-}" != "--" ]]; then
  usage
  exit 64
fi

run_dir="$1"
shift 2

mkdir -p "$run_dir"
: >"$run_dir/output.log"

if ! command -v setsid >/dev/null 2>&1; then
  printf '%s\n' "detached-dispatch: setsid is required" >&2
  exit 69
fi

if ! command -v nohup >/dev/null 2>&1; then
  printf '%s\n' "detached-dispatch: nohup is required" >&2
  exit 69
fi

setsid nohup "$0" --child "$run_dir" "$@" >/dev/null 2>&1 </dev/null &
pid=$!
printf '%s\n' "$pid" >"$run_dir/pid"

verdict="$run_dir/verdict.env"
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if [[ -s "$verdict" ]]; then
    break
  fi
  sleep 0.05
done

if [[ ! -s "$verdict" ]]; then
  printf '%s\n' "detached-dispatch: child did not publish a disk verdict" >&2
  exit 70
fi

printf 'detached dispatch launched\n'
printf 'pid=%s\n' "$pid"
printf 'output=%s\n' "$run_dir/output.log"
printf 'verdict=%s\n' "$verdict"
