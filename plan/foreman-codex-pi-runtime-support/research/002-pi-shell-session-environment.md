# Pi live-session identity carrier

Measured 2026-08-27 against the installed
`@earendil-works/pi-coding-agent` 0.84.3 package.

## Finding

Pi already exposes a supported carrier for the active session at the exact
boundary where the shared foreman skill invokes `foreman-runtime`. Commands
run by Pi's LLM-callable `bash` and `powershell` tools receive:

- `PI_SESSION_ID`, resolved from the current `SessionManager` when the command
  starts;
- `PI_SESSION_FILE`, the absolute path to that current session's JSONL file;
- the inherited process markers `AI_AGENT=pi` and `PI_CODING_AGENT=true`.

The injection source first deletes inherited `PI_SESSION_ID` and
`PI_SESSION_FILE` values, then writes the current manager's values. A nested Pi
therefore cannot accidentally present stale parent-session metadata through
the built-in tool path. The Pi foreman binding uses that path when it runs the
shared wrapper. User-entered `!` / `!!` commands deliberately receive no
session variables and must fail the foreman gate closed.

The referenced session format provides the remaining identity fields as
metadata records:

- the first `session` header is metadata-only and carries the session `id` and
  exact `cwd`;
- the latest `session_info` metadata entry carries the current name set by
  `--name` or `/name`.

Together these form the same join the existing gate requires: the command is
issued by the active Pi session, the environment names that session's file and
ID, the header binds the ID to the repository, and the latest session-info name
must equal the canonical `<repo-slug>-foreman` tmux name.

This is sufficient current-runtime evidence. No `livespec-driver-pi` contract
change is needed.

## Evidence

The installed package documents the contract in
`docs/environment-variables.md` and `docs/session-format.md`. Its
`dist/core/tools/bash.js` `resolveSpawnContext` implementation performs the
delete-then-inject behavior from `ctx.sessionManager`. Its
`dist/core/session-manager.js` writes the metadata-only header and appends
`session_info` entries while exposing the current session ID and file.

The public CLI also makes the identity inputs first-class: `--name` / `-n`
sets the display name, `--session` and `--session-id` select an exact session,
and `/session` reports the current ID and file. This is supported runtime
metadata rather than pane-text inference.

## Fail-closed implementation boundary

Add a stdlib-only Pi identity reader in this repository. It should accept only
when all of these facts agree:

1. the Pi process markers identify the invoking tool path;
2. `PI_SESSION_ID` is present and `PI_SESSION_FILE` names an existing regular
   file;
3. the metadata header is well-formed and its ID exactly equals
   `PI_SESSION_ID`;
4. the header cwd resolves to the governed repository;
5. the latest `session_info` metadata name exactly equals the canonical
   foreman name;
6. the canonical tmux session exists and the repository is in the watch set,
   preserving the existing gate legs.

The reader must stream only the header and `session_info` record shapes. It
must skip message, tool-result, compaction, and other transcript-bearing lines
without decoding, retaining, logging, or returning their contents. Bounded
line handling must fail closed on malformed or oversized metadata rather than
turn transcript content into an identity source.

The following cases refuse: `--no-session` / missing `PI_SESSION_FILE`, a
missing or non-regular file, malformed metadata, ID mismatch, absent or empty
session name, wrong name, wrong cwd, absent Pi process markers, and invocation
through the non-injecting `!` / `!!` path.

## Codex and routing consequence

Codex remains a separate current-repository slice: `foreman-runtime` can add
`codex_sessions.read_live_codex_sessions()` to the existing Claude identities,
because `CodexSession` already carries the name and cwd shape consumed by the
gate. Pi should enter through the environment-backed reader above rather than
through global process discovery.

Both slices conform to the ratified canonical-name scenario and preserve its
exact tmux-name plus runtime-name requirement. They can be filed as
implementation work under this plan after a scope event; neither requires a
specification proposal. Acceptance still owes real interactive tmux positive
and refusal controls for Claude, Codex, and Pi.
