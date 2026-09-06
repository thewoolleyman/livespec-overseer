"""Beside-tests for foreman_gather_sources.py — the repo-config readers.

These re-home coverage the foreman-test deletion took with it. The foreman seat was
retired whole by SPECIFICATION v047 and its tests went with it, but three readers
survived because bucket-1 code still calls them: `_registry_epic` and `ledger_comments`
read `parse_repo_config` and `string_list`, and
`scripts/check-full-autonomy-config-conformance.py` read `parse_repo_config`. The
JSONC line-comment stripper behind `parse_repo_config` is the interesting one — a `//`
inside a JSON string VALUE is data, not a comment, and stripping it silently truncates
a watched repository's configuration.

``import foreman_gather_sources`` resolves via conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import foreman_gather_sources

__all__: list[str] = []


def test_a_trailing_line_comment_is_stripped():
    line = '  "epic": "abc",  // the plan anchor'

    assert foreman_gather_sources.strip_jsonc_line_comment(line=line) == '  "epic": "abc",  '


def test_a_line_with_no_comment_is_returned_unchanged():
    line = '  "repos": ["/data/projects/livespec"],'

    assert foreman_gather_sources.strip_jsonc_line_comment(line=line) == line


def test_a_double_slash_inside_a_json_string_is_data_not_a_comment():
    """A URL value is the ordinary case, and truncating it would corrupt the config."""
    line = '  "remote": "https://example.invalid/repo",'

    assert foreman_gather_sources.strip_jsonc_line_comment(line=line) == line


def test_a_comment_after_a_string_holding_a_double_slash_is_still_stripped():
    line = '  "remote": "https://example.invalid/repo",  // upstream'

    stripped = foreman_gather_sources.strip_jsonc_line_comment(line=line)

    assert stripped == '  "remote": "https://example.invalid/repo",  '


def test_an_escaped_quote_does_not_end_the_string_so_a_later_slash_pair_stays_data():
    r"""`\"` keeps the string open, so the `//` after it is still inside the value."""
    line = r'  "note": "she said \"go//stop\" once",'

    assert foreman_gather_sources.strip_jsonc_line_comment(line=line) == line


def test_a_backslash_outside_a_string_does_not_arm_an_escape():
    """Only an in-string backslash escapes; a stray one must not swallow the next quote."""
    line = r'\ "value": "x" // trailing'

    assert foreman_gather_sources.strip_jsonc_line_comment(line=line) == r'\ "value": "x" '


def test_a_trailing_backslash_inside_a_string_ends_the_line_without_a_comment():
    line = r'  "path": "c:\\tmp\\'

    assert foreman_gather_sources.strip_jsonc_line_comment(line=line) == line


def test_a_lone_slash_is_not_a_comment_opener():
    line = '  "ratio": "1/2",'

    assert foreman_gather_sources.strip_jsonc_line_comment(line=line) == line


def test_parse_repo_config_keeps_a_url_value_whole_while_dropping_comments(
    *, tmp_path: Path
) -> None:
    config = tmp_path / ".livespec.jsonc"
    config.write_text(
        "\n".join(
            (
                "{",
                "  // the watched remote",
                '  "remote": "https://example.invalid/repo", // upstream',
                '  "slug": "demo"',
                "}",
            )
        ),
        encoding="utf-8",
    )

    parsed = foreman_gather_sources.parse_repo_config(repo=tmp_path)

    assert parsed == {"remote": "https://example.invalid/repo", "slug": "demo"}


def test_parse_repo_config_is_none_when_the_file_is_absent(*, tmp_path: Path) -> None:
    assert foreman_gather_sources.parse_repo_config(repo=tmp_path) is None


def test_parse_repo_config_is_none_when_the_stripped_text_is_not_an_object(
    *, tmp_path: Path
) -> None:
    (tmp_path / ".livespec.jsonc").write_text("// only a comment\n", encoding="utf-8")

    assert foreman_gather_sources.parse_repo_config(repo=tmp_path) is None


def test_string_list_accepts_a_list_of_strings():
    assert foreman_gather_sources.string_list(value=["a", "b"]) == ["a", "b"]


def test_string_list_rejects_a_list_holding_a_non_string():
    assert foreman_gather_sources.string_list(value=["a", 1]) is None


def test_string_list_rejects_a_value_that_is_not_a_list():
    assert foreman_gather_sources.string_list(value="a") is None
