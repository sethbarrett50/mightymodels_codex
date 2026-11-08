"""Verify native web-scout transport does not assume Claude web tools."""

import tomllib
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_agents.py'))
generate = SYNC['generate']
native_web_scout_tools = SYNC['native_web_scout_tools']


@pytest.mark.unit
def test_web_scout_uses_available_host_tools_only() -> None:
    path = '.codex/agents/mm-triage-web-scout.toml'
    expected = generate(ROOT)[path]
    assert expected == (ROOT / path).read_text(encoding='utf-8')
    body = tomllib.loads(expected)['developer_instructions']
    assert 'WebSearch' not in body
    assert 'WebFetch' not in body
    assert 'Inspect the tools actually exposed to this agent' in body
    assert 'return UNKNOWN-BLOCKED' in body
    assert 'host-provided web search' in body
    assert 'host-provided web fetch' in body


@pytest.mark.unit
def test_web_scout_translation_fails_closed_on_source_drift() -> None:
    with pytest.raises(ValueError, match='Missing expected upstream web-scout tool references'):
        native_web_scout_tools('no Claude web tools')
