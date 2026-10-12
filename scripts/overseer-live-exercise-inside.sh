#!/usr/bin/env bash
set -euo pipefail

backend="${OVERSEER_EXERCISE_BACKEND:?missing exercise backend}"
instance="${OVERSEER_EXERCISE_INSTANCE:?missing exercise instance}"
endpoint="${OVERSEER_EXERCISE_ENDPOINT:?missing exercise endpoint}"
topic="${OVERSEER_EXERCISE_TOPIC:?missing exercise topic}"
backend_pid=""

cleanup_backend() {
  if [[ "$backend" == herdr ]]; then
    herdr --session "$instance" server stop >/dev/null 2>&1 || true
  else
    tmux -S "$endpoint" kill-server >/dev/null 2>&1 || true
  fi
  if [[ -n "$backend_pid" ]]; then
    wait "$backend_pid" 2>/dev/null || true
  fi
}
trap cleanup_backend EXIT HUP INT TERM

if [[ "$backend" == herdr ]]; then
  herdr --session "$instance" server >"/evidence/backend.log" 2>&1 &
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
fi

export OVERSEER_EXERCISE_TOPIC="$topic"
"$@"
