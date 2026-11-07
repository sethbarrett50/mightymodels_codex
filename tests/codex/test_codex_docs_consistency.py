"""Keep public Codex metadata consistent with the generated role inventory."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_codex_documented_agent_counts() -> None:
    report = json.loads((ROOT / '.codex/compatibility-report.json').read_text())
    agents = report['agents']
    enabled = [agent for agent in agents if 'codex_model' in agent]
    disabled = [agent for agent in agents if 'codex_status' in agent]
    assert report['count'] == len(agents) == 12
    assert len(enabled) == 11
    assert len(disabled) == 1
    assert disabled[0]['role'] == 'mm-triage-wingman'
    assert len(list((ROOT / '.codex/agents').glob('mm-*.toml'))) == 11
    assert len(list((ROOT / '.codex/skills').glob('*/SKILL.md'))) == 19

    readme = (ROOT / 'README.md').read_text()
    guide = (ROOT / 'docs/CODEX.md').read_text()
    assert '11 enabled native Codex agents' in readme
    assert '11 enabled agents' in guide
    assert '12 native Codex agents' not in readme
    assert 'each of the 12 roles explicitly' not in guide
    assert 'symlinks the 12 native roles' not in guide
    assert 'experimental' in readme.lower()
    assert 'host-verified' in readme
