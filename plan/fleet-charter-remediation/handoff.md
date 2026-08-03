# Fleet charter remediation — terminal handoff

## Status: COMPLETE AND ARCHIVED

This thread has no pending remediation, verification, ledger, or archive work.
Do not reopen or redispatch it from this handoff.

**You were handed this path by a respawn prompt, and that prompt is stale by
design.** The daemon builds it as `<repo>/plan/<topic>/handoff.md`
(`overseer/_supervisor_prompts.py:142`) — a FIXED live path computed from the
topic, which knows nothing about `plan/archive/`. This file exists so that
prompt resolves to something true instead of a missing file.

The authoritative completed records are
`plan/archive/fleet-charter-remediation/handoff.md` and
`supervisor-handoff.md`. They record the sweep, the three corrections the
supervisor made against its own conduct, and the honest statement of what the
sweep did not reach.

## What it did

The sweep took every supervisor charter in the fleet from **119 to 0**, across
six repos, merged through `#1248`, `#1919`, `#542`, `homelab#215`,
`livespec-console-beads-fabro#602`, `livespec-dev-tooling#1140`, `#549` and
`#551`, and archived by `#554`. Re-measured after the archive: **0 defects
across 41 charters**.

Two of the three baseline corrections were the GATE being wrong rather than the
corpus — detector `(h)` hard-coded one wrapper name, and separately required the
wrapper and `bd` on one physical line. `(h)` is now zero fleet-wide because every
finding it had left was a false positive.

All three ledger items are closed: `overseer-yho` (epic, 2026-08-03T02:03:45Z),
`overseer-yho.3` (01:58:31Z) and `overseer-c45` (01:59:03Z). The acting overseer
daemon was never stopped or restarted.

## What it did NOT reach — and that work has its own thread now

**Nothing enforces this anywhere but `livespec-overseer`.** The gate exists in
exactly one copy, scanning its own tree only, so **27 of the fleet's 40 charters
have no enforcement** and this result is a snapshot rather than a ratchet.

That is `overseer-x1q` (P1), and it is now owned by
**`plan/charter-gate-ratchet/`**. Resume there, not here. Separately unowned:
nothing schedules charter REGENERATION.

## ONE THING IS STILL IN FLIGHT — `livespec-overseer#611`

Added by the worker at wind-down, 2026-08-03. This is the only loose end; the
sweep itself is finished.

**`#611` fixes `check-pre-push`**, which decided "doc-only" from
`git diff "${upstream}..HEAD"` where `upstream` came from `@{upstream}`. For a
branch pushed once with `-u` and then REBASED, that is the branch's own STALE
REMOTE REF, so the diff spans every `origin/master` commit the rebase absorbed
and a genuinely doc-only branch is classified as a code push. Measured on this
thread's own archive branch: **34 `.py` files changed vs the stale `@{upstream}`,
ZERO vs `origin/master`.** It cost eight failed pushes across ~50 minutes; a bare
`git branch --unset-upstream` then made the identical push succeed first try.
The fix uses `origin/master...HEAD` (three dots, merge-base), matching what
`check-changed`, `check-prose-release-hygiene` and the workflow-drift gate in the
same justfile already use.

**WHAT TO DO:** confirm `#611` merged. If it did, close `overseer-oo8` — its
other half (a `tests/prompts/conftest.py` `155->157` partial branch) was fixed
independently by another track in `021914d`, verified at 100% with zero partial
branches, so nothing remains on that item. If `#611` did NOT merge, read its
checks; it is a one-line justfile change with both directions already verified
(doc-only branch → doc-only; a real `.py`-bearing range → still a code push).

**DO NOT re-derive `overseer-oo8` from its early notes.** That item was filed
with the wrong headline ("just check cannot pass on a loaded host"), corrected
once when the real cause turned out to be `@{upstream}`, and corrected again when
its second half was fixed elsewhere. The corrections are recorded on the item in
order; read to the END of the notes before acting.

## If a fresh session receives this file

Its only actions are to confirm on a freshly fetched `origin/master` that
`plan/archive/fleet-charter-remediation/` exists, that
`plan/charter-gate-ratchet/handoff.md` carries the remaining work, and to
discharge the `#611` section above. There is no remediation to resume.
Re-measure rather than trusting any number above; every one is a claim with a
timestamp.
