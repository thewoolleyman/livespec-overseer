"""Fixed-path fake keyring and 1Password services inside the installed-test chroot."""

import json
import os
from pathlib import Path

__all__: list[str] = [
    "MACHINE_ID",
    "OP_STATE",
    "install_services",
]

MACHINE_ID = "0123456789abcdef0123456789abcdef"
OP_STATE = "/fixture/op-state.json"
_UID = 1000
_GID = 1000

_KEYCTL = """#!/opt/lpm/bin/python
import sys

ROLES = {
    "lpm-op-acquisition-reader": "101",
    "lpm-op-acquisition": "102",
    "lpm-op-metadata-reader": "103",
    "lpm-op-metadata-writer": "104",
    "lpm-op-provider-observer": "105",
    "lpm-op-value-reader": "106",
}
TOKENS = {serial: "fixture-token-" + description for description, serial in ROLES.items()}
argv = sys.argv[1:]
if argv[:3] == ["search", "@u", "user"] and argv[3] in ROLES:
    sys.stdout.write(ROLES[argv[3]])
elif argv[:1] == ["rdescribe"] and argv[1] in TOKENS:
    description = next(name for name, serial in ROLES.items() if serial == argv[1])
    sys.stdout.write("user;1000;1000;3f0b0000;" + description)
elif argv[:1] == ["pipe"] and argv[1] in TOKENS:
    sys.stdout.write(TOKENS[argv[1]])
else:
    raise SystemExit(1)
"""

_OP = """#!/opt/lpm/bin/python
import json
import os
import sys

STATE = "/fixture/op-state.json"


def item_object(item):
    return {
        "id": item["id"],
        "title": item["title"],
        "vault": {"name": item["vault"]},
        "fields": [
            {"id": label, "label": label, "type": "STRING", "value": value}
            for label, value in item["fields"].items()
        ],
    }


with open(STATE, encoding="utf-8") as handle:
    state = json.load(handle)
argv = sys.argv[1:]
verb = " ".join(argv[:2])
vault = argv[argv.index("--vault") + 1]
state["calls"].append({"argv": argv, "token": os.environ.get("OP_SERVICE_ACCOUNT_TOKEN", "")})
answer = None
garbled_list = verb == "item list" and state.get("garble_list_count", 0) > 0
if garbled_list:
    state["garble_list_count"] -= 1
if verb not in state["refuse"] and verb not in state["garble"] and not garbled_list:
    if verb == "item list":
        answer = [
            {"id": item["id"], "title": item["title"], "vault": {"name": vault}}
            for item in state["items"]
            if item["vault"] == vault
        ]
    elif verb == "item get":
        answer = next(
            (
                item_object(item)
                for item in state["items"]
                if item["vault"] == vault and item["id"] == argv[2]
            ),
            None,
        )
    elif verb == "item create":
        template = json.loads(sys.stdin.read())
        created = {
            "id": "fixture-%d" % (len(state["items"]) + 1),
            "title": template["title"],
            "vault": vault,
            "fields": {field["label"]: field["value"] for field in template["fields"]},
        }
        state["items"].append(created)
        answer = {"id": created["id"], "title": created["title"]}
        if state.get("interrupt_next_create", False):
            state["interrupt_next_create"] = False
            state["garble_list_count"] = 1
with open(STATE, "w", encoding="utf-8") as handle:
    json.dump(state, handle)
if verb in state["garble"] or garbled_list:
    sys.stdout.write("not-json")
elif answer is not None:
    sys.stdout.write(json.dumps(answer))
else:
    raise SystemExit(1)
"""


def install_services(*, root: Path) -> None:
    """Install the fixed production paths against wholly fixture-owned state."""
    machine = root / "etc" / "machine-id"
    machine.write_text(f"{MACHINE_ID}\n", encoding="ascii")
    machine.chmod(0o444)
    proc = root / "proc" / "self"
    (proc / "fd").mkdir(mode=0o555, parents=True)
    (proc / "stat").write_text("fixture-process\n", encoding="ascii")
    fixture = root / "fixture"
    fixture.mkdir(mode=0o700)
    os.chown(fixture, _UID, _GID)
    state = root / OP_STATE.lstrip("/")
    state.write_text(json.dumps({"items": [], "calls": [], "refuse": [], "garble": []}))
    os.chown(state, _UID, _GID)
    state.chmod(0o600)
    _write_executable(path=root / "usr" / "bin" / "keyctl", source=_KEYCTL)
    _write_executable(path=root / "usr" / "bin" / "op", source=_OP)


def _write_executable(*, path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
