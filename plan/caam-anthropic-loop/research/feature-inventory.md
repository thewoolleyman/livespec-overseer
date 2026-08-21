# Feature inventory — every behavior `/caam-anthropic-loop` has today

**Ledger anchor:** epic `overseer-54k2za`. All mutable plan state — status, next
action, handoff entries — lives on that epic and its child items. This note is
write-once research and is never authoritative about what remains.

**MEASURED AS OF vps-info `cc9c83e`** (re-pinned 2026-08-21). The source is a LIVE
repo and it moved FIVE times while this thread was being opened — see
"The source is a moving target" below. **Re-measure against that repo's HEAD
before treating this list as complete, and update this pin when you do.** A
carrier list with no as-of commit is a claim with no timestamp.

**RE-MEASURE ATTEMPT, 2026-08-21, overseer-54k2za.13.** The factory sandbox
could not read the source repo: no `vps-info` checkout existed under the mounted
repo/workspace/project roots, unauthenticated `git ls-remote` could not prompt
for credentials, and the sibling lookup through this sandbox's configured GitHub
credential reported the repository unavailable. The pin above therefore remains
the last verified source commit rather than a refreshed claim.

## Why this thread exists

`/caam-anthropic-loop` is a working, maintainer-authored skill living in the
**vps-info** repo at `.claude/skills/caam-anthropic-loop/SKILL.md` (1170 lines),
documented in that repo's `AGENTS.md` §"Claude Max account switching: caam +
`/caam-anthropic-loop`" (lines ~750–1035). It watches Claude Max quota across
several caam-managed accounts, rotates the host-wide credential when the active
account's window fills, and pins per-session models on `-foreman` tmux sessions.

It works. It was also built as a deliberate best-effort pass, with the Python
program **embedded inside the markdown skill file** and no tests of any kind. Its
own author closed the AGENTS.md section with the instruction this thread executes:

> This skill is coupled to `livespec-overseer` fleet conventions (the `-foreman`
> naming). It should move to that repo and be rebuilt spec-first with red-green
> tests; this pass is deliberately a working best-effort implementation, not the
> final home.

So this thread rebuilds it **here**, as a first-class `livespec-overseer` plugin
skill alongside `foreman`, `grooming`, `overseer` and `supervise-plan` — spec
first, red-green-replay per commit, and **feature-identical** to what the
maintainer already owns and runs.

The mandate is reproduction, not redesign. Every behavior below is a requirement
carrier. The exit gate is an independent completeness review that walks this
inventory item by item against the rebuilt implementation.

## Provenance, and which source wins

Three sources describe the skill, and **they do not agree**. Resolve conflicts in
this order:

| rank | source | why |
|---|---|---|
| 1 | the embedded Python program in `SKILL.md` | it is what actually runs |
| 2 | `vps-info/AGENTS.md` §caam | maintained; matches the program |
| 3 | the prose sections of `SKILL.md` | partly stale residue — see below |

### The stale-prose trap — do NOT re-implement what §"How it decides" says about Fable

`SKILL.md` §"How it decides" ¶3 describes a **two-tier Fable candidate
selection**: tier 1 = candidates that still hold Fable quota, ranked by
soonest-expiring *Fable*; tier 2 only when no candidate has Fable left; and an
account with **zero Fable** "blocked no matter how much of its 5-hour window is
free". The same section calls Fable "a separate, scoped allowance" that is
"disqualifying at zero".

**None of that is in the program, and it is not the current design.**

- `is_eligible()` does not read `fable` at all. Its disqualifiers are
  `seven_day >= 100` and `five_hour >= 100` only.
- The candidate sort key is `resets_at(seven_day_resets_at)` alone. There is no
  Fable tier and no Fable horizon in the ranking.
- `binding()` documents in terms that "Fable deliberately triggers nothing."

The commit history shows the supersession directly: `4deb285 feat(caam-loop):
Fable carries 5-hour priority, two-tier candidate selection` was replaced by
`2ef0876 feat(caam-loop): weekly outranks Fable; enforce models on -foreman
sessions`. `AGENTS.md` records the surviving rule correctly — "account selection
ignores Fable entirely: no tiering, no exclusion, and Fable never triggers a
rotation. Fable decides only which *model* a session runs" — with the reasoning:
Fable is **not a separate pool**, it caps how much of the weekly allowance one
model may spend and draws down `weekly_all` too, so leaving Fable unused forfeits
no capacity (it is still spendable via Opus) while leaving weekly unspent
forfeits it for good.

The rewrite of §"How it decides" was simply never landed with `2ef0876`. A
rebuild that faithfully implements the documented text would resurrect a design
the maintainer already rejected, and would strand perishable weekly balance.

**Requirement: the rebuilt skill implements the program's rule (F7, G4, H1) and
its own prose says so. The two-tier text is not carried forward.**

A second, harmless residue in the same file: §"Output shape" repeats the sentence
"The CURRENT column marks the account in use with ✅…" three times, each slightly
truncated. An editing artifact, not three features.

---

# The inventory

Each item is a requirement carrier with a stable id. Ids are referenced by the
child work-items and by the exit-gate review.

## A — Schedule self-installation

The skill installs and owns its own recurring schedule. This is LLM-driven
(harness tool calls), not part of the Python program.

- **A1** Every invocation calls `CronList` **first**, before anything else.
- **A2** If a recurring job already exists whose prompt starts
  `/caam-anthropic-loop`, do **not** create another — note its job id and
  continue. This is the normal case when the scheduled firing re-invokes the
  skill, and skipping it is what stops the job breeding a duplicate every 30
  minutes.
- **A3** **Exception:** if that existing job's prompt lacks the `--scheduled`
  marker (an older job, or one created by `/loop`), `CronDelete` it and create a
  replacement carrying the marker. Without the marker every scheduled firing
  looks like a manual run and would force a switch every 30 minutes.
- **A4** Otherwise `CronCreate` with `cron: "7,37 * * * *"`, `prompt:
  "/caam-anthropic-loop --scheduled"`, `recurring: true`.
- **A5** After creating, tell the user the job id, that it fires every 30
  minutes, and the two limits that otherwise bite silently: the job lives only
  while this Claude session is open (closing the session or its tmux pane stops
  reporting with **no error**), and recurring jobs **auto-expire after 7 days**.
  Cancel early with `CronDelete <id>`.
- **A6** Never wrap this skill in `/loop` — it schedules itself, and doing both
  produces two overlapping jobs.
- **A7** `7,37` is deliberate: off the `:00`/`:30` marks the whole fleet lands on.
- **A8** Marking the **scheduled** side rather than the manual side is
  deliberate. A missing marker then degrades to *forcing*, which is visible,
  rather than to *never forcing*, which is silent.

## B — Invocation mode and reporting

- **B1** Invoked **with** `--scheduled` ⇒ the recurring job firing. Run the
  program with no extra flags; the trigger applies.
- **B2** Invoked **without** `--scheduled` ⇒ a human typed it. Run the program
  with `--force`, which skips the trigger and takes the best available target
  immediately.
- **B3** A forced run still refuses to move to an account with *less* headroom
  than the current one, and still skips any account with zero weekly quota. A
  switch that loses ground is not what "force" should mean.
- **B4** Show the user the table **verbatim** — it is the point of the turn, not
  a detail to summarize away — then add the decision line. Quote its percentages
  rather than paraphrasing them.
- **B5** If the program prints `FAIL`, say so plainly and **stop**. Do not retry
  with a lowered threshold and do not attempt a manual switch.
- **B6** Flags: `--force` (bypass the 5-hour trigger), `--dry-run` (decide and
  log without switching), `--no-models` (skip model enforcement).
- **B7** To stop watching entirely: `CronDelete` the job id from A.

## C — Usage polling

- **C1** Source is `https://api.anthropic.com/api/oauth/usage` — undocumented,
  used by the CLI itself.
- **C2** Bearer auth with the OAuth access token and **no `anthropic-beta`
  header**. Sending `oauth-2025-04-20` returns `401 OAuth access token is
  invalid`, which reads like a bad token but is a bad header.
- **C3** The `*_dollars` fields (`limit_dollars`, `used_dollars`,
  `remaining_dollars`) are **`null` on Max plans**, so every quota figure is
  derived from `utilization` percentages, never dollars.
- **C4** The active profile is polled with the **live** credential at
  `~/.claude/.credentials.json`; every other profile with its stored snapshot at
  `<vault>/<profile>/.credentials.json`.
- **C5** `read_creds(path)` returns `(access_token, expires_at_epoch_seconds)`
  from the `claudeAiOauth` object, converting `expiresAt` from ms to s. Either
  may be `None`. `OSError`/`KeyError`/`ValueError` ⇒ `(None, None)`.
- **C6** `live_token(path)` refuses a token that is missing (`"no token in
  snapshot"`) or already expired (`"token expired %.1fh ago"`), using a **60
  second skew margin** (`exp <= time.time() + 60`).
- **C7** `fetch_usage()` **never raises**. `HTTPError` ⇒ the response body's
  `error.message`, else `"HTTP <code>"`. Any other exception ⇒
  `"<TypeName>: <exc>"`. Request timeout is 30s.
- **C8** Fable extraction: iterate `body["limits"]`, match `kind ==
  "weekly_scoped"` **and** `scope.model.display_name == "Fable"`, take `percent`
  and `resets_at`, then break. **Absence is not an error** — an account with no
  such scoped limit reports `-`.
- **C9** The usage record is exactly: `five_hour`, `seven_day` (utilization
  floats), `five_hour_resets_at`, `seven_day_resets_at`, `fable`,
  `fable_resets_at`. A shape that does not yield those ⇒ `"unexpected response
  shape"`.
- **C10** **The program never performs an OAuth refresh.** Polling is read-only
  GETs only. Rotating a refresh token behind Claude Code's back can revoke the
  whole token family and force a browser re-login — which is why `caam refresh`
  itself refuses for claude (`token refresh disabled; Claude Code handles refresh
  internally`).
- **C11** Skipping a known-expired token (C6) is not an optimization, it is
  correctness. Measured 2026-08-19 with three probes from the same IP at the same
  instant: **expired token ⇒ 429** `rate_limit_error`, **garbage token ⇒ 401**
  `authentication_error`, **live token ⇒ 200**. The live 200 rules out an
  endpoint- or IP-level limit; the garbage 401 rules out "429 is just what a bad
  token gets". The endpoint backs off a *specific* repeatedly-rejected token, so
  **a loop that retries a dead token manufactures the error it reports**. Loop
  interval has no bearing on this.
- **C12** Cost of C10, accepted: an access token lasts ~8h from its last
  activation, so an account left idle longer goes **dark** and shows `-`.
  Accounts in regular rotation refresh themselves and stay pollable.

## D — Profile enumeration and the reading cache

- **D1** Vault is `~/.local/share/caam/vault/claude/<profile>/`.
- **D2** Entries whose name starts `_` are **excluded**. caam writes its own
  auto-backups there (e.g. `_original` from `auto_backup_before_switch`); they
  are snapshots of another profile, not accounts, and must never be rotated onto
  or shown as candidates.
- **D3** Names are enumerated in sorted order.
- **D4** If the active profile is not among them it is appended, so the active
  account always appears.
- **D5** A successful poll updates the cache `state["profiles"][name] = {"at":
  now, **usage}` and the row's source is `"live"`.
- **D6** A failed poll falls back to the cached reading when its age is
  `<= CAAM_ROTATE_CACHE_MAX_AGE_S`; the source becomes `"cached %.1fh"`.
- **D6a** **THE DEFAULT CHANGED FROM 24h TO 1h in vps-info `3c0ad85`.** The
  reasoning is the carrier, not the number: this cache is **display-only** —
  eligibility requires `source == "live"` (**G8**), so a cached reading can never
  be a switch target and feeds nothing but the table. A day-old reading of a
  five-hour window is worse than no reading. One hour is two ticks, enough to
  cover the gap between a token lapsing and keep-warm refreshing it; beyond that
  the row reads as dark, **which is the truth**.
- **D7** With no usable cache the row is `usage=None`, source `"dark: <why>"`.
- **D8** State file `~/.local/state/caam-usage-rotate/state.json`; directory mode
  **0700**, file mode **0600**, written atomically (temp + `os.replace`) with
  `indent=1, sort_keys=True`. Concurrent writers are last-writer-wins, which
  costs a cached reading, never a corrupt file.

## E — Identifying the active profile

- **E1** `caam status --json` is consulted first: scan `tools[]` for the entry
  whose `tool == "claude"` with a non-empty `active_profile`.
- **E2** **It must never be depended on.** caam identifies the active profile by
  byte-matching the live credential against each snapshot, and Claude Code
  refreshes that token roughly every 8 hours as normal operation — after which it
  matches nothing and caam omits `active_profile` entirely. Treating that as
  fatal **stalled the loop for 3.5 hours on 2026-08-19**, failing identically
  every tick with "could not determine active claude profile".
- **E3** Fallback is identity, not bytes: `oauthAccount.accountUuid` from
  `~/.claude.json`, matched against each snapshot's own `.claude.json` UUID. The
  UUID survives token rotation, which is the whole point of using it.
- **E4** The fallback scan applies D2 (skip `_`-prefixed) and sorted order.
- **E5** If neither path resolves ⇒ `FAIL could not determine active claude
  profile`, exit 2.

## F — Triggers and the binding allowance

- **F1** `THRESHOLD` = `CAAM_ROTATE_FIVE_HOUR_THRESHOLD`, default **85**
  (percent *used*). **85, not 95:** the loop polls every 30 minutes and heavy
  fleet use can cross the last 5% between two polls, blocking before the trigger
  is ever seen.
- **F2** `WEEKLY_RESERVE` = `CAAM_ROTATE_WEEKLY_RESERVE`, default **10** (percent
  *remaining*). An account is stopped at 10% rather than run flat.
- **F3** `MIN_GAIN` = `CAAM_ROTATE_MIN_HEADROOM_GAIN`, default **10** points.
- **F4** `weekly_left(u)` is `100 - u["seven_day"]`.
- **F5** `binding(usage)` returns `(dimension, spent, label)`:
  `five_hour >= THRESHOLD` ⇒ `("five_hour", five_hour, "5-hour window")`;
  else `weekly_left < WEEKLY_RESERVE` ⇒ `("seven_day", seven_day, "weekly
  reserve")`; else the 5-hour default.
- **F6** `triggered` is `five_hour >= THRESHOLD or weekly_left < WEEKLY_RESERVE`.
- **F7** Candidates are compared **on whichever dimension triggered**. Comparing
  on a dimension that is not the reason you are leaving is how you land somewhere
  no better off.
- **F8** **Fable triggers nothing.** See the stale-prose trap above for why.

## G — Candidate eligibility

- **G1** `is_eligible(u, current, gain_needed, dimension)` requires: `u` is not
  `None`; both sides have the dimension; `(theirs - mine) >= gain_needed`;
  `u["seven_day"] < 100` (nothing left to spend this week); `u["five_hour"] <
  100` (cannot serve a request right now).
- **G2** The headroom test is **relative on purpose**. An absolute "candidate
  must be below the threshold" test strands you: with three accounts at 51–55%
  used and a 50% bar, nothing qualifies, so the loop holds while the active
  account climbs to 100% and blocks — refusing to touch two accounts that each
  still hold half a window.
- **G3** The margin also **makes flapping impossible**: a switch requires a
  strict improvement, which the reverse move cannot match.
- **G4** `is_eligible` does **not** consult Fable. A Fable-exhausted account
  still spends its weekly allowance perfectly well via Opus, so excluding it
  would strand the one quota that is genuinely forfeitable.
- **G5** `gain_needed` is `0.01` under `--force`, else `MIN_GAIN`. Force relaxes
  to "any strict improvement" — it never drops to zero (B3).
- **G6** The candidate filter additionally requires `name != active`,
  `source == "live"`, and `weekly_left(u) >= WEEKLY_RESERVE`.
- **G7** **Reserve release.** If that yields nothing, the filter is re-run
  *without* the reserve clause. Once every account is under the reserve it
  protects nothing, so withholding them would strand everyone. When the retry
  finds candidates, log `note: every account is under the N% weekly reserve --
  releasing it`.
- **G8** **`source == "live"` is a hard safety rule, not a preference.** A
  `cached` or `dark` row means that snapshot's own access token could not be used
  just now — and that is precisely the credential `caam activate` installs as the
  host-wide login. On 2026-08-19 a switch onto a `cached 0.2h` profile wrote an
  expired credential live and stopped **11 running sessions** with `Login expired
  · Please run /login`. Post-switch verification cannot catch this: the switch
  *did* stick, onto a dead token.
- **G9** The consequence of G8: rotation **stalls** when every other profile has
  gone dark (~8h without activation). The loop holds and prints the revival
  recipe. A stalled rotation costs quota; a bad switch costs the fleet.
- **G9a** **THIS WAS RECORDED AS A DELIBERATE, ACCEPTED CONSEQUENCE. IT WAS A
  DEADLOCK, AND vps-info `0070050` FIXED IT.** Observed: the loop held every tick
  while the active account ran its five-hour window to zero, and the switch had to
  be made by hand. The set of valid targets drains to empty precisely when
  rotation is needed. The maintainer's own summary is the thing to carry: *"It
  behaved exactly as written, which is the problem"*, and *"The loop even warned
  about it each tick; warning is not a fix."*
  **G8 IS NOT WEAKENED — it still holds absolutely.** What changed is that the
  live set is now actively MAINTAINED so it cannot drain (carrier group **X**).
  The dark snapshots' refresh tokens were valid for another 28 days; they were
  dark only because nothing refreshed them.
  **The rebuild MUST implement G8 and X together. Implementing G8 alone
  reproduces the deadlock** — faithfully, and uselessly.

## H — Ranking

- **H1** Eligible candidates sort ascending by
  `resets_at(seven_day_resets_at)` — **soonest weekly reset first** — and the
  first is the target.
- **H2** Rationale: spend the most perishable balance before it expires. Weekly
  allowances reset on independent clocks, so a balance rolling over in 38h is
  perishable while one with 141h of runway can be spent later. Ranking by *most
  weekly remaining* hoards the perishable balance and forfeits it at the reset —
  quota left on the table every week.
- **H3** Measured 2026-08-19: Fable and weekly reset at the **same instant** on
  every account, so this one key orders both and there is no separate Fable
  horizon to weigh.
- **H4** `resets_at()` returns `+inf` for a missing or unparseable timestamp, so
  an unreadable reset time sorts **last** and is never mistaken for one about to
  reset.
- **H5** Weekly figures only **rank** candidates; they never disqualify one for
  being low. Any account with headroom is a working account, and holding out for
  a fuller one would leave you blocked for no gain. The only weekly disqualifier
  is **zero** (G1).

## I — Performing the switch

- **I1** A non-blocking exclusive `flock` on
  `~/.local/state/caam-usage-rotate/switch.lock` guards the switch. The loser
  logs `hold: another caam-anthropic-loop holds the switch lock` and returns 0.
- **I2** The lock guards the **decision**, not the write. caam writes the live
  credential via temp-file + fsync + atomic rename at 0600, so it cannot be torn
  even without the lock. Without the lock, two loops polling at the same moment
  both see the active account over threshold and both call `caam activate`,
  producing back-to-back switches off a stale view — and each switch
  re-snapshots the outgoing profile, the exact window that can orphan a snapshot
  and cost a browser re-login.
- **I3** **Under the lock**, re-read the active profile. If it changed, log
  `hold: active changed X -> Y while deciding; re-evaluating next tick` and
  return 0 — the decision was made before the lock was held.
- **I4** **Under the lock**, re-probe the target's stored credential with
  `fetch_usage`. If it does not work now ⇒ `FAIL refusing to switch to <target>
  -- its stored credential does not work right now (<why>). Installing it would
  break every running session.`, exit 2. Cheap, and the alternative is a
  host-wide outage.
- **I5** Switch with `caam activate claude <target>` (timeout 60) — **never
  `/login`**. caam re-snapshots the outgoing profile on the way out; `/login`
  skips that and orphans the snapshot.
- **I6** The lock is released in a `finally`, after `activate` returns and before
  the stick-verification.
- **I7** Non-zero return ⇒ `FAIL caam activate <target>: <stderr or stdout,
  stripped>`, exit 2.
- **I8** **Stick verification.** Compare the target snapshot's token against the
  live credential's token; if both are present and differ ⇒ `FAIL switch to
  <target> did not stick -- the live credential no longer matches the snapshot. A
  running Claude session most likely refreshed its own token over the swap.
  Re-run to retry.`, exit 2. ~20 sessions share this one credential file and each
  rewrites it when its own token refreshes, so a refresh landing just after the
  swap silently reinstates the old account. Nothing here can *prevent* that —
  Claude Code does not take our lock — but a switch that did not take **must not
  be reported as a success**.
- **I9** On success record `state["last_switch"] = {"at", "from", "to"}`, save
  state, **re-render the table with the new active profile** so `CURRENT` is not
  stale, and log the `SWITCHED …` line.
- **I10** Model enforcement then runs against the **new** account's usage — Fable
  availability just changed.

## J — Dry run

- **J1** `--dry-run` decides and logs without switching: save state, print the
  table, log `DRY-RUN would switch X -> Y (N% week left, resets in D -- soonest,
  <source>)`, return 0. It returns before the lock is taken.
- **J2** Within model enforcement, dry-run records `"<session> would
  <model>-><want>"` and emits no keystrokes.

## K — Effort re-assertion

- **K1** `caam activate` restores `~/.claude/settings.json` from the profile
  snapshot, and that file carries `effortLevel` — so **every rotation overwrites
  the effort setting** with whatever that snapshot captured. The snapshots held a
  mix of `low` and `high`, so rotating flipped it at random and new sessions kept
  coming up on `low`.
- **K2** `WANT_EFFORT` = `CAAM_ROTATE_EFFORT`, default `"high"`; `""` disables.
- **K3** `EFFORT_ORDER` is ascending: `("low", "medium", "high", "xhigh",
  "max")`.
- **K4** **It is a FLOOR, not an exact value.** If the current value is in the
  order and its index is `>=` that of `WANT_EFFORT`, leave it alone. It raises
  `low`/`medium` back up and leaves `xhigh`/`max` untouched. The first version
  **clamped**, and was caught pulling a deliberate `xhigh` down to `high` on
  every tick.
- **K5** It rewrites **only that one key**, preserving everything else in the
  file — which also holds hooks, env, plugin and MCP config that must survive
  untouched.
- **K6** The write is atomic: temp file, `json.dump(indent=2)`, `chmod 0600`,
  `os.replace`.
- **K7** Failure is silent-safe: an unreadable or unparseable settings file
  returns without acting; an `OSError` on write returns without acting.
- **K8** A change logs `effort: settings.json effortLevel <was> -> <want> (raised
  to the floor; a switch had reset it)`.
- **K9** Effort enforcement runs **before** the `--no-models` early return, so
  `--no-models` still re-asserts effort.
- **K10** This is a *settings* write, not a keystroke — the picker's effort
  control is never touched (see P16).
- **K11** The `model` key in `settings.json` drifts exactly the same way (the
  snapshots disagree: `claude-fable-5[1m]`, `opus[1m]`, `opus`), so a rotation
  also changes the default model for new sessions. **Deliberately left alone**,
  because per-session enforcement covers what matters.

## L — Model enforcement: the rules

Applied every tick, and again after any switch, against the **active account's**
Fable balance.

| # | rule |
|---|---|
| **L1** (1a) | tmux sessions whose name ends `-foreman` run **Fable** |
| **L2** (1b) | …unless the active account's Fable is spent — then **Opus** |
| **L3** (2a) | every other Claude session is left alone |
| **L4** (2b) | …unless the active account's Fable is spent — then reset to **Opus** too |

- **L5** `fable_left` is `fable is not None and fable < 100`. Note the
  consequence: an account with **no Fable limit at all** (`fable is None`) counts
  as *not* having Fable left, so foreman sessions are pointed at Opus.
- **L6** `want_foreman` is `"fable"` if `fable_left` else `"opus"`.
- **L7** Suffix matching is **exact** (`str.endswith`): `livespec-foreman`
  matches, `foreman-improvements` does not.
- **L8** Enforcement also runs on both **hold** paths (nothing triggered, and no
  eligible candidate), not only after a switch.
- **L9** A session already on the wanted model, or covered by the memo (N), is
  skipped.

## M — Model enforcement: identifying the session and its model

- **M1** Sessions come from `tmux list-sessions -F '#{session_name}'`.
- **M2** A pane is a Claude pane **iff** `CLAUDE_CODE_SESSION_ID` appears in its
  process tree's environment. Anything else is skipped — never type into a shell.
- **M3** `descendant_pids(root, depth=4)` walks breadth-first via `pgrep -P`,
  depth-limited, including the root.
- **M4** The pane pid comes from `tmux display-message -p -t <session>
  '#{pane_pid}'` and must be all digits.
- **M5** Each candidate pid's `/proc/<pid>/environ` is read as bytes, decoded
  lossily, split on NUL, and scanned for the `CLAUDE_CODE_SESSION_ID=` prefix.
- **M6** **The model is never read from the tmux status line.** A narrow pane
  truncates that line, so status-line detection silently reported "not a Claude
  pane" and **skipped those sessions from enforcement forever**.
- **M7** `pane_model` locates the transcript by **session id**:
  `~/.claude/projects/*/<sid>.jsonl`, reads only the **last 65536 bytes** (these
  files reach hundreds of KB), scans lines for `message.model`, keeps the **last**
  one found, and maps it through `MODEL_PREFIXES` — `claude-fable`→`fable`,
  `claude-opus`→`opus`, `claude-sonnet`→`sonnet`, `claude-haiku`→`haiku`. An
  unrecognized prefix yields `None`.
- **M8** **Rejected alternative:** "newest transcript in the project directory".
  Several sessions share a cwd, so it resolves to whichever session wrote last and
  enforcement then reads *another session's* model.
- **M9** A **resumed** session writes to a differently-named transcript, so the
  model is often unreadable. **Unknown is treated as "may need setting", not
  skipped** — that is what stopped narrow panes being skipped forever — bounded by
  the memo (N).
- **M10** The transcript records the model of the last assistant **message**, so a
  model just changed on an idle session is not visible until it next does work.
  The memo covers that gap.

## N — Model enforcement: the memo

- **N1** `SET_SUPPRESS_S` = `CAAM_ROTATE_SET_SUPPRESS_S`, default **3600** (one
  hour).
- **N2** `recently_set(state, session, want)` is true when
  `state["models"][session]` records the same `want` within the window.
- **N3** Without it, a session idle after a switch never writes a new assistant
  message, its transcript keeps reporting the **old** model, and every tick fires
  the picker at it again.
- **N3a** **THE MEMO DID NOT ACTUALLY WORK UNTIL vps-info `4b1a391`, AND THE
  REBUILD MUST IMPLEMENT THE FIXED BEHAVIOR.** Every caller saved state
  *before* invoking enforcement (`save_state` at line 1052, `enforce_models` at
  1066, and the same ordering on the other two call sites), so everything
  enforcement wrote into `state` — this memo, and later the foreman pin — was
  discarded in memory and never reached disk. N1–N4 therefore described an
  *intent* that the code silently defeated: the picker was re-driven at unknown
  panes every tick regardless of the memo. See **W1** for the fix. This is the
  one place in this inventory where the pre-fix program and its own stated
  design disagree, and the design is the thing to reproduce.
  Corroborated empirically by the maintainer: the first run after the fix
  recorded **14 memos**, where the pre-fix implementation had persisted none.
- **N4** A successful `set_model` records `state["models"][session] = {"want":
  want, "at": now}`.

## O — Model enforcement: the idle guard

- **O1** `pane_is_idle` captures the pane, drops blank lines, scans the **last 6**
  in reverse, and lets the first line starting with `❯` decide: idle **iff** that
  line is exactly `❯`.
- **O2** It is **the only guard**. Without it a keystroke lands inside whatever
  half-typed prompt or picker the pane is showing.
- **O3** It is not retry or recovery logic. A busy pane is simply skipped and
  recorded as `<session> busy(<model>-><want>)` until the next tick.

## P — Model enforcement: driving the picker

- **P1** `send-keys -l "/model"` → sleep **0.4** → `send-keys Enter` → sleep
  **1.5**.
- **P2** Capture the pane and parse rows under the `Select model` header.
- **P3** `picker_rows(screen, header)` finds the **last** occurrence of the header
  (`rfind`) and applies `^[^0-9\n]*?(\d+)\.\s+(\S.*)$` multiline to the text
  **after** it.
- **P4** **Menu parsing is scoped to the menu.** Scanning the whole pane matches
  ordinary numbered lines in the transcript above the prompt — not hypothetical: a
  pane whose conversation contained a numbered list had those lines parsed as menu
  rows, the cursor offset computed from them, and the session **repeatedly
  switched to Haiku**.
- **P5** The currently highlighted row is read back with `❯\s*(\d+)\.` over the
  same post-header slice.
- **P6** `row_for_model(rows, want)` matches on a **word boundary**, case
  insensitively, in **two passes**: first against each row's **label** (the row
  text split on runs of 2+ spaces, first field), then anywhere in the row.
- **P7** **Rows are matched by model NAME, never by position** — menu order is
  Anthropic's to change, and a reordering would otherwise silently select the
  wrong model with no signal but the wrong model appearing next tick.
- **P8** The two-pass order matters: several rows describe the same underlying
  model — "Default (recommended)" is described as "Opus 5 with 1M context" just as
  "Opus (1M context)" is — and the **explicitly-labelled** row is the one a caller
  asking for `opus` means.
- **P9** If the picker did not open, the highlight is unreadable, or the wanted
  model is absent ⇒ send **Escape** and return, rather than firing stray keys into
  whatever is on screen or guessing at a row.
- **P10** Cursor movement is `(target - here) % len(rows)` **Down** presses.
- **P11** **The picker wraps**, so there is no walking to a known start position.
  Walking "up six times to reach the top" of a five-row list lands on row 2, not
  row 1 — it silently re-selected the model already in use. Both the target row
  and the highlighted row are read back from the open menu and the cursor moved by
  the difference, modulo the list length.
- **P12** Sleep **0.3** → `send-keys -l "s"` (session only).
- **P13** Sleep **1.2**, re-capture. If `Switch model?` is absent, done.
- **P14** **Pressing `s` is not the end of the flow.** A conversation already
  cached for the current model raises a second `Switch model?` dialog, and the
  pane accepts **no input** until it is answered. Fresh scratch sessions never
  show it, so testing on disposable panes **structurally cannot** catch it — 15
  live panes blocked at once when this was missed.
- **P15** The second dialog is answered **by name**, same as the picker: parse its
  rows, read its highlight, find the row matching `^Yes\b` (case-insensitive), move
  by the modular difference, sleep **0.2**, `Enter`. If rows, highlight or the Yes
  row are missing, return without acting.
- **P16** **INVARIANT: never emit `Left`/`Right`** (or Home/End/PageUp/PageDown).
  The picker carries an **effort** selector adjusted with `←/→` **on the same
  dialog** as the model rows. Up/Down move between model rows and are safe; a
  stray horizontal arrow would silently change the effort level and nothing in the
  program would notice. The full emitted key set is: the `/model` text, `Down`,
  `s`, `Enter`, `Escape`.
- **P17** **`/model <name>` is not a shortcut.** It works in one shot but reports
  *"saved as your default for new sessions"* — it sets the global default, not the
  session, which is why the picker plus `s` is used instead.
- **P18** Best effort by design: **no verification, no retry bookkeeping, no
  recovery**. If the pane is busy, the picker does not open, or the keystrokes land
  badly, the attempt is lost and the next tick tries again.
- **P19** tmux is invoked as the absolute `/usr/bin/tmux`, never bare `tmux`.
- **P20** `tmux_out` returns stdout on return code 0, else `""`, swallowing
  exceptions, with a 15s timeout.

## Q — Isolation of model enforcement

- **Q1** Each session's work is wrapped **per session**: a failure records
  `<session> SKIPPED(<ExcType>)` and the sweep continues. One unreadable or
  misbehaving session must not stop the sweep.
- **Q2** The whole pass is wrapped again: a failure logs `models: enforcement
  failed (<Type>: <exc>) -- table and rotation unaffected`.
- **Q3** Neither can take down the usage table or the account rotation. Enforcement
  is advisory.
- **Q4** `--no-models` skips the sweep (but not effort — K9).
- **Q5** The pass ends with `models: foremen want <want> (active account Fable
  left|EXHAUSTED)` followed by `; <comma-joined actions>` or `; nothing to
  change`.

## R — The table

- **R1** Columns, in order: `PROFILE`, `CURRENT`, `5H`, `5H RESET`, `WEEK`,
  `WEEK RESET`, `FABLE`, `FABLE RESET`, `SOURCE`.
- **R2** Header format `"%-13s %-*s %7s %13s %9s %13s %10s %13s   %s"` with
  `CURRENT_COL = 8`; data rows `"%-13s %s %6.0f%% %13s %8.0f%% %13s %9s %13s   %s"`.
- **R3** Quota columns are **remaining** (`100 - utilization`), not used.
- **R4** Reset columns are **time until** the window rolls over — relative, not an
  absolute UTC instant. "How long have I got" is the question being asked, and a
  wall-clock instant makes the reader do the subtraction.
- **R5** `CURRENT` marks the active account with ✅.
- **R6** `current_cell` pads by **display width**: the check mark is one Python
  character but occupies **two terminal cells**, so `%-8s` would leave the column
  one cell short on the active row and misalign every column to its right. The
  padding is `mark + " " * (8 - (2 if active else 0))`.
- **R7** A row with no usage renders `-` in every quota and reset column, with its
  source text intact.
- **R8** A missing Fable limit renders `-`; otherwise `100 - fable` as `%.0f%%`.
- **R9** A blank line precedes and follows the table.
- **R10** `fmt_duration` drops units **from the left** when zero: `%dd %dh %dm`
  when there are days, `%dh %dm` when there are hours, else `%dm`. Negative
  clamps to 0.
- **R11** `until(iso)` renders `-` for a missing or unparseable timestamp.
- **R12** The first line is `<stamp>  triggers: 5h-remaining < N% or
  weekly-remaining < N% (candidate must gain >=N pts)` where the stamp is
  `%Y-%m-%dT%H:%M:%SZ` in UTC.
- **R13** After a successful switch the table is **re-rendered** against the new
  active profile so `CURRENT` is not stale.

## S — Decision lines and exit codes

- **S1** Not triggered, not forced ⇒ `hold: <label> is the binding allowance and
  still has N% left (weekly N%, reserve N%)`, exit **0**.
- **S2** Forced but not triggered ⇒ `forced: ignoring the N% trigger, rotating to
  the best target now`.
- **S3** Triggered ⇒ `trigger: <label> -- N% spent, weekly N% left -- comparing
  candidates on <dimension>`.
- **S4** No eligible candidate ⇒ `hold: no candidate has >=N.NN points more
  <dimension> headroom than <active> (all similarly spent, exhausted, or
  unverifiable)`, exit **0**. If any non-live rows exist, additionally: `note:
  <names> could not be verified live and were not considered. Revive with: caam
  activate claude <name>; claude -p ok; caam backup claude <name>` — a deliberate
  stall, not a failure.
- **S5** Successful switch ⇒ `SWITCHED X -> Y (5h left was N%; target has N% week
  left resetting in D -- soonest, <source>)`, exit **0**.
- **S6** **Fail-loud contract.** Every failure path prints a line starting `FAIL`
  and exits **2**.
- **S7** A single top-level catch turns any unexpected exception into `FAIL
  <Type>: <exc>` and exit 2 — so a missing `caam` binary or an unwritable state
  dir can never look like a quiet success, and never surfaces as a bare traceback
  that could be mistaken for one.
- **S8** The `FAIL` cases are exactly: no active profile (E5); no profiles found
  in the vault; usage unreadable for the active profile; the target credential
  fails its under-lock probe (I4); `caam activate` returns non-zero (I7); the
  switch did not stick (I8).
- **S9** State is saved before every return path.

## T — Concurrency contract

- **T1** Run **one** watcher. Several are *safe* but wasteful.
- **T2** Polling is read-only, so any number of sessions can print the table.
- **T3** Switching is serialized by the non-blocking `flock`; the winner re-reads
  the active profile **under the lock** and abandons a switch whose premise
  changed.
- **T4** Known-unfixed and accepted: a hand-run `caam activate` takes no lock; the
  decision rests on usage readings a few seconds old; and cron jobs are **not
  deduplicated across sessions** — `CronList` is per-session and in-memory, so N
  sessions running the skill means N independent 30-minute schedules. That is safe
  (the lock serializes switching) but it multiplies polling, and the usage endpoint
  does back off under load.
- **T5** The one that bites — a running session rewriting the credential when its
  own token refreshes, silently reinstating the old account — **cannot be
  prevented from here**, so the loop verifies after switching and reports `FAIL …
  did not stick` rather than lying.

## U — Host facts the skill assumes (context; not re-implemented here)

Recorded so the rebuild's tests can fake them deliberately rather than
accidentally, and so the review can tell "not implemented" from "out of scope".

- **U1** `caam` is a standalone static Go binary at `~/.local/bin/caam`
  ("Coding Agent Account Manager"). It was originally installed by
  agent-flywheel/acfs, which is otherwise abandoned on the host; using it does not
  revive acfs.
- **U2** **Version matters.** The acfs-installed 0.1.0 was silently broken for
  Claude: it looked for the credential at `~/.claude.json` and
  `~/.config/claude-code/auth.json`, while Claude Code stores it at
  `~/.claude/.credentials.json` (key `claudeAiOauth`) — a path absent from that
  binary entirely, so `caam backup claude` captured settings files and **no
  token**. Verify any version with `caam paths`, which must list
  `~/.claude/.credentials.json` as `(required)`.
- **U3** The vault is a **credential store** holding live refresh tokens
  (0700/0600). Config lives at `~/.caam/config.yaml`, with
  `safety.auto_backup_before_switch: smart`.
- **U4** **A switch moves the whole host.** `~/.claude/.credentials.json` is shared
  by every Claude process. New sessions pick the new account up immediately;
  already-running sessions keep their in-memory token until it refreshes or they
  restart, so they keep spending the *old* account's quota for a while.
- **U5** `caam activate` restores `~/.claude.json` **verbatim** — 206 KB of live
  per-project session state that running sessions write to constantly, so a switch
  can clobber recent state there. `settings.json` is merged, carrying live plugin
  keys forward.
- **U6** **The profile name does not encode the email.** Verify identity from the
  snapshot's `oauthAccount.emailAddress` rather than trusting the label — a login
  that silently landed on an already-captured account is otherwise invisible.
- **U7** **Snapshot capture timing is load-bearing.** Capture right after a login
  or activation, never at the tail of a long session: one profile was captured with
  11.6 minutes left on its access token, the live session refreshed a minute later
  and rotated the refresh token, and the snapshot became unusable — costing a
  browser re-login.
- **U8** `caam ls` mis-renders EMAIL as `n/a` and PLAN as `Pro` for these Max
  accounts (a cosmetic 0.1.16 bug); `.credentials.json` correctly reports
  `subscriptionType: max`. Its health colour is computed from the *access* token,
  so a red row means "snapshot older than 8h", not "account unhealthy".
- **U9** The vault is **not restore-safe**. Losing it costs a few browser logins,
  which is cheap; restoring stale token snapshots from a backup is worse than
  re-minting.

## V — The foreman-model override (added vps-info `4b1a391`, 2026-08-20)

An escape hatch for a failure mode **no other rule can see**. Fable began
refusing messages outright — `Fable 5's safeguards flagged this message`, with
`Details: [reasoning_extraction]` — which is **not a quota condition**. Every
rule in **L** keys off the Fable *balance*, so a Fable that is available but
non-responsive reads as healthy, and the loop kept pinning foreman sessions to a
model that could not answer. The override lets an operator pin the model
directly.

- **V1** `--foreman-model=<value>` is parsed from `sys.argv` by prefix match at
  module scope; the value is `.strip().lower()`ed. Absent flag ⇒ `None`.
- **V2** A pin **overrides rules L1 and L2** (1a/1b). It does not affect L3/L4
  (2a/2b), which continue to key off the actual Fable balance.
- **V3** The pin is **persisted** in `state["foreman_model"]`. This is the whole
  point: a one-run flag would be undone by the next scheduled tick 30 minutes
  later, so an un-persisted override would appear to work and then silently
  revert. Persistence depends on **W1**; the two shipped in one commit for that
  reason.
- **V4** `auto` — and also the empty string and `none` — **clears** the pin via
  `state.pop("foreman_model", None)` and logs `models: foreman override cleared
  -- back to Fable unless spent`.
- **V5** A value in `WANTED_MODELS` sets the pin and logs `models: foreman
  override set to <value> -- persists until --foreman-model=auto`.
- **V6** An unrecognized value is **ignored, not fatal**: it logs `models:
  ignoring --foreman-model=<value> (expected fable/opus or auto)` and leaves any
  existing pin untouched.
- **V7** When `state["foreman_model"]` holds a value in `WANTED_MODELS`, it
  becomes `want_foreman` outright. A stored value **not** in `WANTED_MODELS` is
  ignored and the L1/L2 default applies, so a corrupted state file degrades to
  normal behavior rather than breaking enforcement.
- **V8** Pinning `fable` while the active account's Fable is spent logs `models:
  WARNING foreman override pins fable but the active account's Fable is spent --
  those sessions will be blocked` **and honors the pin anyway**. The operator is
  warned, not overruled.
- **V9** The summary line appends ` [pinned]` to the wanted model whenever a pin
  is set, so the table shows `foremen want opus [pinned]`.
- **V10** The override block sits **after** the `--no-models` early return, so
  `--no-models` does not process, set, or clear a pin. Only effort enforcement
  (**K9**) runs in that mode.
- **V11** **MAINTAINER RULING, 2026-08-21: the override is a TEMPORARY ESCAPE
  HATCH, not a new default.** The question was put explicitly — should the pin
  merely persist so it need not be re-passed, or should the general model become
  the outright foreman default with the flag opting back INTO the scoped model?
  The ruling is the former. **Rule L1 stands unchanged.** The rebuild MUST NOT
  harden the current incident into the default, and the exit gate MUST NOT score
  L1's survival as a stale carrier.
- **V12** Context, so the reproduction is taken seriously: this is **not
  hypothetical**. As of the ruling the override is in ACTIVE USE — the scoped
  model began refusing messages outright and every foreman session on the host is
  pinned to the general model through scheduled ticks.

## W — State persistence after enforcement (added vps-info `4b1a391`)

- **W1** `enforce_models` persists state **after** `_enforce_models` returns.
  The save sits in the wrapper, **outside** the try/except that catches
  enforcement failure, so state is written even when enforcement raised; and the
  save itself is wrapped in a bare `except Exception: pass`, so a failed write
  cannot break the run either.
- **W2** The defect it fixes: every caller saved state *before* invoking
  enforcement, so everything enforcement wrote — the **N** memo and the **V**
  pin — was discarded. Both were silently defeated. See **N3a**.
- **W3** Consequence for the rebuild's tests: a test that asserts the memo
  suppresses a second attempt, or that a pin survives to the next tick, MUST
  exercise the save ordering, not just the in-memory dictionary. An in-memory-only
  assertion passes against the *broken* implementation and is therefore not a
  discriminating test.

## X — Keeping idle profiles warm (added vps-info `0070050`, 2026-08-20)

The fix for the deadlock in **G9a**. Read it together with **G8**: the live-only
rule decides what may be switched onto, and this group is what keeps that set
from emptying.

- **X1** After each run, any **non-active** profile whose access token is expired
  or within `WARM_MARGIN_S` of expiring is refreshed.
- **X2** The refresh runs in an **isolated `CLAUDE_CONFIG_DIR` sandbox** under the
  state directory. The snapshot's `.credentials.json`, `.claude.json` and
  `settings.json` are copied in, with the credential file at 0600.
- **X3** **THE REFRESH IS PERFORMED BY THE AGENT, NOT BY THIS PROGRAM.** It runs
  `claude -p ok` against the sandbox with a 180s timeout and lets Claude Code
  perform its own refresh. **This preserves C10 rather than violating it**, and
  the distinction is the single easiest thing to get wrong here: a reviewer who
  reads "keep profiles warm" as "refresh the token" will look for a call to the
  OAuth token endpoint, not find one, and may either flag a missing feature or —
  far worse — an implementer may add one. Rotating a refresh token behind Claude
  Code's back can revoke the whole token family.
- **X4** Success is decided by comparing the recorded expiry **before** (the vault
  snapshot) against **after** (the sandbox copy).
- **X4a** **THE ORIGINAL DIAGNOSTIC WAS WRONG IN BOTH DIRECTIONS AND vps-info
  `3c0ad85` FIXED IT.** It reported `no refresh (snapshot likely orphaned)` for
  *every* failure, having discarded the agent's output, so two unrelated
  conditions hid behind one string — and it also reported healthy profiles as
  failed.
- **X4b** **The false-failure case.** A profile whose token is still valid gives
  the agent no reason to refresh, so the recorded expiry does not advance and the
  before/after comparison reads it as failure. When the after-expiry is still
  comfortably beyond the staleness margin, that is now a **success**: `already
  valid, no refresh needed`. One profile reported dead this way was polling live
  at the time.
- **X4c** **The conflated-failure case.** A genuine failure now reports the
  agent's own first line of output (captured from stdout and stderr, truncated),
  or `no output`. Swallowing it made an orphaned snapshot and a transient error
  indistinguishable.
- **X4d** **The two failures need OPPOSITE remedies, which is why the string
  mattered.** `OAuth session expired and could not be refreshed` means genuinely
  orphaned — a browser re-login. A spend or usage cap (`You've hit your monthly
  spend limit`) means the snapshot is **fine** and a re-login would be wasted
  effort. One account was reported orphaned while its token demonstrably worked.
- **X4e** **`refreshTokenExpiresAt` IS NOT EVIDENCE A SNAPSHOT WORKS.** One
  account's read `+27.7 days` while its refresh failed outright — the token had
  been *rotated*, not expired. **Only an attempt tells you.** Do not let the
  rebuild substitute a cheap field read for the sandboxed attempt.
- **X5** On success the refreshed credential is copied **back to the vault** at
  0600 and logged as `refreshed, +N.Nh`.
- **X6** Any exception yields a failure reason rather than raising. A failure here
  is **expected and survivable** — it usually means that snapshot was already
  orphaned, which is worth learning now rather than at the moment of rotation.
- **X7** The sandbox is always removed in a `finally`, ignoring errors.
- **X8** **PARANOIA CHECK, in the same `finally`:** the live credential's token is
  captured before the operation and re-compared after. A change logs `FAIL
  keep-warm altered the LIVE credential -- this must never happen; investigate
  before trusting the next rotation`. Silently swapping the host's account would
  be worse than the bug being fixed.
- **X9** The whole pass is skipped under `--no-warm`, under `--dry-run`, or when
  the vault directory is absent.
- **X10** It skips underscore-prefixed entries (**D2**) and the **active** profile.
- **X11** A profile still comfortably valid — expiry further out than
  `WARM_MARGIN_S` — is skipped.
- **X12** A per-profile **retry backoff** memo lives in state: a profile attempted
  within `WARM_RETRY_S` is skipped regardless of outcome.
- **X13** It is invoked at **three** sites — both hold paths and after a successful
  switch, the last using the **new** active profile.
- **X14** Tunables: `CAAM_ROTATE_WARM_MARGIN_S` (default **7200**),
  `CAAM_ROTATE_WARM_RETRY_S` (default **3600**), and the `--no-warm` flag.
- **X15** First live run revived one profile by +8.0h and reported another as
  orphaned — that one needs a browser re-login. Three of four profiles live again,
  rotation unblocked. **An orphan-detection report is a feature, not a failure.**

## Y — Operating rule: never keep a local copy of the program (vps-info `74429a7`)

- **Y1** The source skill now requires the program be extracted **fresh from the
  skill file on every invocation**, piped straight through with no intermediate
  file. Keeping a scratchpad copy, and above all **editing** one to add something
  that appears missing, is forbidden: if a constant or flag looks absent, the copy
  is stale, not the skill.
- **Y2** This is an operating rule for the SOURCE, so the rebuilt skill does not
  reproduce it literally — extracting a program from markdown is the very defect
  the rebuild removes. **Carry the reasoning instead.** The stated justification
  is that a patched local copy silently diverges from the version under review,
  *"which is exactly how this skill's prose and program came apart once already"* —
  the drift this thread opened by reporting. The rebuilt package's equivalent
  obligation is that the shipped plugin artifact and the repository package stay
  byte-verified against each other, which this repo already enforces for its
  materialized plugin copy.

## Z — The table MUST NOT assert what it cannot know (vps-info `ee88266`)

Absorbed by slice 2 (rendering); no separate slice.

- **Z1** `stale_past_reset(usage, source)` is true when a **cached** reading is
  older than the reset it describes. A `live` row is never stale. Both the weekly
  and five-hour reset timestamps are checked; a parseable timestamp in the past
  makes the row stale.
- **Z2** Such a row renders `?` for every quota figure, `reset` for every clock,
  and its source is suffixed `, stale`.
- **Z3** **Why withholding beats reporting.** Once a window has rolled over, the
  remembered percentages describe a period that no longer exists — the account has
  *replenished*. Rendering them anyway showed one account at 8% weekly, **under
  the reserve and therefore unattractive**, when it had reset five hours earlier
  and was in fact full. The table was steering the reader **away from the best
  account available**. The balance is unknown-but-replenished, not exhausted, and
  `?` is the honest rendering of that.
- **Z4** The old rendering showed `0m` in the reset columns for such rows, because
  the duration helper clamps a negative remaining time to zero (**R10**). That
  read as "resets right now" when it actually meant the cached reset timestamp is
  **in the past** — the clamp turned staleness into false imminence.
- **Z5** **No behavioral change to rotation.** Candidates already had to be
  live-verified (**G8**), so a stale row was never eligible. This is entirely
  about the table not asserting things it cannot know — **because a human reads it
  when deciding whether to intervene**, and that reader was being actively
  misdirected.

Z is worth holding onto as a class, not just a fix: **G8 made the stale row
harmless to the machine, and that is exactly why it stayed harmful to the human
for so long.** A safety rule that quarantines bad data from the decision path does
not make the bad data disappear from the display, and nothing else was checking.

## The source is a moving target — the finding that outlives these two entries

This inventory was first taken against vps-info `c7f8bed`. Between that reading
and this note landing, the source moved **twice** in about ninety minutes:

| commit | change | effect on this inventory |
|---|---|---|
| `c131592` | corrected `SKILL.md` prose that contradicted its own program | prose-only; program byte-identical, every carrier held |
| `4b1a391` | `--foreman-model` override; persist state after enforcement | **new carriers V and W**, and it falsified the working assumption behind **N** |
| `74429a7` | forbid keeping or patching a local copy of the program | **new carrier Y**; an operating rule, reasoning carried not copied |
| `0070050` | keep idle profiles warm so rotation cannot deadlock | **new carrier group X**, and it falsified **G9** — a recorded *deliberate accepted consequence* that was actually a deadlock |
| `ee88266` | stop showing cached quota figures from before a reset | **new carrier group Z**; the table was misdirecting the human while the machine was correctly protected |
| `3c0ad85` | report why keep-warm failed, and stop crying orphan | **revised X4 into X4a–X4e, and superseded D6** — the orphan diagnostic was wrong in *both* directions |

The first was verified harmless by extracting the fenced program from both sides
and diffing it — **893 lines, byte-identical**. That check is cheap and is the
right first move on any future source change: *did the program move, or only the
prose?* If only the prose moved, no carrier changes.

The second was not harmless, and it is the one to learn from. It did not merely
**add** behavior — it **corrected** behavior this inventory had already recorded
as working. An inventory that is only ever *appended to* would still assert that
the memo works, which was never true of the code it was measured against.

**FIVE MOVES, AND RE-MEASUREMENT HAS NOW FALSIFIED FOUR CARRIERS RATHER THAN MERELY
ADDING TO THEM** — **N**, **G9**, **D6** and **X4**. Two of those (**X4**, **D6**)
were carriers this inventory added *the same day*, from a commit that was itself a
fix. **A carrier taken from freshly-changed code is not more reliable for being
fresh; it is less.** The newest code is the least exercised.

**TWICE NOW, RE-MEASUREMENT HAS FALSIFIED A CARRIER RATHER THAN MERELY ADDING ONE.**
First **N**, described as working when the code discarded its writes. Then **G9**,
recorded as a *deliberate, accepted* design consequence when it was in fact a
deadlock that stopped rotation dead and forced manual switching. The second is the
more instructive: a carrier can be wrong not because it misread the code, but
because it faithfully recorded a rationale the maintainer later rejected. **A
stated "we accept this cost" is a claim with a shelf life.**

**So re-measurement is not optional and it is not append-only.** Before the exit
gate runs, and before any slice is implemented against a carrier, re-read the
source at its current HEAD and ask both questions: what is new, and what did I
previously record that is now false? Update the as-of pin at the top of this file
when you do.

There is a second-order consequence worth stating plainly, because it changes how
the exit gate should be run rather than merely what it checks: **the reviewer must
re-pin too.** A completeness review that walks this list against the
implementation, while the source has moved underneath both, will certify a
faithful reproduction of a superseded program and record durable evidence saying
so. The review MUST begin by re-measuring the source and reconciling this file,
not by trusting it.
