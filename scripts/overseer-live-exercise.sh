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
#
# Binding the launcher FILE alone is not enough when that launcher is a SCRIPT that runs
# an install tree elsewhere under the operator home. Measured on the release host
# 2026-10-22: `~/.local/bin/codex` is a bash shim that execs the bun global install under
# `~/.bun`, the scratch home hid that tree, and Codex never reached its input prompt — a
# failed `bootstrap` stage an hour into an authenticated run. So resolve every home-rooted
# path such a launcher names to its top-level install directory under the operator home.
launcher_install_roots() {
  sed -e 's|[$]{HOME}|@home@|g' -e 's|[$]HOME|@home@|g' -e 's|[~]|@home@|g' \
    -e "s|$operator_home|@home@|g" "$1" |
    grep -oE '@home@/[A-Za-z0-9_.][A-Za-z0-9_.-]*' | sed -e 's|^@home@/||' | sort -u || true
}

is_script_launcher() {
  [[ "$(head -c 2 "$1")" == '#!' ]]
}

# An install root is NEVER bound back when it is one of the home subtrees the scratch
# home itself provides. Binding one would undo this namespace's whole purpose: the
# operator's real `~/.claude` or `~/.codex` — credentials, the session registry the
# daemon's adoption reads — would be re-exposed inside it, would shadow the
# `--credential` installed into the scratch copy below, and would reach the client
# READ-ONLY, so it could not write the session state it is adopted by. A client whose
# only install tree is such a root therefore cannot be made runnable here, and is
# refused by name rather than bound.
scratch_home_state=(
  .claude
  .codex
  .livespec-overseer-repos.json
  .livespec-overseer.jsonl
)

is_scratch_home_state() {
  local candidate="$1" provided
  for provided in "${scratch_home_state[@]}"; do
    [[ "$candidate" == "$provided" || "$candidate" == "$provided"/* ]] && return 0
  done
  return 1
}

home_binaries=()
client_refusal=""
for tool in "$backend" "$agent" uv; do
  tool_path="$(command -v "$tool" || true)"
  if [[ -z "$tool_path" ]]; then
    if [[ "$tool" == "$agent" ]]; then
      client_refusal="agent client $tool is not on PATH"
    fi
    continue
  fi
  case "$tool_path" in
    "$operator_home"/*) ;;
    *) continue ;;
  esac
  tool_source="$(realpath "$tool_path")"
  if [[ "$(basename "$tool_source")" == mise ]]; then
    tool_source="$(mise which "$tool")" || die "mise cannot resolve $tool"
  fi
  home_binaries+=(--ro-bind "$tool_source" "$tool_path")
  is_script_launcher "$tool_source" || continue
  named_roots=0
  resolved_roots=0
  scratch_state_roots=()
  while IFS= read -r install_root; do
    [[ -n "$install_root" ]] || continue
    named_roots=$((named_roots + 1))
    if is_scratch_home_state "$install_root"; then
      scratch_state_roots+=("$operator_home/$install_root")
      continue
    fi
    if [[ -e "$operator_home/$install_root" ]]; then
      resolved_roots=$((resolved_roots + 1))
      home_binaries+=(--ro-bind "$operator_home/$install_root" "$operator_home/$install_root")
    fi
  done < <(launcher_install_roots "$tool_source")
  if [[ "$tool" == "$agent" ]] && ((named_roots > 0 && resolved_roots == 0)); then
    client_refusal="agent client launcher $tool_path names no resolvable install tree under $operator_home"
    if ((${#scratch_state_roots[@]} > 0)); then
      client_refusal+=": ${scratch_state_roots[*]} is agent state the scratch home replaces, so binding it would re-expose the operator's own"
    fi
  fi
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

# An agent client that cannot be made runnable inside the namespace is refused HERE,
# before any terminal backend starts, so the condition is never reported later as a
# failed `bootstrap` lifecycle stage.
[[ -z "$client_refusal" ]] || die "$client_refusal"

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
