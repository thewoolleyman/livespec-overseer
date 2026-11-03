#!/usr/bin/env bash
set -euo pipefail

backend="${OVERSEER_EXERCISE_BACKEND:?missing exercise backend}"
instance="${OVERSEER_EXERCISE_INSTANCE:?missing exercise instance}"
endpoint="${OVERSEER_EXERCISE_ENDPOINT:?missing exercise endpoint}"
topic="${OVERSEER_EXERCISE_TOPIC:?missing exercise topic}"
evidence="${OVERSEER_EXERCISE_EVIDENCE:?missing exercise evidence directory}"
isolation_check="${OVERSEER_EXERCISE_ISOLATION_CHECK:-false}"
backend_pid=""

cleanup_backend() {
  local cleanup_status=0
  if [[ "$backend" == herdr ]]; then
    herdr session stop "$instance" >/dev/null 2>&1 || cleanup_status="$?"
  else
    tmux -S "$endpoint" kill-server >/dev/null 2>&1 || cleanup_status="$?"
  fi
  if [[ -n "$backend_pid" ]]; then
    wait "$backend_pid" 2>/dev/null || true
  fi
  if ((cleanup_status == 0)); then
    printf 'format=livespec-overseer-live-exercise-v1\nbackend=%s\ninstance=%s\nstatus=passed\n' \
      "$backend" "$instance" >"$evidence/backend-cleanup.env"
  else
    printf 'format=livespec-overseer-live-exercise-v1\nbackend=%s\ninstance=%s\nstatus=failed\n' \
      "$backend" "$instance" >"$evidence/backend-cleanup.env"
  fi
  return "$cleanup_status"
}

finish() {
  local run_status="$?"
  local cleanup_status=0
  trap - EXIT HUP INT TERM
  set +e
  cleanup_backend
  cleanup_status="$?"
  if ((run_status != 0)); then
    exit "$run_status"
  fi
  exit "$cleanup_status"
}
trap finish EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

[[ "$isolation_check" == true || "$isolation_check" == false ]] || {
  echo "invalid exercise isolation-check selector: $isolation_check" >&2
  exit 1
}

# Herdr and tmux both start panes through the scratch user's shell. Seed zsh's
# startup file before either backend starts so a first-run configuration menu
# cannot consume the controller's first pane submission.
: >"$HOME/.zshrc"

if [[ "$backend" == herdr ]]; then
  herdr --session "$instance" server >"$evidence/backend.log" 2>&1 &
  backend_pid="$!"
  socket="$HOME/.config/herdr/sessions/$instance/herdr.sock"
  for _attempt in {1..200}; do
    [[ -S "$socket" ]] && break
    kill -0 "$backend_pid" 2>/dev/null || {
      echo "exercise Herdr server exited before its socket became ready" >&2
      exit 1
    }
    sleep 0.05
  done
  [[ -S "$socket" ]] || {
    echo "exercise Herdr server did not create $socket" >&2
    exit 1
  }
else
  tmux -S "$endpoint" new-session -d -s "$instance" \
    -c /tmp/livespec-overseer-exercise-repo
  backend_pid="$(tmux -S "$endpoint" display-message -p '#{pid}')"
fi

printf 'format=livespec-overseer-live-exercise-v1\nbackend=%s\ninstance=%s\nendpoint=%s\npid=%s\nstatus=live\n' \
  "$backend" "$instance" "$endpoint" "$backend_pid" >"$evidence/backend-runtime.env"

if [[ "$isolation_check" == true ]]; then
  exit 0
fi

export OVERSEER_EXERCISE_TOPIC="$topic"
"$@"
