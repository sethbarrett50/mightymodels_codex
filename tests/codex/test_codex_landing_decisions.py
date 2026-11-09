"""Native Codex landing must wait for explicit review-or-handoff choice."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translated = SYNC['translated']
native_landing_decisions = SYNC['native_landing_decisions']
native_landing_frontmatter = SYNC['native_landing_frontmatter']


@pytest.mark.unit
def test_landing_asks_natively_and_matches_generated_asset() -> None:
    generated = translated(ROOT / 'skills/stick-the-landing/SKILL.md')
    assert 'invoke native `request_user_input` in Default or Plan mode' in generated
    assert 'stop with the decision pending' in generated
    assert 'Neither timeout nor auto-resolution is consent' in generated
    assert 'ask once through `Codex user decision gate`' not in generated
    assert generated == (ROOT / '.codex/skills/stick-the-landing/SKILL.md').read_text(
        encoding='utf-8'
    )


@pytest.mark.unit
def test_landing_translation_refuses_missing_decision_step() -> None:
    with pytest.raises(ValueError, match='exactly one landing decision instruction'):
        native_landing_decisions('missing')


@pytest.mark.unit
def test_landing_frontmatter_translation_refuses_source_drift() -> None:
    with pytest.raises(ValueError, match='exactly one landing frontmatter'):
        native_landing_frontmatter('missing')
