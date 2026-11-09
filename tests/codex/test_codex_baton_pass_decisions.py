"""Codex baton handoffs cannot rely on unverified question-recorder hooks."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translated = GENERATOR['translated']
native_baton_pass_decisions = GENERATOR['native_baton_pass_decisions']


@pytest.mark.unit
def test_baton_requires_native_questions_and_durable_handoff() -> None:
    generated = translated(ROOT / 'skills/baton-pass/SKILL.md')
    assert 'Use native `request_user_input` for the next-session focus' in generated
    assert 'end the turn until the user explicitly answers' in ' '.join(generated.split())
    assert "Preserve only the user's actual" in generated
    assert 'do not claim a persisted handoff' in generated
    assert 'recorder hook on `Codex user decision gate` already stored' not in generated
    assert generated == (ROOT / '.codex/skills/baton-pass/SKILL.md').read_text(encoding='utf-8')


@pytest.mark.unit
def test_baton_translation_rejects_absent_question_steps() -> None:
    with pytest.raises(ValueError, match='exactly one baton-pass decision instruction'):
        native_baton_pass_decisions('no decision steps')
