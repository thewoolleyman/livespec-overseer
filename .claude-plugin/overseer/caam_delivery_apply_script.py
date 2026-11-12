"""The host-side apply step, sent over ssh as a program on `python3 -`'s stdin.

`apply_program` appends one call carrying the delivery to APPLY_SCRIPT, so the
whole stdin is the program followed by the delivery and nothing reaches argv.
The step takes an exclusive lock, refuses a delivered object carrying a refresh
token, refuses a host whose own login still holds one (`not-converted`),
refuses a sequence that is not greater than the applied one (`stale-sequence`),
then writes the credential, the global state file and the applied sequence
temp-then-rename at 0600 and verifies them. On any failure it attempts BOTH
restores, credential first, and names each one that failed. It always prints
exactly one result line naming applied, stale-sequence, not-converted or
failed, with the sequence.
"""

from __future__ import annotations

__all__: list[str] = ["APPLY_SCRIPT", "apply_program"]

APPLY_SCRIPT = r"""
import fcntl, json, os, sys, tempfile
def out(line, code):
    print(line)
    sys.stdout.flush()
    sys.exit(code)
def raw(p):
    try:
        with open(p, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None
def put(p, data):
    fd, t = tempfile.mkstemp(dir=os.path.dirname(p))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(t, 0o600)
        os.replace(t, p)
    finally:
        if os.path.exists(t):
            os.remove(t)
def restore(p, data):
    if data is None:
        if os.path.exists(p):
            os.remove(p)
    else:
        put(p, data)
def apply(seq, oauth, identity):
    home = os.path.expanduser("~")
    cp = os.path.join(home, ".claude", ".credentials.json")
    sp = os.path.join(home, ".claude.json")
    qp = os.path.join(home, ".claude", ".caam-delivery-sequence")
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(os.path.join(home, ".claude", ".caam-delivery.lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = [(cp, "credential", raw(cp)), (sp, "global-state", raw(sp))]
        cred = json.loads(before[0][2] or b"{}")
        if (cred.get("claudeAiOauth") or {}).get("refreshToken"):
            out("not-converted %d" % seq, 3)
        try:
            last = int((raw(qp) or b"0").strip() or 0)
        except ValueError:
            last = 0
        if seq <= last:
            out("stale-sequence %d host-applied %d" % (seq, last), 0)
        cred["claudeAiOauth"] = oauth
        state = json.loads(before[1][2] or b"{}")
        state["oauthAccount"] = identity.get("oauthAccount")
        state["userID"] = identity.get("userID")
        try:
            for p, v in ((cp, cred), (sp, state)):
                put(p, json.dumps(v).encode())
            for p, v in ((cp, cred), (sp, state)):
                with open(p) as f:
                    if json.load(f) != v:
                        raise OSError("verify " + os.path.basename(p))
            put(qp, str(seq).encode())
        except Exception as exc:
            unrestored = []
            for p, name, data in before:
                try:
                    restore(p, data)
                except Exception:
                    unrestored.append(name)
            why = type(exc).__name__
            if unrestored:
                out("failed %d %s; unrestored %s" % (seq, why, ",".join(unrestored)), 5)
            out("failed %d rolled-back %s" % (seq, why), 5)
    out("applied %d" % seq, 0)
def main(text):
    try:
        d = json.loads(text)
        seq = int(d["sequence"])
        oauth = d["oauth"]
        identity = d["identity"]
        if not isinstance(oauth, dict) or not isinstance(identity, dict):
            raise ValueError("shape")
    except Exception:
        out("failed - bad-delivery", 5)
    if "refreshToken" in oauth:
        out("failed %d delivered-refresh-token" % seq, 4)
    try:
        apply(seq, oauth, identity)
    except Exception as exc:
        out("failed %d %s" % (seq, type(exc).__name__), 5)
"""


def apply_program(*, payload: str) -> str:
    """The apply step followed by the one call that hands it `payload`."""
    return f"{APPLY_SCRIPT}\nmain({payload!r})\n"
