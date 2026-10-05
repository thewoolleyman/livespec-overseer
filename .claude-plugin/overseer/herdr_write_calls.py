"""herdr_write_calls.py — the herdr WRITE operations' params and replies. PURE, no I/O.

The write-side twin of :mod:`herdr_calls`, and split from it for the same reason
that module is split from :mod:`herdr_adapter`: this layer knows what each
MUTATION asks for and what its answer means, and nothing else. It opens no
socket and makes no claim that anything it shaped was actually delivered.

Keeping it pure is what lets the wire shape below be asserted without a herdr
server at all, which matters because this repository's CI container does not
ship herdr — the deterministic suite is the only thing covering this code on
that lane.

**The paste's wire shape is part of the CONTRACT, not an implementation detail.**
Measured on this host against herdr 0.9.3 / protocol 22, three delivery forms
exist and only one of them is usable:

  - `pane.send_input` with `keys: []` delivered `\\x1b[200~ONE\\nTWO\\x1b[201~` to
    a raw-mode child — ONE bracketed paste carrying NO carriage return. The
    payload is DELIVERED but NOT EXECUTED, which is precisely what the daemon's
    paste-then-observe-then-submit protocol requires.
  - `pane.send_input` with `text: ""` and `keys: ["Enter"]` appended exactly
    `\\r`, so submission is separable from delivery.
  - `pane.send_text` delivered the same characters with NO bracketing at all.

That last one is the trap, and it is why :func:`paste_params` exists rather than
callers shaping a dict inline. A `send_text` paste looks correct in a screen
capture while letting a multi-line payload fragment into separate submitted
prompts — the exact failure the tmux backend's atomic-paste discipline
(`load-buffer` + `paste-buffer -p`) was adopted to prevent. `keys` is sent as an
EMPTY list rather than omitted because the measured request carries it
explicitly; herdr validates keys before sending, so an empty list is the
statement that no key accompanies this text.
"""

from __future__ import annotations

import herdr_protocol

__all__: list[str] = [
    "ENTER_KEY",
    "EXPECT_OK",
    "PASTE_METHOD",
    "RESULT_TYPE_OK",
    "enter_params",
    "paste_params",
]

# MEASURED: the one method that brackets a paste. `pane.send_text` is NOT an
# alternative spelling of this — see the module docstring.
PASTE_METHOD = herdr_protocol.METHOD_PANE_SEND_INPUT
# MEASURED: the key name herdr accepts for a submit, and the result discriminator
# both write calls answer with.
ENTER_KEY = "Enter"
RESULT_TYPE_OK = "ok"

# A write answers `{"type": "ok"}` and carries no payload members, so there is
# nothing to require beyond the discriminator itself.
EXPECT_OK = herdr_protocol.ReplyExpectation(result_type=RESULT_TYPE_OK)


def paste_params(*, pane_id: str, text: str) -> dict[str, object]:
    """Deliver `text` to `pane_id` as ONE bracketed paste, submitting nothing."""
    return {"pane_id": pane_id, "text": text, "keys": []}


def enter_params(*, pane_id: str) -> dict[str, object]:
    """Submit whatever `pane_id` currently holds, delivering no new text."""
    return {"pane_id": pane_id, "text": "", "keys": [ENTER_KEY]}
