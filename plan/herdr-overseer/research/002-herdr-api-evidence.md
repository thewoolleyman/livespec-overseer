# Herdr integration measurements — 2026-10-04

Measured locally on vmi3006760 as ubuntu; binary `/home/ubuntu/.local/bin/herdr`, version 0.9.3, API protocol 22. Read-only source checkout `/tmp/herdr-source-overseer-20261004` is upstream tag v0.9.3 / commit `7b116c05bfda646af39d2524c54e70c751f57ee8`. Full bundled request/response JSON schema: `/tmp/herdr-schema-overseer-research.json`.

Official source: https://github.com/herdrdev/herdr/tree/v0.9.3
Official docs index: https://herdr.dev/llms.txt
API docs: https://raw.githubusercontent.com/herdrdev/herdr/v0.9.3/docs/next/website/src/content/docs/socket-api.mdx

## Session isolation and identity

`herdr --session overseer-probe-20261004-herdr server` starts an empty headless server. It is a foreground persistent process, so launch with a proper supervising PTY/process lifetime. Named instance socket: `~/.config/herdr/sessions/overseer-probe-20261004-herdr/herdr.sock`; default: `~/.config/herdr/herdr.sock`. Always apply same explicit `--session` selector on all CLI probe commands. No existing user session was mutated. `herdr session stop NAME` then `herdr session delete NAME` cleans up a session created for this exercise.

Unix socket protocol is newline-delimited JSON: connect AF_UNIX/SOCK_STREAM, send one request `{"id":"unique","method":"pane.process_info","params":{"pane_id":"w1:p1"}}\n`, read one newline-terminated JSON reply, close. Replies wrap `result` or `error`. Set connect/read timeouts; ambiguous writes are not automatic retry permission. Linux `getsockopt(SOL_SOCKET, SO_PEERCRED, 12)` decoded as struct `3i` returns server PID, UID, GID; measured PID exactly matched isolated `herdr ... server` ancestor.

Pane IDs are opaque and only unique within a server (`w1:p1` repeats between test and default instances). Workspace IDs `w1`, tab IDs `w1:t1`. Namespace persistent identities by backend + canonical socket instance + tab/pane identifiers. Pane IDs survive swap, but a cross-workspace move assigns a new qualified pane ID; do not derive them from label/position.

`herdr status --json` includes server.running, version, protocol, socket, session, compatible, restart_needed, server_binary_stale. It does not return a server PID; SO_PEERCRED provides that independently.

## Parent / pane discovery

Injected into actual test pane process: HERDR_ENV=1, HERDR_PANE_ID=w1:p1, HERDR_TAB_ID=w1:t1, HERDR_WORKSPACE_ID=w1, HERDR_SESSION=overseer-probe-20261004-herdr, HERDR_SOCKET_PATH=<named socket>, HERDR_BIN_PATH=<binary>.

Actual direct pane process chain is python -> interactive zsh shell -> herdr server. `herdr pane process-info --pane ID` returns:

    {"result":{"type":"pane_process_info","process_info":{
      "pane_id":"w1:p2","shell_pid":1015684,
      "foreground_process_group_id":1017533,
      "foreground_processes":[{"pid":1017533,"name":"python3","argv":["/usr/bin/python3",...],"cmdline":"...","cwd":"/tmp"}]
    }}}

At shell prompt, foreground PGID == shell_pid and foreground_processes identifies shell. During an application, foreground PGID is application job group and not shell_pid. Discovery must verify own process ancestry against pane shell_pid/foreground processes and socket peer PID. Environment is a hint, not proof. Current Codex tool subprocess is zsh -> detached managed codex app-server PID 3710587 -> PID 1; its inherited HERDR_PANE_ID=w1:p1 is stale (active conversation UI appears in w1:p5). Never infer caller from current UI focus when ancestry lacks ownership proof. Existing panes can be enumerated by `pane list` / `api snapshot`; use exact matching or fail closed.

## Layout and enumeration

`workspace create --cwd /tmp --label NAME --no-focus` returns `.result.root_pane`, `.result.tab`, `.result.workspace`. Initial workspace is focused because no prior workspace exists, despite no-focus.

`tab create --workspace w1 --cwd PATH --label LABEL --no-focus` returns `.result.tab` and `.result.root_pane`.

`pane split --pane w1:p1 --direction down --ratio 0.25 --cwd /tmp --no-focus` creates w1:p2 as bottom, old w1:p1 remains top. Ratio is old/top share: measured 40 rows => old top y=0 height=10, new bottom y=10 height=30. Supported split directions ONLY right and down.

To place new daemon above existing LLM, split down then `pane swap --source-pane OLD --target-pane NEW`. Measured new pane now top height10 and original pane now bottom height30, same stable IDs and shell PIDs; caller focus remains original pane.

`pane layout --pane ID` returns `.result.layout`: area {x,y,width,height}, panes [{pane_id,focused,rect:{x,y,width,height}}], splits [{direction,ratio,id,rect}], tab_id, workspace_id, focused_pane_id, zoomed. `api snapshot` gives all workspaces/tabs/panes/layouts/agents in one JSON result.snapshot plus version/protocol.

`pane list` rows include pane_id, tab_id, workspace_id, terminal_id, cwd, foreground_cwd, focused, agent/agent_status, terminal_title, scroll viewport size. `tab list` rows include label, pane_count. Labels are presentation, IDs identity.

## Input and styled capture

`pane read ID --source recent-unwrapped --lines N --format ansi` prints raw ANSI text (NOT JSON); defaults text. Sources: visible, recent, recent-unwrapped, detection. Raw API method `pane.read` result.read.text contains the captured string, so it is easier to keep a consistent JSON transport. API source spelling is `recent_unwrapped` (CLI uses hyphen). Set `format:"ansi"` and `strip_ansi:false` when style evidence is needed. Measured ESC[2mOVERSEER_DIM_PROMPT ESC[0m survives ANSI capture.

`pane send-text ID TEXT` / `pane.send_text` send LITERAL RAW bytes, with NO bracketed paste. This was proven with a raw-mode program that enabled bracketed paste; ONE\nTWO arrived as literal ONE LF TWO. Do not use this for guarded LLM multiline prompt injection.

Correct bracketed paste-only operation is socket API:

    {"id":"...","method":"pane.send_input","params":{"pane_id":"w1:p1","text":"BRACKET\nPASTE","keys":[]}}

Measured application received `b'\x1b[200~BRACKET\nPASTE\x1b[201~'` and NO Enter. Implementation is `src/app/api/panes.rs:handle_pane_send_input`, which calls encode_api_input (honors current terminal bracketed-paste mode), builds all text+keys bytes, and writes one runtime message. Invalid key validation occurs before sending.

`pane send-keys ID Enter` produces CR separately. `pane run ID STRING` = same pane.send_input with text plus keys:["Enter"] atomically. Appropriate for known shell command launch, NOT the daemon's paste -> observe -> Enter protocol. `agent prompt` also atomically pastes+Enter but asserts agent state and therefore is not a substitute for overseer's guards.

`pane wait-output` matches existing screen immediately and can match command echo; never use a marker already included in the launch command as sole process-start evidence.

## Replacement constraints and measured fallback

No public pane respawn/restart API exists in protocol22; schema method list and v0.9.3 source confirm. Native Herdr internal respawn_shell_for_launch_pane is NOT exposed. `layout.apply` supports command argv but ALWAYS creates a whole NEW TAB and then closes the old target tab. It cannot reuse old pane processes based on pane_id in leaf description. It would kill a top daemon as well as bottom agent and changes all IDs; unsuitable.

Measured application replacement retaining same shell/pane: verify process_info exact foreground group and process identity (PGID != shell_pid); signal that owned process group SIGTERM; poll until shell_pid becomes foreground; then pane.run new launch command. Python process 1017533 terminated and replacement 1022159 printed success, same pane ID. Detection uses process identity only, NO prompt scraping, NO /exit. Never use `exec agent` with this path: a test `exec python` exit removed its pane entirely (pane IDs not reused).

This is NOT atomic. Production must represent stages before-stop / stopped-awaiting-shell / launch-submitted / replacement-observed, keep bounded timeouts, do not re-signal replacement or blindly replay an ambiguous launch. Require original ready declaration/generation interlock before any stopping; revalidate PID start time/PGID ownership and socket instance before effects. Shell reacquisition timeout or ambiguous launch is a visible failure requiring recovery, not permission to repeat kill.

Stronger architecture option: an overseer-owned persistent pane runner with a serialized private control socket manages the child lifecycle and can stop+spawn without shell text. That requires design for adoption of existing unwrapped LLM (first ready transition) and new runner code. Public Herdr alone cannot provide atomic same-pane kill+replace.

## HP

`hp` hostname fails DNS here. Correct shell access (fabro-hosts AGENTS): `tailscale ssh cwoolley@hp-xubuntu`. Read-only probe succeeded. Herdr absent from PATH, ~/.local/bin/herdr, /usr/local/bin/herdr. Fabro present `/home/cwoolley/.fabro/bin/fabro`; noninteractive PATH omits ~/.fabro/bin. Do real Herdr live exercise on VPS unless explicitly provisioning test Herdr on hp.
