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

import http.client
import json
import os
import shutil
import sys
from collections.abc import Generator, Iterator, MutableMapping
from dataclasses import dataclass
from pathlib import Path

import pytest

_PACKAGE_DIR = str(Path(__file__).resolve().parent.parent / "overseer")
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)


class ProviderRequestRefusedError(RuntimeError):
    """A test tried to send a LIVE request to an LLM provider.

    Deliberately NOT an `OSError`: the caam provider boundary
    (`caam_oauth_get.get_json`) fails closed on `OSError` and turns it into a
    reason string, which would swallow the refusal and let the test pass quietly
    against a real request.
    """


# The caam rotation pass sends TWO read-only requests per account per pass -- the
# usage poll and the capacity read -- and each resolves a real HTTPS connection
# unless the test seams it. A pass test that seamed only the usage fetcher would
# therefore reach the live provider once per account: slowly, against the
# maintainer's own quota, and reported as a flake. This guard makes forgetting
# one loud instead.
_REFUSED_PROVIDER_HOSTS: frozenset[str] = frozenset({"api.anthropic.com"})


@pytest.fixture(autouse=True)
def refuse_live_provider_requests(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test under `tests/` may open a connection to a live provider endpoint.

    It refuses at CONSTRUCTION, and it replaces the initializer rather than the
    class, because `HTTPSConnection.__init__` reaches its base through
    `super(HTTPSConnection, self)` -- which resolves the module global at call
    time. Rebinding that global to a wrapper function therefore breaks every
    legitimate connection with `super() argument 1 must be type, not function`.

    The tests that exercise the DEFAULT HTTPS transport stand in for the whole
    class themselves, and their own patch replaces this one.
    """
    real_init = http.client.HTTPSConnection.__init__

    def _refuse(*, host: str) -> ProviderRequestRefusedError:
        return ProviderRequestRefusedError(
            f"test tried to send a live provider request to {host!r}; "
            "seam the usage fetcher AND the capacity source instead"
        )

    def _guarded_init(
        self: http.client.HTTPSConnection, host: str, *args: object, **kwargs: object
    ) -> None:
        if host.split(":")[0] in _REFUSED_PROVIDER_HOSTS:
            raise _refuse(host=host)
        real_init(self, host, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(http.client.HTTPSConnection, "__init__", _guarded_init)


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


@pytest.fixture(autouse=True)
def _tmp_path_stays_removable(tmp_path: Path) -> Iterator[None]:
    """Give a passing test's `tmp_path` tree back its write permission before pytest removes it.

    pytest removes a passing test's `tmp_path` directory under the `failed` retention
    policy with `ignore_errors=True`, so a tree a fixture left non-writable (a git
    repository's 0444 objects under 0555 directories) is silently NOT removed and its
    files stay in /tmp until the host runs out of inodes (livespec-dev-tooling-jxhi63,
    2026-11-16). This fixture requests `tmp_path`, so it tears down first and restores
    the owner write bit on every directory in the tree.
    """
    yield
    for directory, _subdirectories, _files in os.walk(tmp_path):
        try:
            # os.* on purpose: some tests monkeypatch Path.stat while this teardown runs.
            os.chmod(directory, os.stat(directory).st_mode | 0o700)  # noqa: PTH101, PTH116
        except OSError:
            continue


_CALL_REPORT = pytest.StashKey[pytest.TestReport]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Remember each test's call report so a fixture can tell at teardown whether it passed."""
    report = yield
    if report.when == "call":
        item.stash[_CALL_REPORT] = report
    return report


def _make_removable(*, root: Path) -> None:
    """Restore the owner write bit on every directory under `root` so it can be removed."""
    for directory, _subdirectories, _files in os.walk(root):
        try:
            # os.* on purpose: some tests monkeypatch Path.stat while this teardown runs.
            os.chmod(directory, os.stat(directory).st_mode | 0o700)  # noqa: PTH101, PTH116
        except OSError:
            continue


@pytest.fixture(autouse=True)
def _factory_dirs_removed(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Remove the `tmp_path_factory.mktemp` directories a PASSING test made.

    pytest's `tmp_path_retention_policy` prunes only the `tmp_path` fixture's own
    directory, so every directory a fixture makes through `mktemp` (seven per test in
    this file) stayed in /tmp and, at about 105k files per suite run, exhausted a seat
    host's tmpfs inodes (livespec-dev-tooling-jxhi63, 2026-11-16). The directories a
    test makes are recorded here and, when its call phase passed, made writable and
    removed; a failing test keeps them for diagnosis, as the `failed` policy keeps its
    `tmp_path`. Higher-scoped fixtures are set up before this function-scoped one, so
    a session or module directory is never recorded.
    """
    made: list[Path] = []
    original = tmp_path_factory.mktemp
    remove_tree = shutil.rmtree  # bound before the test can monkeypatch shutil

    def recording(basename: str, *, numbered: bool = True) -> Path:
        path = original(basename, numbered=numbered)
        made.append(path)
        return path

    monkeypatch.setattr(tmp_path_factory, "mktemp", recording)
    yield
    report = request.node.stash.get(_CALL_REPORT, None)
    if report is not None and report.passed:
        for path in made:

            def sweep(target: Path = path) -> None:
                _make_removable(root=target)
                remove_tree(target, ignore_errors=True)

            # Removal waits for session cleanup: a background thread a test started can
            # still be writing into its directory when the test itself has ended.
            request.config.add_cleanup(sweep)


# Repo-locating variables a git hook exports into the environment of a test run.
# A test that shells out to `git init`, `git config` or `git commit` with one of
# them inherited writes into the SURROUNDING repository instead of its tmp path.
GIT_REPO_LOCATING_VARS: tuple[str, ...] = (
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_WORK_TREE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
)


def scrub_inherited_git_repo_locating_env(environ: MutableMapping[str, str]) -> None:
    """Remove every repo-locating git variable from `environ`, leaving all others."""
    for var in GIT_REPO_LOCATING_VARS:
        environ.pop(var, None)


@pytest.fixture(scope="session", autouse=True)
def _scrub_inherited_git_repo_locating_env() -> Iterator[None]:
    """Scrub the inherited repo-locating git variables once for the WHOLE session."""
    saved = {var: os.environ[var] for var in GIT_REPO_LOCATING_VARS if var in os.environ}
    scrub_inherited_git_repo_locating_env(os.environ)
    yield
    os.environ.update(saved)
