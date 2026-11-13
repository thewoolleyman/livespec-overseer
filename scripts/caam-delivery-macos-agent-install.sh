#!/usr/bin/env bash
# Install or revert the caam-delivery launch agent on ONE listed macOS host.
#
#   install <user@host>    idempotent: copy the agent program and a per-user
#                          launchd plist that watches the delivery inbox, then
#                          (re)load it in that user's GUI domain.
#   uninstall <user@host>  the documented revert: unload, remove both files.
#
# Run it on the credential-rotation role holder, after the host is in the host
# list and `just install-caam-delivery-push` has pinned its host key. It connects
# exactly as the push does: the role key, the service's own known-hosts record,
# BatchMode, and the program on ssh's stdin. Never `tailscale ssh` to a Mac. The
# agent's first Keychain write may raise one macOS "allow access" prompt on the
# Mac, which its user answers once.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:?usage: caam-delivery-macos-agent-install.sh install|uninstall <user@host>}"
target="${2:?usage: caam-delivery-macos-agent-install.sh install|uninstall <user@host>}"
record="${HOME}/.local/state/caam-usage-rotate/delivery-known_hosts"
key="${HOME}/.ssh/id_ed25519"

case "${action}" in
  install | uninstall) ;;
  *)
    echo "unknown action: ${action}" >&2
    exit 2
    ;;
esac
if [[ ! -f "${record}" ]]; then
  echo "no known-hosts record at ${record}; run 'just install-caam-delivery-push' first" >&2
  exit 1
fi

PYTHONPATH="${repo}/overseer" "${repo}/.venv/bin/python" -c \
  'import sys; from caam_delivery_macos import install_program; sys.stdout.write(install_program(action=sys.argv[1]))' \
  "${action}" |
  ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes \
    -o "UserKnownHostsFile=${record}" -o GlobalKnownHostsFile=/dev/null \
    -i "${key}" -o IdentitiesOnly=yes -- "${target}" 'python3 -'
