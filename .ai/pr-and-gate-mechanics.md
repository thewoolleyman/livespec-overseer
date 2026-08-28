# PR, commit-hook and gate mechanics that cost rework

Moved verbatim from `AGENTS.md` (three sections: the LLOC soft band, the charter gate, and the PR mechanics).

## `check-no-lloc-soft-warnings` CANNOT FAIL when you run it by hand

Measured 2026-08-22, after it rejected two pushes in a row while every attempt to
reproduce it standalone said the tree was clean.

Run the recipe directly and it prints rows that look reassuring and exits **0**:

    {"file": "overseer/_supervisor_core.py", "lloc": 224, "soft_ceiling": 200,
     "hard_ceiling": 250, "failing": false, "event": "file in 201-250 LLOC soft band",
     "level": "warning", ...}

`"failing": false`, `"level": "warning"`, exit 0. Run `just check` and the same
tree fails on the same target. **The row is not lying about itself — it is
answering a different question than the aggregate asks.** The check only converts
warnings into failures when `LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST` is set,
and only the aggregate sets it. The variable's name is right there in every row,
which is the tell, but a row that says `failing: false` reads as a verdict rather
than as a conditional.

**Reproduce it the way the aggregate runs it, or it will keep telling you the tree
is clean:**

    LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST=1 just check-no-lloc-soft-warnings

which prints the row the aggregate actually acts on, with the remedy in it:

    "expected_marker": "# livespec-lloc-soft-band-owner: <work-item-id>",
    "failing": true, "level": "error",
    "event": "file in 201-250 LLOC soft band with no owning work-item marker"

**The remedy is a marker, not a split.** A file between the 200 soft ceiling and
the 250 hard ceiling is allowed to sit there as long as it names an owning
work-item, which is how its siblings already carry the debt — `grep -rn
'livespec-lloc-soft-band-owner' overseer/` shows the convention and where in the
file the line goes. A split is what the HARD ceiling forces; the soft band asks
only that the debt be owned. Crossing 200 is easy to do without noticing: adding
~25 lines to a 190-line module does it, and nothing warns you at edit time.

Measured 2026-08-23 in the Fabro sandbox clone for `overseer-tdfe.27`, at
unmodified `origin/master` (`9d59b1af`): `LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST=true
just check-no-lloc-soft-warnings` exited 0. Every soft-band row carried
`"failing": false`; the `.claude-plugin/overseer/*` mirror rows carried
`"phase": "0-warn"` and `"newly_covered": true`. Docker was not available inside
that sandbox, so the nested image command could not be run there, but the
sandbox-side checkout measurement matched the operator-host baseline exactly.
That rules out an unmodified-master non-hermetic failure for the incident; if a
refused push reports this check now, read the hook's emitted `failing:true` lines
and treat the named file as the actual crossing until proven otherwise.

**Why this belongs beside the charter-gate entry below.** That one says to suspect
the detector when a gate looks wrong. This is the mirror case — the detector is
correct and its STANDALONE INVOCATION is the thing that misleads, because it
cannot fail. This repo already catalogues checks that cannot fail as a hazard when
they are *written*; here one arrives through how a healthy check is *invoked*. The
general rule covers both: **before concluding a gate is flaky or wrong, confirm you
are running it with the same environment the aggregate gives it.** A green
standalone run is not evidence about a red aggregate.

## The charter gate's false positives all point ONE way — suspect the detector first

`tests/prompts/test_charters_carry_no_known_defects.py` scores every supervisor
charter in the fleet. During the 2026-08-03 fleet sweep (119 defects → 0, all six
repos) **every** false positive it produced pointed the same direction: it flagged
code that was **already correct**, and "fixing" the charter would have made it
worse. Three measured instances:

| what fired | the charter was actually | fixed by |
|---|---|---|
| `(h)` × 4 in `homelab` | resolving the wrapper from `.livespec.jsonc` — **better** than the hard-coded name the detector demanded | keying `(h)` on the wrapper PROPERTY |
| `(h)` × 1 in the orchestrator | invoking the wrapper across a `\` **line continuation** | joining continuations before matching |
| `(a)`+`(f)` in `homelab` | a **worked counter-example** in a block labelled `# DEMONSTRATION, not a check` | unfencing the block (see below) |

**So when a charter looks wrong, prove it with a THREE-WAY CONTROL before editing
it:** the suspect form, the same thing written differently, and a known-real
defect. If the first two disagree, the detector is wrong. Two of the three above
were caught exactly that way, and each would otherwise have had a session rewrite
correct code to satisfy a broken check.

**The escape for legitimate counter-examples needs NO gate change.** The detectors
read **fenced** bodies only — `_code_blocks` matches ``` and `~~~`, nothing else.
A charter that must SHOW a defective form as evidence puts it in an **indented
literal block** or in prose with inline code spans, and scores zero while changing
not one character of the demonstration. That is why this repo's own charters score
zero while discussing every one of these hazards. **Never add a self-declared
"skip this block" marker**: it would need its own discrimination leg and is exactly
the thing that later gets used to silence a real finding.

## Two PR mechanics that cost rework, both measured 2026-08-03

**Auto-merge is enabled in several fleet repos and it RACES you.** A PR merges
itself the moment checks go green — before you can push a follow-up commit or amend
a title. Observed twice in one session: one PR merged a minute after a supervisor
measured it, carrying a title that overclaimed by one defect; another merged at an
older commit, which **orphaned** the newer commit onto the branch and cost a second
PR to land it.

**Push every commit you intend to ship BEFORE opening the PR**, and never plan to
amend a title afterwards. When it happens anyway, correct the record with a comment
on the merged PR rather than leaving the claim standing.

**IT STILL HAPPENS WHEN YOU KNOW ABOUT IT — recorded 2026-08-13 as a repeat.** A
session that had just READ this warning opened a PR, kept working on the same
file, and pushed the follow-up commit four minutes after auto-merge had already
landed the first. The orphaned commit needed its own PR, exactly as described
above. Reading the warning does not help if the follow-up work is discovered
AFTER the PR is open. The operative discipline is narrower than "push first":
**once a PR is open, treat that branch as frozen** — put the next thought on a
new branch instead of reaching back.

### The GitHub rate-limit guard hook denies on the WORD "for", not on your intent

Measured 2026-08-13, after four consecutive denials of a legitimate command. The
`github_rate_limit_guard.py` PreToolUse hook denies any command matching BOTH a
GitHub call and a "loop or sleep":

    _GH_READ      = \bgh\s+(?:run|pr)\b
    _LOOP_OR_SLEEP = \b(?:for|while|until|select)\b|\bsleep\b

Those alternations match ordinary ENGLISH. A PR title containing the word "for",
or a commit message mentioning `while`, is enough — the guard cannot tell prose
in a `--title` from a shell loop. Denials it produced here included a `gh pr
create` whose only sin was the title "... extrapolations **for** the lessons
tally", and a `git commit` whose message quoted a `gh pr list` command.

The message it prints ("use the cached alternative `gh api --cache`") is sound
advice for a genuine polling loop and actively misleading for this case: there is
no loop, and no cache flag exists on `gh pr create`.

**Remedies, in order:** reword the title or message to avoid `for` / `while` /
`until` / `select` / `sleep` as standalone words; put long prose in a file and
pass `--body-file` / `-F` so it never reaches the command line; and split
`gh` calls away from any `sleep` used to wait. The guard is doing useful work
against real polling — do not disable it.

**THE `--body-file` REMEDY IS NECESSARY BUT NOT SUFFICIENT, AND THE MISSING HALF
IS WHAT ACTUALLY BITES: WRITE THE FILE IN A SEPARATE TOOL CALL.** The guard matches
the WHOLE command string it is handed, so a heredoc that writes the body and a
`gh pr create --body-file` in the SAME invocation still puts every word of that
prose on the command line — and the file indirection buys nothing. The denial then
looks inexplicable, because you did exactly what the remedy above says. Write the
body in one call, then invoke `gh` in the next, with no prose beside it.

Recorded because it caught the same session TWICE on 2026-08-19, the second time
minutes after it had hit the first and written up the guard's behaviour. Knowing
about the trap does not help; the shape of the command is what matters. Note also
that a body long enough to need a file is *precisely* the body most likely to
contain the word "for" somewhere, so these two remedies are needed together far more
often than either alone.

**AND THE THIRD DENIAL THAT SAME DAY HAD NO `gh` INVOCATION IN IT AT ALL — WRITING
*ABOUT* THIS GUARD TRIPS IT.** The denied command was a plain heredoc writing a file,
with no GitHub call anywhere. It matched because the PROSE BEING WRITTEN quoted the
command form the guard looks for, and that same prose — being ordinary English about
a defect — also contained "for" and "while". Both alternations hit inside a document
that was merely *describing* the hazard.

This is the same shape as the delimiter-token trap elsewhere in this file: **quoting
the evidence poisons the report.** A good write-up quotes the failing command
verbatim, and here the quoted command *is* the poison. So when documenting this guard
— in a PR body, a commit message, a ledger comment, or a file written by a heredoc —
**name the subcommand in words rather than reproducing the literal invocation form**,
or keep the quoted form and the English in different files. Do not rely on there
being no actual GitHub call to save you; the guard reads the command string, not your
intent.

**The red-green-replay ritual is ONE commit with `--amend`, not two commits.** Red
stages the test file **alone**; Green stages the impl and amends it. The test-file
bytes must be **byte-identical** across the pair, and exactly **one** test file may
be staged at Red — editing the test after the Red commit invalidates the pair.

**A change confined to `tests/` has no impl bucket at all**, so it never reaches
the Green leg. It takes the **green-verified** leg instead: a single commit, a
**non-`feat:`/`fix:`** prefix, and the full suite must pass. A `feat:` prefix there
is rejected with `test-passed-at-red`.

**THREE MORE, ALL MEASURED 2026-08-21 while landing `overseer-5lrp` and unblocking
PR 1397.** Each cost a full aggregate run or a CI cycle to discover, and none of
them announces its cause.

**A `.claude-plugin/` edit FORCES a `fix:`/`feat:` subject — and that does NOT put
you on the Red leg.** `check-prose-release-hygiene` refuses a `chore:` subject on
any commit touching the shipped plugin surface: a plugin edit must produce a
version bump on merge, or it does not belong under `.claude-plugin/`. The remedy it
prints is correct. What the remedy does not say, and what makes it look dangerous
to follow, is that the replay ritual routes on **HEAD state** once product impl is
staged, not on the subject — `_dispatch_impl_staged` is explicitly prefix-agnostic.
So with no Red awaiting a Green at HEAD, a `fix:` subject still takes the
green-verified leg. The Red-intent regex only reaches a **tests-only** staged tree.
Reading the ritual docs alone suggests `fix:` will demand a failing test; it will
not, when impl is staged.

**`git commit --amend -F <file>` SILENTLY DROPS THE HOOK-STAMPED `TDD-*`
TRAILERS.** The commit-msg hook writes its evidence trailers into the message.
Amending with a fresh message file replaces the whole message — trailers included —
and the amend re-runs the hook with an **empty staged set**, which is the
no-content-trigger branch: it returns 0 without re-stamping. The commit is then
carrying no evidence and `check-red-green-replay`'s range validation is what finally
refuses it, at push, several minutes later. **The tell is a sub-second replay
hook**: a real leg runs the suite and takes minutes. The fix is
`git reset --soft HEAD~1` and commit again so the hook re-runs with content staged.
(This is about re-wording, not about the ritual's own Green amend, which stages impl
and therefore has content.)

**A PR WHOSE BASE MOVED DOES NOT RE-TEST ITSELF, AND CLOSE-REOPEN RACES THE
MERGE.** `ci.yml` triggers on bare `pull_request:`, whose default types do not
include base-branch updates, so after you land the fix a PR was waiting on, that
PR's rollup keeps reporting the **stale** verdict indefinitely. `gh run rerun` does
not help: it replays the same event payload and therefore the same old merge SHA.
Close-and-reopen fires `reopened` and does produce a fresh run — but measured here,
a reopen fired **seventy seconds after** the unblocking PR merged still tested a
merge computed without it and failed identically, because GitHub's `refs/pull/N/merge`
lags. Two further consequences: close-and-reopen **clears auto-merge**, which must be
re-armed by hand; and the second re-trigger is indistinguishable from the first
unless you have independent evidence.

**THE CHEAP INSTRUMENT BEHIND ALL THREE IS A DETACHED REBASE PROBE**, and it is
worth reaching for before any of the reasoning above:

    git worktree add --detach <scratch> origin/<pr-branch>
    cd <scratch> && git rebase origin/master && just <the-one-failing-gate>

Under a minute, no push, no commit, nothing published. It answers — with a
measurement rather than an argument — whether the rebase conflicts at all, what the
merged tree actually contains, whether a proposed fix works **before** you author
it, and whether a re-triggered CI run was even testing the right tree. This repo
allows rebase-merge only, so that probe tree is precisely what CI evaluates. Used
four times in one session here; each use replaced a guess that would otherwise have
been committed.
