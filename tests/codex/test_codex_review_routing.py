"""Codex review model metadata follows pinned native reviewer configurations."""

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from mightymodels_core.primitives import (
    create_codex_review_routing_table,
    create_routing_table,
)

if TYPE_CHECKING:
    from mightymodels_core.vocabulary.reviews import Depth

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.parametrize('depth', ['quick', 'standard', 'deep'])
def test_codex_review_depth_records_actual_sol_model(depth: Depth) -> None:
    routing = create_codex_review_routing_table()
    assert routing.reviewer_model(depth) == 'gpt-6.1-sol'
    for role in ('merge-vader', 'uncle-bob'):
        toml = (ROOT / '.codex/agents' / f'mm-review-{role}.toml').read_text()
        assert 'model = "gpt-6.1-sol"' in toml
        assert 'model_reasoning_effort = "high"' in toml


@pytest.mark.unit
def test_legacy_claude_review_depth_stays_unchanged() -> None:
    routing = create_routing_table()
    assert routing.reviewer_model('quick') == 'sonnet'
    assert routing.reviewer_model('standard') == 'opus'
    assert routing.reviewer_model('deep') == 'opus'
    assert routing.override_model == 'fable'


@pytest.mark.unit
def test_codex_runtime_switch_requires_explicit_launcher_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module('mightymodels_mcp.review.use_cases')
    monkeypatch.delenv('MIGHTYMODELS_RUNTIME', raising=False)
    assert not module.codex_runtime()
    monkeypatch.setenv('MIGHTYMODELS_RUNTIME', 'codex')
    assert module.codex_runtime()


@pytest.mark.unit
def test_launcher_enables_codex_runtime_and_disables_fable() -> None:
    launcher = (ROOT / 'bin/mightymodels-mcp-codex').read_text()
    tools = (ROOT / 'packages/mcp/src/mightymodels_mcp/review/tools.py').read_text()
    assert 'export MIGHTYMODELS_RUNTIME=codex' in launcher
    assert 'if codex_runtime():' in tools
    assert 'Codex Fable review override disabled' in tools
