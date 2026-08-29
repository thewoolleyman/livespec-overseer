# caam model enforcement re-drives the /model picker when the model is already set

Filed 2026-08-29 from a live symptom: the foreman session's transcript carries
dozens of consecutive `/model` local-command invocations, each answering
"Set model to Fable 5" (with occasional stray "Opus 5 (1M context)" flips) --
overseerd's caam model enforcement keeps driving the model picker into a pane
whose model is already the wanted one. The maintainer's directive: overseerd
must not spam a model change when that model is already set.

## Mechanism, read from source (all paths relative to repo root)

1. `overseer/caam_sessions.py` `enforce_session_models` skips a pane only when
   `pane.model == want`, or `recently_set` says the same want was set within
   `CAAM_ROTATE_SET_SUPPRESS_S` (default 3600s).
2. `pane.model` comes from `pane_model` -> `_model_from_transcript`: the LAST
   assistant `message.model` within the final 65,536 bytes of the session's
   transcript (`~/.claude/projects/<slug>/<session-id>.jsonl`), mapped through
   `_MODEL_PREFIXES` to a short name.
3. A `/model` local command writes NO assistant `message.model` line. So a
   session that has been idle since its last assistant turn -- the normal state
   of a parked foreman -- accumulates local-command entries that push the last
   model-bearing line past the 64KB tail. `pane.model` then reads `None`
   ("unknown"), which never equals `want`, so enforcement drives the picker
   again. Each drive appends MORE model-free local-command lines, so the
   `None` read is self-perpetuating: the spam is its own cause.
4. `overseer/caam_picker.py` `drive_model_picker` never checks the picker's
   own highlighted "current model" row against `want` before acting: it opens
   the picker, moves to the target row, presses `s`, and answers the switch
   dialog -- so even when the pane is already on the wanted model, the drive
   emits a visible model-set into the pane.
5. Secondary amplifier: `recently_set` suppression is keyed on the exact
   `want` value, so any flip of the wanted model (fable <-> opus as
   `fable_left` changes) resets the suppression window.

## The fix shape

Two independent legs, both in stdlib-only overseer modules, both testable
with the existing seam-injected beside-test style:

- **Actuator idempotence** (`caam_picker.drive_model_picker`): after opening
  the picker, read the current-model row (the picker marks the active model);
  if it already matches `want`, send Escape and return a distinct no-op
  outcome instead of pressing `s`. This makes the spam impossible at the last
  line of defense regardless of how the model was mis-read.
- **Sensor honesty** (`caam_sessions`): treat `model is None` (unknown) as
  "verify, do not blind-fire" rather than as a mismatch -- and/or make
  `_model_from_transcript` robust to a tail full of local-command entries
  (scan further back for the last assistant model line, bounded). At minimum
  an unknown read must not re-drive the picker every pass forever.

The deliverable is a repository `.py` change with beside-tests; no
`SPECIFICATION/` change is required (spec governs the supervision contract,
not caam picker mechanics). Dispatch-safe: no template tokens, no cross-repo
deps, deliverable is a repo change.
