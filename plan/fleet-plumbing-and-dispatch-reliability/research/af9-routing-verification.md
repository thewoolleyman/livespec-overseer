# overseer-af9: routing verification

Measured 2026-08-19T05:43Z, resuming this thread against its opening handoff.
That handoff named exactly one next action -- "take `overseer-af9` first ...
**confirm where the fix lands before sizing it**". This note is that
confirmation. It answers the routing question with measurements rather than
inference, so the maintainer call the item is now blocked on can be made from
evidence.

Nothing here sizes or fixes the defect. The fix does not land in this repo.

## The defect is still present, at source, today

`overseer-af9` was filed 2026-08-03. Sixteen days later it is unfixed, and not
merely stale-in-cache:

| where | file | line | predicate |
|---|---|---|---|
| installed build `f1e497d78701` | `lib/resolve_core_root.py` | 269 | `if (checkout / "prose").is_dir():` |
| `livespec-driver-claude` master (`e6d5b28`) | `.claude-plugin/lib/resolve_core_root.py` | 269 | identical |

The ordered algorithm is unchanged from the item's description: rule 1
`LIVESPEC_CORE_PLUGIN_ROOT`, rule 2 the `.claude-plugin/prose/` directory test,
rule 3 the `projectPath`-keyed install record.

## It reproduces live in this repo

    $ env -u LIVESPEC_CORE_PLUGIN_ROOT python3 \
        ~/.claude/plugins/cache/livespec-driver-claude/livespec/f1e497d78701/lib/resolve_core_root.py \
        --project-root .
    .claude-plugin

This repo carries `.claude-plugin/prose/{foreman,overseer,supervise-plan}.md`
and no `revise.md`, so rule 2 fires, returns `.claude-plugin`, rule 3 is never
consulted, and the follow-on prose read hard-stops.

## Control: rule 3 would have answered correctly

The `livespec@livespec` registry holds 16 install records. The one keyed to
this exact `projectPath` reads:

    projectPath  /data/projects/livespec-overseer
    installPath  ~/.claude/plugins/cache/livespec/livespec/1768d10c92c5
    version      1768d10c92c5   (lastUpdated 2026-08-19T00:07:40Z)

and `.../1768d10c92c5/prose/revise.md` exists. So the correct answer is present
and reachable on this host; rule 2 simply reaches a wrong one first. This
reproduces the item's own 2026-08-03 control against a build sixteen days newer.

## Three-way control on the item's suggested predicate

The item suggests rule 2 test for something identifying core SPECIFICALLY --
e.g. requiring `prose/revise.md` rather than the bare `prose/` directory. Run
over every plugin-shipping repo in `/data/projects`:

| repo | `prose/` present | `prose/revise.md` present | current rule 2 | suggested rule 2 |
|---|---|---|---|---|
| `livespec` (core) | yes | **yes** | fires (correct) | fires (correct) |
| `livespec-overseer` | yes | no | **fires (wrong)** | does not fire |
| `livespec-orchestrator-beads-fabro` | yes | no | **fires (wrong)** | does not fire |

The suggested predicate discriminates correctly on all three, and preserves the
`--plugin-dir .` dogfooding case the current rule exists to serve. Two of three
plugin-shipping repos measured here are broken today, which is the blast-radius
claim, measured rather than asserted.

## Where the fix lands, and why this thread cannot land it

**`livespec-driver-claude`, at `.claude-plugin/lib/resolve_core_root.py`.** Not
in this repo, and not in either sibling this repo can reach: `.livespec.jsonc`'s
`cross_repo_targets` lists exactly `livespec-dev-tooling` and
`livespec-orchestrator-beads-fabro`. `livespec-driver-claude` is absent, so the
dependency cannot even be EXPRESSED as an edge from here -- and per this
thread's own scope note, an unresolvable sibling fails closed forever, so adding
one would make the item permanently undispatchable rather than merely blocked.

That is precisely the routing call the 2026-08-19 intake pass parked as
`blocked-reason:needs-human`, and it is genuinely a maintainer decision because
it is a question about record topology across tenants, not about the evidence.
The evidence is no longer in any doubt.

## Scope of the block, corrected

The opening handoff treated `overseer-af9` as the one item to take first. As of
the intake pass seven minutes later, **all thirteen** of this thread's
requirement carriers sit behind a human valve, and none appear in the `impl:`
ready set:

- seven `blocked / needs-human`: `overseer-af9`, `overseer-1hv`, `overseer-fs4`,
  `overseer-lvp`, `overseer-6pn`, `overseer-n04`, `overseer-izh7`
- five `pending-approval` (admission valve): `overseer-l0f`, `overseer-mim`,
  `overseer-ye5`, `overseer-vfz5v5`, `overseer-iwu`
- one `backlog` gated on an external precondition: `overseer-n11`, which waits
  on the orchestrator deleting the `host_dispatch_cap` key

So the thread's throughput is not limited by investigation. It is limited by
valve decisions, and this note removes the investigation excuse from the largest
of them.

## The two carriers that are in-repo and factory-safe

Worth separating, because they need only the admission valve rather than a
cross-tenant routing call -- both are labelled `Autonomy tier: factory` with
`Repo target: livespec-overseer`, and both already carry acceptance criteria:

- `overseer-vfz5v5` -- replace `justfile:127-142`'s hard-coded
  `ensure-codex-plugins` body with the shared delegation.
- `overseer-iwu` -- state call-time resolution of the orchestrator plugin build
  in `CLAUDE.md`, with a regression test carrying a positive control.

These are the cheapest available progress in the thread and do not depend on
`overseer-af9` in any way.
