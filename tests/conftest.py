"""Test bootstrap for the top-of-pyramid `tests/` tree.

The supervision package uses BARE sibling imports (`overseer/registry.py` does
`import jsonio`, not `from . import jsonio`), so it resolves only with the
package directory itself on `sys.path`. The beside-tests get that from
`overseer/conftest.py`; collecting from `tests/` reaches the same modules by a
different route, so it needs the same insertion.

Without this, `from overseer import registry` fails at import with
`ModuleNotFoundError: No module named 'jsonio'` — the package imports fine as a
package only because something already put its directory on the path.
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_PACKAGE_DIR = str(Path(__file__).resolve().parent.parent / "overseer")
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)


@pytest.fixture(autouse=True)
def fake_claude_on_path(
    *, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude = tmp_path_factory.mktemp("fake-claude-bin") / "claude"
    claude.parent.mkdir(exist_ok=True)
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{claude.parent}{os.pathsep}{path}" if path else str(claude.parent))


# ---------------------------------------------------------------------------
# The isolated fixture `op` — the LLM-credential-provider SecretStore harness.
# ---------------------------------------------------------------------------
#
# THE WHOLE POINT IS THAT NO TEST EVER REACHES A HOST VAULT. The manager's
# OnePassword backend spawns a real `op` child, so proving it spawns the right
# child, with only its own token, and reads only what that child printed needs a
# REAL subprocess — and the only safe real subprocess is one whose vaults are a
# JSON file this fixture owns. `op` is not installed on the factory host at all,
# so a test that forgot to point at the fixture fails rather than silently
# escaping to a live account.
#
# THE CHILD IS A PYTHON SCRIPT AND THAT IS A COVERAGE HAZARD, handled the same
# way `test_lpm_credential_role_joined.py` handles it: every caller hands the
# product runner an EXPLICIT environment with no `COVERAGE_PROCESS_START`, so the
# child cannot self-instrument and race the suite's own coverage data. The
# scrubbed role environment the contract already requires is what makes that
# true, not an extra precaution.
#
# IT RECORDS EVERY CALL, because the interesting assertions are about what the
# manager ASKED for — the exact argv, the vault, and which credential variables
# reached the child — rather than about the answer it got back. A fake that only
# returned data could not distinguish `op item create` from `op item edit`.

_OP_FIXTURE_SOURCE = '''#!/usr/bin/env python3
"""An isolated fixture `op`: three verbs over a JSON vault file, never a host vault."""
import json
import os
import sys

STATE = "__STATE__"


def _load():
    with open(STATE, encoding="utf-8") as handle:
        return json.load(handle)


def _save(state):
    with open(STATE, "w", encoding="utf-8") as handle:
        json.dump(state, handle)


def _vault_of(argv):
    return argv[argv.index("--vault") + 1] if "--vault" in argv else ""


def _item_object(item):
    return {
        "id": item["id"],
        "title": item["title"],
        "vault": {"name": item["vault"]},
        "fields": [
            {"id": label, "label": label, "type": "STRING", "value": value}
            for label, value in item["fields"].items()
        ],
    }


def _listed(state, vault):
    return [
        {"id": item["id"], "title": item["title"], "vault": {"name": vault}}
        for item in state["items"]
        if item["vault"] == vault
    ]


def _got(state, argv, vault):
    for item in state["items"]:
        if item["vault"] == vault and item["id"] == argv[2]:
            return _item_object(item)
    return None


def _created(state, vault):
    template = json.loads(sys.stdin.read())
    state["items"].append(
        {
            "id": "fixture-%d" % (len(state["items"]) + 1),
            "title": template["title"],
            "vault": vault,
            "fields": {field["label"]: field["value"] for field in template["fields"]},
        }
    )
    return {"id": state["items"][-1]["id"], "title": template["title"]}


def main():
    argv = sys.argv[1:]
    verb = " ".join(argv[:2])
    vault = _vault_of(argv)
    state = _load()
    state["calls"].append(
        {
            "argv": argv,
            "credential_names": sorted(
                name
                for name in os.environ
                if name.startswith(("OP_", "LPM_", "ANTHROPIC_", "CLAUDE"))
            ),
            "token": os.environ.get("OP_SERVICE_ACCOUNT_TOKEN", ""),
        }
    )
    if verb in state["refuse"]:
        _save(state)
        return 1
    if verb in state["garble"]:
        _save(state)
        sys.stdout.write("not json at all")
        return 0
    if verb == "item list":
        answer = _listed(state, vault)
    elif verb == "item get":
        answer = _got(state, argv, vault)
    else:
        answer = _created(state, vault)
    _save(state)
    if answer is None:
        return 1
    sys.stdout.write(json.dumps(answer))
    return 0


sys.exit(main())
'''


@dataclass
class OpFixture:
    """One isolated fixture `op` plus the JSON vault file it reads and appends to."""

    executable: str
    state_path: Path

    def seed(
        self,
        *,
        items: list[dict[str, object]] | None = None,
        refuse: tuple[str, ...] = (),
        garble: tuple[str, ...] = (),
    ) -> None:
        """Replace the fixture vault contents and the verbs it refuses or garbles."""
        self.state_path.write_text(
            json.dumps(
                {
                    "items": [] if items is None else items,
                    "refuse": list(refuse),
                    "garble": list(garble),
                    "calls": [],
                }
            ),
            encoding="utf-8",
        )

    def _state(self) -> dict[str, object]:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def calls(self) -> list[dict[str, object]]:
        """Every invocation the fixture saw, in order, with its argv and environment."""
        return self._state()["calls"]

    def argvs(self) -> list[list[str]]:
        """Just the argument vectors, for asserting on the verbs that were used."""
        return [call["argv"] for call in self.calls()]

    def items(self, *, vault: str) -> list[dict[str, object]]:
        """The fixture items now in `vault`, including anything `item create` appended."""
        return [item for item in self._state()["items"] if item["vault"] == vault]


@pytest.fixture(name="op_fixture")
def _op_fixture(*, tmp_path: Path) -> OpFixture:
    root = tmp_path / "fixture-op"
    root.mkdir()
    state_path = root / "vaults.json"
    executable = root / "op"
    executable.write_text(
        _OP_FIXTURE_SOURCE.replace("__STATE__", str(state_path)), encoding="utf-8"
    )
    executable.chmod(0o755)
    fixture = OpFixture(executable=str(executable), state_path=state_path)
    fixture.seed()
    return fixture
