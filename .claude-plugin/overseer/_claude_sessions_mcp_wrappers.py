"""Credential-wrapper MCP shell classification for descendant-shell liveness."""

from __future__ import annotations

from _seams import PidToIntList, PidToOptionalBytes, PidToOptionalStr

__all__: list[str] = ["is_mcp_wrapper_shell"]


def is_mcp_wrapper_shell(
    *,
    pid: int,
    parent_by_pid: dict[int, int],
    children_of: PidToIntList,
    comm_of: PidToOptionalStr,
    cmdline_of: PidToOptionalBytes,
    max_nodes: int,
) -> bool:
    """Recognise the credential-wrapper ``… shell → op → …`` launch subtree.

    A resumed Codex process can start this MCP subtree long after its own process,
    so its timestamps cannot distinguish it from task work.  The wrapper's `op`
    process is the structural evidence: shells on either side of it are launch
    plumbing only when the shell argv itself names the fleet credential wrapper.
    A mere ``op`` descendant is insufficient: task shells can invoke `op` too
    and must remain busy.
    """
    seen: set[int] = set()
    ancestor = pid
    wrapper_ancestor = False
    op_ancestor = False
    while ancestor not in seen:
        seen.add(ancestor)
        argv = cmdline_of(pid=ancestor)
        wrapper_ancestor = wrapper_ancestor or (
            argv is not None and b"/usr/local/bin/with-" in argv and b"-env.sh" in argv
        )
        if comm_of(pid=ancestor) == "op":
            op_ancestor = True
        parent = parent_by_pid.get(ancestor)
        if parent is None:
            break
        ancestor = parent
    if wrapper_ancestor and op_ancestor:
        return True

    descendants = list(children_of(pid=pid))
    while descendants and len(seen) < max_nodes:
        descendant = descendants.pop()
        if descendant in seen:
            continue
        seen.add(descendant)
        if comm_of(pid=descendant) == "op":
            return wrapper_ancestor
        descendants.extend(children_of(pid=descendant))
    return False
