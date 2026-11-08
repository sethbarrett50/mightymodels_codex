"""Codex review skill must not invoke Fable or fake user-input dialogs."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translate = SYNC['translated']
native_review_circus_decisions = SYNC['native_review_circus_decisions']


@pytest.mark.unit
def test_review_decision_prompts_and_disabled_override_are_native() -> None:
    generated = translate(ROOT / 'skills/review-circus/SKILL.md')
    assert 'When `review_start` returns `needs input`' in generated
    assert 'ask the user about those finding IDs in ordinary chat' in generated
    assert 'Codex disables the Fable review override.' in generated
    assert 'Never call `review_override`' in generated
    assert 'moving it to fable' not in generated
    assert generated == (ROOT / '.codex/skills/review-circus/SKILL.md').read_text(
        encoding='utf-8'
    )


@pytest.mark.unit
def test_review_translation_refuses_missing_source_steps() -> None:
    with pytest.raises(ValueError, match='exactly one review-circus decision instruction'):
        native_review_circus_decisions('missing')
