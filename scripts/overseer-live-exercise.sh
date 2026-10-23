#!/usr/bin/env bash
set -euo pipefail

# Hermetic host runner for the released overseer lifecycle exercises. HOME keeps
# its real pathname: a private mount supplies disposable contents at that path.

usage() {
  cat <<'EOF'
usage: overseer-live-exercise.sh run [--plan-only | --isolation-check]
       --backend herdr|tmux
       --agent claude|codex --topic TOPIC --checkout ABSOLUTE_PATH
       --evidence ABSOLUTE_PATH [--credential ABSOLUTE_PATH]
       [-- COMMAND [ARG...]]
EOF
}

die() {
  echo "overseer live exercise: $*" >&2
  exit 2
}

# The first directory below the operator home on one absolute path, or the operator home
# itself when the path sits directly in it. Empty for a path outside that home.
install_root_of() {
  local path="$1" rest
  case "$path" in
    "$operator_home"/*) rest="${path#"$operator_home"/}" ;;
    *) return 0 ;;
  esac
  case "$rest" in
    */*) printf '%s/%s\n' "$operator_home" "${rest%%/*}" ;;
    *) printf '%s\n' "$operator_home" ;;
  esac
}

# One exec-line token with a leading operator-home reference expanded. A token naming any
# OTHER unexpanded variable stays as written, so it fails to resolve and the client is
# refused rather than bound at a guessed path.
expand_operator_home() {
  local token="$1"
  case "$token" in
    # Bracket classes, not quoted literals: every one of these is matched LITERALLY in
    # the launcher's own text, and quoting a tilde or a dollar here reads to shellcheck
    # as one the runner meant to expand (SC2088, SC2016).
    [~]/*) printf '%s/%s\n' "$operator_home" "${token#[~]/}" ;;
    [\$]HOME/*) printf '%s/%s\n' "$operator_home" "${token#[\$]HOME/}" ;;
    [\$]'{HOME}'/*) printf '%s/%s\n' "$operator_home" "${token#[\$]'{HOME}'/}" ;;
    *) printf '%s\n' "$token" ;;
  esac
}

# The real path of one exec-line program or script argument, or empty when the runner
# cannot resolve it. A bare name is looked up on PATH; anything else must already exist.
resolve_exec_target() {
  local token resolved
  token="$(expand_operator_home "$1")"
  [[ -n "$token" ]] || return 0
  case "$token" in
    */*) ;;
    *)
      token="$(command -v "$token" || true)"
      [[ -n "$token" ]] || return 0
      ;;
  esac
  resolved="$(realpath -e "$token" 2>/dev/null || true)"
  [[ -n "$resolved" ]] || return 0
  printf '%s\n' "$resolved"
}

# Whether one launcher is a script, which is what makes its text worth reading at all. A
# self-contained executable runs nothing else and needs no install root.
launcher_is_script() {
  local first=""
  IFS= read -r first <"$1" 2>/dev/null || true
  [[ "$first" == '#!'* ]]
}

# The program one launcher's exec line runs and, when it passes one, the script file it
# passes to it — at most two lines. `exec` options are skipped. Nothing when the launcher
# carries no exec line.
launcher_exec_tokens() {
  local line
  line="$(sed -n 's/^[[:space:]]*exec[[:space:]]\{1,\}//p' "$1" | head -n 1)"
  [[ -n "$line" ]] || return 0
  local -a words=()
  read -r -a words <<<"${line//[\"\']/}"
  while ((${#words[@]})); do
    case "${words[0]}" in
      -a) words=("${words[@]:2}") ;;
      -*) words=("${words[@]:1}") ;;
      *) break ;;
    esac
  done
  ((${#words[@]})) || return 0
  printf '%s\n' "${words[@]:0:2}"
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
isolation_check=false
while (($#)); do
  case "$1" in
    --plan-only)
      plan_only=true
      shift
      ;;
    --isolation-check)
      isolation_check=true
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
[[ "$plan_only" != true || "$isolation_check" != true ]] || \
  die "--plan-only and --isolation-check are mutually exclusive"
if [[ "$isolation_check" == true ]]; then
  (($# == 0)) || die "--isolation-check does not accept a controller COMMAND"
else
  (($#)) || die "a controller COMMAND is required after --"
fi

checkout="$(realpath "$checkout")"
evidence="$(realpath -m "$evidence")"
case "$evidence" in
  "$checkout" | "$checkout"/*) die "--evidence must be outside the released checkout" ;;
esac
mkdir -p "$evidence"
if find "$evidence" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  die "--evidence must name an empty directory"
fi
chmod 700 "$evidence"

operator_home="${HOME:?HOME must name the operator home}"
operator_uid="$(id -u)"

# The namespace mounts a scratch home at the operator home path, so whatever the agent
# client executes from under that home vanishes. Measured on the release host 2026-10-22
# (work-item `overseer-fr8f`): `~/.local/bin/codex` is a bash shim whose exec line runs
# the bun global install under `~/.bun`, and binding only the shim file left Codex unable
# to start — reported sixty seconds later as a FAILED `bootstrap` stage, after the
# backend was already running. So resolve the client FIRST, before any evidence record or
# terminal backend exists, and refuse by name when it cannot be made runnable.
#
# Resolution follows what the launcher EXECUTES, never what it MENTIONS: a denylist of
# the other home paths a launcher happens to name cannot converge, because every further
# named path is one more entry.
agent_path="$(command -v "$agent" || true)"
[[ -n "$agent_path" ]] ||
  die "cannot make the agent client runnable inside the namespace: $agent is not on PATH"
agent_real="$(realpath -e "$agent_path" 2>/dev/null || true)"
[[ -n "$agent_real" ]] ||
  die "cannot make the agent client runnable inside the namespace: $agent_path"
if [[ "$(basename "$agent_real")" == mise ]]; then
  agent_real="$(mise which "$agent")" ||
    die "cannot make the agent client runnable inside the namespace: $agent_path"
fi

agent_exec_tokens=()
if launcher_is_script "$agent_real"; then
  mapfile -t agent_exec_tokens < <(launcher_exec_tokens "$agent_real")
fi
agent_program_root=""
agent_script_root=""
if ((${#agent_exec_tokens[@]})); then
  agent_program="$(resolve_exec_target "${agent_exec_tokens[0]}")"
  [[ -n "$agent_program" ]] ||
    die "cannot make the agent client runnable inside the namespace: $agent_real"
  agent_program_root="$(install_root_of "$agent_program")"
  if ((${#agent_exec_tokens[@]} > 1)); then
    agent_script="$(resolve_exec_target "${agent_exec_tokens[1]}")"
    if [[ -n "$agent_script" ]]; then
      agent_script_root="$(install_root_of "$agent_script")"
    fi
  fi
  # Two first-level home trees are two install roots, and the contract admits one. The
  # runner refuses rather than binding a parent of both, which would be the operator home.
  if [[ -n "$agent_program_root" && -n "$agent_script_root" ]]; then
    [[ "$agent_program_root" == "$agent_script_root" ]] ||
      die "cannot make the agent client runnable inside the namespace: $agent_real"
  fi
fi

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

# The namespace replaces the operator home with a scratch home, so a backend or agent
# client installed under that home (for example ~/.local/bin/herdr) would vanish, and
# so would the `uv` that the shipped `overseer-start` shim runs under. Bind each such
# executable read-only at its own path, beneath the scratch home bind. A mise shim is
# `mise` itself and needs mise's hidden install tree, so bind the tool it resolves to.
home_binaries=()
for tool in "$backend" "$agent" uv; do
  tool_path="$(command -v "$tool" || true)"
  case "$tool_path" in
    "$operator_home"/*)
      tool_source="$(realpath "$tool_path")"
      if [[ "$(basename "$tool_source")" == mise ]]; then
        tool_source="$(mise which "$tool")" || die "mise cannot resolve $tool"
      fi
      home_binaries+=(--ro-bind "$tool_source" "$tool_path")
      ;;
  esac
done

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
  --bind "$evidence" /tmp/livespec-overseer-exercise-evidence
  "${home_binaries[@]}"
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
  "OVERSEER_EXERCISE_EVIDENCE=/tmp/livespec-overseer-exercise-evidence"
  "OVERSEER_EXERCISE_ISOLATION_CHECK=$isolation_check"
  /bin/bash
  "$checkout/scripts/overseer-live-exercise-inside.sh"
)
if [[ "$isolation_check" == false ]]; then
  namespace+=("$@")
fi
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

namespace_status=0
"${namespace[@]}" || namespace_status="$?"
if ((namespace_status != 0)); then
  if [[ "$isolation_check" == true ]]; then
    echo "FAILED isolation: namespace/backend exited $namespace_status" >&2
    exit "$namespace_status"
  fi
  printf '{"stage":"bootstrap","status":"failed","detail":"namespace/controller exited %s"}\n' \
    "$namespace_status" >>"$evidence/lifecycle.jsonl"
fi
if [[ "$isolation_check" == true ]]; then
  [[ -f "$evidence/backend-runtime.env" ]] || \
    die "isolation check produced no native backend runtime record"
  [[ -f "$evidence/backend-cleanup.env" ]] || \
    die "isolation check produced no native backend cleanup record"
  grep -qx 'status=live' "$evidence/backend-runtime.env" || \
    die "isolation check did not prove a live native backend"
  grep -qx 'status=passed' "$evidence/backend-cleanup.env" || \
    die "isolation check did not prove native backend cleanup"
  echo "COMPLETE isolation: native backend started and stopped inside namespace"
  exit 0
fi
python3 "$checkout/scripts/overseer_live_exercise_evidence.py" "$evidence/lifecycle.jsonl"
