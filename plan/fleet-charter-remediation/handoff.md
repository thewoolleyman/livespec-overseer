# Plan — fleet-charter-remediation

**Owning repo:** `livespec-overseer`. **Ledger anchor:** `overseer-yho.3`
(this repo's beads tenant). Split out of `plan/supervisor-prompt-quality/` when
that thread archived on 2026-08-02; it was that thread's last open slice and it
outlived it.

**Second item, adopted 2026-08-02: `overseer-c45`.** It does NOT re-open the
phase-1 cut — see "Second item" near the end of this file before touching it.

**Status is not stored here.** Read it from the ledger. `bd` needs the fleet
credential wrapper in this tenant — a bare `bd` returns `Access denied`. Use
`with-livespec-env.sh -- bd show overseer-yho.3 --json`.

## What this is

Every generated supervisor charter in the fleet is scored by this repo's shipped
eleven-detector gate, `tests/prompts/test_charters_carry_no_known_defects.py`.
**This repo scores ZERO. The rest of the fleet does not.** This thread remediates
them.

The measurement, reproduced three times a day apart by different code paths (the
shipped module imported and called — never a grep), most recently
2026-07-31T15:50Z:

| repo | charters | dirty | defects |
|---|---|---|---|
| `livespec-orchestrator-beads-fabro` | 6 | 5 | **56** |
| `homelab` | 7 | 2 | 23 |
| `livespec-dev-tooling` | 3 | 2 | 18 |
| `livespec-console-beads-fabro` | 1 | 1 | 15 |
| `livespec` | 4 | 2 | 5 |
| `livespec-overseer` | 8 | 0 | **0** |
| **total** | **29** | **12** | **117** |

By class: (a) 92, (c) 7, (d) 7, (b) 5, (h) 2, (e) 1, (f) 1, (i) 1, (j) 1, (k) 0.

## The scope is already DECIDED — do not re-open it

**PHASED, `livespec-orchestrator-beads-fabro` FIRST.** The maintainer's cut. That
repo holds **56 of 117** with five of its six charters dirty, so one scoped slice
clears roughly half the fleet exposure.

**The single highest-leverage edit in the fleet is ONE LINE.**
`livespec-orchestrator-beads-fabro/.ai/supervisor-protocol.md` uses
`-t "$WORKER_TARGET"` ten times and **never binds it**. Adding the one binding
line this repo already ships takes that file **10 → 0** with no other change. It
is a SHARED layer, so it fixes every thread in the repo holding 48% of the
exposure. Verified three times, twice from a standalone copy of the module
running outside this repo entirely, each with a control confirming the on-disk
file still scores 10 afterwards so nothing leaked to disk.

## Two constraints that ride with it — both are load-bearing

1. **IT TOUCHES ANOTHER TRACK'S REPO. Tell that track before changing anything.**
   A charter whose worker and supervisor sessions are both live is **ARMED**: the
   defect is dormant and fires when a session exits. Check for live sessions
   (`tmux list-sessions`) and send a notice first. Confirm a pasted notice by the
   `[Pasted text …]` placeholder or a non-empty prompt line, **never by grepping
   the pane for its text** — that returns zero on a paste that landed perfectly
   (charter C21), and the render lags, so re-capture rather than re-send.
2. **ON COMPLETION, STATE WHAT REMAINS.** Phase 1 leaves **61 defects across 4
   repos** untouched. Saying "the fleet is clean" after phase 1 would be false.
   Say the number.

## What the edit actually is, and its honest limit

A deliberately stupid rewrite — bare `-t X` to the exact `-t '=X:'` form, plus
one added binding line — applied IN MEMORY and re-scored by the shipped gate took
the fleet **117 → 25**, clearing **all 92 of class (a)**. Control: an unmodified
re-scan afterwards still reported 117, so nothing leaked to disk.

Class (a) is 92 of 117 (79%), and by target shape it is **71 LITERAL** (the
session name is already in the line — a purely syntactic rewrite that decides
nothing), 9 placeholder, 2 `name:window.pane`, and 10 VARIABLE collapsing to
**one** distinct binding fleet-wide. The residue after (a) is ~13 genuinely
distinct edits, because (b)'s 5 instances are ONE distinct line and (d)'s 7 are
ONE distinct line.

**THE LIMIT, STATED:** this proves the corpus is mechanically CLEARABLE PER THE
GATE, not mechanically CORRECT. A human reads the diff. The claim is that the
diff is uniform and readable, not that review is unnecessary.

**The remedy is safe on every subcommand the fleet's charters use.** The single
most plausible way the rewrite could be wrong was that some tmux subcommand
rejects the exact-match form — and this repo's own `AGENTS.md` asserted exactly
that about `respawn-pane`, the one destructive operation. **Measured on a private
socket: false.** `=name:` **with the trailing colon** works on `respawn-pane`,
`capture-pane`, `list-panes`, `send-keys`, `paste-buffer` and `has-session`. Only
`=name` without the colon fails. Corrected in PR #456.

## Facts that change the shape — carry these, do not re-derive

- **Carry all ELEVEN detectors, not the seven or ten earlier costings assumed.**
  (k) adds zero fleet-wide, and that zero is CONTROLLED: the trap was injected in
  memory into a real fleet charter and the same call returned 1, so the absence is
  real rather than a broken pattern.
- **Detector (h) hardcodes one wrapper name** (`with-livespec-env.sh`), so
  `homelab`'s correct `with-homelab-env.sh -- bd show` scores as a defect. 1 of
  homelab's 23 is this false positive, making the fleet's real figure **116, not
  117**. It fails QUIETLY and in the wrong direction. **Parameterising the wrapper
  name is a precondition for ever pointing this gate at `homelab`.**
- **51 of 117 (44%) sit in `plan/archive/`**, which never regenerates — so
  "accept it and let instances decay" cannot reach nearly half the exposure.
- **`homelab` consumes no pin** (Rust/Nix — no `pyproject.toml`, no `justfile`,
  no `.mise.toml`), so adopting the gate per repo reaches only **94 of 117**. The
  measurement points at a **3-for-pin-consumers + 1-for-homelab** shape that none
  of the four originally-costed options describes.
- **Four of the eleven detectors are DOCUMENT-scoped** ((e), (h), (i), (j)): they
  return nothing once the correct property appears anywhere in a file's fenced
  blocks. So a count for those classes counts FILES LACKING A PROPERTY, not
  defective lines. Fleet-wide they contribute 5 of 117 (4%) — architecturally real,
  numerically minor, and it does NOT move this costing.
- **The detectors are calibrated to charters and do not generalise.** Pointed at
  arbitrary fleet markdown they returned 368, of which the overwhelming majority
  were false (a mermaid node label trips (h); one label became 13 findings). Do
  not widen the corpus.

## Next action

Re-measure `overseer-yho.3` from the ledger first — everything above is a claim
with a timestamp, including this sentence.

Then, if the maintainer approves it onward, **implement it through the FACTORY
DISPATCH ROUTE**: the `drive` operation, action `impl:overseer-yho.3`, or the
Dispatcher drain. **Not** the in-session Red→Green driver. The item is `backlog`
and unassigned; moving it onward is the maintainer's valve, not a supervisor's.

Before dispatching, confirm the item's text carries no literal double-brace
`just`-interpolation token: `drive.py` interpolates item text into fabro's
templated `goal`, so such a token is parsed as a fabro template variable and the
graph is rejected before any agent runs, leaving a phantom `active`/`fabro` claim
with no run behind it. Measured 2026-08-02: `overseer-yho.3` is **clean** (zero
tokens). `fabro ps` is the evidence of a run; `ACTIVE` never is.

## Second item, adopted 2026-08-02: `overseer-c45` — the watcher-gate defect

**THIS DOES NOT RE-OPEN THE PHASE-1 CUT.** The scope section above stands
untouched: phased, `livespec-orchestrator-beads-fabro` first, 56 of 117. `c45` is
a SECOND item that now shares this thread, not an addition to that slice, and it
is not a precondition for it. Work phase 1 first.

**What it is.** A supervisor pane reported `working (background shell)` for days
while its worker idled, because its watcher added a content grep on top of the
canonical stability test — and an idle Claude pane permanently shows the
lingering completed-turn summary, which that grep matches. The idle exit could
therefore never fire. Two asks: a `tests/prompts/` detector requiring a generated
charter's watcher idle-exit to rest on pane stability ALONE, and a membership
check on whether the offending charter's divergent watcher is among this thread's
117 defects.

**Why HERE and not `plan/daemon-liveness-truth/`.** The archived
`supervisor-prompt-quality` charter suggested that thread on a symptom match: a
pane whose reported state diverges from reality is the `overseer-j1r` /
`overseer-mkx` family. Measured against the item's own text, both of its asks are
charter-generator work — the detector lives in `tests/prompts/`, and the second
ask is literally a question about `overseer-yho.3`'s sweep. It names no daemon
module and states that the daemon reports TRUTHFULLY, so it carries no daemon
fix at all. `overseer-x29`'s own description draws that boundary and warns that
absorbing generator-quality work would make that epic mean "whatever the
supervisor thread surfaced". Maintainer-decided 2026-08-02; the routing rationale
is recorded on the item as a note.

**Its ledger parent is unchanged and correct.** `overseer-c45` remains a
`parent-child` of `overseer-yho`, exactly as `overseer-yho.3` is. Both of that
epic's open children now live in this thread, so `overseer-yho` closes when this
thread finishes and not before — it is open because work is open under it, not
by oversight.

**The second ask is cheap to discharge and worth doing first**, because it is a
membership question against a measurement this thread already owns: if the
divergent watcher was session-improvised rather than written into a charter file,
it is out of the 117 and the sweep does not cover it.

## Discipline

Fleet-standard: worktree → PR → rebase-merge, never a commit on the primary
checkout. Never `--no-verify`; halt and report on hook failure. Never touch
another session's worktrees or branches. Never kill the acting overseer daemon in
tmux `livespec-overseer:1.1`.

**`just worktree-create` is effectively broken in this repo at scale** —
`worktree-lib.sh:89` pipes `git worktree list --porcelain` into an `awk` that
exits on the first match, so git takes SIGPIPE and the recipe dies at 141 before
printing anything. It worsens with the worktree count: 4-of-8 at 56 worktrees, 14
attempts at 63, and **65 consecutive failures at 77 on 2026-08-02**. Filed as
`livespec-dev-tooling-zi4q`; the fix is one line in that package's source and the
gitignored `dev-tooling/` copy must never be hand-edited. **Rescue path, used
successfully:** `git worktree add <path> -b <branch>` then
`just install-worktree-pack` inside it, then `git checkout -- .livespec.jsonc` to
discard the `worktree_discipline` key it writes into that tracked file.
