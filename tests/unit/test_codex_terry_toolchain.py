"""Check generated Codex Terry survey stays read-only and host-native."""

import tomllib
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_agents.py'))
generate = SYNC['generate']
native_terry_toolchain = SYNC['native_terry_toolchain']


@pytest.mark.unit
def test_terry_native_survey_does_not_invoke_claude_cli() -> None:
    path = '.codex/agents/mm-triage-terry-toolchain.toml'
    generated = generate(ROOT)[path]
    assert generated == (ROOT / path).read_text(encoding='utf-8')
    body = tomllib.loads(generated)['developer_instructions']
    assert 'claude mcp list' not in body
    assert 'claude plugin list' not in body
    assert 'codex plugin list' not in body
    assert 'claude --version' not in body
    assert 'codex mcp list' in body
    assert 'Codex plugin inventory has no assumed CLI' in body
    assert '$HOME/.agents/skills/*/SKILL.md' in body
    assert 'unverified rules under `Not seen`' in body


@pytest.mark.unit
def test_terry_source_drift_is_reported() -> None:
    with pytest.raises(ValueError, match='exactly one Terry survey source section'):
        native_terry_toolchain('missing source text')
