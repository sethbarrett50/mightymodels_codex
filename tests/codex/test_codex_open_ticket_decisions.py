"""Codex open-ticket must pause for actual user input instead of fake dialogs."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translated = GENERATOR['translated']
native_open_ticket_decisions = GENERATOR['native_open_ticket_decisions']


@pytest.mark.unit
def test_open_ticket_decisions_use_native_input_and_generated_output_is_current() -> None:
    generated = translated(ROOT / 'skills/open-ticket/SKILL.md')
    assert (
        'Ask only unanswered interview questions using native `request_user_input`'
        in generated
    )
    assert 'never auto-select or continue' in generated
    assert 'then call `ticket_write` again using those actual answers' in generated
    assert 'Ask once using native `request_user_input` when exposed in Default or Plan mode' in generated
    assert 'One `Codex user decision gate` dialog' not in generated
    assert 'one `Codex user decision gate` dialog' not in generated
    assert generated == (ROOT / '.codex/skills/open-ticket/SKILL.md').read_text(encoding='utf-8')


@pytest.mark.unit
def test_missing_open_ticket_questions_are_not_silently_accepted() -> None:
    with pytest.raises(ValueError, match='exactly one open-ticket decision instruction'):
        native_open_ticket_decisions('No interview steps available')
