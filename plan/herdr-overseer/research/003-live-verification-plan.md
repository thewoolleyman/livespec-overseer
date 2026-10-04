# Herdr overseer live verification plan

Owner: independent read-only design reviewer; no product implementation performed.
Scope: prove real released daemon and real interactive LLM work inside real Herdr while preventing any interaction with existing user panes or stores.

## Measured prerequisites

- Docker 28.2.2 answers normally.
- `bwrap --unshare-pid --ro-bind / / --proc /proc true` succeeds on this host.
- Host user is ubuntu (uid 1000), normal home `/home/ubuntu`.
- Herdr and uv are `/home/ubuntu/.local/bin/herdr` and `/home/ubuntu/.local/bin/uv`.
- Claude launcher resolves to `/home/ubuntu/.local/share/claude/versions/2.1.289`.
- `overseer-start` requires a real Claude/Codex process ancestor and launches a versioned installed daemon through `runtime_prefix.ensure_current_runtime`; do not replace that with a fake daemon or call a mock bootstrap and describe it as the production path.
- `overseerd` CLI deliberately has no watch/store/stamp override. Production defaults are `Path.home()/.livespec-overseer-{repos.json,stamps.json,status.json,input-provenance.json}`, mapping `.livespec-overseer.jsonl`, and mapping-derived `.daemon.lock`.
- Watch declaration is JSONC `{"repos": ["absolute-repository-path"]}`. Only listed roots with `plan/` exist are discovered. No fleet manifest fallback is used.
- Default daemon log follows the selected overseer checkout; give the namespace its own writable checkout at the same pathname.

## Isolation: mount a fresh home at the normal path, retain normal HOME

Use a private bwrap PID/mount namespace with a read-only host filesystem. Bind a fresh temporary directory over `/home/ubuntu` so the value of HOME is never repurposed. Bind separate writable scratch directories over `/tmp`, `/run/user/1000` and `/data/projects/livespec-overseer`; mount namespace-local `/proc`; use `--new-session --die-with-parent`. Keep networking so the real LLM can authenticate. Do not use a host PID namespace or host Herdr socket.

Create the scratch tree outside the production repo, mode 0700; keep a parent evidence directory mounted to `/evidence` inside the namespace. A command skeleton (paths supplied as argv, shell quoted):

    bwrap --die-with-parent --new-session --unshare-pid \
      --ro-bind / / --proc /proc --dev /dev \
      --bind "$probe_home" /home/ubuntu \
      --bind "$probe_tmp" /tmp \
      --bind "$probe_runtime" /run/user/1000 \
      --bind "$probe_checkout" /data/projects/livespec-overseer \
      --bind "$probe_evidence" /evidence \
      --chdir /data/projects/livespec-overseer \
      /usr/bin/env -u TMUX -u TMUX_PANE -u HERDR_ENV -u HERDR_PANE_ID \
      -u HERDR_TAB_ID -u HERDR_WORKSPACE_ID -u HERDR_SESSION \
      -u HERDR_SOCKET_PATH -u HERDR_BIN_PATH \
      /bin/bash /evidence/run-inside-namespace.sh

The Herdr variable spellings above are measured in `/tmp/herdr-api-evidence.md`. Scrub all inherited backend selectors; the test server will inject its own. Likewise scrub OTEL export endpoints/headers so test telemetry stays local. The namespace-local server command is `herdr --session <unique-test-name> server`; use its explicit session selector consistently for every CLI command. Its socket lives in private `~/.config/herdr/sessions/<name>/herdr.sock`.

Populate only the required executables in scratch home, using explicit read-only binds or copies of the resolved binaries; do not bind the host's entire `.local/share`, `.claude`, or `.codex`. A readonly bind of the resolved Claude binary to scratch `.local/bin/claude` avoids broken symlinks. Herdr and uv can be bound similarly. Use system Python/git/bash. If toolchain needs a mise Python binary, bind that precise installation, not the host config tree.

For authentication, copy only the normal CLI auth file into scratch home (Claude `.claude/.credentials.json`, or Codex `.codex/auth.json`) with mode 0600, without displaying contents. Copy narrowly selected onboarding/account fields only if required; never copy settings containing host hooks/MCP servers. Refreshes then alter only the disposable copy. Do not place credentials in evidence or command arguments. No new login or fake model is needed.

Write a minimal scratch Claude settings file with dangerous-mode consent per the user's autonomous test authorization and a statusLine command which prints `Ctx: <context_window.remaining_percentage>% left` from the real statusline JSON. This is measured actual runtime context, not a fabricated percentage. Keep all production host hooks, projects and MCP servers out. Use the real model through the normal auth mechanism.

Copy/clone the released checkout into the writable scratch checkout; all other host repos remain read-only. Make a dedicated scratch test repo under the private `/tmp` with `.gitignore` containing `tmp/`, `plan/<unique-topic>/`, and task instructions forbidding writes outside this scratch repo. Set the private watch declaration to this test repo alone. The test's plan epic should be a real isolated test thread created through the orchestrator by the parent; if the final fresh session cannot read a real ledger, explicitly record that limitation instead of calling it a full end-to-end plan resume.

Run everything (Herdr server, attachment terminal, Claude, bootstrap, observing controller) inside the same namespace. Use a dedicated named Herdr server. Start an attached Herdr TUI under a namespace-local tmux socket at a known size (for example 160 columns by 50 rows) to prove visible top/bottom geometry. This tmux is the terminal transport around Herdr, not the backend selected for panes. Nearest verified Herdr ancestor must win. Capture the outer test tmux screen as visual evidence and Herdr native pane reads as machine evidence.

The actual interactive Claude session should run the shipped `overseer-start` command itself on request, not a controller process outside its ancestry. This proves runtime and pane detection. The top pane must contain the installed `overseerd` PID; bottom pane must retain the same original LLM PID/session after splitting. Record selected package/version from the status snapshot and installed executable.

## Positive live sequence

1. Record initial namespace-local process identities, server/socket, tabs, pane IDs and geometry; record host active pane identity set separately for before/after comparison without capturing unrelated content.
2. Start real Claude in an isolated Herdr pane, name its session with the exact scratch plan topic, and obtain one model-generated nonce response. Save registry PID/procStart/session identity plus capture.
3. Ask this Claude to run shipped overseer bootstrap with `--warn-percent 99`. Record actual tool exit, top daemon PID and terminal, bottom unchanged LLM identity, focus, and increasing status tick_generation. Re-run bootstrap through the same real LLM; prove exactly two panes and one acting daemon remain.
4. Keep one deliberately differently named sibling tab with a long-lived harmless sentinel process. Record its PID/starttime and counter throughout to prove target isolation.
5. Confirm adopted row backend/controller/tab/pane identity, repository, topic, runtime, model profile and context agree with live process evidence. Read styled Herdr capture and verify exact real Claude dim placeholder bytes are preserved.
6. Cause an actual model turn large enough to bring real reported remaining percentage to <=99; observe one complete bracketed wrap-up paste and submission at settled idle. Do not synthesize context telemetry. Verify no prompt fragmentation and exactly one round stamp/notified band.
7. Let the real LLM acknowledge winding-down and declare ready via shipped `overseer-declare ready`. Preserve the command result and its final-stop behavior. The controller must not write ready on the model's behalf for this positive test.
8. Observe guarded replacement, source identity termination and genuinely fresh successor session ID/procStart, same intended backend pane/tab, preserved runtime/model/cwd/env profile, and unchanged daemon/sibling. Confirm resume prompt was actually submitted and model produced a fresh response referencing the handoff nonce from the real plan state. Verify round consumption only after successful submit.
9. Observe at least two additional daemon ticks proving successor re-adoption and supervision, not merely a one-shot restart.
10. Run tmux-only control with a separate namespace-local tmux server and actual interactive LLM bootstrap/restart to verify legacy path still works. A full live Codex path is also desirable if auth and supported model are available; at minimum require real Claude and hermetic both-runtime tests.
11. End only test processes, archive/disposition test ledger thread, delete disposable credential files, and compare production stores and active pane identities with baseline. Keep redacted screenshots/captures, status, UTC timestamps, process identities, CLI responses and test logs as evidence.

## Negative controls and crash boundaries

Automate hermetic tests for every row; execute selected safe controls on the isolated live session as well.

| Area | Required controls |
|---|---|
| Backend detection | Native tmux; native Herdr; Herdr nested in tmux; tmux nested in Herdr; stale inherited env; matching-looking env but detached app-server ancestry; multiple controllers with same tab/pane names; process disappears during walk; PID reused with different starttime; permission-denied proc reads; malformed/cyclic/deep ancestry. |
| Pane identity | Rename/reorder tab while observed; focus changes; multiple agents in same tab; sibling with same prefix/name; stale pane id reused after server restart; same bare pane id on two servers; peercred server PID mismatch; source process exits between read and act. |
| Input fidelity | Empty input; dim generated placeholder; visually identical undimmed typed text; ANSI combined/reordered SGR; Unicode and multiline payload; bracketed escape sequences; quotes/shell metacharacters passed as literal bytes; separate Enter; capture timeout/error/malformed JSON; gates and busy markers; bottom statusline retained without Herdr chrome. |
| Authorization | No ready; blocked; malformed state; stale ready; ready from predecessor; busy/subagent/background-shell; missing epic; changed cwd/model/profile; identity changes after settle; all suppress destructive action. |
| Replacement transaction | Failure before kill leaves old process/ready intact; kill succeeds but shell return times out; source dies naturally; shell is gone; kill races group-id reuse; launch RPC times out after actually starting successor; daemon dies at each phase; capture/identity proof unavailable; re-exec during pending transaction; two daemons contend; successor starts but resume paste/Enter fails. |
| Recovery | A persisted transaction distinguishes unconsumed source authorization from killed source/unknown launch/successor-live; retries never kill successor; resume retries submit only; uncertain target/process identity fails closed; progress/ready consumed only after proof; a new ready from fresh successor is independent. |
| Layout | Bootstrap outside real LLM refuses before mutation; split failure; launch failure after split; repeat bootstrap; a differently owned titled pane; resized/reordered panes; extra preexisting pane; server disconnect; daemon recovery preserves bottom agent; tab jump command targets exact controller/tab. |
| Runtime parity | Claude and Codex discovery, naming, context, input gates, launch-profile preservation, fresh restart and declare topic resolution; existing tmux mappings deserialize unchanged; mixed backend tracks can coexist. |

## Non-atomic replacement review standard

Current PaneDriver boolean contract assumes `False` means nothing killed and `True` means stable target now replaced. Herdr stop-then-run creates a third state. Do not hide it behind that boolean without durable recovery semantics. Before source termination persist a transaction with exact server identity, tab/pane, source PID/starttime, command/profile and phase; each subsequent action must be guarded by a fresh identity observation. If stop succeeded and launch outcome is unknown, retrying must inspect the observed successor rather than repeat kill. The predecessor ready token cannot authorize destructive action on any new successor.

A foreground PGID is not sufficient by itself: prove it belongs to the expected runtime, differs from the persistent pane shell group, and is still the same process generation immediately before signalling. Linux pidfd can protect a single PID but does not make killpg atomic against group reuse. If stable safe group termination cannot be proven, surface the failure instead of broadening kill scope. Read process-info to prove returned shell foreground; never scrape a shell prompt. RPC timeout is an unknown outcome, not proof no command executed. An LLM launched with `exec` has replaced its shell; measured Herdr removes the pane when it exits, so replacement must refuse that case before signalling. Server identity must include process generation: canonical socket path plus pane id can recur after server restart.

Existing TDD artifacts must be audited independently: genuine assertion failure before existing product changes, exactly one staged Red test file, byte-identical test at Green, hook-stamped trailers retained, replay verified, full checks green. Live evidence supplements those tests and does not replace them.
