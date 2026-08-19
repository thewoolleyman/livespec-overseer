"""registry.py — overseer mapping store + discovery ⋈ mapping join.

Pure-logic, stdlib-only. Host-only tooling under ``.claude/skills/overseer/``:
LOCAL-ONLY and unsynced, but no longer outside the product gates — the folder's
beside-tests and ruff both gate it (``just check-overseer`` / ``just
check-lint``). It remains outside pyright.include, coverage, and import-linter;
those are tracked separately in ``plan/overseer-productization/``. See
``design.md`` beside this file.

Vocabulary (see design.md, the discovery-join model):
  - A "track" is one plan topic in one repo the overseer watches this run.
  - "discovery" = enumerate each watched repo's ``plan/*/`` DIRECTORIES; nothing
    inside one is read, stat-ed, or named.
  - "mapping"   = the durable topic↔tmux rows in ``~/.livespec-overseer.jsonl``,
    which hold ONLY facts that cannot be rederived from the filesystem
    (the plan's ledger ``epic`` id, pinned session id, custom resume line,
    threshold override). The ``epic`` is a track's read-first locator: the daemon
    hands it to sessions and never reads the entries it names.
  - the displayed list = discovery LEFT-JOIN mapping.

The tmux session name is the BARE plan ``<topic>`` (maintainer-declared 2026-07-19);
it is repo-qualified as ``<repo-slug>-<topic>`` (single dash) ONLY when that topic
collides across watched repos, because tmux session names are GLOBAL while plan topics
are only unique per repo (adversarial-review blocker #8). See :func:`tmux_id` /
:func:`colliding_topics`.

**This module is now a FACADE.** Its implementation was split across four private
sibling modules when it crossed the 250-LLOC hard ceiling, at the section banners it
already carried:

  - :mod:`_registry_core`      — the ``Track`` value type, the ``DEFAULT_*``
                                 defaults, and the shared path/lock helpers.
  - :mod:`_registry_store`     — the durable JSONL mapping store.
  - :mod:`_registry_discovery` — plan discovery, the join, the watch set.
  - :mod:`_registry_stamps`    — the injection-stamp sidecar.

Every name below is re-exported, so ``import registry`` remains the whole consumer
surface and no production caller changed. The siblings are ``_``-prefixed because a
private-helper MODULE is exempt from the mirror-test pairing rule, while their shared
members are PUBLIC — the same shape the orchestrator's ``_dispatcher_*`` collaborators
use. That pairing is forced, not stylistic: pyright-strict's ``reportPrivateUsage``
rejects importing an ``_``-prefixed name across modules, so a helper shared between
siblings cannot stay underscore-named once it moves out of one file.
"""

from __future__ import annotations

from _registry_core import DEFAULT_CTX_THRESHOLD as DEFAULT_CTX_THRESHOLD
from _registry_core import DEFAULT_STAMP_PATH as DEFAULT_STAMP_PATH
from _registry_core import DEFAULT_STORE_PATH as DEFAULT_STORE_PATH
from _registry_core import DEFAULT_WATCH_SET_PATH as DEFAULT_WATCH_SET_PATH
from _registry_core import Track as Track
from _registry_core import atomic_write as atomic_write
from _registry_core import colliding_topics as colliding_topics
from _registry_core import file_lock as file_lock
from _registry_core import norm as norm
from _registry_core import repo_slug as repo_slug
from _registry_core import tmux_id as tmux_id
from _registry_discovery import archived_or_gone as archived_or_gone
from _registry_discovery import discover_plans as discover_plans
from _registry_discovery import join as join
from _registry_discovery import plan_liveness_topic as plan_liveness_topic
from _registry_discovery import repo_root_present as repo_root_present
from _registry_discovery import watch_set_from_config as watch_set_from_config
from _registry_epic import epic_from_plan_anchor as epic_from_plan_anchor
from _registry_rounds import RoundRecord as RoundRecord
from _registry_rounds import mark_expiry_notice_sent as mark_expiry_notice_sent
from _registry_rounds import read_round_open_identity as read_round_open_identity
from _registry_rounds import read_round_record as read_round_record
from _registry_rounds import record_ready_expiry as record_ready_expiry
from _registry_stamps import add_notified_band as add_notified_band
from _registry_stamps import clear_injection_stamp as clear_injection_stamp
from _registry_stamps import read_injection_stamp as read_injection_stamp
from _registry_stamps import read_notified_bands as read_notified_bands
from _registry_stamps import read_post_respawn as read_post_respawn
from _registry_stamps import read_resume_pending as read_resume_pending
from _registry_stamps import record_post_respawn as record_post_respawn
from _registry_stamps import set_resume_pending as set_resume_pending
from _registry_stamps import write_injection_stamp as write_injection_stamp
from _registry_store import append_mapping as append_mapping
from _registry_store import read_mapping as read_mapping
from _registry_store import record_derived_epic as record_derived_epic
from _registry_store import record_observed_session_identity as record_observed_session_identity
from _registry_store import remove_mapping as remove_mapping
from _registry_store import repoint_tmux as repoint_tmux
from _registry_store import rewrite_mapping as rewrite_mapping
from _registry_store import set_epic as set_epic

__all__: list[str] = [
    "DEFAULT_CTX_THRESHOLD",
    "DEFAULT_STAMP_PATH",
    "DEFAULT_STORE_PATH",
    "DEFAULT_WATCH_SET_PATH",
    "RoundRecord",
    "Track",
    "add_notified_band",
    "append_mapping",
    "archived_or_gone",
    "atomic_write",
    "clear_injection_stamp",
    "colliding_topics",
    "discover_plans",
    "epic_from_plan_anchor",
    "file_lock",
    "join",
    "mark_expiry_notice_sent",
    "norm",
    "plan_liveness_topic",
    "read_injection_stamp",
    "read_mapping",
    "read_notified_bands",
    "read_post_respawn",
    "read_resume_pending",
    "read_round_open_identity",
    "read_round_record",
    "record_derived_epic",
    "record_observed_session_identity",
    "record_post_respawn",
    "record_ready_expiry",
    "remove_mapping",
    "repo_root_present",
    "repo_slug",
    "repoint_tmux",
    "rewrite_mapping",
    "set_epic",
    "set_resume_pending",
    "tmux_id",
    "watch_set_from_config",
    "write_injection_stamp",
]
