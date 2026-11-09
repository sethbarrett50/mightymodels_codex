"""Native reviewer decision gates must not fall back to ordinary-chat choices."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))


@pytest.mark.unit
def test_review_uses_actual_native_question_tool() -> None:
    generated = SYNC['translated'](ROOT / 'skills/review-circus/SKILL.md')
    assert generated == (ROOT / '.codex/skills/review-circus/SKILL.md').read_text()
    assert 'invoke native `request_user_input` for each required choice' in generated
    assert 'invoke native `request_user_input` for those finding IDs' in generated
    assert 'ask for each required choice in ordinary chat' not in generated
    assert 'ask the user about those finding IDs in ordinary chat' not in generated
    assert 'automatic response as consent' in generated


@pytest.mark.unit
def test_review_native_question_translation_rejects_source_drift() -> None:
    with pytest.raises(ValueError, match='exactly one review-circus decision instruction'):
        SYNC['native_review_circus_decisions']('unrelated text')
