# Initial scope

Audit every runtime-specific branch where overseer offers equivalent operator behavior to Claude and Codex. The review covers discovery and adoption, context and status parsing, wrap-up delivery, ready-state validation, restart/resume, input submission, model-profile preservation, liveness and stall detection, diagnostics, recovery, and release/live-operation surfaces.

A finding becomes a child work item only after code-path evidence, a test gap or contradiction, and a reproducible failure shape establish that Codex behavior is broken while the Claude path works. Speculation and pure feature asymmetry are recorded as investigated and not filed.
