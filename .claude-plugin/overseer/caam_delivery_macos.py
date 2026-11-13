"""The macOS leg of the push: hand a delivery to a Mac's launch agent.

Claude Code keeps a Mac's interactive credential in the login Keychain, which an
ssh session cannot write. So for a `macos` host the push does not send the apply
step. It sends INBOX_PROGRAM, which writes the delivery to an owner-only inbox in
the user's home directory, temp-then-rename at 0600, for the per-user launch
agent to apply. It prints one line. When the agent's owner-only result file
already names this delivery's sequence, that line is the result, and the inbox
is left alone. Otherwise the line is `queued <sequence>`, with the agent's last
result appended as detail. So every push or retry to the host reads the agent's
result back, which is when the service records it.

AGENT_SCRIPT is the per-user launch agent itself. The install recipe copies it to
the Mac once, and launchd starts it when the inbox appears. It is a program text,
not a module of this package, for the same reason the Linux apply step is one: it
runs under the Mac's own /usr/bin/python3, which is 3.9, and imports nothing from
here.
"""

from __future__ import annotations

__all__: list[str] = [
    "AGENT_LABEL",
    "AGENT_SCRIPT",
    "INBOX_PROGRAM",
    "INSTALL_PROGRAM",
    "inbox_program",
    "install_program",
]

INBOX_PROGRAM = r"""
import json, os, sys, tempfile
def main(text):
    home = os.path.expanduser("~")
    folder = os.path.join(home, ".claude")
    try:
        seq = int(json.loads(text)["sequence"])
    except Exception:
        print("failed - bad-delivery")
        sys.stdout.flush()
        sys.exit(5)
    last = ""
    try:
        with open(os.path.join(folder, ".caam-delivery-result")) as f:
            lines = f.read().split("\n")
        last = ([line.strip() for line in lines if line.strip()] or [""])[-1]
    except FileNotFoundError:
        pass
    if last.split()[1:2] == [str(seq)]:
        print(last)
        return
    os.makedirs(folder, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=folder)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, os.path.join(folder, ".caam-delivery-inbox.json"))
    finally:
        if os.path.exists(temp):
            os.remove(temp)
    print("queued %d" % seq + ("; last-result " + last if last else ""))
"""


def inbox_program(*, payload: str) -> str:
    """The inbox program followed by the one call that hands it `payload`."""
    return f"{INBOX_PROGRAM}\nmain({payload!r})\n"


AGENT_SCRIPT = r'''"""The per-user launch agent that applies a pushed delivery on a Mac.

Installed once per Mac and started by launchd when the inbox appears. It applies
the delivery to the login Keychain under the same rules as the Linux apply step:
- one exclusive lock;
- `stale-sequence` when the delivery is not newer than the applied sequence;
- `not-converted` while the Keychain credential holds a refresh token;
- `claudeAiOauth` replaced and every other key kept;
- only `oauthAccount` and `userID` changed in ~/.claude.json;
- each write verified, and on any failure BOTH previous contents restored.
Then it deletes the inbox and writes exactly one result line, atomically, to an
owner-only result file beside it.

It runs under the Mac's own /usr/bin/python3, which is 3.9, so it must stay
3.9-compatible and import nothing from this package. The Keychain is written
through `security -i` with the value hex-encoded on its STDIN, so no credential
ever reaches a command line.
"""

from __future__ import annotations

import fcntl
import getpass
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

__all__: List[str] = ["KEYCHAIN_SERVICE", "apply_inbox", "main", "run_security"]

KEYCHAIN_SERVICE = "Claude Code-credentials"
Security = Callable[[List[str], str], Tuple[int, str]]


def run_security(args: List[str], stdin: str) -> Tuple[int, str]:
    """Run /usr/bin/security with `args`, feeding `stdin`; return (rc, stdout)."""
    done = subprocess.run(  # noqa: S603 - fixed executable, no shell, secrets only on stdin
        ["/usr/bin/security", *args], input=stdin, capture_output=True, text=True, check=False
    )
    return done.returncode, done.stdout


class _Keychain:
    def __init__(self, security: Security, account: str) -> None:
        self.security = security
        self.account = account

    def read(self) -> Optional[str]:
        rc, out = self.security(
            ["find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", self.account, "-w"], ""
        )
        return out.rstrip("\n") if rc == 0 else None

    def write(self, value: Optional[str]) -> None:
        if value is None:
            command = f'delete-generic-password -s "{KEYCHAIN_SERVICE}" -a "{self.account}"\n'
        else:
            command = (
                f'add-generic-password -U -s "{KEYCHAIN_SERVICE}" -a "{self.account}"'
                f" -X {value.encode('utf-8').hex()}\n"
            )
        rc, _ = self.security(["-i"], command)
        if rc != 0 or self.read() != value:
            raise OSError("keychain write not verified")


def _raw(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _put(path: Path, data: bytes) -> None:
    fd, temp = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            _ = handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def _restore(
    *, keychain: _Keychain, before: Tuple[Optional[str], Optional[bytes]], state: Path
) -> str:
    unrestored = []
    try:
        keychain.write(before[0])
    except Exception:  # noqa: BLE001 - every restore is attempted whatever the earlier outcome
        unrestored.append("credential")
    try:
        if before[1] is None:
            state.unlink(missing_ok=True)
        else:
            _put(state, before[1])
    except Exception:  # noqa: BLE001
        unrestored.append("global-state")
    return "; unrestored " + ",".join(unrestored) if unrestored else " rolled-back"


def _apply(*, home: Path, text: str, keychain: _Keychain) -> str:
    try:
        delivery: Dict[str, object] = json.loads(text)
        seq = int(str(delivery["sequence"]))
        oauth = delivery["oauth"]
        identity = delivery["identity"]
        if not isinstance(oauth, dict) or not isinstance(identity, dict):
            raise ValueError("shape")
    except Exception:  # noqa: BLE001 - any malformed inbox is one refusal line
        return "failed - bad-delivery"
    if "refreshToken" in oauth:
        return f"failed {seq} delivered-refresh-token"
    state = home / ".claude.json"
    sequence_file = home / ".claude" / ".caam-delivery-sequence"
    before = (keychain.read(), _raw(state))
    credential = json.loads(before[0] or "{}")
    if (credential.get("claudeAiOauth") or {}).get("refreshToken"):
        return f"not-converted {seq}"
    last = int((_raw(sequence_file) or b"0").strip() or b"0")
    if seq <= last:
        return f"stale-sequence {seq} host-applied {last}"
    credential["claudeAiOauth"] = oauth
    global_state = json.loads(before[1] or b"{}")
    global_state["oauthAccount"] = identity.get("oauthAccount")
    global_state["userID"] = identity.get("userID")
    try:
        keychain.write(json.dumps(credential))
        _put(state, json.dumps(global_state).encode("utf-8"))
        if json.loads(state.read_text(encoding="utf-8")) != global_state:
            raise OSError("verify global-state")
        _put(sequence_file, str(seq).encode("utf-8"))
    except Exception as error:  # noqa: BLE001 - restore both, then report
        restored = _restore(keychain=keychain, before=before, state=state)
        return f"failed {seq} {type(error).__name__}{restored}"
    return f"applied {seq}"


def apply_inbox(*, home: Path, security: Security, account: str) -> Optional[str]:
    """Apply the inbox, if any, and return the result line written beside it."""
    folder = home / ".claude"
    inbox = folder / ".caam-delivery-inbox.json"
    if not inbox.exists():
        return None
    with open(folder / ".caam-delivery.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        text = inbox.read_text(encoding="utf-8")
        try:
            line = _apply(home=home, text=text, keychain=_Keychain(security, account))
        except Exception as error:  # noqa: BLE001 - the agent always leaves one result line
            line = f"failed - {type(error).__name__}"
        _put(folder / ".caam-delivery-result", (line + "\n").encode("utf-8"))
        inbox.unlink(missing_ok=True)
    return line


def main() -> int:
    """The launchd entry point: apply the inbox for the current user."""
    line = apply_inbox(home=Path.home(), security=run_security, account=getpass.getuser())
    if line is not None:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

AGENT_LABEL = "com.livespec.caam-delivery-agent"

INSTALL_PROGRAM = r"""
import os, subprocess, sys
LABEL = "com.livespec.caam-delivery-agent"
PLIST = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>%(label)s</string>
<key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>%(agent)s</string></array>
<key>WatchPaths</key><array><string>%(inbox)s</string></array>
<key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>%(log)s</string>
<key>StandardErrorPath</key><string>%(log)s</string>
</dict></plist>
'''
def write(path, text, mode):
    temp = path + ".tmp"
    with open(temp, "w") as f:
        f.write(text)
    os.chmod(temp, mode)
    os.replace(temp, path)
def main(action, agent_text):
    home = os.path.expanduser("~")
    folder = os.path.join(home, "Library", "Application Support", "caam-delivery")
    agent = os.path.join(folder, "agent.py")
    plist = os.path.join(home, "Library", "LaunchAgents", LABEL + ".plist")
    domain = "gui/%d" % os.getuid()
    subprocess.run(["/bin/launchctl", "bootout", domain + "/" + LABEL], capture_output=True)
    if action == "uninstall":
        for path in (plist, agent):
            if os.path.exists(path):
                os.remove(path)
        print("uninstalled " + LABEL)
        return
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.makedirs(os.path.dirname(plist), exist_ok=True)
    os.makedirs(os.path.join(home, ".claude"), mode=0o700, exist_ok=True)
    os.makedirs(os.path.join(home, "Library", "Logs"), exist_ok=True)
    write(agent, agent_text, 0o700)
    write(plist, PLIST % {
        "label": LABEL,
        "agent": agent,
        "inbox": os.path.join(home, ".claude", ".caam-delivery-inbox.json"),
        "log": os.path.join(home, "Library", "Logs", "caam-delivery-agent.log"),
    }, 0o644)
    done = subprocess.run(
        ["/bin/launchctl", "bootstrap", domain, plist], capture_output=True, text=True
    )
    if done.returncode != 0:
        print("failed bootstrap %d %s" % (done.returncode, done.stderr.strip()[:160]))
        sys.exit(1)
    print("installed " + LABEL)
"""


def install_program(*, action: str) -> str:
    """The program the install recipe runs on a Mac to install or remove the agent."""
    return f"{INSTALL_PROGRAM}\nmain({action!r}, {AGENT_SCRIPT!r})\n"
