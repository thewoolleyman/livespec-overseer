# caam-mixed-plan-capacity — factory landing, proof plan and what stays unobserved (2026-10-16)

## What landed, and through which route

The plan's three code children went through the hp factory in dependency order under the
freeze driver's GO, after the maintainer reversed the 2026-10-14 "implement by hand" exception
("I have delegated it to you", relayed 2026-10-15 02:47Z). Each run kept its dispatch-time
credential, which is the exposure this plan exists to shorten.

| Child | Scenario family (v056) | Run | PR | Merge | Release |
|---|---|---|---|---|---|
| `overseer-pffwyp` | refusal trigger | `01M508TAFWWCNTENA5M1S3PNX2` | #2500 | `37b1ca14` | 5.29.1 |
| `overseer-wzw2zw` | capacity column | `01M50YECZ5EG688Q8CD2XAK323` | #2504 | `30c1c028` | 5.30.0 |
| `overseer-ivpkrf` | fast-drain and capacity test | `01M51F6Y5ANKE4G31VQW0G8XJY` | #2508 | `740bbace` | 5.31.1 |

`overseer-prdmie` ratified the specification as v056 (PR #2487, `94f1e78e`). `overseer-5jp2sw`
captured the Claude Code 2.1.301 idle-canary fixture the pffwyp post-merge janitor needed (PR
#2502); `overseer-7kkzgy` fixed the timing-flaky `tests/test_lpm_terminal_performer.py` test that
failed pffwyp's first publish; `overseer-bnd23c` carried the host-side usage-API lag question.
All seven children are closed.

Two runs died on the provider, not on the code: `01M50M23FX6Q` (wzw2zw) and `01M5154NVCD6`
(ivpkrf) both ended at `implement` with "You've hit your session limit" on `anthropic-1`. Both
were recovered by a plain re-dispatch seeded from the preserved `needs-human/<uuid>` ref; neither
needed a code change. The irony is the plan's own thesis: a session-limit refusal on the factory
credential is exactly what the refusal trigger now rotates the loop off, and the loop runner
that would have done so was still on the pre-5.29.1 build.

## Rulings that bear on the record

- **R12**: ivpkrf's dependency on wzw2zw was a CODE dependency, satisfied by the wzw2zw merge;
  the row was released with the `resolve-blocked` valve, not a hand edit.
- **R13**: the "hp" in the wzw2zw host clause was a loose label. The caam loop's only live
  deployment is the operator host `vmi3006760`, so its host proof counts when it names that
  hostname verbatim. The Definition of Done text was left unedited.
- **R24**: hold on the shipped `claude-cred-status` probe, no route-around; a provider
  session-limit death is "parked resumable", never a defect class.
- **R32/R33/R34, capacity-first halt (~06:30Z)**: dispatch thresholds stepped down to combined
  non-terminal ≤3 with non-reserved ≤7 after a 0–90 s jitter, then halted outright for general
  owners. None of this plan's remaining work needs a dispatch.

## Proof of Done: what is proved, and what is not yet observable

The epic carries four `host_captured` assertions. The captured record (posted 2026-10-16
12:16Z against release v5.31.1, installed build `72d551dd8236`) proves them as follows:

- **Assertion 4** (capacity column) is observed directly: the installed program's
  `--dry-run --no-warm --no-models` pass on `vmi3006760` prints a CAPACITY column on all five
  rows, each reading `large (default_claude_max_20x)`.
- **Assertions 1–3** (fast-drain rotation, refusal rotation, capacity-scaled candidate exclusion)
  are proved through the released artifact's decision path: the scenario tests that
  `tests/heading-coverage.json` pins to the governing v056 scenarios, run against the release
  tree that `diff -rq` shows byte-identical to the installed build under `overseer/`.

They are NOT yet observable on the fleet, and the record says so. Every caam-managed account has
been on the large plan since the maintainer moved them on 2026-10-14, so no small-plan account
exists to drain fast or to be excluded by the capacity test, and the live loop runner
(`caam-anthropic-loop-runner`, this host) still runs plugin build `82e0c1cb1746`, so no 5.29.1+
pass has handled a live refusal. The fleet observation that would close the gap is a maintainer
act (`/reload-plugins` in the runner's pane) followed by the next provider refusal; it is tracked
by the freeze driver as a maintainer item and recorded on the epic as a post-merge obligation.

## Two things a later reader should know

- Branch `feat/overseer-pffwyp` (one commit, `cef9669a`, the pre-dispatch decision-path split)
  is obsolete: the factory landed pffwyp from master without it. Its worktree was removed on
  2026-10-16; the unmerged branch awaits deletion by a maintainer, since deleting an unmerged
  branch is gated per instance.
- The installed caam loop program does not recognise `--help`. Invoked with it, it runs ONE
  unflagged pass against the shared state file. Measured 2026-10-16 12:05:22Z: outcome
  "nothing to change", no rotation. Its flags are `--dry-run`, `--no-models`, `--no-warm`,
  `--session-model`, `--protected-account`.
