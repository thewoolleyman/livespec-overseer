"""Tests for registry.py — plan discovery, the discovery-mapping join, and the watch set.

Split out of `test_registry.py` at the section banners it already carried, when
that module crossed the 250-LLOC hard ceiling. This module owns `discover_plans`,
the LEFT JOIN that fills discovered plans from the mapping and marks the rest
unassigned, and the manifest-JSONC watch set (including the JSONC parser
underneath it). The store API itself lives in `test_registry.py`.

``import registry`` resolves via conftest.py.
"""

import json
from pathlib import Path

import _registry_discovery
import pytest
import registry
from registry import Track

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Every test runs with cwd inside tmp_path (repo convention)."""
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Discovery.
# --------------------------------------------------------------------------- #


def _make_plan(repo, topic, *, with_handoff=True):
    plan_topic = repo / "plan" / topic
    plan_topic.mkdir(parents=True, exist_ok=True)
    if with_handoff:
        (plan_topic / "handoff.md").write_text("handoff\n", encoding="utf-8")
    return plan_topic


def test_discover_plans_excludes_archive(tmp_path):
    repo = tmp_path / "repo"
    _make_plan(repo, "topic-a")
    _make_plan(repo, "topic-b")
    # Directory existence IS the track now — a plan/<topic>/ dir with NO handoff.md
    # is still discovered (the handoff path is only a conventional pointer).
    _make_plan(repo, "no-handoff", with_handoff=False)
    # An archived plan (under plan/archive/) must still be excluded.
    archived = repo / "plan" / "archive" / "old-topic"
    archived.mkdir(parents=True)
    (archived / "handoff.md").write_text("old\n", encoding="utf-8")
    # A stray FILE directly under plan/ must be ignored (only child DIRS are tracks).
    (repo / "plan" / "README.md").write_text("x\n", encoding="utf-8")

    triples = registry.discover_plans(watch_repos=[repo])
    topics = [topic for _repo, topic, _handoff in triples]
    # Every plan/<topic>/ dir is a track (sorted); the literal 'archive' dir excluded.
    assert topics == ["no-handoff", "topic-a", "topic-b"]
    # The handoff path is the conventional <topic>/handoff.md pointer (need not exist).
    assert triples[0][2].endswith("/repo/plan/no-handoff/handoff.md")


def test_discover_plans_fail_soft_on_missing_plan_dir(tmp_path):
    repo = tmp_path / "repo-without-plan"
    repo.mkdir()
    assert registry.discover_plans(watch_repos=[repo]) == []


def test_discover_plans_fail_soft_on_an_unreadable_plan_dir(tmp_path, monkeypatch, capsys):
    """B7: a plan/ that becomes unlistable between the is_dir check and iterdir
    (chmod, NFS hiccup, mid-clone) skips that ONE repo — every other watched repo
    still contributes, rather than the whole discovery pass crashing the daemon.

    ``iterdir`` is denied for the poisoned repo only, rather than via ``chmod`` —
    CI runs as root, where mode bits deny nothing. Matching on the repo directory
    NAME rather than on path equality keeps this robust against the path
    normalization ``discover_plans`` applies before building ``plan_dir``.
    """
    poisoned = tmp_path / "repo-poisoned"
    _make_plan(poisoned, "topic-a")
    healthy = tmp_path / "repo-healthy"
    _make_plan(healthy, "topic-b")
    real_iterdir = Path.iterdir

    def _deny(self):
        if self.name == "plan" and self.parent.name == "repo-poisoned":
            raise PermissionError(13, "Permission denied")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _deny)
    triples = registry.discover_plans(watch_repos=[poisoned, healthy])

    assert [(registry.repo_slug(repo=r), t) for r, t, _h in triples] == [
        ("repo-healthy", "topic-b")
    ]
    assert "unreadable plan dir" in capsys.readouterr().err


def test_discover_plans_fail_soft_on_an_unreadable_plan_child(tmp_path, monkeypatch, capsys):
    """B7: with plan/ listable but one child un-stattable, iterdir still lists the
    children while stat'ing one raises — that child is dropped and named, and the
    rest of the discovery set survives.

    The raise is injected at ``Path.is_dir`` for that ONE child, rather than via a
    ``chmod(0o444)`` on the parent — CI runs as root, where mode bits deny nothing.
    Keying on the child's own name leaves ``plan_dir.is_dir()`` (the guard just
    above the loop) working normally, which is what isolates this to the child.
    """
    poisoned = tmp_path / "repo-poisoned"
    _make_plan(poisoned, "unstattable")
    healthy = tmp_path / "repo-healthy"
    _make_plan(healthy, "topic-b")
    real_is_dir = Path.is_dir

    def _deny(self):
        if self.name == "unstattable":
            raise PermissionError(13, "Permission denied")
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", _deny)
    triples = registry.discover_plans(watch_repos=[poisoned, healthy])

    assert [(registry.repo_slug(repo=r), t) for r, t, _h in triples] == [
        ("repo-healthy", "topic-b")
    ]
    assert "unreadable plan child" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Join = discovery LEFT-JOIN mapping.
# --------------------------------------------------------------------------- #


def test_join_left_join_fills_and_marks_unassigned(tmp_path):
    repo = str(tmp_path / "repo")
    discovered = [
        (repo, "mapped", f"{repo}/plan/mapped/handoff.md"),
        (repo, "unmapped", f"{repo}/plan/unmapped/handoff.md"),
    ]
    mapping = [
        Track(topic="mapped", repo=repo, tmux="repo:mapped", handoff=None),  # no handoff
    ]
    rows = registry.join(discovered, mapping)
    by_topic = {t.topic: t for t in rows}

    assert by_topic["mapped"].assigned is True
    assert by_topic["mapped"].tmux == "repo:mapped"
    # Handoff filled from discovery because the mapping row lacked one.
    assert by_topic["mapped"].handoff == f"{repo}/plan/mapped/handoff.md"

    assert by_topic["unmapped"].is_unassigned is True
    assert by_topic["unmapped"].tmux is None
    assert by_topic["unmapped"].handoff == f"{repo}/plan/unmapped/handoff.md"


def test_join_is_repo_qualified_no_cross_link(tmp_path):
    """Two repos share topic 'shared'; a mapping for only one must not
    cross-link to the other (adversarial-review blocker #8)."""
    repo_a = str(tmp_path / "repo-a")
    repo_b = str(tmp_path / "repo-b")
    discovered = [
        (repo_a, "shared", f"{repo_a}/plan/shared/handoff.md"),
        (repo_b, "shared", f"{repo_b}/plan/shared/handoff.md"),
    ]
    mapping = [Track(topic="shared", repo=repo_a, tmux="repo-a:shared")]
    rows = registry.join(discovered, mapping)
    by_repo = {t.repo: t for t in rows}
    assert by_repo[repo_a].assigned is True
    assert by_repo[repo_a].tmux == "repo-a:shared"
    assert by_repo[repo_b].is_unassigned is True


# --------------------------------------------------------------------------- #
# watch_set (manifest JSONC → local checkouts with a plan/ dir).
# --------------------------------------------------------------------------- #


def _write_watch_set(path, repos):
    path.write_text(json.dumps({"repos": [str(r) for r in repos]}), encoding="utf-8")
    return path


def test_watch_set_from_config_admits_only_cloned_repos_that_carry_a_plan_dir(tmp_path):
    """The `$HOME` declaration applies the SAME admission rule the manifest path applied:
    a declared repo counts only if its checkout exists AND has a `plan/` dir. Keeping the
    rule identical is what makes the relocation a move rather than a behavior change."""
    alpha = tmp_path / "alpha"
    (alpha / "plan").mkdir(parents=True)
    (tmp_path / "gamma").mkdir()  # cloned, but no plan/ dir
    declaration = _write_watch_set(
        tmp_path / "repos.json",
        [alpha, tmp_path / "beta", tmp_path / "gamma"],  # beta is not cloned
    )

    result = registry.watch_set_from_config(config_path=declaration)

    assert [registry.repo_slug(repo=p) for p in result] == ["alpha"]
    assert all(p == registry.norm(repo=p) for p in result)  # normalized absolute


def test_watch_set_from_config_admits_a_repo_with_no_assigned_track(tmp_path):
    """A declared repo with a plan but ZERO mapping rows must still be watched — that is
    the whole reason the watch-set cannot be derived from the mapping store's own rows.
    Discovery has to reach repos with no assigned track in order to surface their
    UNASSIGNED plans; deriving from assigned rows would make a brand-new plan invisible
    until someone had already assigned it."""
    fresh = tmp_path / "fresh"
    (fresh / "plan" / "brand-new-topic").mkdir(parents=True)
    declaration = _write_watch_set(tmp_path / "repos.json", [fresh])

    assert [
        registry.repo_slug(repo=p) for p in registry.watch_set_from_config(config_path=declaration)
    ] == ["fresh"]


def test_watch_set_from_config_fail_soft_on_absent_declaration(tmp_path):
    """An absent declaration is the ordinary FIRST-RUN state, not a crash: warn and fall
    back to the extras, matching how the manifest path failed soft."""
    extra = tmp_path / "extra"
    extra.mkdir()

    result = registry.watch_set_from_config(config_path=tmp_path / "nope.json", extra_repos=[extra])

    assert [registry.repo_slug(repo=p) for p in result] == ["extra"]


def test_watch_set_from_config_fail_soft_on_malformed_declaration(tmp_path):
    """Unparsable JSON warns and yields the extras rather than taking the daemon down."""
    declaration = tmp_path / "repos.json"
    declaration.write_text("{ not json", encoding="utf-8")
    extra = tmp_path / "extra"
    extra.mkdir()

    result = registry.watch_set_from_config(config_path=declaration, extra_repos=[extra])

    assert [registry.repo_slug(repo=p) for p in result] == ["extra"]


def test_watch_set_from_config_fail_soft_when_repos_key_is_missing_or_wrong_type(tmp_path):
    """A well-formed document whose `repos` is absent or not a list is a DISTINCT failure
    from unparsable bytes, and is reported separately rather than silently yielding an
    empty watch-set that looks like 'nothing to supervise'."""
    for payload in ('{"repos": "not-a-list"}', "{}"):
        declaration = tmp_path / "repos.json"
        declaration.write_text(payload, encoding="utf-8")

        assert registry.watch_set_from_config(config_path=declaration) == []


def test_watch_set_from_config_ignores_non_string_entries(tmp_path):
    """A declaration is hand-edited, so a stray non-string entry must be skipped rather
    than crashing the whole enumeration — name the good rows, drop the bad one."""
    alpha = tmp_path / "alpha"
    (alpha / "plan").mkdir(parents=True)
    declaration = tmp_path / "repos.json"
    declaration.write_text(json.dumps({"repos": [str(alpha), 17, None]}), encoding="utf-8")

    assert [
        registry.repo_slug(repo=p) for p in registry.watch_set_from_config(config_path=declaration)
    ] == ["alpha"]


def test_watch_set_from_config_skips_an_extra_that_is_not_cloned(tmp_path):
    """An `extra_repos` override naming a path that does not exist is skipped, and the
    scan CONTINUES to the remaining extras rather than aborting — the same
    name-the-good-rows-and-drop-the-bad discipline the declared entries get."""
    present = tmp_path / "present"
    present.mkdir()
    declaration = _write_watch_set(tmp_path / "repos.json", [])

    result = registry.watch_set_from_config(
        config_path=declaration, extra_repos=[tmp_path / "absent", present]
    )

    assert [registry.repo_slug(repo=p) for p in result] == ["present"]


def test_watch_set_from_config_dedupes_a_repo_named_twice(tmp_path):
    """A repo both declared and passed as an extra appears ONCE — the dedupe the manifest
    path performed must survive the move."""
    alpha = tmp_path / "alpha"
    (alpha / "plan").mkdir(parents=True)
    declaration = _write_watch_set(tmp_path / "repos.json", [alpha])

    result = registry.watch_set_from_config(config_path=declaration, extra_repos=[alpha])

    assert [registry.repo_slug(repo=p) for p in result] == ["alpha"]


def test_parse_jsonc_is_string_aware_and_tolerates_trailing_comma():
    text = (
        "{\n"
        '  "url": "http://example.com/a//b",  // trailing line comment\n'
        "  /* block comment */\n"
        '  "items": ["a", "b",],\n'  # trailing comma
        "}\n"
    )
    parsed = _registry_discovery._parse_jsonc(text=text)
    assert parsed["url"] == "http://example.com/a//b"  # // inside string preserved
    assert parsed["items"] == ["a", "b"]


def test_parse_jsonc_honors_backslash_escapes_inside_a_string_literal():
    # A BACKSLASH-ESCAPED quote does not end the literal, so the `//` and `/*` that
    # follow it are still INSIDE the string and must survive stripping. An escaped
    # backslash is likewise consumed as one character, not as an escape of the quote.
    parsed = _registry_discovery._parse_jsonc(text=r'{"a": "x\"y // z /* w */", "b": "trailing\\"}')
    assert parsed["a"] == 'x"y // z /* w */'
    assert parsed["b"] == "trailing\\"


def test_strip_jsonc_comments_consumes_an_unterminated_string_literal():
    # The stripper is not a validator: an unterminated literal runs to the end of
    # the input, so the `//` inside it is preserved rather than treated as the
    # start of a comment. Reporting the malformed JSON is json.loads's job.
    text = '{"a": "unterminated // not-a-comment'
    assert _registry_discovery._strip_jsonc_comments(text=text) == text
    with pytest.raises(json.JSONDecodeError):
        _registry_discovery._parse_jsonc(text=text)


def test_archived_or_gone(tmp_path):
    repo = tmp_path / "repo"
    _make_plan(repo, "live")
    assert registry.archived_or_gone(repo=str(repo), topic="live") is False
    # Gone entirely.
    assert registry.archived_or_gone(repo=str(repo), topic="never-existed") is True
    # Moved under plan/archive/.
    archived = repo / "plan" / "archive" / "retired"
    archived.mkdir(parents=True)
    assert registry.archived_or_gone(repo=str(repo), topic="retired") is True
