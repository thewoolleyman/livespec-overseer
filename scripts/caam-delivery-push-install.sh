#!/usr/bin/env bash
# Install or revert the role holder's caam-delivery-push user unit.
#
#   install    idempotent: write the unit (ExecStart -> this checkout's installed
#              entry point), create the host list and the known-hosts record if
#              absent (mode 600, never overwritten), pin each listed host's key
#              into the record, daemon-reload, enable and (re)start, then print
#              is-active plus `caam-delivery-push status` as the read-back.
#              Re-run it after adding a host so that host's key is pinned.
#   uninstall  the documented revert: disable --now, remove the unit and any
#              drop-in dir, daemon-reload. The host list and record are kept.
#
# Pinning copies a host's existing entries from ~/.ssh/known_hosts (keys the
# operator already accepted) into the record and prints their fingerprints for
# review; the push service trusts ONLY the record. A listed host with no entry
# there is reported and stays unpushable until its key is added by hand.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
unit_name="caam-delivery-push.service"
unit_dir="${HOME}/.config/systemd/user"
state_dir="${HOME}/.local/state/caam-usage-rotate"
hosts="${state_dir}/delivery-hosts"
record="${state_dir}/delivery-known_hosts"
entry="${repo}/.venv/bin/caam-delivery-push"

create_private() {
  local path="$1"
  shift
  if [[ ! -e "${path}" ]]; then
    mkdir -p "$(dirname "${path}")"
    (
      umask 077
      printf '%s\n' "$@" >"${path}"
    )
  fi
  chmod 600 "${path}"
}

pin_host_keys() {
  local label target machine found
  while read -r label target _; do
    [[ -z "${label}" || "${label}" == \#* ]] && continue
    machine="${target#*@}"
    if ssh-keygen -F "${machine}" -f "${record}" >/dev/null 2>&1; then
      printf 'pinned %s (%s): already in the record\n' "${label}" "${machine}"
      continue
    fi
    found="$(ssh-keygen -F "${machine}" -f "${HOME}/.ssh/known_hosts" 2>/dev/null | grep -v '^#' || true)"
    if [[ -z "${found}" ]]; then
      printf 'UNPINNED %s (%s): no key in ~/.ssh/known_hosts; add it to %s by hand\n' \
        "${label}" "${machine}" "${record}"
      continue
    fi
    printf '%s\n' "${found}" >>"${record}"
    printf 'pinned %s (%s):\n' "${label}" "${machine}"
    printf '%s\n' "${found}" | ssh-keygen -l -f - | sed 's/^/  /'
  done <"${hosts}"
}

install_unit() {
  if [[ ! -x "${entry}" ]]; then
    (cd "${repo}" && uv sync)
  fi
  mkdir -p "${unit_dir}"
  sed "s#^ExecStart=.*#ExecStart=${entry} run#" "${repo}/overseer/${unit_name}" >"${unit_dir}/${unit_name}.tmp"
  mv "${unit_dir}/${unit_name}.tmp" "${unit_dir}/${unit_name}"
  create_private "${hosts}" \
    "# caam-delivery-push host list: <label> <user@host> <linux|macos>, one host per line." \
    "# A host whose credential file still holds its own refresh token reports not-converted."
  create_private "${record}" \
    "# caam-delivery-push known-hosts record: the only host keys the push service trusts."
  pin_host_keys
  systemctl --user daemon-reload
  systemctl --user enable "${unit_name}"
  systemctl --user restart "${unit_name}"
  systemctl --user is-active "${unit_name}" || true
  "${entry}" status
}

uninstall_unit() {
  systemctl --user disable --now "${unit_name}" 2>/dev/null || true
  rm -f "${unit_dir}/${unit_name}"
  rm -rf "${unit_dir}/${unit_name}.d"
  systemctl --user daemon-reload
  printf 'removed %s; kept %s and %s\n' "${unit_name}" "${hosts}" "${record}"
}

case "${1:-}" in
  install) install_unit ;;
  uninstall) uninstall_unit ;;
  *)
    printf 'usage: %s install|uninstall\n' "$0" >&2
    exit 2
    ;;
esac
