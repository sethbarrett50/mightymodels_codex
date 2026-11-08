"""Codex toolchain survey should inspect native host capabilities without Claude CLIs."""

import tomllib
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_agents.py'))
generate = SYNC['generate']
native_terry_toolchain = SYNC['native_terry_toolchain']


@pytest.mark.unit
def test_toolchain_survey_uses_native_host_inspection() -> None:
    path = '.codex/agents/mm-triage-terry-toolchain.toml'
    generated = generate(ROOT)[path]
    assert generated == (ROOT / path).read_text(encoding='utf-8')
    body = tomllib.loads(generated)['developer_instructions']
    assert 'codex mcp list' in body
    assert 'codex --version' in body
    assert '$HOME/.agents/skills/' in body
    assert 'approval_policy' in body
    assert 'claude mcp list' not in body
    assert 'claude plugin list' not in body
    assert 'claude --version' not in body
    assert 'skill listing is already in your context' not in body


@pytest.mark.unit
def test_toolchain_survey_refuses_unrecognized_source() -> None:
    with pytest.raises(ValueError, match='native toolchain survey start'):
        native_terry_toolchain('unrecognized source')
