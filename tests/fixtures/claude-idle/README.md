# Claude Idle Fixture Provenance

The canary registry is the set of `*.txt` files in this directory. Keep this
note beside the fixtures so a reader can tell whether a file is a live pane
capture or a constructed rendering.

| Fixture | Provenance |
|---|---|
| `2.1.235.txt` | Constructed rendering of the measured two-trailing-rule titled idle border. Its shape is based on the daemon predicate measurement over all 45 live Claude panes at 2026-08-20T21:20Z, recorded in `plan/fix-restart-problem/research/root-cause-2026-08-20.md`. |
| `2.1.237.txt` | Constructed rendering of the measured one-trailing-rule titled idle border. Its shape is based on the same 45-pane live measurement at 2026-08-20T21:20Z in `plan/fix-restart-problem/research/root-cause-2026-08-20.md`. |
| `2.1.238.txt` | Live capture from the canonical Claude idle canary capture path. |
| `2.1.239.txt` | Live capture from the canonical Claude idle canary capture path. |
| `2.1.240.txt` | Live capture from the canonical Claude idle canary capture path. |
| `2.1.241.txt` | Live capture, but from a LINKED WORKTREE rather than the canonical capture path, so it carries a longer cwd line, a repo-state warning row and an extra statusline row that its siblings do not. The predicate classifies it idle regardless, which is the property being registered; it is noted here so nobody reads the extra rows as drift in the build. |
| `2.1.246.txt` | Live capture from the canonical capture path in the primary checkout, deliberately NOT from a linked worktree, so it carries the plain cwd line and none of the extra rows `2.1.241.txt` records. Captured 2026-08-26 to clear a pre-existing local block: no fixture existed for the installed build, so `check-claude-idle-canary` failed on every operator host running it and no local push could pass the pre-push aggregate. |

Do not recapture `2.1.235.txt` or `2.1.237.txt`; those installed builds are no
longer available on the host. Add new installed builds by capturing a new
version-keyed `*.txt` fixture, not by editing older provenance.
