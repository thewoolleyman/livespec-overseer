---
name: llm-provider-manager
description: >-
  Acquire, validate, store, select, provision, revalidate and replace LLM
  provider credentials for a requested provider, account, credential kind and
  purpose. Invoke as `/livespec-overseer:llm-provider-manager` to list what
  needs operator attention, or with `--provider <v> --account-id <v> --kind <v>
  --purpose <v>` to acquire one credential identity.
---

# llm-provider-manager — the credential-provider boundary

This is the harness-neutral operator contract for the `llm-provider-manager`
operation. The Claude, Codex and Pi bindings each resolve this plugin's root
their own way and then read THIS file; none of them carries behavior of its own,
and none of them restates what is written here.

## 0. What this operation is, and what it is not

It is a **distinct operator operation**, not a mode or a rename of
`caam-anthropic-loop`. The two are neighbours with different jobs, and confusing
them is the mistake this section exists to prevent:

| | `caam-anthropic-loop` | `llm-provider-manager` |
|---|---|---|
| what it publishes | an **identity-only** selection record — which account is active | a credential **provisioned into one isolated target** |
| what it never does | hand out credential material at all | treat that identity record as a credential source |

The published selection record carries identity ONLY. It is not a credential, it
is not authority to skip validation, and this operation must never read it as
either. Which credential a consumer presents for a published account is that
consumer's own concern.

**This operation provisions DIRECTLY into an isolated consumer target, and is
not a proxy.** It exposes no inference-request proxy, no relay, no gateway and
no forwarding endpoint: no model request passes through it, and no consumer
sends inference traffic to it. The only enabled target adapter is
`isolated-run`, which binds one credential to one consumer run and commits it
with a single atomic write. If you are looking for something to point a client's
base URL at, this is the wrong operation — it puts the credential where the
client already reads, and then gets out of the way.

**It is also not the place credential behavior lives.** Acquisition, validation,
storage, selection, provisioning, revalidation and replacement are implemented as
importable modules of this repository's `overseer` package and run behind the
plugin's own manager executable. Nothing in this file and nothing in a binding
may reimplement, restate or work around any of it.

## 1. Invocation

The operator argument surface is CLOSED. There are exactly two accepted shapes:

```text
/livespec-overseer:llm-provider-manager
```

Zero arguments — report every credential identity currently waiting on a human.
This requests no state change; it only lists.

```text
/livespec-overseer:llm-provider-manager --provider <value> --account-id <value> \
    --kind <value> --purpose <value>
```

All four pairs, each exactly once, each with a non-empty value, in any order —
acquire a credential for that one identity. The four fields together ARE the
identity: the same four values name the same credential every time, so repeating
an acquisition is a retry of one operation rather than a request for a second
credential.

Anything else — a missing pair, an empty value, a repeated flag, an unknown flag,
a bare positional argument — is refused before the manager is invoked at all, and
the refusal names the fields at fault.

## 2. What happens before anything runs

Each binding resolves this plugin's root through its own harness's installed-plugin
discovery, canonicalizes it to an absolute directory, and then hands it to the
shared entrypoint, which **validates it**. Validation requires that the outer
`plugin.json` names `livespec-overseer` with a non-empty version and description;
that the nested `.codex-plugin/plugin.json` agrees with it field for field and
carries its exact `skills` registration value; and that all three bindings plus
this prose file are present as regular files.

That validation is not ceremony. A harness hands back whichever root its own
discovery resolved — a cache directory, an install path, a dogfooding checkout —
and reading one plugin's contract while running another plugin's executable is a
failure that would otherwise be silent.

A mismatched manifest, a missing required file, or a manager executable that
cannot be launched is reported as `internal-bug` with exit `70`, without retrying
and without changing anything.

## 3. Running the operation

Resolve `$PLUGIN_ROOT` as your binding describes, then delegate — passing the
operator's arguments through unchanged:

```bash
PYTHONPATH="$PLUGIN_ROOT" python3 -m overseer.llm_provider_manager "$@"
```

Present what it writes. Do not add arguments, do not reorder them, and do not
substitute a different executable.

## 4. Reading the result

The operation writes exactly **one line of JSON** and exits. Show that line
verbatim; you may add secret-free explanation around it, but never re-format,
re-serialize or summarize the line itself — consumers read those bytes.

Report the exit status unchanged. It carries the outcome:

| exit | meaning |
|---|---|
| `0` | success |
| `2` | `invalid-request` — the request was malformed; nothing was changed |
| `3` | `retryable-exhaustion` — no eligible credential right now; ask again later |
| `4` | `store-unavailable` — the credential store could not be used; fail closed |
| `5` | `provisioning-failed` — the target write definitively did not commit |
| `70` | `internal-bug` — a mismatched plugin root, or a launch that never produced a result |

A failure object carries exactly `version`, `status`, `error_type` and `message`,
and the message is secret-free by construction. If you ever find a credential,
login, mailbox or backend token in operator-visible output, stop and report it —
that is a defect in this operation, not something to redact by hand.

## 5. The attention surface

A zero-argument run lists the credential identities whose acquisition is waiting
on a human, each with the record it belongs to and the deadline it expires at.

Resolving one is a **local operator action, and not yours to take**. You may
show the operator the `attention --resolve <record_id>` or
`attention --give-up <record_id>` command to run themselves; you must never
construct, forward or execute either. The binding's argument grammar in §1 cannot
express them, which is the point: an operator's decision about a pending
credential is made by the operator, at their own terminal.

This attention surface is the MANAGER's, and is a different thing from the
overseer daemon's attention block. They share a word and nothing else.

## 6. Boundaries

These are not style preferences. Each one is a property something else depends on.

- **No credential value is ever printed, logged, pasted into a session, written
  to a handoff, or placed in an agent's context.** Credential material moves from
  the store to an isolated target and nowhere else.
- **The operator never supplies a `record_id`.** It is generated for a genuinely
  new identity and reused for a known one; a caller-supplied one would let two
  identities collide.
- **Nothing here reads or writes the credential store directly**, and no binding
  or prose step may add a step that does.
- **A refused request changes nothing.** If the operation says `invalid-request`,
  no lock was taken, no worker was started and no record was created — fix the
  request and re-run rather than looking for partial state to clean up.
