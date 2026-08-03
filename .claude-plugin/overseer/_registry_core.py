"""Shared leaf for the registry modules — the Track value type and store defaults.

Extracted when `registry.py` crossed the 250-LLOC hard ceiling. This module is the
LEAF of the registry package: it imports nothing from its siblings, and each of
`_registry_store`, `_registry_discovery` and `_registry_stamps` imports from it.
`registry.py` re-exports the whole surface, so consumers keep importing `registry`.

`resolve_store` and `resolve_stamp_store` live HERE, beside the `DEFAULT_*_PATH` constants they
read, and that placement is load-bearing rather than tidy. Both resolve their
default by reading a module global, so a test that redirects the default away from
the developer's real `$HOME` must patch the module the READER lives in. Splitting
the reader from the constant would leave `monkeypatch.setattr(...)` silently
ineffective — the attribute would still exist and still be set, while the resolver
kept returning the real home path.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import tempfile
from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import signals
import streams

__all__: list[str] = [
    "DEFAULT_CTX_THRESHOLD",
    "DEFAULT_STAMP_PATH",
    "DEFAULT_STORE_PATH",
    "DEFAULT_WATCH_SET_PATH",
    "ROW_KEYS",
    "Track",
    "atomic_write",
    "colliding_topics",
    "file_lock",
    "norm",
    "repo_slug",
    "resolve_stamp_store",
    "resolve_store",
    "tmux_id",
]


@contextlib.contextmanager
def file_lock(*, target: str | os.PathLike[str]) -> Iterator[None]:
    """Hold an exclusive advisory lock spanning a read-modify-write of ``target``.

    The mapping store and the injection-stamp sidecar are read-modify-written by
    the daemon AND — per the shipped two-pane topology — the bottom-pane CLI
    (`add`/`remove`/`start`) at the same time; without a lock an interleaving
    silently drops a freshly-added live row or a pending track's stamp
    (adversarial code review 2026-07-13, blocker B6). A ``<target>.lock`` sidecar
    is flock'd LOCK_EX for the whole critical section. Fail-soft: if the lock file
    cannot be created/locked (e.g. an unwritable dir), proceed unlocked rather
    than crash — losing the race is better than losing the daemon.
    """
    lock_path = Path(str(target) + ".lock")
    handle = None
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("w", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    except OSError as exc:
        warn(message=f"could not acquire lock {lock_path}: {exc}; proceeding unlocked")
        if handle is not None:
            handle.close()
            handle = None
    try:
        yield
    finally:
        if handle is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


# The default remaining-context threshold (percent LEFT) at which the first
# wrap-up is injected. Overridable per-daemon via `overseerd --warn-percent` and
# per-track via a mapping-store override.
DEFAULT_CTX_THRESHOLD = 50

# The durable mapping store and the injection-stamp sidecar both live beside
# the maintainer's home dir (NOT inside any governed repo — the single
# `.overseer-state` file, under the repo's gitignored `tmp/`, is the only overseer
# state that lives inside a governed repo). Both paths are parameterizable so tests can point
# them at a tmp_path.
DEFAULT_STORE_PATH = Path.home() / ".livespec-overseer.jsonl"
DEFAULT_STAMP_PATH = Path.home() / ".livespec-overseer-stamps.json"
# The watch-set declaration: which repo checkouts this host supervises. It sits
# beside the two sidecars above for one reason beyond tidiness — it is what lets
# a relocated overseer learn its watch-set WITHOUT reading
# `.livespec-fleet-manifest.jsonc`, which decision D5 forbids a shipped overseer
# from depending on (that manifest is fleet self-application infrastructure, not
# a contract a governed consumer inherits). Keeping the declaration in `$HOME`
# also keeps the daemon's invocation surface knob-free, honoring the deliberate
# de-gold-plating that removed `--repos` / `--manifest` / `--store` / `--stamp`.
DEFAULT_WATCH_SET_PATH = Path.home() / ".livespec-overseer-repos.json"

# The durable keys serialized to a mapping row. `added_at` is written on append
# but is not a Track field (it is bookkeeping only).
ROW_KEYS = (
    "topic",
    "repo",
    "tmux",
    "handoff",
    "resume",
    "epic",
    "ctx_threshold",
    "pinned_session_id",
)


def warn(*, message: str) -> None:
    """Emit a fail-soft diagnostic to stderr (never crash the caller)."""
    streams.write_stderr(text=f"overseer.registry: {message}\n")


def norm(*, repo: str | os.PathLike[str]) -> str:
    """Normalize a repo path for join/index keys (no filesystem access).

    ``os.path.normpath`` collapses ``..`` and trailing slashes and does NOT
    follow symlinks, so it is a pure, deterministic key derivation. Both sides
    of the discovery ⋈ mapping join must normalize identically or the join
    silently drops rows.
    """
    return os.path.normpath(str(repo))


def repo_slug(*, repo: str | os.PathLike[str]) -> str:
    """The repo-slug used to repo-qualify a tmux session id — the basename."""
    return Path(repo).name


def _reserved_session_refusal(*, repo: str | os.PathLike[str], topic: str, session: str) -> str:
    return (
        f"refusing reserved supervisor session name {session} "
        f"for {norm(repo=repo)}::{topic}; "
        "worker sessions may not end in -supervisor or -foreman"
    )


def colliding_topics(
    *,
    discovered: Iterable[tuple[str, str, str]],
) -> frozenset[str]:
    """Topics that appear in >=2 DISTINCT watched repos.

    ``discovered`` is the ``(repo, topic, handoff)`` triple list from
    :func:`discover_plans`. A topic in this set would collide on its bare tmux
    name if two of its repos ran at once (tmux session names are global), so
    :func:`tmux_id` repo-qualifies exactly these — and nothing else. Repos are
    de-duplicated via :func:`norm` (the same key both sides of the join use), so
    the SAME repo discovered twice never counts as a collision.
    """
    repos_by_topic: dict[str, set[str]] = {}
    for repo, topic, _ in discovered:
        if signals.topic_reserved_for_supervisor(topic=topic):
            warn(message=f"refusing reserved supervisor topic in collision set: {repo}::{topic}")
            continue
        repos_by_topic.setdefault(topic, set()).add(norm(repo=repo))
    return frozenset(t for t, repos in repos_by_topic.items() if len(repos) > 1)


def tmux_id(
    *,
    repo: str | os.PathLike[str],
    topic: str,
    colliding: Collection[str] = frozenset(),
) -> str:
    """The tmux session name for a plan ``topic``.

    Default is the **bare plan topic** (maintainer-declared 2026-07-19): a session
    is named after the plan topic the operator reads and navigates by, NOT
    repo-qualified. A repo prefix is added ONLY on a real cross-repo collision —
    when the SAME topic exists in more than one watched repo (``topic in
    colliding``) — as ``<repo-slug>-<topic>`` with a **single** dash. tmux session
    names are global, so two live sessions cannot both be named ``<topic>``; the
    single-dash prefix disambiguates exactly those clashes and nothing else.

    ``colliding`` is the set of topics appearing in >=2 watched repos, from
    :func:`colliding_topics` over the discovery set. The default (empty) means "no
    known collisions" and yields the bare topic; a caller holding the discovery
    set SHOULD pass the real collision set so a genuine clash is prefixed.

    Both forms are tmux-legal and round-trip: the separator is ``-`` (NOT ``:`` or
    ``.``, which tmux ≥3.3 SANITIZES to ``_`` in a ``new-session -s`` name, breaking
    ``-t`` lookup — adversarial code review blocker B1, 2026-07-13). A plan topic
    itself may contain dashes (e.g. ``autonomous-mode``); that is fine, a dash is
    never sanitized. The predecessor ``<repo-slug>--<topic>`` (double-dash, ALWAYS
    prefixed) form is retired.
    """
    session = f"{repo_slug(repo=repo)}-{topic}" if topic in colliding else topic
    if signals.topic_reserved_for_supervisor(topic=session):
        raise ValueError(_reserved_session_refusal(repo=repo, topic=topic, session=session))
    return session


@dataclass(frozen=True, kw_only=True)
class Track:
    """One overseer row: a plan topic in a repo, possibly mapped to a session.

    Frozen + keyword-only. A *mapped* track (``assigned=True``) carries the
    durable facts from a ``~/.livespec-overseer.jsonl`` row. An *unassigned*
    track (``assigned=False``, blank ``tmux``) is a discovered plan with no
    mapping row — build it via :meth:`make_unassigned`.
    """

    topic: str
    repo: str
    tmux: str | None = None
    handoff: str | None = None
    resume: str | None = None
    epic: str | None = None
    # None = NO per-track override → inherit the daemon-wide default warn
    # threshold (``Supervisor.warn_percent``, itself defaulting to
    # ``DEFAULT_CTX_THRESHOLD``). An int is an explicit per-track override that
    # wins over the daemon default. Serialized only when set (the row omits the
    # key when None) so a bare row means "no override".
    ctx_threshold: int | None = None
    pinned_session_id: str | None = None
    assigned: bool = True

    @property
    def is_unassigned(self) -> bool:
        return not self.assigned

    @classmethod
    def make_unassigned(
        cls,
        *,
        repo: str,
        topic: str,
        handoff: str | None = None,
    ) -> Track:
        """A discovered-but-unmapped track: blank tmux, status `unassigned`."""
        return cls(
            topic=topic,
            repo=repo,
            tmux=None,
            handoff=handoff,
            assigned=False,
        )


# --------------------------------------------------------------------------- #
# Mapping store: read / append / remove-by-(repo,topic) / rewrite-filter.
# JSONL = one JSON object per line. Fail SOFT on a malformed line.
# --------------------------------------------------------------------------- #


def resolve_store(*, store_path: str | os.PathLike[str] | None) -> Path:
    return Path(store_path) if store_path is not None else DEFAULT_STORE_PATH


# --------------------------------------------------------------------------- #
# Injection-stamp sidecar: the per-track timestamp the restart-authorization check
# compares the `.overseer-state` file's mtime against (a `ready` must be THIS round's).
# --------------------------------------------------------------------------- #


def resolve_stamp_store(*, stamp_path: str | os.PathLike[str] | None) -> Path:
    return Path(stamp_path) if stamp_path is not None else DEFAULT_STAMP_PATH


def atomic_write(*, path: Path, body: str, raise_errors: bool = False) -> None:
    """Write ``body`` to ``path`` atomically: temp file in the same dir + os.replace.

    A bare truncate-then-write (the old ``path.write_text``) leaves a
    truncated/partial store if the process dies mid-write — and this store is
    rewritten every ~10s tick, so that window recurs constantly (adversarial code
    review 2026-07-13, blocker B6). ``os.replace`` is atomic on POSIX, so a reader
    always sees either the old or the new complete file, never a partial one.
    Fail-soft by default: an OSError is warned, not raised (B7). Callers that need
    their own edge reporting can set ``raise_errors`` after the shared warning.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                _ = handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            _ = Path(tmp_name).replace(path)
        except OSError:
            with contextlib.suppress(OSError):
                Path(tmp_name).unlink()
            raise
    except OSError as exc:
        warn(message=f"could not write {path}: {exc}")
        if raise_errors:
            raise
