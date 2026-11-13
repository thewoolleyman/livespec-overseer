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
"""

from __future__ import annotations

__all__: list[str] = ["INBOX_PROGRAM", "inbox_program"]

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
