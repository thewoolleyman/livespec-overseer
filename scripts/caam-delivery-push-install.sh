#!/usr/bin/env bash
# Install or revert the role holder's caam-delivery-push user unit.
#
#   install    idempotent: write the unit (ExecStart -> this checkout's installed
#              entry point), create the host list if absent (mode 600, never
#              overwritten), daemon-reload, enable and (re)start, then print
#              is-active plus `caam-delivery-push status` as the read-back.
#   uninstall  the documented revert: disable --now, remove the unit and any
#              drop-in dir, daemon-reload. The host list is kept.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
unit_name="caam-delivery-push.service"
unit_dir="${HOME}/.config/systemd/user"
hosts="${HOME}/.config/caam-delivery/hosts"
entry="${repo}/.venv/bin/caam-delivery-push"

install_unit() {
  if [[ ! -x "${entry}" ]]; then
    (cd "${repo}" && uv sync)
  fi
  mkdir -p "${unit_dir}"
  sed "s#^ExecStart=.*#ExecStart=${entry} run#" "${repo}/overseer/${unit_name}" >"${unit_dir}/${unit_name}.tmp"
  mv "${unit_dir}/${unit_name}.tmp" "${unit_dir}/${unit_name}"
  if [[ ! -e "${hosts}" ]]; then
    mkdir -p "$(dirname "${hosts}")"
    (
      umask 077
      printf '%s\n' \
        "# caam-delivery-push host list: one ssh target per line (user@host or an ssh-config alias)." \
        "# A host whose credential file still holds its own refresh token reports not-converted." \
        >"${hosts}"
    )
    chmod 600 "${hosts}"
  fi
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
  printf 'removed %s; kept %s\n' "${unit_name}" "${hosts}"
}

case "${1:-}" in
  install) install_unit ;;
  uninstall) uninstall_unit ;;
  *)
    printf 'usage: %s install|uninstall\n' "$0" >&2
    exit 2
    ;;
esac
