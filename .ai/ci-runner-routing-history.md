# CI runner routing — the k3s cutover, rollback, and AppArmor root cause

Moved verbatim from `AGENTS.md` §"CI runner routing", whose governance rules and current `CI_RUNNER_LABELS` value stay there.

Between 2026-08-17 ~13:05Z and that re-cut it was on `["ubuntu-latest"]`: the
morning's cutover to the ARC k3s scale set
`livespec-overseer-k3s` (livespec-s43svm.16) deterministically failed FOUR of
this repo's environment-sensitive tests on every master run it touched — both
`tests/prompts/test_repo_containment_discriminates.py` tests (tmux pane-cwd
reads return `''` in the pod), `tests/test_detached_dispatch.py`'s
process-group survival test (`os.killpg` PermissionError), and a foreman e2e
whose cwd-identity change went undetected — yet the SAME commits are green on
hosted runners and in the fabro sandbox container image under docker. The
flip-back is the workflow's own sanctioned direction (see the routing comment
block at the top of `ci.yml`) and was panel-ratified after master sat red
about three hours. Re-cut condition, recorded on `livespec-s43svm.16`
(livespec tenant): the pod must pass this repo's full suite — those four
named tests specifically — before `CI_RUNNER_LABELS` points at the scale set
again. See `livespec/plan/fleet-ci-runner-pool/research/
k3s-arc-kueue-migration.md` ("Real-traffic cutover log") and the
`livespec-s43svm.16` ledger comments.

**Root cause, found 2026-08-18 (livespec `livespec-s43svm.18`): ONE AppArmor
denial behind all four failures — nothing to do with the pid namespace, and
nothing wrong with the tests.** Ubuntu's
`kernel.apparmor_restrict_unprivileged_userns=1` *stacks* the AppArmor label of
every confined task, so a workflow-pod process carries
`cri-containerd.apparmor.d//&unconfined` rather than the bare profile name.
containerd's default profile grants intra-container `signal` and `ptrace` only
to `peer=cri-containerd.apparmor.d` — a bare peer name, which a stacked label
does not match — so the profile denied its own containers both operations.
`os.killpg` returns `EACCES` outright; tmux's `#{pane_current_path}` reads back
EMPTY because tmux derives it by `readlink()`ing `/proc/<pane pgrp>/cwd`, and
reading another process's `/proc/PID/cwd` is a ptrace-read. That is why the
denial arrived as an empty string instead of an error, and why it laundered into
assertion failures in tests that look unrelated to each other. Plain docker is
unaffected because `docker-default` is not stacked the same way — which is
exactly why the same Fabro image was green under docker and red in a pod.

The fix is in `livespec-dev-tooling`
(`ci-runner/k3s/phase2/apparmor/ci-runner-workflow`,
https://github.com/thewoolleyman/livespec-dev-tooling/pull/1531): a node-loaded
profile keeping every containerd deny rule and widening only the
`ptrace`/`signal` peer expressions, applied to hook-generated workflow pods via
`ACTIONS_RUNNER_CONTAINER_HOOK_TEMPLATE`. AppArmor stays in enforce mode; no
capability was added and nothing was made privileged. Verified in real CI by
run `32199679954`: all ten gating jobs carried
`labels=["livespec-overseer-k3s"]` with real pod runner names and went green,
including the full-suite `check-coverage` job.

**Second lesson, and it generalizes past this repo: in ARC's
`containerMode: kubernetes`, the pod your tests run in is NOT the runner pod.**
The container hook creates a separate `<runner-pod>-workflow` pod per job and
builds its spec itself, with an empty `securityContext`. Anything set under the
scale set's `template.spec` reaches the runner pod only. Reading a scale set's
`securityContext` and concluding you know what the tests executed under is
reading the wrong object — the same class of error as the runner-identity
mistake below.

**Triage lesson that cost a withdrawn revert (PR #1063):** these failures were
first mis-attributed to test interference from the PR that merged minutes
before the cutover took effect. Runner identity is part of CI-failure triage
in this repo — check WHICH runner executed the failing jobs (the jobs API's
`runner_name`) before attributing a red master to content. A docs-only commit
failing CI is the tell that the environment, not the tree, changed.
