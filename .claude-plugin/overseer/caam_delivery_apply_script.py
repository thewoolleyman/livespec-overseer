"""The host-side apply step, sent over ssh and run under `python3 -c`.

The delivery arrives on stdin. The step takes an exclusive lock, refuses a
delivered object carrying a refresh token, refuses a host whose own login still
holds one (`not-converted`), refuses an older sequence (`stale-sequence`), then
writes both files temp-then-rename at 0600, verifies them, and rolls both back
on any failure. It prints exactly one result line.
"""

from __future__ import annotations

__all__: list[str] = ["APPLY_SCRIPT"]

APPLY_SCRIPT = r"""
import fcntl, json, os, sys, tempfile
home = os.path.expanduser("~")
cp = os.path.join(home, ".claude", ".credentials.json")
sp = os.path.join(home, ".claude.json")
qp = os.path.join(home, ".claude", ".caam-delivery-sequence")
os.makedirs(os.path.dirname(cp), exist_ok=True)
def out(line, code):
    print(line)
    sys.exit(code)
def raw(p):
    try:
        with open(p, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None
def put(p, data):
    fd, t = tempfile.mkstemp(dir=os.path.dirname(p))
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(t, 0o600)
    os.replace(t, p)
try:
    d = json.load(sys.stdin)
    seq = int(d["sequence"])
    oauth = d["oauth"]
except Exception:
    out("failed bad-delivery", 5)
if "refreshToken" in oauth:
    out("failed delivered-refresh-token", 4)
with open(os.path.join(home, ".claude", ".caam-delivery.lock"), "w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    before = {p: raw(p) for p in (cp, sp)}
    cred = json.loads(before[cp] or b"{}")
    if (cred.get("claudeAiOauth") or {}).get("refreshToken"):
        out("not-converted", 3)
    try:
        last = int((raw(qp) or b"0").strip() or 0)
    except ValueError:
        last = 0
    if seq < last:
        out("stale-sequence %d" % last, 0)
    if seq == last:
        out("current %d" % seq, 0)
    cred["claudeAiOauth"] = oauth
    state = json.loads(before[sp] or b"{}")
    state.update(d["identity"])
    want = {cp: cred, sp: state}
    try:
        for p, v in want.items():
            put(p, json.dumps(v).encode())
        for p, v in want.items():
            with open(p) as f:
                if json.load(f) != v:
                    raise OSError("verify " + os.path.basename(p))
    except Exception as exc:
        for p, data in before.items():
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                put(p, data)
        out("failed rolled-back %s" % type(exc).__name__, 5)
    put(qp, str(seq).encode())
    out("applied %d" % seq, 0)
"""
