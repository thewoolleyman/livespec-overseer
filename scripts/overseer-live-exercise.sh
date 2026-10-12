#!/usr/bin/env bash
set -euo pipefail

# Hermetic host runner for the released overseer lifecycle exercises. HOME keeps
# its real pathname: a private mount supplies disposable contents at that path.

usage() {
  cat <<'EOF'
usage: overseer-live-exercise.sh run [--plan-only] --backend herdr|tmux
       --agent claude|codex --topic TOPIC --checkout ABSOLUTE_PATH
       --evidence ABSOLUTE_PATH [--credential ABSOLUTE_PATH] -- COMMAND [ARG...]
EOF
}

die() {
  echo "overseer live exercise: $*" >&2
  exit 2
}

cleanup() {
  if [[ -n "${scratch_root:-}" ]]; then
    case "$scratch_root" in
      "${TMPDIR:-/tmp}"/livespec-overseer-exercise.*)
        rm -rf -- "$scratch_root"
        ;;
      *)
        echo "overseer live exercise: refusing unsafe cleanup target: $scratch_root" >&2
        ;;
    esac
  fi
}

[[ "${1:-}" == run ]] || {
  usage >&2
  exit 2
}
shift

backend=""
agent=""
topic=""
checkout=""
evidence=""
credential=""
plan_only=false
while (($#)); do
  case "$1" in
    --plan-only)
      plan_only=true
      shift
      ;;
    --backend | --agent | --topic | --checkout | --evidence | --credential)
      (($# >= 2)) || die "$1 needs a value"
      option="${1#--}"
      value="$2"
      case "$option" in
        backend) backend="$value" ;;
        agent) agent="$value" ;;
        topic) topic="$value" ;;
        checkout) checkout="$value" ;;
        evidence) evidence="$value" ;;
        credential) credential="$value" ;;
      esac
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ "$backend" == herdr || "$backend" == tmux ]] || die "--backend must be herdr or tmux"
[[ "$agent" == claude || "$agent" == codex ]] || die "--agent must be claude or codex"
[[ "$topic" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "--topic must be a lowercase slug"
[[ -d "$checkout" ]] || die "--checkout must name an existing directory"
[[ -n "$evidence" ]] || die "--evidence is required"
(($#)) || die "a controller COMMAND is required after --"

checkout="$(realpath "$checkout")"
evidence="$(realpath -m "$evidence")"
case "$evidence" in
  "$checkout" | "$checkout"/*) die "--evidence must be outside the released checkout" ;;
esac
mkdir -p -m 700 "$evidence"

operator_home="${HOME:?HOME must name the operator home}"
operator_uid="$(id -u)"
scratch_root="$(mktemp -d "${TMPDIR:-/tmp}/livespec-overseer-exercise.XXXXXX")"
trap cleanup EXIT HUP INT TERM
chmod 700 "$scratch_root"

scratch_home="$scratch_root/home"
scratch_tmp="$scratch_root/tmp"
scratch_runtime="$scratch_root/runtime"
scratch_checkout="$scratch_root/checkout"
scratch_repo="$scratch_tmp/livespec-overseer-exercise-repo"
mkdir -p "$scratch_home" "$scratch_tmp" "$scratch_runtime" "$scratch_checkout"
mkdir -p "$scratch_repo/plan/$topic" "$scratch_repo/tmp"
printf 'tmp/\nplan/%s/\n' "$topic" >"$scratch_repo/.gitignore"
git -C "$scratch_repo" init -q

cat >"$scratch_home/.livespec-overseer-repos.json" <<'EOF'
{"repos": ["/tmp/livespec-overseer-exercise-repo"]}
EOF
: >"$scratch_home/.livespec-overseer.jsonl"

backend_instance="livespec-overseer-exercise-${backend}-${operator_uid}-$$"
backend_endpoint="/tmp/${backend_instance}.sock"
cat >"$evidence/isolation.env" <<EOF
format=livespec-overseer-live-exercise-v1
backend=$backend
agent=$agent
topic=$topic
backend_instance=$backend_instance
backend_endpoint=$backend_endpoint
scratch_root=$scratch_root
scratch_home=$scratch_home
watch_repo=/tmp/livespec-overseer-exercise-repo
mapping_store=$operator_home/.livespec-overseer.jsonl
checkout=$checkout
EOF

namespace=(
  bwrap
  --die-with-parent
  --new-session
  --unshare-pid
  --ro-bind / /
  --proc /proc
  --dev /dev
  --bind "$scratch_home" "$operator_home"
  --bind "$scratch_tmp" /tmp
  --bind "$scratch_runtime" "/run/user/$operator_uid"
  --bind "$scratch_checkout" "$checkout"
  --bind "$evidence" /evidence
  --chdir "$checkout"
  /usr/bin/env
  -u TMUX
  -u TMUX_PANE
  -u HERDR_ENV
  -u HERDR_PANE_ID
  -u HERDR_TAB_ID
  -u HERDR_WORKSPACE_ID
  -u HERDR_SESSION
  -u HERDR_SOCKET_PATH
  -u HERDR_BIN_PATH
  -u OTEL_EXPORTER_OTLP_ENDPOINT
  -u OTEL_EXPORTER_OTLP_HEADERS
  "OVERSEER_EXERCISE_BACKEND=$backend"
  "OVERSEER_EXERCISE_INSTANCE=$backend_instance"
  "OVERSEER_EXERCISE_ENDPOINT=$backend_endpoint"
  "OVERSEER_EXERCISE_TOPIC=$topic"
  /bin/bash
  "$checkout/scripts/overseer-live-exercise-inside.sh"
  --
  "$@"
)
printf '%s\n' "${namespace[@]}" >"$evidence/namespace.argv"

if [[ "$plan_only" == true ]]; then
  echo "exercise plan written to $evidence; no namespace or terminal was started"
  exit 0
fi

command -v bwrap >/dev/null 2>&1 || die "bwrap is required"
cp -a "$checkout/." "$scratch_checkout/"

if [[ -n "$credential" ]]; then
  [[ -f "$credential" ]] || die "--credential must name a file"
  if [[ "$agent" == claude ]]; then
    credential_target="$scratch_home/.claude/.credentials.json"
  else
    credential_target="$scratch_home/.codex/auth.json"
  fi
  mkdir -p "$(dirname "$credential_target")"
  install -m 600 "$credential" "$credential_target"
fi

"${namespace[@]}"
