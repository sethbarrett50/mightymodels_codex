"""Verify Codex landing dispatch uses native role routing rather than Claude aliases."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translate = SYNC['translated']
native_landing_decisions = SYNC['native_landing_decisions']


@pytest.mark.unit
def test_landing_uses_native_models_and_requires_real_approval() -> None:
    generated = translate(ROOT / 'skills/stick-the-landing/SKILL.md')
    assert generated == (ROOT / '.codex/skills/stick-the-landing/SKILL.md').read_text(
        encoding='utf-8'
    )
    assert 'registered native Codex roles' in generated
    assert 'proof of the effective host model' in generated
    assert 'Models are the fixed aliases' not in generated
    assert 'ask in ordinary chat whether to review now or hand off' in generated


@pytest.mark.unit
def test_landing_model_routing_refuses_source_drift() -> None:
    with pytest.raises(ValueError, match='exactly one landing decision instruction'):
        native_landing_decisions('not the original steps')
