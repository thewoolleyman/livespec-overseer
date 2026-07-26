"""Shared tmux subprocess fakes for the `tmuxio` beside-tests.

Extracted so `test_tmuxio.py` (reads + fail-soft) and `test_tmuxio_writes.py`
(writes) share ONE `subprocess.run` stand-in instead of one importing the
other's privates. Both files exceeded no ceiling individually before the split;
their COMBINED module did, which is what forced it.

No tests live here. The name keeps the `test_*` prefix deliberately: coverage
omits `overseer/test_*.py`, so a differently-named helper in this package would
be measured as product code and demand 100% coverage of a test double.
"""

import types

import tmuxio

__all__: list[str] = ["FakeRun", "io"]


class FakeRun:
    """Stands in for ``subprocess.run``; records argv + stdin, returns canned result.

    ``timeout`` is accepted and RECORDED rather than ignored: a hung tmux would
    otherwise block the daemon forever, so every call must carry one, and a double
    that silently swallowed the kwarg could not prove it.
    """

    def __init__(self, *, returncode=0, stdout="", raises=None):
        self.returncode = returncode
        self.stdout = stdout
        self.raises = raises
        self.calls = []

    def __call__(
        self, argv, *, input=None, capture_output=None, text=None, check=None, timeout=None
    ):
        self.calls.append({"argv": argv, "input": input, "timeout": timeout})
        if self.raises is not None:
            raise self.raises
        return types.SimpleNamespace(returncode=self.returncode, stdout=self.stdout, stderr="")


def io(**kwargs):
    """A `TmuxIO` wired to a fresh `FakeRun`, returned as `(io, fake)`."""
    fake = FakeRun(**kwargs)
    return tmuxio.TmuxIO(run=fake), fake
