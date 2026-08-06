"""The consensus tier must be REACHABLE, not merely implemented.

WHY THIS FILE EXISTS. Every deterministic artifact of the consensus panel was
built, merged, released and proven end-to-end through the shipped executables —
and the foreman still could not have used any of it, because
`.claude-plugin/prose/foreman.md` told it "Do not add Phase C consensus, Phase D
gate driving". That prose is not documentation: `SKILL.md` is a thin binding
carrying no behavior of its own, which delegates the entire operator contract to
the prose and instructs the model to execute it end-to-end. The foreman is an LLM
session, so the prose IS the control flow.

So the gap was invisible to every existing gate. The subprocess E2E proved the
chain WORKS; nothing asked whether the shipped instructions permit calling it.
This module asks that, from two directions:

  1. BEHAVIOUR — the shipped `foreman-valve-disposition` executable resolves the
     tier correctly from real config, under a scrubbed environment.
  2. CONTRACT — the shipped prose routes the decision through that resolver and
     does not carry a blanket prohibition on the tier.

Leg 2 is a prose assertion, which is normally weak. It is justified here because
the prose is the executed artifact for the LLM half of this product, and because
the defect it catches actually shipped in release 0.33.0.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = ROOT / ".claude-plugin"
ENTRYPOINT = PLUGIN_ROOT / "bin" / "foreman-valve-disposition"
PROSE = PLUGIN_ROOT / "prose" / "foreman.md"


def _scrubbed_env() -> dict[str, str]:
    removed = {"PYTHONPATH", "COVERAGE_PROCESS_START"}
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in removed and not key.startswith("COV_CORE_")
    }
    assert "PYTHONPATH" not in env
    return env


def _resolve(*, repo: Path) -> dict[str, object]:
    """Execute the SHIPPED entrypoint, never an imported module."""
    completed = subprocess.run(  # noqa: S603
        [str(ENTRYPOINT), "--repo", str(repo)],
        capture_output=True,
        text=True,
        check=False,
        env={**_scrubbed_env(), "PYTHONPATH": ""},
    )
    assert completed.returncode == 0, completed.stderr
    parsed = json.loads(completed.stdout)
    assert isinstance(parsed, dict)
    return parsed


def _repo_with(*, tmp_path: Path, value: object | None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    config: dict[str, object] = {}
    if value is not None:
        config["livespec-overseer"] = {"foreman_valve_disposition": value}
    (repo / ".livespec.jsonc").write_text(json.dumps(config), encoding="utf-8")
    return repo


def test_unset_disposition_fails_closed_to_report_only(*, tmp_path: Path) -> None:
    """An absent key must resolve to report-only, from the SHIPPED executable."""
    resolved = _resolve(repo=_repo_with(tmp_path=tmp_path, value=None))
    assert resolved["effective"] == "report-only"
    assert resolved["configured"] is None
    assert resolved["source"] == "default"


def test_consensus_tier_is_reachable_by_configuration(*, tmp_path: Path) -> None:
    """THE POINT OF THIS MODULE: the opt-in tier can actually be selected.

    If this fails, the panel is unreachable no matter how well it works.
    """
    resolved = _resolve(repo=_repo_with(tmp_path=tmp_path, value="consensus"))
    assert resolved["effective"] == "consensus"
    assert resolved["recognized"] is True


def test_unrecognized_value_fails_closed_and_says_so(*, tmp_path: Path) -> None:
    """A typo must not silently arm or silently disarm; it must be reported.

    This is the discriminating control for the two tests above: it proves the
    resolver distinguishes VALUES rather than merely echoing whatever it is given.
    """
    resolved = _resolve(repo=_repo_with(tmp_path=tmp_path, value="consensuss"))
    assert resolved["effective"] == "report-only"
    assert resolved["recognized"] is False
    assert resolved["warning"] == "unrecognized_foreman_valve_disposition"


def test_shipped_prose_routes_the_valve_through_the_resolver() -> None:
    """The operator contract must NAME the resolver it is supposed to consult.

    Sabotage that reddens this: delete the `foreman-valve-disposition` invocation
    from the prose. The foreman would then have no instruction to resolve the
    tier, and would fall back to whatever it assumed — which is exactly the
    failure this module exists to prevent.
    """
    text = PROSE.read_text(encoding="utf-8")
    assert "foreman-valve-disposition" in text
    assert "report-only" in text
    assert "consensus" in text


def test_shipped_prose_does_not_forbid_the_tier_it_ships() -> None:
    """The regression that actually shipped, in release 0.33.0.

    The prose read "Do not add Phase C consensus, Phase D gate driving, or Phase
    E federation behavior" while the consensus panel and the gate-driving
    interlock were both merged, released and proven. A blanket prohibition makes
    the shipped tier unreachable and contradicts the ratified config key.

    Phase E federation genuinely is NOT built, so prohibiting THAT is correct and
    must stay. This asserts the narrow thing: no blanket ban on the tiers that do
    ship.
    """
    text = PROSE.read_text(encoding="utf-8")
    assert "Do not add Phase C consensus" not in text
    assert "Phase D gate driving" not in text
    assert "Phase A+B v1 foreman only" not in text
    # The genuinely-unbuilt phase must still be fenced off.
    assert "Phase E federation" in text


def test_the_floors_survive_the_unfencing() -> None:
    """Making the tier reachable must not relax the ratified hard floors.

    v007: no configuration value may authorize disposing of a truly unresolvable
    decision, nor of any decision human-gated by design.
    """
    text = PROSE.read_text(encoding="utf-8")
    assert "truly unresolvable" in text
    assert "human-gated BY DESIGN" in text
    assert "Journal before you act" in text
