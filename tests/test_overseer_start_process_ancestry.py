"""Process-ancestry coverage for overseer-start runtime admission."""

import importlib

__all__: list[str] = []


def _load():
    return importlib.import_module("overseer.start")


def _comm_reader(*, comms):
    return lambda *, pid: comms.get(pid)


def _ppid_reader(*, parents):
    return lambda *, pid: parents.get(pid)


def test_process_ancestry_accepts_codex_agent_before_wrapper():
    mod = _load()
    for comm in ("codex", "codex-acp"):
        assert mod._has_supported_agent_ancestor(
            pid=30,
            claudecode_present=False,
            comm_of=_comm_reader(comms={30: "bash", 20: comm, 10: "bun"}),
            ppid_of=_ppid_reader(parents={30: 20, 20: 10, 10: 0}),
        )


def test_process_ancestry_accepts_claude_only_with_marker():
    mod = _load()
    comm_of = _comm_reader(comms={30: "bash", 20: "node"})
    ppid_of = _ppid_reader(parents={30: 20, 20: 0})

    assert mod._has_supported_agent_ancestor(
        pid=30, claudecode_present=True, comm_of=comm_of, ppid_of=ppid_of
    )
    assert not mod._has_supported_agent_ancestor(
        pid=30, claudecode_present=False, comm_of=comm_of, ppid_of=ppid_of
    )


def test_process_ancestry_rejects_plain_or_broken_chains():
    mod = _load()
    assert not mod._has_supported_agent_ancestor(
        pid=30,
        claudecode_present=False,
        comm_of=_comm_reader(comms={30: "bash"}),
        ppid_of=_ppid_reader(parents={30: 30}),
    )
    assert not mod._has_supported_agent_ancestor(
        pid=30,
        claudecode_present=False,
        comm_of=_comm_reader(comms={30: "bash", 20: "zsh"}),
        ppid_of=_ppid_reader(parents={30: 20, 20: 10}),
        max_hops=1,
    )


def test_running_under_supported_agent_threads_process_and_env(*, monkeypatch):
    mod = _load()
    observed = {}

    def fake_has_supported_agent_ancestor(*, pid, claudecode_present):
        observed["pid"] = pid
        observed["claudecode_present"] = claudecode_present
        return True

    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setattr(mod.os, "getpid", lambda: 4242)
    monkeypatch.setattr(mod, "_has_supported_agent_ancestor", fake_has_supported_agent_ancestor)

    assert mod._running_under_supported_agent()
    assert observed == {"pid": 4242, "claudecode_present": True}
