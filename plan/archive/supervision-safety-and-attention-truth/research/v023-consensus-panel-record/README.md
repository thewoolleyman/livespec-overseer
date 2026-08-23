# v023 consensus panel record — durable copy

These three files are the disposition authority cited by **SPECIFICATION v023**,
the ratification of `acting-safety-third-keystroke-act`. They are preserved here
byte-for-byte because the ratified record cites them at a path that is **not in
source control**.

## Why this directory exists

`SPECIFICATION/history/v023/proposed_changes/acting-safety-third-keystroke-act-revision.md`
cites its authority as:

    tmp/overseer/foreman/consensus/
      4e066523c6948156e4a2b8497ddcecc61b66ea17b39364188ec3d394f06ad2d4.json

`tmp/` is gitignored (`.gitignore` line 2). So a ratified specification revision
depended for its stated authority on files with **no history, no review, no CI, and
no guarantee of survival** — any scratch cleanup would have silently broken the
citation, and nothing would have failed loudly when it did.

That is precisely the exposure recorded on work-item `overseer-yqza`
(`tmp/overseer/` scratch discipline). It is a stronger instance than the 22 KB
`.patch` file that item calls its strongest single case, because a dangling patch is
merely unreviewed work, whereas this was **the cited authority of an already-ratified
letter**.

Copying them here does not fix `overseer-yqza`'s general problem. It closes this one
citation.

## What was NOT done, deliberately

The v023 revision record was **not edited** to point here. It is an archived
historical record of what was decided and on what basis at the time; rewriting it to
match a later remedy would falsify the provenance it exists to preserve. The mapping
from the cited `tmp/` path to this durable copy is recorded in this README instead,
and on `overseer-yqza`.

## Integrity

The copies are byte-identical to the originals as they stood on 2026-08-19.
`verdict.json` is the file the revision record cites by its content-addressed name;
its sha256 at copy time was:

    3ba97855d250df6500a6513eae32a89004a2217371770ae8ac5840f929b4712a

Note that this hash is of the FILE, and is not the same value as the
`4e066523…` in the original filename, which is the panel's own `cache_key` over the
request rather than a digest of the response document.

## The files

| file | original name under `tmp/overseer/foreman/consensus/` | what it holds |
|---|---|---|
| `verdict.json` | `4e066523c6948156e4a2b8497ddcecc61b66ea17b39364188ec3d394f06ad2d4.json` | the panel verdict: outcome, reason, the three models, and each reviewer's typed action |
| `request.json` | `4e066523-request.json` | the question put to the panel |
| `responses.json` | `4e066523-responses.json` | the three reviewers' rationales, verbatim |

## What the panel decided

Convened under a maintainer delegation relayed by the livespec-overseer foreman, to
settle three questions raised while drafting the acting-safety proposal. Outcome
recorded as `unanimous`, reason `three_typed_actions_equal`, `mutated: false`, across
`claude-fable-5`, `claude-opus-5` and `gpt-5.6-sol`:

- **q1 — `both-suffixes`.** Ratify the shipped scope of
  `signals.topic_reserved_for_supervisor`: BOTH the `-supervisor` and `-foreman`
  reserved entity suffixes.
- **q2 — `require-code-fix-before-ratification`.** The once-per-episode sentence
  lands ONLY together with the code made true. This was a sequencing constraint on
  `/livespec:revise`, not a wording preference; it was discharged by
  `overseer-6tfncs.1` / PR #1209 before the ratification ran.
- **q3 — `five-acts-expiry-as-wrapup-tail`.** Five daemon informational acts, with
  the ready-expiry notice enumerated as a member but characterized as the wrap-up's
  round-scoped tail.

Every reviewer independently recorded the action as **reversible**, with the rollback
stated as: the spec change lands as a PR, and reverting the PR restores the prior
letter.

## Caveat a later reader should keep

The panel record is verifiable; the **maintainer delegation that authorized convening
it arrived as a relayed quote**, not as a directly observed instruction. The drafting
session recorded that distinction at the time and declined to self-authorize the
ratification on the strength of the panel alone. The ratification ultimately proceeded
on a separate, explicit maintainer authorization to run the revise pass. Both facts
are on `overseer-um53`.
