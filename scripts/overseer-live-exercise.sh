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
#
# Against the RESOLVED home, because every path handed here came back from `realpath`.
# A home reached through a symlink -- `/home/x` standing for `/mnt/.../x`, an ordinary
# layout -- makes a raw `$HOME` prefix test miss all of them at once, and the miss is
# silent: the root reads as empty, so nothing is bound AND nothing is refused, which is
# byte for byte the pre-fix behaviour this runner exists to stop.
install_root_of() {
  local path="$1" rest
  case "$path" in
    "$operator_home_real"/*) rest="${path#"$operator_home_real"/}" ;;
    *) return 0 ;;
  esac
  case "$rest" in
    */*) printf '%s/%s\n' "$operator_home_real" "${rest%%/*}" ;;
    *) printf '%s\n' "$operator_home_real" ;;
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

# Whether one exec-line word is WHOLLY a positional-parameter expansion -- `$@`, `$*`, or
# a numbered `$1` -- in any of its brace spellings.
#
# Such a word forwards the launcher's OWN caller arguments, so it names no path: not one
# the runner failed to determine, but none at all. It is therefore the one exception to
# the unexpanded-`$` rule below, and it has to be, because the exec line's words are read
# with their quotes stripped: the `"$@"` ending nearly every real shim arrives as the bare
# `$@`. Reading that as an undeterminable path refused every launcher shaped
# `exec <program> "$@"` -- the commonest shim shape there is -- while naming the launcher
# as unresolvable, which was the opposite of what the runner had just measured, since the
# program resolved and its install root was already in hand.
#
# Anchored at both ends, so a word merely CONTAINING such an expansion is not swept in; a
# launcher-local `$CODEX_APP_DIR/main.js` and a bare `${CODEX_APP_DIR}` both stay owed.
is_argument_forwarding_word() {
  # `[$]` as a bracket class rather than a quoted literal for the same reason the arms
  # below use them: the dollar is matched LITERALLY in the launcher's own text (SC2016).
  [[ "$1" =~ ^[$](([@*]|[0-9]+)|\{([@*]|[0-9]+)\})$ ]]
}

# Whether one exec-line token NAMES something the runner is OWED a resolution of, so that
# failing to resolve it means the runner cannot say what the launcher executes.
#
# Two kinds of token qualify. One rooted in the operator home names content the scratch
# home will hide, so an unresolved one leaves the client unrunnable inside the namespace.
# One still carrying a `$` or a leading `~` after expansion names a path the runner cannot
# determine AT ALL -- a launcher-local `CODEX_APP_DIR="$HOME/.codexapp"` indirected
# through `exec /bin/sh "$CODEX_APP_DIR/main.js"`, say, whose program lies outside the
# home so no root is owed on it either.
#
# Anything else is tolerated unresolved, and must be: the `run` of `exec bun run codex` is
# a subcommand word rather than a file, an argument-forwarding word names no path at all,
# and a path outside the operator home names nothing the scratch home hides. So the
# discriminator is what the token NAMES, never whether it happened to resolve.
exec_target_is_owed() {
  local token
  token="$(expand_operator_home "$1")"
  # Before the arms below, because the dollar an argument-forwarding word carries is the
  # very character the undeterminable-path arm matches on.
  if is_argument_forwarding_word "$token"; then
    return 1
  fi
  case "$token" in
    # Bracket classes for the same reason `expand_operator_home` uses them: these are
    # matched LITERALLY in the launcher's own text (SC2088, SC2016).
    "$operator_home" | "$operator_home"/*) return 0 ;;
    "$operator_home_real" | "$operator_home_real"/*) return 0 ;;
    *[\$]* | [~]*) return 0 ;;
  esac
  return 1
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
# The same home with every symlink resolved, which is the form every install-root rule
# below compares against -- see `install_root_of`. The scratch home still mounts at the
# UNRESOLVED path, and that is not an inconsistency: a mount resolves its own target, so
# both names reach one directory and the client's binds layer over the scratch home
# whichever name either side is spelled with. `-m` rather than `-e` so a home that does
# not exist normalizes instead of aborting here, leaving the ordinary refusals to report
# a client nothing under that home can resolve.
operator_home_real="$(realpath -m "$operator_home")"
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
    elif exec_target_is_owed "${agent_exec_tokens[1]}"; then
      die "cannot make the agent client runnable inside the namespace: $agent_real"
    fi
  fi
  # Two first-level home trees are two install roots, and the contract admits one. The
  # runner refuses rather than binding a parent of both, which would be the operator home.
  if [[ -n "$agent_program_root" && -n "$agent_script_root" ]]; then
    [[ "$agent_program_root" == "$agent_script_root" ]] ||
      die "cannot make the agent client runnable inside the namespace: $agent_real"
  fi
fi

# At most TWO read-only binds, and no other operator-home path: the install root of what
# the launcher executes, then the launcher itself at its own path so the client stays
# callable by name. The root comes first so a launcher living inside it is layered on top.
# When the exec line's program lies outside the operator home, the root is the one on the
# script file that program is passed; a self-contained executable has no root at all.
agent_install_root="$agent_program_root"
[[ -n "$agent_install_root" ]] || agent_install_root="$agent_script_root"
agent_binaries=()
if [[ -n "$agent_install_root" ]]; then
  # The runner's OWN fixed list of the home roots it writes inside the namespace: the
  # scratch home at the operator home path, the agent credential under ~/.claude or
  # ~/.codex, and the Herdr client socket under ~/.config. Binding the home read-only
  # would defeat the scratch home; binding one of the other three would make read-only a
  # directory the exercise must write. This list grows only when the exercise starts
  # writing somewhere new — never with the home paths a launcher happens to name.
  for exercise_owned_root in \
    "$operator_home_real" \
    "$operator_home_real/.claude" \
    "$operator_home_real/.codex" \
    "$operator_home_real/.config"; do
    [[ "$agent_install_root" != "$exercise_owned_root" ]] ||
      die "refusing the agent client install root $agent_install_root: the exercise writes it inside the namespace"
  done
  agent_binaries+=(--ro-bind "$agent_install_root" "$agent_install_root")
fi
# Each name against the home in ITS OWN form: `$agent_path` came off PATH unresolved, so
# it is compared with the raw home, while `$agent_real` came back from `realpath` and is
# compared with the resolved one. A launcher reached only through a symlinked home
# satisfies the second alone.
if [[ "$agent_path" == "$operator_home"/* || "$agent_real" == "$operator_home_real"/* ]]; then
  agent_binaries+=(--ro-bind "$agent_real" "$agent_path")
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

# The namespace replaces the operator home with a scratch home, so a backend installed
# under that home (for example ~/.local/bin/herdr) would vanish, and so would the `uv`
# that the shipped `overseer-start` shim runs under. Bind each such executable read-only
# at its own path, beneath the scratch home bind. A mise shim is `mise` itself and needs
# mise's hidden install tree, so bind the tool it resolves to.
#
# The AGENT CLIENT is deliberately not in this loop: its binds are governed by the
# at-most-two-paths rule resolved above, not by this one's bind-the-launcher-file rule.
home_binaries=()
for tool in "$backend" uv; do
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
  "${agent_binaries[@]}"
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
