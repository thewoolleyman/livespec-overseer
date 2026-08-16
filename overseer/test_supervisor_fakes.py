"""The tmux and tty DOUBLES for the `supervisor` beside-tests.

Extracted so the `test_supervisor*` modules share ONE set of doubles instead of one
test module importing another's privates. `test_supervisor.py` had grown to 3193
LLOC — more than twelve times the 250-LLOC hard ceiling — and splitting it required
first untangling the helpers that fifteen of its sections reach across section
boundaries to use.

No tests live here. The name keeps the `test_*` prefix deliberately: coverage omits
`overseer/test_*.py`, so a differently-named helper in this package would be measured
as PRODUCT code and demand 100% coverage of a test double.

The members are PUBLIC even though the module is private. Sharing an `_`-prefixed
name across modules is exactly what the private-usage rules forbid, so a helper that
moves out of a single file cannot keep its underscore. `make_supervisor` became
`make_supervisor` rather than `sup`: `sup` is used as a local variable 594 times in
these tests, and de-underscoring into that name would have shadowed the builder with
its own result.
"""

import io as _io

__all__: list[str] = ["NO_SUBSHELL_PID", "FakeTmux", "TtyOut"]

# A pid that cannot exist, so the real ``claude_sessions.proc_children`` reader
# fails soft to ``[]`` → no descendant, no subshell. FakeTmux.pane_pid returns
# this by default so bg-shell detection is inert unless a test opts in.
NO_SUBSHELL_PID = 2**30


class FakeTmux:
    """Injectable stand-in for tmuxio.TmuxIO — canned reads, recorded writes."""

    def __init__(self):
        self.sessions = set()
        self.panes = {}
        self.cmds = {}
        self.paths = {}
        self.calls = []
        self.window_name = None  # last name written by the attention badge
        self.on_paste = None  # callback(session, text) for stamp-before-paste checks
        self.paste_ok = True  # set False to model a failed bracketed paste (B5)
        self.pasted_inputs = {}
        self.respawn_ok = True  # set False to model a failed respawn (B5)
        # set False to model a codex respawn whose pane never becomes a live codex TUI
        # (so `_await_pane(pane_is_codex)` fails) — the Codex-restart await-fail leg.
        self.respawn_yields_codex = True
        # A real `codex resume <uuid> <prompt>` records its argv prompt in the
        # successor transcript.  Set False to model the picker-shaped failure:
        # Codex is present, but its required resume kick never arrived.
        self.respawn_shows_command = True
        self.new_session_ok = True  # set False to model a failed new-session (Codex #3)
        self.pane_pids = {}  # {pane_pid: session} for the registry→tmux adopt join
        # Per-session pane PID (the login shell) fed to has_active_subshell. Defaults
        # to a NONEXISTENT pid so the real /proc reader returns [] → NO subshell,
        # keeping every legacy test's bg_shell False unless it opts in by setting a
        # pane pid here AND injecting fake children_of/comm_of on the Supervisor.
        self.pane_pid_map = {}
        # Sessions that EXIST but whose pane id cannot be resolved (RB3): `pane_id`
        # returns None for these while `session_exists` still reports True. That
        # combination is the "a tmux session that is not live process evidence" case —
        # a supervisor session with no pane must not count as a running supervisor.
        # A seam rather than a subclass: the repo bans inheritance in favour of
        # composition, and every other variation this double models (`paste_ok`,
        # `respawn_ok`, `respawn_yields_codex`, `new_session_ok`, `on_paste`) is already
        # an opt-in attribute, so a sixth one keeps the double's one shape.
        self.no_pane_sessions = set()
        self._cap_idx = {}
        self._cmd_idx = {}

    def pane_pid_sessions(self):
        return dict(self.pane_pids)

    def serve(self, *, session, repo, capture=None, cmd="node"):
        """Register ``session`` as a live Claude TUI whose cwd is inside ``repo``.

        The identity gate (B3) requires `pane_current_command` to look like Claude
        AND `pane_current_path` to resolve inside the row's repo before any act, so
        a valid tracked session must report both. ``cmd="zsh"`` models a pane that
        dropped to a shell (identity-gate `not-claude`).
        """
        self.sessions.add(session)
        self.cmds[session] = cmd
        self.paths[session] = str(repo)
        if capture is not None:
            self.panes[session] = capture

    def session_exists(self, *, session):
        self.calls.append(("exists", session))
        return session in self.sessions

    def pane_id(self, *, session):
        # Model pane-id resolution (RB3): return the session name itself as the
        # "pane id" for a live session (so target == name and the canned dicts,
        # keyed by name, still resolve), or None if the session is gone — or if the
        # test declared the session paneless via `no_pane_sessions`.
        self.calls.append(("pane_id", session))
        if session in self.no_pane_sessions:
            return None
        return session if session in self.sessions else None

    def pane_pid(self, *, session):
        # The pane's login-shell PID. Default is a nonexistent pid (real
        # proc_children → []), so bg_shell is False unless a test sets a pid here
        # and injects a fake process tree via the Supervisor's children_of/comm_of.
        self.calls.append(("pane_pid", session))
        return self.pane_pid_map.get(session, NO_SUBSHELL_PID)

    def capture_pane(self, *, session):
        self.calls.append(("capture", session))
        val = self.panes.get(session, "")
        # A list value is a sequence of successive frames (for the settled-delta
        # check): each capture returns the next frame, repeating the last once
        # exhausted. A plain string returns the same frame every call (a settled
        # pane). The daemon's `_pane_settled` captures twice; a 2-frame list with
        # different content makes those two captures differ → "streaming".
        if isinstance(val, list):
            i = min(self._cap_idx.get(session, 0), len(val) - 1) if val else 0
            self._cap_idx[session] = i + 1
            return val[i] if val else ""
        return val

    def pane_current_command(self, *, session):
        self.calls.append(("cmd", session))
        val = self.cmds.get(session)
        # A list models a CHANGING command across successive calls (e.g. the
        # identity re-check sees the pane after it exited to a shell — Codex #1).
        if isinstance(val, list):
            i = min(self._cmd_idx.get(session, 0), len(val) - 1) if val else 0
            self._cmd_idx[session] = i + 1
            return val[i] if val else None
        return val

    def pane_current_path(self, *, session):
        self.calls.append(("path", session))
        return self.paths.get(session)

    def list_sessions(self):
        return sorted(self.sessions)

    def send_keys(self, *, session, keys):
        self.calls.append(("keys", session, keys))
        if keys == "Enter" and session in self.pasted_inputs:
            text = self.pasted_inputs.pop(session)
            val = self.panes.get(session, "")
            if isinstance(val, str):
                self.panes[session] = val.replace(f"❯ {text}\n", "❯ \n")
        return True

    def bracketed_paste(self, *, session, text):
        self.calls.append(("paste", session, text))
        if self.on_paste is not None:
            self.on_paste(session, text)
            return self.paste_ok
        if self.paste_ok:
            val = self.panes.get(session, "")
            display_text = text.splitlines()[0]
            if isinstance(val, str) and "\n❯ \n" in val:
                self.panes[session] = val.replace("\n❯ \n", f"\n❯ {display_text}\n", 1)
                self.pasted_inputs[session] = display_text
        return self.paste_ok

    def respawn_pane(self, *, session, cwd, command):
        self.calls.append(("respawn", session, cwd, command))
        if not self.respawn_ok:
            return False
        # Model the runtime the command launches so the post-respawn identity await
        # (`_await_pane`) matches: a `codex resume …` respawn yields a codex pane (`bun`,
        # the launcher), any other command a fresh Claude TUI (`node`). A codex respawn
        # with `respawn_yields_codex=False` comes up non-codex (`node`), modeling the
        # await-fail leg.
        if "codex resume" in command and self.respawn_yields_codex:
            self.cmds[session] = "bun"
            self.panes[session] = (
                command if self.respawn_shows_command else "Resume a previous session"
            )
        else:
            self.cmds[session] = "node"
        self.paths[session] = cwd
        self.sessions.add(session)
        return True

    def new_session(self, *, name, cwd):
        self.calls.append(("new", name, cwd))
        if not self.new_session_ok:
            return False  # model a failed new-session (session NOT created)
        self.sessions.add(name)
        return True

    def rename_window(self, *, pane, name):
        # The attention badge on the tmux WINDOW name (`overseer` → `overseer(2!)`) —
        # the only overseer surface visible from a session the operator is attached to.
        self.calls.append(("rename_window", pane, name))
        self.window_name = name
        return True

    # test helpers ---------------------------------------------------- #
    def paste_texts(self):
        return [c[2] for c in self.calls if c[0] == "paste"]

    def renames(self):
        return [c[2] for c in self.calls if c[0] == "rename_window"]

    def has(self, *, method):
        return any(c[0] == method for c in self.calls)


class TtyOut:
    """A StringIO-alike that reports as a TTY, so `render` emits ANSI color (the
    real daemon writes to a tmux pane, which is a TTY). Duck-typed on purpose —
    the overseer only calls `write` / `flush` / `isatty`, and tests read via
    `getvalue`."""

    def __init__(self):
        self._buf = _io.StringIO()
        # BOUND, not redefined. `write` implements the stdlib `IO[str]` interface,
        # whose calling convention is POSITIONAL and not ours to change — the
        # overseer writes through `sup.out.write(...)`, and a keyword-only `write`
        # here would be a double that no longer matches the thing it doubles.
        # Binding the buffer's own method keeps the interface exact and leaves no
        # signature for `check-keyword-only-args` to flag. `flush` / `isatty` /
        # `getvalue` need no such treatment: they take nothing but `self`.
        self.write = self._buf.write

    def flush(self):
        self._buf.flush()

    def isatty(self):
        return True

    def getvalue(self):
        return self._buf.getvalue()
