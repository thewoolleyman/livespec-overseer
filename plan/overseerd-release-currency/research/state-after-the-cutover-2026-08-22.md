# State after the cutover — the requirement is met, and running it for real found a defect

ledger anchor `overseer-6s3pk6`

This supersedes the earlier note in this directory,
`cutover-blocked-on-provisioning-2026-08-22.md`. That note is correct about the
blocker it found and **overtaken on its conclusions**: it says `.10` is *blocked*
and that the epic is "no longer nine done, one cutover left". Both were true when
written at ~18:40Z; neither survived the evening. The note is left in place because
its near-miss is the reason the cutover was safe.

## What happened

`overseer-6s3pk6.12` fixed provisioning (PR 1723) — `uv venv` plus
`uv pip install --python`, with a failed provision removing its own partial prefix.
Verified live at 19:56Z on the host that had failed. The cutover then ran
20:01:20Z–20:04:40Z.

**The daemon now runs released code from an isolated prefix, and keeps itself
current without help.** At 21:44:43Z it publishes `1.41.12` against `origin/master`
`v1.41.12` — gap zero.

## The part that was not merely a bounce

Seventy seconds after the cutover, unprompted:

| time | what |
|---|---|
| 20:01:30Z | launched by hand at 1.41.10, prefix `runtime/1.41.10` |
| 20:02:40Z | the daemon **created** `runtime/0d2a99de9e66…` by itself |
| 20:03:24Z | publishing 1.41.11 from that prefix |
| later | adopted 1.41.12 into `runtime/e9f7111e44e6…` |

`pid 826718` is **unchanged across both** — same process, new image, i.e. `os.execv`
and therefore `.3`'s tick-boundary re-exec rather than a respawn. The prefixes are
named by **commit sha**, so the daemon resolved release targets and provisioned them
through `.12`'s uv path on its own. `.5`'s ledger recorded each adoption and cleared
`pending` to `last_good`, with nothing rejected.

So `.1`, `.2`, `.3`, `.5`, `.9` and `.12` executed end to end, autonomously, twice.

## How the cutover was done, and why not through the bootstrap

`overseer-start` refuses unless a Claude or Codex ancestor is in its **process
ancestry**, then splits beside *that* pane from `$TMUX_PANE` with no override flag.
From the plan session it would have built a second overseer layout in the wrong tmux
session — and its pane-by-title lookup does not recognise an untitled acting pane, so
it would have split a **third** pane and started a **second** daemon.

The daemon was replaced **in place** in pane `%166`: provision and prove the prefix
first with the old daemon still up, confirm zero open wrap-up rounds, `kill -TERM` on
the daemon pid so the pane's shell survives, then launch the prefix executable into
that same pane. The top-pane rider is satisfied **by construction** rather than by
re-splitting, and it held across both self-updates.

The pane was afterwards titled `overseer-daemon`, so the bootstrap now takes its
idempotent path instead of splitting a third pane. The underlying code gap — the
bootstrap can *add* a daemon pane but never *adopt* one — is unfixed and recorded on
`.10`.

## Then running it for real found a defect no test could

**`overseer/daemon.py:45` resolves the alert log from its own module location:**

```python
return Path(__file__).resolve().parent.parent / "tmp" / "overseer" / "daemon.log"
```

While the daemon lived in the checkout, `parent.parent` *was* the checkout. From the
prefix it is **site-packages** — so the structured alert stream now writes inside the
installed package while the operator's bottom pane still reads
`<checkout>/tmp/overseer/daemon.log`.

The baseline, so the claim is falsifiable:

| file | contents |
|---|---|
| `<checkout>/tmp/overseer/daemon.log` | 1485 alert entries 09:34–20:00Z, **129 in the final hour**; since 20:05:37Z, six entries and **zero alerts in 90 minutes** |
| `<prefix>/…/site-packages/tmp/overseer/daemon.log` | 426 live entries, real instance ids |

The conditions did not stop — the live table holds 9 `picker-stalled`, 2
`foreman-escalated`, 3 `foreman-heartbeat-stale`. They are written where nobody reads.
And it **fragments on every self-update**: 108 KB abandoned in the 1.41.11 prefix,
220 KB in 1.41.12.

**State the blast radius in both directions.** The primary surface is fine — capturing
pane `%166` shows the live table and the full `NEEDS YOU` block rendering correctly,
because that is stdout. What broke is the structured feed. This is not "the cutover
broke the overseer"; it is "the cutover exposed a path assumption never exercised".

Filed and dispatched as `overseer-6s3pk6.13`.

### The asymmetry that hid it

`start.py` resolves this correctly and cwd-aware, via `_default_core_root` /
`_checkout_root_from_cwd`, **preferring** a checkout found from the working directory.
`daemon.py` has no such logic. Two resolvers that agreed for exactly as long as the
daemon lived in the checkout. The daemon's cwd *is* the checkout — `daemon.py` never
asks.

## The method lesson

Every test runs with the package **as** the checkout, which is the one configuration
in which this defect cannot occur. That is a check that cannot fail at the level of
the test *environment* rather than the assertion — a variant worth naming, because
the assertion looks fine and the coverage looks complete.

It is also the argument against declaring victory on green code. The machinery was
complete and merged for hours while being, in `.10`'s own words, *in force nowhere*.
The first thing to run it for real found a defect in under two hours.
